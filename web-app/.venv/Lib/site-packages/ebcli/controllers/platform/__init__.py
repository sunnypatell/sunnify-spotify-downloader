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
import textwrap

from ebcli.core import fileoperations
from ebcli.core import io
from ebcli.core.ebglobals import Constants
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.resources.strings import strings


class PlatformController(AbstractBaseController):
    class Meta:
        label = 'platform'
        description = strings['platform.info']
        usage = 'eb platform <command> [options...]'
        arguments = []

    def do_command(self):
        self.app.args.print_help()

    @classmethod
    def _add_to_handler(cls, handler):
        handler.register(cls)

    @property
    def _help_text(self):
        """
        Override the equivalent method in cement.core.controller.CementControllerBase
        to be able to separate application workspace-only commands from the platform
        workspace-only commands.
        """
        command_categories = _partition_commands()

        txt = self._meta.description
        command_help_overrides = {
            'platform show': 'Shows information about current platform.',
            'platform select': 'Selects a default platform.',
            'platform init': 'Initializes your directory with the EB CLI to create and manage '
                             'Platforms.',
            'platform list': 'In a platform workspace, lists versions of the custom platform '
                             'associated with this workspace. Elsewhere, lists available '
                             'platforms.'
        }
        for command_category in command_categories:
            cmd_txt = ''
            for label in command_category[1]:
                cmd = self._dispatch_map[label]
                cmd_txt = cmd_txt + '  %-18s' % cmd['aliases'][0]
                cmd_txt = cmd_txt + "    %s\n" % (command_help_overrides.get(label) or cmd['help'])

            txt += '''

{0}:
{1}


            '''.format(command_category[0], cmd_txt)

        return textwrap.dedent(txt)


def _partition_commands():
    application_workspace_labels = [
        'platform show',
        'platform select'
    ]

    platform_workspace_labels = [
        'platform init',
        'platform status',
        'platform use',
        'platform create',
        'platform delete',
        'platform events',
        'platform logs'
    ]

    common_labels = [
        'platform list',
    ]

    return (
        ('application workspace commands', application_workspace_labels),
        ('platform workspace commands', platform_workspace_labels),
        ('common commands', common_labels),
    )
