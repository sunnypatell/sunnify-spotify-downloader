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
from ebcli.lib import utils
from ebcli.core import io

from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.resources.strings import strings, flag_text, prompts
from ebcli.operations import gitops


class CodeSourceController(AbstractBaseController):
    class Meta(AbstractBaseController.Meta):
        label = 'codesource'
        description = strings['codesource.info']
        arguments = [
            (
                ['sourcename'],
                dict(
                    action='store',
                    nargs='?',
                    help=flag_text['codesource.sourcename'],
                    choices=['codecommit', 'local'],
                    type=str.lower
                )
            ),
        ]
        usage = 'eb codesource <sourcename> [options ...]'

    def do_command(self):
        sourcename = self.app.pargs.sourcename
        if sourcename is not None:
            if sourcename == 'local':
                gitops.print_current_codecommit_settings()
                self.set_local()
            if sourcename == 'codecommit':
                self.set_codecommit()
        else:
            self.prompt_for_codesource()

    def prompt_for_codesource(self):
        gitops.print_current_codecommit_settings()
        io.echo(prompts['codesource.codesourceprompt'])
        setup_choices = ['CodeCommit', 'Local']
        choice = utils.prompt_for_item_in_list(setup_choices, 2)
        if choice == setup_choices[0]:
            self.set_codecommit()
        elif choice == setup_choices[1]:
            self.set_local()

    def set_local(self):
        gitops.disable_codecommit()
        io.echo(strings['codesource.localmsg'])

    def set_codecommit(self):
        gitops.initialize_codecommit()
