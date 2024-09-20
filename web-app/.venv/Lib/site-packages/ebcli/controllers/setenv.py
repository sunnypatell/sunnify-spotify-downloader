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
from ebcli.core import fileoperations, io
from ebcli.lib import elasticbeanstalk
from ebcli.operations import envvarops


class SetEnvController(AbstractBaseController):
    class Meta:
        label = 'setenv'
        description = strings['setenv.info']
        usage = 'eb setenv [VAR_NAME=KEY ...] [-e environment] [options ...]'
        arguments = [
            (
                ['varKey'],
                dict(
                    action='store',
                    nargs='+',
                    default=[],
                    help=flag_text['setenv.vars']
                )
            ),
            (
                ['-e', '--environment'],
                dict(
                    dest='environment_name',
                    help=flag_text['setenv.env']
                )
            ),
            (
                ['--timeout'],
                dict(
                    type=int,
                    help=flag_text['general.timeout']
                )
            ),
        ]
        epilog = strings['setenv.epilog']

    def do_command(self):
        app_name = self.get_app_name()
        env_name = self.get_env_name()
        var_list = self.app.pargs.varKey
        timeout = self.app.pargs.timeout

        envvarops.setenv(app_name, env_name, var_list, timeout)
