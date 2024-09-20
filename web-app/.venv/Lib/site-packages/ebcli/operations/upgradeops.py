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
from ebcli.objects.platform import PlatformVersion
from ebcli.resources.strings import prompts
from ebcli.resources.statics import namespaces, option_names
from ebcli.core import io
from ebcli.lib import elasticbeanstalk
from ebcli.operations import commonops, solution_stack_ops


def _get_warning_message(confirm, single, rolling_enabled, webserver, noroll):
    if confirm:
        return None
    elif single:
        return prompts['upgrade.singleinstance']
    elif not rolling_enabled and noroll:
        return prompts['upgrade.norollingforce']
    elif not rolling_enabled:
        if webserver:
            type = 'Health'
        else:
            type = 'Time'
        return prompts['upgrade.norollingapply'].format(type)
    elif rolling_enabled:
        return prompts['upgrade.rollingupdate']


def _should_add_rolling(single, rolling_enabled, noroll):
    if noroll:
        return False
    if single:
        return False
    if rolling_enabled:
        return False
    return True


def upgrade_env(app_name, env_name, timeout, confirm, noroll):
    env = elasticbeanstalk.get_environment_settings(app_name, env_name)
    latest = solution_stack_ops.find_solution_stack_from_string(env.platform.name, find_newer=True)

    if latest.name == env.platform.name:
        io.echo(prompts['upgrade.alreadylatest'])
        return
    else:
        single = elasticbeanstalk.get_option_setting(
            env.option_settings, namespaces.ENVIRONMENT,
            'EnvironmentType') == 'SingleInstance'
        rolling_enabled = elasticbeanstalk.get_option_setting(
            env.option_settings, namespaces.ROLLING_UPDATES,
            option_names.ROLLING_UPDATE_ENABLED) == 'true'
        webserver = env.tier.name.lower() == 'webserver'

        io.echo()
        io.echo(prompts['upgrade.infodialog'].format(env_name))
        io.echo('Current platform:', env.platform)
        io.echo('Latest platform: ', latest.name)
        io.echo()

        warning = _get_warning_message(confirm, single,
                                       rolling_enabled, webserver, noroll)
        if warning:
            io.log_warning(warning)
            io.echo(prompts['upgrade.altmessage'])
            io.echo()

        if not confirm:
            io.validate_action(prompts['upgrade.validate'], env.name)

        add_rolling = _should_add_rolling(single, rolling_enabled, noroll)

        do_upgrade(env_name, add_rolling, timeout, latest.name,
                   health_based=webserver, platform_arn=latest.name)


def do_upgrade(env_name, add_rolling, timeout, solution_stack_name,
               health_based=False, platform_arn=None):
    if add_rolling:
        if health_based:
            roll_type = 'Health'
        else:
            roll_type = 'Time'
        changes = [
            elasticbeanstalk.create_option_setting(
                namespaces.ROLLING_UPDATES,
                option_names.ROLLING_UPDATE_ENABLED,
                'true'),
            elasticbeanstalk.create_option_setting(
                namespaces.ROLLING_UPDATES,
                option_names.ROLLING_UPDATE_TYPE,
                roll_type)
        ]
        io.log_warning(prompts['upgrade.applyrolling'].format(roll_type))
    else:
        changes = None

    if PlatformVersion.is_valid_arn(platform_arn):
        commonops.update_environment(
            env_name, changes, None, timeout=timeout,
            platform_arn=platform_arn)
    else:
        commonops.update_environment(
            env_name, changes, None, timeout=timeout,
            solution_stack_name=solution_stack_name)
