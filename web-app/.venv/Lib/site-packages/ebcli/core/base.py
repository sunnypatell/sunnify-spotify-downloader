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

import textwrap
import sys

from cement.core import controller

from ebcli import __version__
from ebcli.resources.strings import strings, flag_text
from ebcli.core import io


class EbBaseController(controller.CementBaseController):
    """
    This is the application base controller.
    It handles eb when no sub-commands are given
    """
    class Meta:
        label = 'base'
        description = strings['base.info']
        arguments = [
            (['--version'], dict(action='store_true',
                                 help=flag_text['base.version'])),
        ]
        epilog = strings['base.epilog']

    @controller.expose(hide=True)
    def default(self):
        if self.app.pargs.version:
            io.echo(strings['app.version_message'], __version__,
                    '(Python', sys.version + ')')
        else:
            self.app.args.print_help()

    @property
    def _help_text(self):
        """
        Prints the output of `eb --help`
        """
        longest = 0

        def pad(label):
            padlength = longest - len(label) + 2
            padding = '   '
            if padlength < 0:
                for x in range(0, longest):
                    padding += ' '
            else:
                for x in range(0, padlength):
                    padding += ' '
            return padding

        help_txt = ''
        for label in self._visible_commands:
            # get longest command
            if len(label) > longest:
                longest = len(label)

        command_help_overrides = {
            'platform': 'Commands for managing platforms.'
        }
        for label in self._visible_commands:
            cmd = self._dispatch_map[label]
            cmd_txt = '  '
            if len(cmd['aliases']) > 0 and cmd['aliases_only']:
                if len(cmd['aliases']) > 1:
                    first = cmd['aliases'].pop(0)
                    cmd_txt += "%s (alias: %s)\n" % \
                               (first, ', '.join(cmd['aliases']))
                else:
                    cmd_txt += "%s" % cmd['alias'][0]
            elif len(cmd['aliases']) > 0:
                cmd_txt += "%s (alias: %s)\n" % (label, ', '.join(cmd['aliases']))
            else:
                cmd_txt += label

            if cmd['help']:
                cmd_txt += pad(cmd_txt) + "%s\n" % (command_help_overrides.get(label) or cmd['help'])
            else:
                cmd_txt += "\n"

            help_txt += cmd_txt

        if len(help_txt) > 0:
            txt = '''%s

commands:
%s


''' % (self._meta.description, help_txt)
        else:
            txt = self._meta.description

        return textwrap.dedent(txt)
