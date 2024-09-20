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
import json

import sys
import os
from cement.core import controller

from ebcli import __version__
from ebcli.core.ebglobals import Constants
from ebcli.lib import elasticbeanstalk, utils
from ebcli.core import io, fileoperations
from ebcli.objects.exceptions import (
    NoEnvironmentForBranchError,
    PlatformWorkspaceNotSupportedError,
    ApplicationWorkspaceNotSupportedError,
    EBCLIException,
    NotInitializedError
)
from ebcli.resources.strings import strings, flag_text
from ebcli.objects import region
from ebcli.operations import commonops


class AbstractBaseController(controller.CementBaseController):
    """
    This is an abstract base class that is useless on its own, but used
    by other classes to sub-class from and to share common commands and
    arguments.

    """
    class Meta:
        label = 'abstract'
        stacked_on = 'base'
        stacked_type = 'nested'
        arguments = [
            (['environment_name'], dict(action='store', nargs='?',
                                        default=[],
                                        help=flag_text['general.env'])),
        ]
        epilog = ''
        usage = 'eb {cmd} <environment_name> [options ...]'

    def do_command(self):
        pass

    @classmethod
    def validate_workspace(cls):
        workspace_type = fileoperations.get_workspace_type(None)
        is_platform_workspace_only_command = cls.Meta.__dict__.get(
            'is_platform_workspace_only_command'
        )
        requires_directory_initialization = cls.Meta.__dict__.get(
            'requires_directory_initialization'
        )

        if '--modules' in sys.argv:
            pass
        elif '--help' in sys.argv:
            pass
        elif cls.__name__ == 'PlatformListController' or cls.__name__ == 'EBPListController':
            pass
        elif requires_directory_initialization and not workspace_type:
            raise NotInitializedError(strings['exit.notsetup'])
        elif is_platform_workspace_only_command:
            if Constants.WorkSpaceTypes.APPLICATION == workspace_type:
                raise ApplicationWorkspaceNotSupportedError(
                    strings['exit.applicationworkspacenotsupported']
                )


    @controller.expose(hide=True)
    def default(self):
        """
        This command will be shared within all controllers that sub-class
        from here.  It can also be overridden in the sub-class

        """
        self.validate_workspace()
        self.do_command()
        self.check_for_cli_update(__version__)

    def check_workspace_type(self, expected_type):
        workspace_type = fileoperations.get_workspace_type()
        if workspace_type != expected_type:
            if Constants.WorkSpaceTypes.PLATFORM == workspace_type:
                raise PlatformWorkspaceNotSupportedError(
                    strings['exit.platformworkspacenotsupported']
                )
            if Constants.WorkSpaceTypes.APPLICATION == workspace_type:
                raise ApplicationWorkspaceNotSupportedError(
                    strings['exit.applicationworkspacenotsupported']
                )

    def check_for_cli_update(self, version):
        label = self.Meta.label
        if label in ('create', 'deploy', 'status', 'clone', 'config'):
            if cli_update_exists(version):
                if self.check_install_script_used():
                    io.log_alert(strings['base.update_available_script_install'])
                else:
                    io.log_alert(strings['base.update_available'])

    def get_app_name(self):
        app_name = fileoperations.get_application_name()
        return app_name

    def get_env_name(self, cmd_example=None, noerror=False, varname='environment_name'):
        env_name = getattr(self.app.pargs, varname, None)
        if not env_name:
            env_name = commonops. \
                get_current_branch_environment()

        workspace_type = fileoperations.get_workspace_type(Constants.WorkSpaceTypes.APPLICATION)

        if not env_name:
            if Constants.WorkSpaceTypes.PLATFORM == workspace_type:
                raise EBCLIException(strings['platform.nobuilderenv'])

            if noerror:
                return None

            if not cmd_example:
                message = strings['branch.noenv'].replace('{cmd}',
                                                          self.Meta.label)
            else:
                message = strings['branch.noenv'].replace('eb {cmd}',
                                                          cmd_example)
            io.log_error(message)
            raise NoEnvironmentForBranchError()

        return env_name

    def check_install_script_used(self):
        return '.ebcli-virtual-env' in os.path.abspath(__file__)

    @classmethod
    def _add_to_handler(cls, handler):
        handler.register(cls)

    @property
    def _help_text(self):
        """
        Returns the help text displayed when for the commands of the type `eb <command> <subcommand>`
        except where <command> is "platform".
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
            if len(label) > longest:
                longest = len(label)

        for label in self._visible_commands:
            cmd = self._dispatch_map[label]
            cmd_txt = '  '

            cmd_name = label
            cmd_aliases = cmd['aliases']

            if len(cmd_aliases) > 0 and cmd['aliases_only']:
                cmd_name = cmd_aliases.pop(0)

            cmd_txt += '{}'.format(cmd_name)

            if cmd['help']:
                cmd_txt += '{}{}'.format(pad(cmd_txt), cmd['help'])

            if len(cmd_aliases) > 0:
                cmd_txt += '\n{}(alias: {})'.format(pad(''), ', '.join(cmd_aliases))

            cmd_txt += '\n'
            help_txt += cmd_txt

        if len(help_txt) > 0:
            txt = '''{}

commands:
{}


'''.format(self._meta.description, help_txt)
        else:
            txt = self._meta.description

        return textwrap.dedent(txt)


def cli_update_exists(current_version):
    try:
        data = utils.get_data_from_url(
            'https://pypi.python.org/pypi/awsebcli/json', timeout=5)
        data = json.loads(data)
        latest = data['info']['version']
        return latest != current_version
    except:
        return False
