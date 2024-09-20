# Copyright 2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
import six
import sys
import traceback

from ebcli.lib import elasticbeanstalk, elb, elbv2, utils
from ebcli.core import io
from ebcli.objects.platform import PlatformVersion, PlatformBranch
from ebcli.resources.strings import alerts
from ebcli.resources.statics import (
    platform_branch_lifecycle_states,
    platform_version_lifecycle_states,
)
from ebcli.operations import (
    gitops,
    platformops,
    platform_branch_ops,
    platform_version_ops,
    solution_stack_ops,
)


SPACER = ' ' * 5


def alert_environment_status(env):
    alert_platform_status(
        env.platform,
        platform_old_alert=alerts['env.platform.old'],
        platform_not_recommended_alert=alerts['env.platform.notrecommended'],
        branch_deprecated_alert=alerts['env.platformbranch.deprecated'],
        branch_retired_alert=alerts['env.platformbranch.retired'],
    )


def alert_platform_branch_status(
    branch,
    branch_deprecated_alert=None,
    branch_retired_alert=None,
):
    if not isinstance(branch, PlatformBranch):
        branch = PlatformBranch(branch_name=branch)

    branch.hydrate(platform_branch_ops.get_platform_branch_by_name)

    if branch.is_deprecated:
        default_alert = alerts['platformbranch.deprecated']
        alert_message = branch_deprecated_alert or default_alert
        io.log_alert(alert_message + '\n')
    elif branch.is_retired:
        default_alert = alerts['platformbranch.retired']
        alert_message = branch_retired_alert or default_alert
        io.log_alert(alert_message + '\n')


def alert_platform_version_status(
    platform_version,
    platform_old_alert=alerts['platform.old'],
    platform_not_recommended_alert=alerts['platform.notrecommended'],
):
    if not isinstance(platform_version, PlatformVersion):
        platform_version = PlatformVersion(platform_arn=platform_version)

    platform_version.hydrate(elasticbeanstalk.describe_platform_version)

    if platform_version.platform_branch_name:
        _alert_eb_managed_platform_version_status(
            platform_version,
            platform_not_recommended_alert,
            platform_old_alert,
        )
    elif PlatformVersion.is_custom_platform_arn(platform_version.platform_arn):
        _alert_custom_platform_version_status(
            platform_version,
            platform_old_alert
        )


def alert_platform_status(
    platform_version,
    platform_old_alert=alerts['platform.old'],
    platform_not_recommended_alert=alerts['platform.notrecommended'],
    branch_deprecated_alert=alerts['platformbranch.deprecated'],
    branch_retired_alert=alerts['platformbranch.retired']
):
    """
    Logs an alert for a platform version status and it's platform branch's
    status if either are out-of-date or reaching end-of-life.
    """
    if not isinstance(platform_version, PlatformVersion):
        platform_version = PlatformVersion(platform_arn=platform_version)

    platform_version.hydrate(elasticbeanstalk.describe_platform_version)

    if platform_version.platform_branch_name:
        branch = platform_version.platform_branch_name

        alert_platform_branch_status(
            branch,
            branch_deprecated_alert=branch_deprecated_alert,
            branch_retired_alert=branch_retired_alert,
        )

    alert_platform_version_status(
        platform_version,
        platform_old_alert=platform_old_alert,
        platform_not_recommended_alert=platform_not_recommended_alert,
    )


def status(app_name, env_name, verbose):
    env = elasticbeanstalk.get_environment(app_name=app_name, env_name=env_name)
    env.print_env_details(
        io.echo,
        elasticbeanstalk.get_environments,
        elasticbeanstalk.get_environment_resources,
        health=True
    )
    _print_information_about_elb_and_instances(env_name) if verbose else None
    alert_environment_status(env)
    _print_codecommit_repositories()


def _alert_custom_platform_version_status(platform_version, alert_message):
    filters = [{
        'Operator': '=',
        'Type': 'PlatformName',
        'Values': [platform_version.platform_name]
    }]
    siblings = elasticbeanstalk.list_platform_versions(filters=filters)
    comparable_version = utils.parse_version(platform_version.platform_version)
    for sibling in siblings:
        if utils.parse_version(sibling['PlatformVersion']) > comparable_version:
            io.log_alert(alert_message + '\n')
            break


def _alert_eb_managed_platform_version_status(
    platform_version,
    not_recommended_alert,
    old_alert,
):
    if platform_version.is_recommended:
        return

    platform_branch_name = platform_version.platform_branch_name
    preferred_version = platform_version_ops.get_preferred_platform_version_for_branch(
        platform_branch_name)

    if preferred_version == platform_version:
        return

    if preferred_version.is_recommended:
        io.log_alert(not_recommended_alert + '\n')
    else:
        io.log_alert(old_alert + '\n')


def _print_codecommit_repositories():
    default_branch = gitops.get_default_branch()
    default_repo = gitops.get_default_repository()
    if default_repo and default_branch:
        io.echo("Current CodeCommit settings:")
        io.echo("  Repository: " + str(default_repo))
        io.echo("  Branch: " + str(default_branch))


def _print_information_about_elb_and_instances(env_name):
    env_dict = elasticbeanstalk.get_environment_resources(env_name)
    instances = [instance['Id'] for instance in env_dict['EnvironmentResources']['Instances']]
    io.echo('  Running instances:', len(instances))

    load_balancers = env_dict['EnvironmentResources']['LoadBalancers']
    if load_balancers:
        load_balancer_name = load_balancers[0]['Name']
        if elb.is_classic_load_balancer(load_balancer_name):
            _print_elb_health_stats(load_balancer_name, instances)
        elif load_balancer_name:
            _print_elbv2_health_stats(load_balancer_name, instances)


def _print_elbv2_health_stats(load_balancer_name, instances):
    target_groups = [
        t['TargetGroupArn']
        for t
        in elbv2.get_target_groups_for_load_balancer(load_balancer_name)
    ]
    target_group_states = elbv2.get_target_group_healths(target_groups)

    for target_group_arn, target_group_health in six.iteritems(target_group_states):
        current_target_group_instances = []
        for target_group_description in target_group_health['TargetHealthDescriptions']:
            current_target_group_instances.append(target_group_description['Target']['Id'])
            target_health = target_group_description['TargetHealth']

            io.echo(SPACER * 2, target_group_description['Target']['Id'] + ': ' + target_health['State'])

            if 'Description' in target_health and len(target_health['Description']) > 0:
                io.echo(SPACER * 3, 'Description: ' + target_health['Description'])
            if 'Reason' in target_health and len(target_health['Reason']) > 0:
                io.echo(SPACER * 3, 'Reason: ' + target_health['Reason'])

        for i in set(instances) - set(current_target_group_instances):
            io.echo(SPACER * 2, i + ':', 'N/A (Not registered with Target Group)')


def _print_elb_health_stats(load_balancer_name, instances):
    instance_states = elb.get_health_of_instances(load_balancer_name)
    for i in instance_states:
        instance_id = i['InstanceId']
        state = i['State']
        description = i['Description']
        if state == 'Unknown':
            state += '(' + description + ')'
        io.echo(SPACER, instance_id + ':', state)
    for i in set(instances) - set([x['InstanceId'] for x in instance_states]):
        io.echo(SPACER, i + ':', 'N/A (Not registered with Load Balancer)')
