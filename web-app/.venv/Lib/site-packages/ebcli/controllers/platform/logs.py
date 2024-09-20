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
from ebcli.objects.exceptions import NotFoundError, InvalidPlatformVersionError
from ebcli.objects.platform import PlatformVersion
from ebcli.operations import platform_version_ops, logsops
from ebcli.core import fileoperations
from ebcli.operations.logsops import paginate_cloudwatch_logs
from ebcli.resources.regex import PlatformRegExpressions
from ebcli.resources.strings import strings, flag_text


class GenericPlatformLogsController(AbstractBaseController):
    class Meta:
        is_platform_workspace_only_command = True
        requires_directory_initialization = True
        description = strings['platformlogs.info']
        arguments = [
            (
                ['version'],
                dict(
                    action='store',
                    nargs='?',
                    default=None,
                    help=flag_text['platformlogs.version']
                )
            ),
            (
                ['--stream'],
                dict(
                    action='store_true',
                    help=flag_text['logs.stream']
                )
            )
        ]

        @classmethod
        def clone(cls):
            return type('Meta', cls.__bases__, dict(cls.__dict__))

    @classmethod
    def add_to_handler(cls, handler):
        handler.register(cls)

    def do_command(self):
        version = self.app.pargs.version
        stream = self.app.pargs.stream

        if version is None:
            platform_name = fileoperations.get_platform_name()
            version = fileoperations.get_platform_version()
        else:
            platform_name = fileoperations.get_platform_name()

            if PlatformRegExpressions.VALID_PLATFORM_VERSION_FORMAT.match(version):
                pass
            elif PlatformVersion.is_valid_arn(version):
                _, platform_name, version = PlatformVersion.arn_to_platform(version)
            elif PlatformRegExpressions.VALID_PLATFORM_SHORT_FORMAT.match(version):
                match = PlatformRegExpressions.VALID_PLATFORM_SHORT_FORMAT.match(version)
                platform_name, version = match.group(1, 2)
            else:
                raise InvalidPlatformVersionError(strings['exit.invalidversion'])

        io.echo('Retrieving logs...')

        if stream:
            try:
                logsops.stream_platform_logs(
                    platform_name,
                    version,
                    log_name="%s/%s" % (platform_name, version),
                    formatter=platform_version_ops.PackerStreamFormatter())
            except NotFoundError:
                raise NotFoundError('Unable to find logs in CloudWatch.')
        else:
            paginate_cloudwatch_logs(platform_name, version)


class PlatformLogsController(GenericPlatformLogsController):
    Meta = GenericPlatformLogsController.Meta.clone()
    Meta.label = 'platform logs'
    Meta.aliases = ['logs']
    Meta.aliases_only = True
    Meta.stacked_on = 'platform'
    Meta.stacked_type = 'nested'
    Meta.usage = 'eb platform logs <version> [options...]'


class EBPLogsController(GenericPlatformLogsController):
    Meta = GenericPlatformLogsController.Meta.clone()
    Meta.label = 'logs'
    Meta.usage = 'ebp logs <version> [options...]'
