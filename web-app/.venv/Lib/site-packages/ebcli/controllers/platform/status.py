# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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

from ebcli.core import io
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.objects.exceptions import InvalidPlatformVersionError
from ebcli.objects.platform import PlatformVersion
from ebcli.operations import platformops, platform_version_ops, solution_stack_ops
from ebcli.resources.strings import strings, flag_text


class PlatformShowController(AbstractBaseController):
    class Meta:
        requires_directory_initialization = True
        label = 'platform show'
        aliases = ['show']
        aliases_only = True
        stacked_on = 'platform'
        stacked_type = 'nested'
        description = strings['platformshow.info']
        usage = AbstractBaseController.Meta.usage.format(cmd='platform show')

    def do_command(self):
        app_name = self.get_app_name()
        env_name = self.get_env_name(noerror=True)
        # This could be an ARN or a solution stack platform / or solution stack short name
        config_platform = solution_stack_ops.get_default_solution_stack()
        want_solution_stack = False

        if PlatformVersion.is_custom_platform_arn(config_platform):
            platform_name, latest_platform = self.get_latest_custom_platform(config_platform)
        else:
            want_solution_stack = True
            platform_name, latest_platform = self.get_latest_solution_stack(config_platform)

        io.echo('Current default platform:', config_platform)
        if config_platform.lower() is platform_name.lower():
            io.echo('Most recent platform:    ', latest_platform)
        else:
            io.echo('New environments will be running: ', platform_name)

        if env_name:
            if want_solution_stack:
                platform = platformops.get_environment_platform(
                    app_name,
                    env_name,
                    want_solution_stack=want_solution_stack
                ).name
            else:
                platform = platformops.get_environment_platform(
                    app_name,
                    env_name,
                    want_solution_stack=want_solution_stack
                ).arn

            io.echo()
            io.echo('Platform info for environment "{env_name}":'
                    .format(env_name=env_name))
            io.echo('Current:', platform)
            io.echo('Latest: ', latest_platform)

            if latest_platform is platform:
                io.echo(strings['platformstatus.upgrade'])

    def get_latest_solution_stack(self, solution_stack):
        full_platform = solution_stack_ops.find_solution_stack_from_string(solution_stack)
        latest_platform = solution_stack_ops.find_solution_stack_from_string(
            full_platform.platform_shorthand,
            find_newer=True
        )

        return full_platform.name, latest_platform.name

    def get_latest_custom_platform(self, platform_arn):
        latest_platform = platform_version_ops.get_latest_custom_platform_version(platform_arn)

        return platform_arn, latest_platform.platform_shorthand


class GenericPlatformStatusController(AbstractBaseController):
    class Meta:
        is_platform_workspace_only_command = True
        requires_directory_initialization = True
        description = strings['platformshowversion.info']
        arguments = [
            (
                ['version'],
                dict(
                    action='store',
                    nargs='?',
                    default=None,
                    help=flag_text['platformshowversion.version']
                )
            ),
        ]
        epilog = strings['platformshowversion.epilog']

        @classmethod
        def clone(cls):
            return type('Meta', cls.__bases__, dict(cls.__dict__))

    def do_command(self):
        try:
            platformops.get_version_status(self.app.pargs.version)
        except InvalidPlatformVersionError:
            if not self.app.pargs.version:
                io.log_error("This workspace is currently associated with a deleted version.")
            else:
                raise InvalidPlatformVersionError(strings['exit.nosuchplatformversion'])


class PlatformWorkspaceStatusController(GenericPlatformStatusController):
    Meta = GenericPlatformStatusController.Meta.clone()
    Meta.label = 'platform status'
    Meta.aliases = ['status']
    Meta.aliases_only = True
    Meta.stacked_on = 'platform'
    Meta.stacked_type = 'nested'
    Meta.usage = 'eb platform status <version> [options...]'


class EBPStatusController(GenericPlatformStatusController):
    Meta = GenericPlatformStatusController.Meta.clone()
    Meta.label = 'status'
    Meta.usage = 'ebp status <version> [options...]'
