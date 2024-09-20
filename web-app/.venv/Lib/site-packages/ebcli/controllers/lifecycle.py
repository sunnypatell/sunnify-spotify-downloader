# Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
from ebcli.operations import lifecycleops


class LifecycleController(AbstractBaseController):
    class Meta(AbstractBaseController.Meta):
        label = 'lifecycle'
        stacked_on = 'appversion'
        stacked_type = 'nested'
        description = strings['lifecycle.info']
        arguments = AbstractBaseController.Meta.arguments + [
            (['-p', '--print'], dict(action='store_true', help=flag_text['lifecycle.print'])),
        ]
        usage = 'eb appversion lifecycle [options ...]'
        epilog = strings['lifecycle.epilog']

    def do_command(self):
        app_name = self.get_app_name()
        print_policy = getattr(self.app.pargs, 'print')

        if print_policy:
            lifecycleops.print_lifecycle_policy(app_name)
            return

        lifecycleops.interactive_update_lifcycle_policy(app_name)
