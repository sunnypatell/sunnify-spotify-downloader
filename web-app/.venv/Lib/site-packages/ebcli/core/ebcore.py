#!/usr/bin/env python
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
from argparse import SUPPRESS

from cement.core import foundation, handler, hook
from cement.utils.misc import init_defaults

from ebcli.core import ebglobals, base, hooks
from ebcli.controllers.abort import AbortController
from ebcli.controllers.appversion import AppVersionController
from ebcli.controllers.clone import CloneController
from ebcli.controllers.codesource import CodeSourceController
from ebcli.controllers.config import ConfigController
from ebcli.controllers.console import ConsoleController
from ebcli.controllers.create import CreateController
from ebcli.controllers.deploy import DeployController
from ebcli.controllers.events import EventsController
from ebcli.controllers.health import HealthController
from ebcli.controllers.initialize import InitController
from ebcli.controllers.lifecycle import LifecycleController
from ebcli.controllers.list import ListController
from ebcli.controllers.local import LocalController
from ebcli.controllers.logs import LogsController
from ebcli.controllers.open import OpenController
from ebcli.controllers.platform import PlatformController
from ebcli.controllers.platform.initialize import PlatformInitController
from ebcli.controllers.platform.use import PlatformSelectController
from ebcli.controllers.platform.list import PlatformListController
from ebcli.controllers.platform.status import PlatformShowController, PlatformWorkspaceStatusController
from ebcli.controllers.platform.use import PlatformWorkspaceUseController
from ebcli.controllers.platform.create import PlatformCreateController
from ebcli.controllers.platform.delete import PlatformDeleteController
from ebcli.controllers.platform.events import PlatformEventsController
from ebcli.controllers.platform.logs import PlatformLogsController
from ebcli.controllers.printenv import PrintEnvController
from ebcli.controllers.restore import RestoreController
from ebcli.controllers.scale import ScaleController
from ebcli.controllers.setenv import SetEnvController
from ebcli.controllers.ssh import SSHController
from ebcli.controllers.status import StatusController
from ebcli.controllers.swap import SwapController
from ebcli.controllers.tags import TagsController
from ebcli.controllers.terminate import TerminateController
from ebcli.controllers.upgrade import UpgradeController
from ebcli.controllers.use import UseController
from ebcli.labs.controller import LabsController
from ebcli.resources.strings import flag_text
from ebcli.lib import utils
import ebcli.core.ebrun as ebrun


class EB(foundation.CementApp):
    class Meta:
        label = 'eb'
        base_controller = base.EbBaseController
        defaults = init_defaults('eb', 'log.logging')
        defaults['log.logging']['level'] = 'WARN'
        config_defaults = defaults
        exit_on_close = True

    def setup(self):
        ebglobals.app = self

        hook.register('post_argument_parsing', hooks.pre_run_hook)

        environment_controllers = [
            AbortController,
            AppVersionController,
            CloneController,
            CodeSourceController,
            ConfigController,
            ConsoleController,
            CreateController,
            DeployController,
            EventsController,
            HealthController,
            InitController,
            LabsController,
            LifecycleController,
            ListController,
            LocalController,
            LogsController,
            OpenController,
            PlatformController,
            PrintEnvController,
            RestoreController,
            SSHController,
            ScaleController,
            SetEnvController,
            StatusController,
            SwapController,
            TagsController,
            TerminateController,
            UpgradeController,
            UseController,
            PlatformInitController,
            PlatformShowController,
            PlatformSelectController,
            PlatformListController,
            PlatformWorkspaceStatusController,
            PlatformWorkspaceUseController,
            PlatformCreateController,
            PlatformDeleteController,
            PlatformEventsController,
            PlatformLogsController,
        ]

        for controller in environment_controllers:
            controller._add_to_handler(handler)

        super(EB, self).setup()

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


utils.monkey_patch_warn()


def main():
    app = EB()
    ebrun.run_app(app)
