# Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.s
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
from datetime import datetime
import locale

from botocore.compat import six
from cement.utils.misc import minimal_logger

from ebcli.core import io
from ebcli.display import term
from ebcli.display.data_poller import DataPoller
from ebcli.display.screen import Screen
from ebcli.lib import ec2, elasticbeanstalk, elb, elbv2
from ebcli.resources import statics


Queue = six.moves.queue.Queue
LOG = minimal_logger(__name__)


class TraditionalHealthDataPoller(DataPoller):
    def assemble_environment_data(
            self,
            ids_of_all_instances,
            instances_registered_with_elb
    ):
        total_instances = len(ids_of_all_instances)
        total_in_service = 0
        for instance_state in instances_registered_with_elb:
            if instance_state['State'] == statics.ec2_instance_statuses.IN_SERVICE:
                total_in_service += 1
        env = elasticbeanstalk.get_environment(app_name=self.app_name, env_name=self.env_name)

        return {
            'EnvironmentName': env.name,
            'Color': env.health,
            'Status': env.status,
            'Total': total_instances,
            'InService': total_in_service,
            'Other': total_instances - total_in_service,
            'RefreshedAt': _datetime_utcnow_wrapper()
        }

    def get_instance_health(self, instance_states):
        instance_healths = []
        for instance_state in instance_states:
            instance = {
                'id': instance_state['InstanceId'],
                'state': instance_state['State'],
                'description': instance_state['Description']
            }
            ec2_health = ec2.describe_instance(instance['id'])
            instance['health'] = ec2_health['State']['Name']
            instance_healths.append(instance)

        return instance_healths

    def get_health_information_of_instance_not_associated_with_elb(
            self,
            ids_of_all_instances,
            instances_registered_with_elb
    ):
        instance_healths = []
        ids_of_all_instances = set(ids_of_all_instances)
        ids_of_instances_registered_with_elb = set([x['InstanceId'] for x in instances_registered_with_elb])
        for instance_id in list(ids_of_all_instances - ids_of_instances_registered_with_elb):
            instance = dict([('id', instance_id)])
            instance['description'] = 'N/A (Not registered with Load Balancer)'
            instance['state'] = 'n/a'
            ec2_health = ec2.describe_instance(instance_id)
            instance['health'] = ec2_health['State']['Name']
            instance_healths.append(instance)

        return instance_healths

    def get_instance_states(self, load_balancers):
        if not load_balancers:
            return []

        load_balancer_name = load_balancers[0]['Name']

        return self.get_load_balancer_instance_states(load_balancer_name)

    def get_load_balancer_instance_states(self, load_balancer_name):
        if elb.is_classic_load_balancer(load_balancer_name):
            instance_states = elb.get_health_of_instances(load_balancer_name)
        else:
            load_balancer_arn = load_balancer_name
            elbv2_target_groups = elbv2.get_target_groups_for_load_balancer(
                load_balancer_arn=load_balancer_arn
            )
            target_group_arns = [
                target_group['TargetGroupArn']
                for target_group in elbv2_target_groups
            ]
            instance_states = elbv2.get_instance_healths_from_target_groups(target_group_arns)

        return instance_states

    def _get_health_data(self):
        env_dict = elasticbeanstalk.get_environment_resources(self.env_name)
        environment_resources = env_dict['EnvironmentResources']
        instances_registered_with_elb = self.get_instance_states(environment_resources.get('LoadBalancers'))
        ids_of_all_instances = [instance['Id'] for instance in environment_resources.get('Instances', [])]
        all_instances = (
            self.get_instance_health(instances_registered_with_elb)
            +
            self.get_health_information_of_instance_not_associated_with_elb(
                ids_of_all_instances,
                instances_registered_with_elb
            )
        )

        return {
            'instances': all_instances,
            'environment': self.assemble_environment_data(ids_of_all_instances, instances_registered_with_elb)
        }


class TraditionalHealthScreen(Screen):
    def __init__(self):
        super(TraditionalHealthScreen, self).__init__()
        self.empty_row = 3

    def draw_banner_info_lines(self, lines, data):
        if lines > 2:
            term.echo_line('instances:',
                           io.bold(data.get('Total', 0)), 'Total,',
                           io.bold(data.get('InService', 0)), 'InService,',
                           io.bold(data.get('Other', 0)), 'Other',
                           )
            lines -= 1
        if lines > 2:
            status = data.get('Status', 'Unknown')
            term.echo_line(' Status:', io.bold(status),
                           'Health', io.bold(data.get('Color', 'Grey')))
            lines -= 1
        return lines


def _datetime_utcnow_wrapper():
    return datetime.utcnow()
