#!/usr/bin/env python
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
from argparse import SUPPRESS
import textwrap

from cement.core import foundation, handler, hook
from cement.utils.misc import init_defaults

from ebcli.core import ebglobals, base, hooks
import ebcli.core.ebrun as ebrun
from ebcli.controllers.platform.list import EBPListController
from ebcli.controllers.platform.use import EBPUseController
from ebcli.controllers.platform.status import EBPStatusController
from ebcli.controllers.platform.create import EBPCreateController
from ebcli.controllers.platform.delete import EBPDeleteController
from ebcli.controllers.platform.events import EBPEventsController
from ebcli.controllers.platform.logs import EBPLogsController
from ebcli.controllers.platform.initialize import EBPInitController
from ebcli.lib import utils
from ebcli.resources.strings import flag_text, strings


class EBPBaseController(base.EbBaseController):
    class Meta:
        label = 'base'
        arguments = [
            (['--version'], dict(action='store_true',
                                 help=flag_text['base.version'])),
        ]
        epilog = strings['base.epilog']

    @property
    def _help_text(self):
        """
        Override the equivalent method in cement.core.controller.CementControllerBase
        to be able to separate application workspace-only commands from the platform
        workspace-only commands.
        """
        command_categories = _partition_commands()

        command_help_overrides = {
            'show': 'Shows information about current platform.',
            'select': 'Selects a default platform.',
            'init': 'Initializes your directory with the EB CLI to create and manage Platforms.',
            'list': 'In a platform workspace, lists versions of the custom platform associated '
                    'with this workspace. Elsewhere, lists available platforms.'
        }
        txt = self._meta.description
        for command_category in command_categories:
            cmd_txt = ''
            for label in command_category[1]:
                cmd = self._dispatch_map[label]
                cmd_txt = cmd_txt + '  %-18s' % label
                cmd_txt = cmd_txt + "    %s\n" % (command_help_overrides.get(label) or cmd['help'])

            txt += '''

{0}:
{1}


            '''.format(command_category[0], cmd_txt)

        return textwrap.dedent(txt)


class EBP(foundation.CementApp):
    class Meta:
        label = 'ebp'
        base_controller = EBPBaseController
        defaults = init_defaults('ebp', 'log.logging')
        defaults['log.logging']['level'] = 'WARN'
        config_defaults = defaults
        base_controller.Meta.description = strings['ebpbase.info']
        base_controller.Meta.epilog = strings['ebpbase.epilog']

    def setup(self):
        ebglobals.app = self

        hook.register('post_argument_parsing', hooks.pre_run_hook)

        platform_controllers = [
            EBPInitController,
            EBPCreateController,
            EBPDeleteController,
            EBPEventsController,
            EBPListController,
            EBPLogsController,
            EBPStatusController,
            EBPUseController,
        ]

        [controller._add_to_handler(handler) for controller in platform_controllers]

        super(EBP, self).setup()

        # Register global arguments
        self.add_arg('-v', '--verbose',
                     action='store_true', help=flag_text['base.verbose'])
        self.add_arg('--profile', help=flag_text['base.profile'])
        self.add_arg('-r', '--region', help=flag_text['base.region'])
        self.add_arg('--endpoint-url', help=SUPPRESS)
        self.add_arg('--no-verify-ssl',
                     action='store_true', help=flag_text['base.noverify'])
        self.add_arg('--debugboto',  # show debug info for botocore
                     action='store_true', help=SUPPRESS)


def _partition_commands():
    platform_workspace_labels = ['init', 'create', 'delete', 'events', 'logs', 'status', 'use']

    common_labels = ['list']

    return (
        ('platform workspace commands', platform_workspace_labels),
        ('common commands', common_labels),
    )


utils.monkey_patch_warn()


def main():
    app = EBP()
    ebrun.run_app(app)
