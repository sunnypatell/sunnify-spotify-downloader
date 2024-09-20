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

import sys

from cement.core.controller import expose

from ebcli.objects.platform import PlatformVersion
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.resources.strings import strings, flag_text, alerts
from ebcli.core import io, fileoperations
from ebcli.operations import configops, platformops, saved_configs, solution_stack_ops
from ebcli.operations.tagops import tagops
from ebcli.objects.exceptions import InvalidSyntaxError, NotFoundError, InvalidOptionsError
from ebcli.lib import utils


class ConfigController(AbstractBaseController):
    class Meta:
        label = 'config'
        description = strings['config.info']
        usage = 'eb config < |save|get|put|list|delete> <name> [options ...]'
        arguments = [
            (['name'], dict(action='store', nargs='?',
                            default=[],
                            help='environment_name|template_name')),
            (['-nh', '--nohang'], dict(action='store_true',
                                       help=flag_text['config.nohang'])),
            (['--timeout'], dict(type=int, help=flag_text['general.timeout'])),
            (['--cfg'], dict(help='name of configuration')),
            (['--tags'], dict(help=flag_text['config.tags'])),
            (['-d', '--display'], dict(action='store_true', help=flag_text['config.display'])),
            (['-u', '--update'], dict(help=flag_text['config.update'])),
            (['-f', '--format'], dict(default='yaml', choices=['json', 'yaml'], help=flag_text['config.format']))
        ]
        epilog = strings['config.epilog']

    def do_command(self):
        env_name = self.get_env_name(varname='name')
        app_name = self.get_app_name()
        timeout = self.app.pargs.timeout
        nohang = self.app.pargs.nohang
        cfg = self.app.pargs.cfg
        display = self.app.pargs.display
        update = self.app.pargs.update
        output_format = self.app.pargs.format

        if display and update:
            raise InvalidOptionsError(alerts['create.can_not_use_options_together'].format("--display", "--update"))
        if display:
            configops.display_environment_configuration(app_name, env_name, output_format=output_format)
        elif update:
            configops.modify_environment_configuration(env_name, update, nohang, timeout)
        else:
            input_exists = not sys.stdin.isatty()
            if not cfg and not input_exists:
                configops.update_environment_configuration(app_name, env_name,
                                                           nohang,
                                                           timeout=timeout)
                return

            if cfg:
                cfg_name = saved_configs.resolve_config_name(app_name, cfg)
                saved_configs.update_environment_with_config_file(env_name,
                                                                  cfg_name, nohang,
                                                                  timeout=timeout)
            elif input_exists:
                data = sys.stdin.read()
                saved_configs.update_environment_with_config_data(env_name, data,
                                                                  nohang,
                                                                  timeout=timeout)

    @expose(help='Save a configuration of the environment.')
    def save(self):
        cfg_name = self.app.pargs.cfg
        env_name = self.get_env_name(varname='name',
                                     cmd_example='eb config save')
        app_name = self.get_app_name()
        tags = self.app.pargs.tags
        tags = tagops.get_and_validate_tags(tags)

        if not cfg_name:
            cfg_name = self._choose_cfg_name(app_name, env_name)

        saved_configs.create_config(app_name, env_name, cfg_name, tags)
        if fileoperations.env_yaml_exists():
            io.echo(strings['config.envyamlexists'])

    @expose(help='Upload a configuration to S3.')
    def put(self):
        app_name = self.get_app_name()
        name = self._get_cfg_name('put')
        platform = solution_stack_ops.get_default_solution_stack()

        if not PlatformVersion.is_valid_arn(platform):
            platform = platformops.get_platform_for_platform_string(platform)
            platform = platform.name

        saved_configs.update_config(app_name, name)
        filename = fileoperations.get_filename_without_extension(name)
        saved_configs.validate_config_file(app_name, filename, platform)

    @expose(help='Download a configuration from S3.')
    def get(self):
        app_name = self.get_app_name()
        name = self._get_cfg_name('get')

        try:
            saved_configs.download_config_from_s3(app_name, name)
        except NotFoundError:
            io.log_error(strings['config.notfound'].replace('{config-name}',
                                                            name))

    @expose(help='Delete a configuration.')
    def delete(self):
        name = self._get_cfg_name('delete')
        app_name = self.get_app_name()

        saved_configs.delete_config(app_name, name)

    @expose(help='List all configurations.')
    def list(self):
        app_name = self.get_app_name()

        for c in saved_configs.get_configurations(app_name):
            io.echo(c)

    def _get_cfg_name(self, cmd):
        name = self.app.pargs.name
        if not name:
            io.echo('usage: eb config', cmd, '[configuration_name]')
            raise InvalidSyntaxError('too few arguments')
        else:
            return name

    @staticmethod
    def _choose_cfg_name(app_name, env_name):
        configs = saved_configs.get_configurations(app_name)
        io.echo()
        io.echo('Enter desired name of configuration.')
        default = utils.get_unique_name(env_name + '-sc', configs)
        cfg_name = io.prompt_for_unique_name(default, configs)
        return cfg_name
