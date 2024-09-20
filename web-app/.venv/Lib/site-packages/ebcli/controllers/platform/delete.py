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
from ebcli.core import fileoperations, io
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.operations import platformops, platform_version_ops
from ebcli.resources.strings import strings, flag_text, prompts


class GenericPlatformDeleteController(AbstractBaseController):
    class Meta:
        is_platform_workspace_only_command = True
        requires_directory_initialization = True
        description = strings['platformdeleteversion.info']
        arguments = [
            (
                ['version'],
                dict(
                    action='store',
                    help=flag_text['platformdeleteversion.version'],
                    nargs='?',
                    default=None
                )
            ),
            (
                ['--cleanup'],
                dict(
                    action='store_true',
                    help=flag_text['platformdelete.cleanup']
                )
            ),
            (
                ['--all-platforms'],
                dict(
                    action='store_true',
                    help=flag_text['platformdelete.allplatforms']
                )
            ),
            (
                ['--force'],
                dict(
                    action='store_true',
                    help=flag_text['platformdelete.force']
                )
            )
        ]
        epilog = strings['platformdeleteversion.epilog']

        @classmethod
        def clone(cls):
            return type('Meta', cls.__bases__, dict(cls.__dict__))

    def do_command(self):
        version = self.app.pargs.version
        cleanup = self.app.pargs.cleanup
        force = self.app.pargs.force

        if cleanup:
            self.cleanup_platforms()
        else:
            if version:
                platform_version_ops.delete_platform_version(version, force)
            else:
                self.app.args.print_help()

    def cleanup_platforms(self):
        force = self.app.pargs.force
        all_platforms = self.app.pargs.all_platforms

        if all_platforms:
            platform_name = None
        else:
            platform_name = fileoperations.get_platform_name()

        failed_versions = sorted(
            platform_version_ops.list_custom_platform_versions(
                platform_name=platform_name,
                status='Failed',
            )
        )

        if failed_versions:
            if not force:
                if not platform_name:
                    io.echo(prompts['cleanupplatform.confirm'].replace('{platform-name}', 'All Platforms'))

                    for failed_version in failed_versions:
                        io.echo(failed_version)

                    io.validate_action(prompts['cleanupplatform.validate-all'], 'all')
                else:
                    io.echo(prompts['cleanupplatform.confirm'].replace('{platform-name}', platform_name))
                    io.validate_action(prompts['cleanupplatform.validate'], platform_name)

            for failed_version in failed_versions:
                platform_version_ops.delete_platform_version(failed_version, force=True)


class PlatformDeleteController(GenericPlatformDeleteController):
    Meta = GenericPlatformDeleteController.Meta.clone()
    Meta.label = 'platform delete'
    Meta.aliases = ['delete']
    Meta.aliases_only = True
    Meta.stacked_on = 'platform'
    Meta.stacked_type = 'nested'
    Meta.usage = 'eb platform delete <version> [options...]'


class EBPDeleteController(GenericPlatformDeleteController):
    Meta = GenericPlatformDeleteController.Meta.clone()
    Meta.label = 'delete'
    Meta.usage = 'ebp delete <version> [options...]'
