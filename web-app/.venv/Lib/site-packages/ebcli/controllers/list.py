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

from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.resources.strings import strings, flag_text
from ebcli.operations import listops


class ListController(AbstractBaseController):
    class Meta:
        label = 'list'
        description = strings['list.info']
        usage = 'eb list [options ...]'
        arguments = [
            (['-a', '--all'], dict(action='store_true',
                                   help=flag_text['list.all']))
        ]

    def do_command(self):
        all_apps = self.app.pargs.all
        if not all_apps:
            app_name = self.get_app_name()
        else:
            app_name = None
        verbose = self.app.pargs.verbose

        listops.list_env_names(app_name, verbose, all_apps)
