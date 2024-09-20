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
import argparse
import os

from ebcli.core import io, fileoperations
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.core.ebglobals import Constants
from ebcli.objects.platform import PlatformVersion
from ebcli.objects.exceptions import InvalidOptionsError
from ebcli.operations import platform_version_ops, solution_stack_ops
from ebcli.resources.strings import strings, flag_text


class GenericPlatformListController(AbstractBaseController):
    class Meta:
        argument_formatter = argparse.RawTextHelpFormatter
        is_platform_workspace_only_command = False
        requires_directory_initialization = True
        description = strings['platformlistversions.info']
        arguments = [
            (
                ['-a', '--all-platforms'],
                dict(action='store_true', help=flag_text['platformlist.all'])
            ),
            (
                ['-s', '--status'],
                dict(action='store', help=flag_text['platformlist.status'])
            ),
        ]

        @classmethod
        def clone(cls):
            return type('Meta', cls.__bases__, dict(cls.__dict__))

    def do_command(self):
        workspace_type = fileoperations.get_workspace_type(None)
        if workspace_type == Constants.WorkSpaceTypes.PLATFORM:
            echo(self.custom_platforms())
            return
        elif workspace_type == Constants.WorkSpaceTypes.APPLICATION:
            if self.app.pargs.status:
                raise InvalidOptionsError(
                    'You cannot use the "--status" option in application workspaces.'
                )
            elif self.app.pargs.all_platforms:
                raise InvalidOptionsError(
                    'You cannot use the "--all-platforms" option in application workspaces.'
                )
        else:
            if not self.app.pargs.region:
                raise InvalidOptionsError('You must provide the "--region" option when not in a workspace.')

        echo(self.all_platforms())

    def all_platforms(self):
        solution_stacks = solution_stack_ops.get_all_solution_stacks()

        if self.app.pargs.verbose:
            platform_arns = platform_version_ops.list_custom_platform_versions()
            versions = [s.name for s in solution_stacks]
            versions.extend(platform_arns)
        else:
            platform_arns = platform_version_ops.list_custom_platform_versions(platform_version='latest')
            versions = sorted(set([s.pythonify() for s in solution_stacks]))
            versions.extend([PlatformVersion.get_platform_name(arn) for arn in platform_arns])

        return versions

    def custom_platforms(self):
        platform_name = None if self.app.pargs.all_platforms else fileoperations.get_platform_name()

        return platform_version_ops.list_custom_platform_versions(
            platform_name=platform_name,
            status=self.app.pargs.status,
            show_status=True
        )


class PlatformListController(GenericPlatformListController):
    Meta = GenericPlatformListController.Meta.clone()
    Meta.label = 'platform list'
    Meta.aliases = ['list']
    Meta.aliases_only = True
    Meta.stacked_on = 'platform'
    Meta.stacked_type = 'nested'
    Meta.usage = 'eb platform list [options...]'
    Meta.description = strings['platformlist.info']


class EBPListController(GenericPlatformListController):
    Meta = GenericPlatformListController.Meta.clone()
    Meta.label = 'list'
    Meta.usage = 'ebp list [options...]'
    Meta.description = 'Lists available custom platforms'


def echo(platforms):
    if len(platforms) > 20:
        io.echo_with_pager(os.linesep.join(platforms))
    else:
        io.echo(*platforms, sep=os.linesep)
