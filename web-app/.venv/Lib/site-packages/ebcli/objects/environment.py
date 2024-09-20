# Copyright 2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
import time
import re

from ebcli.objects.solutionstack import SolutionStack
from ebcli.objects.tier import Tier
from ebcli.objects.platform import PlatformVersion
from ebcli.objects.exceptions import WorkerQueueNotFound


class Environment(object):
    ARN_PATTERN = re.compile(
        r'^arn:aws(?:-cn)*:elasticbeanstalk:[\w\-]+:\d+:environment/[^/]+/.*$'
    )
    def __init__(self, version_label=None, status=None, app_name=None,
                 health=None, id=None, date_updated=None,
                 platform=None, description=None,
                 name=None, date_created=None, tier=None,
                 cname=None, option_settings=None, is_abortable=False,
                 environment_links=None, environment_arn=None):

        self.version_label = version_label
        self.status = status
        self.app_name = app_name
        self.health = health
        self.id = id
        self.date_updated = date_updated
        self.platform = platform
        self.description = description
        self.name = name
        self.date_created = date_created
        self.tier = tier
        self.cname = cname
        self.option_settings = option_settings
        self.is_abortable = is_abortable
        self.environment_links = environment_links
        self.environment_arn = environment_arn

    def __str__(self):
        return self.name

    @classmethod
    def is_valid_arn(cls, candidate):
        return not not re.search(cls.ARN_PATTERN, candidate)

    @classmethod
    def json_to_environment_object(
            cls,
            environment_json,
            want_solution_stack=False
    ):
        platform_name = cls.__get_platform_name(environment_json, want_solution_stack)

        tier = environment_json['Tier']
        tier = Tier(tier['Name'], tier['Type'], tier['Version'])

        environment = Environment(
            version_label=environment_json.get('VersionLabel'),
            status=environment_json.get('Status'),
            app_name=environment_json.get('ApplicationName'),
            health=environment_json.get('Health'),
            id=environment_json.get('EnvironmentId'),
            date_updated=environment_json.get('DateUpdated'),
            platform=platform_name,
            description=environment_json.get('Description'),
            name=environment_json.get('EnvironmentName'),
            date_created=environment_json.get('DateCreated'),
            tier=tier,
            cname=environment_json.get('CNAME', 'UNKNOWN'),
            option_settings=environment_json.get('OptionSettings'),
            is_abortable=environment_json.get('AbortableOperationInProgress', False),
            environment_links=environment_json.get('EnvironmentLinks'),
            environment_arn=environment_json.get('EnvironmentArn')
        )

        return environment

    @classmethod
    def json_to_environment_objects_array(
            cls,
            json,
            want_solution_stack=False
    ):
        environments = []
        for environment_json in json:
            environments.append(
                Environment.json_to_environment_object(environment_json, want_solution_stack)
            )

        return environments

    @classmethod
    def __get_platform_name(cls, environment, want_solution_stack=False):
        try:
            if want_solution_stack or environment['SolutionStackName'] == 'custom':
                solution_stack_name = environment['SolutionStackName']
                platform_name = SolutionStack(solution_stack_name)
            else:
                platform_arn = environment['PlatformArn']
                platform_name = PlatformVersion(platform_arn)
        except KeyError:
            platform_name = SolutionStack(environment['SolutionStackName'])

        return platform_name

    def print_env_details(
            self,
            echo_method,
            get_environments_callback,
            get_environment_resources_callback,
            health=True
    ):
        echo_method('Environment details for:', self.name)
        echo_method('  Application name:', self.app_name)
        echo_method('  Region:', self.__region_from_environment_arn())
        echo_method('  Deployed Version:', self.version_label)
        echo_method('  Environment ID:', self.id)
        echo_method('  Platform:', self.platform)
        echo_method('  Tier:', self.tier)
        echo_method('  CNAME:', self.cname)
        echo_method('  Updated:', self.date_updated)
        self.print_env_links(
            echo_method,
            get_environments_callback,
            get_environment_resources_callback
        )

        if health:
            echo_method('  Status:', self.status)
            echo_method('  Health:', self.health)

    def print_env_links(
            self,
            echo_method,
            get_environments_callback,
            get_environment_resources_callback
    ):
        if self.environment_links and len(self.environment_links) > 0:
            links = {}
            linked_envs = []

            for link in self.environment_links:
                link_data = dict(link_name=link['LinkName'], env_name=link['EnvironmentName'])
                links[link_data['env_name']] = link_data
                linked_envs.append(link_data['env_name'])

            linked_env_descriptions = get_environments_callback(linked_envs)

            for linked_environment in linked_env_descriptions:
                if linked_environment.tier.name == 'WebServer':
                    links[linked_environment.name]['value'] = linked_environment.cname
                elif linked_environment.tier.name == 'Worker':
                    links[linked_environment.name]['value'] = self.get_worker_sqs_url(
                        get_environment_resources_callback
                    )
                    time.sleep(.5)

            echo_method('  Environment Links:')

            for link in links.values():
                echo_method('    {}:'.format(link['env_name']))
                echo_method(
                    '      {}: {}'.format(
                        link['link_name'],
                        link['value']
                    )
                )

    def get_worker_sqs_url(self, get_environment_resources_callback):
        resources = get_environment_resources_callback(self.name)['EnvironmentResources']
        queues = resources['Queues']
        worker_queue = None
        for queue in queues:
            if queue['Name'] == 'WorkerQueue':
                worker_queue = queue

        if worker_queue is None:
            raise WorkerQueueNotFound

        return worker_queue['URL']

    def __region_from_environment_arn(self):
        environment_arn_regex = re.compile(r'arn:aws.*:elasticbeanstalk:(.*):\d+:environment/.*/.*$')

        matches = re.match(environment_arn_regex, self.environment_arn)

        return matches.groups(0)[0]
