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
from ebcli.resources.strings import strings
from ebcli.operations import healthops


class HealthController(AbstractBaseController):
    class Meta:
        label = 'health'
        description = strings['health.info']
        usage = AbstractBaseController.Meta.usage.replace('{cmd}', label)
        arguments = AbstractBaseController.Meta.arguments + [
            (['--refresh'], dict(action='store_true', help='refresh')),
            (['--mono'], dict(action='store_true', help='no color')),
            (
                ['--view'], dict(
                    default='split',
                    choices=['split', 'status', 'request', 'cpu']
                )
            )
        ]

    def do_command(self):
        app_name = self.get_app_name()
        env_name = self.get_env_name()
        refresh = self.app.pargs.refresh
        mono = self.app.pargs.mono
        view = self.app.pargs.view

        healthops.display_interactive_health(app_name, env_name, refresh,
                                             mono, view)
