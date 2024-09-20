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

from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.resources.strings import strings, flag_text
from ebcli.operations import upgradeops


class UpgradeController(AbstractBaseController):
    class Meta:
        label = 'upgrade'
        description = strings['upgrade.info']
        usage = AbstractBaseController.Meta.usage.replace('{cmd}', label)
        arguments = AbstractBaseController.Meta.arguments + [
            (['--timeout'], dict(type=int, help=flag_text['general.timeout'])),
            (['--force'], dict(
                action='store_true', help=flag_text['scale.force'])),
            (['--noroll'], dict(
                action='store_true', help=flag_text['upgrade.noroll'])),
        ]

    def do_command(self):
        app_name = self.get_app_name()
        env_name = self.get_env_name()
        timeout = self.app.pargs.timeout
        confirm = self.app.pargs.force
        noroll = self.app.pargs.noroll

        upgradeops.upgrade_env(app_name, env_name, timeout, confirm, noroll)
