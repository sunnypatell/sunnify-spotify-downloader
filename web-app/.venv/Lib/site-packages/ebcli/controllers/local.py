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

from ebcli.core import io
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.containers import factory, log, compat
from ebcli.containers.container_viewmodel import ContainerViewModel
from ebcli.operations import localops
from ebcli.resources.strings import strings, flag_text


class LocalController(AbstractBaseController):
    class Meta:
        label = 'local'
        description = strings['local.info']
        usage = 'eb local (sub-commands ...) [options ...]'
        arguments = []

    def do_command(self):
        self.app.args.print_help()

    @classmethod
    def _add_to_handler(cls, handler):
        handler.register(cls)
        for child_controller in cls._get_child_controllers():
            handler.register(child_controller)

    @staticmethod
    def _get_child_controllers():
        return [LocalLogsController, LocalOpenController,
                LocalPrintEnvController, LocalRunController,
                LocalSetEnvController, LocalStatusController]


class LocalRunController(AbstractBaseController):
    class Meta:
        label = 'local_run'
        description = strings['local.run.info']
        aliases = ['run']
        aliases_only = True
        stacked_on = 'local'
        stacked_type = 'nested'
        usage = 'eb local run [options ...]'
        arguments = [(['--envvars'], dict(help=flag_text['local.run.envvars'])),
                     (['--port'],
                         dict(type=int, help=flag_text['local.run.hostport'])),
                     (['--allow-insecure-ssl'],
                         dict(action='store_true', help=flag_text['local.run.insecuressl']))]

    def do_command(self):
        cnt = factory.make_container(self.app.pargs.envvars,
                                     self.app.pargs.port,
                                     self.app.pargs.allow_insecure_ssl)
        cnt.validate()
        cnt.start()


class LocalLogsController(AbstractBaseController):
    class Meta:
        label = 'local_logs'
        description = strings['local.logs.info']
        aliases = ['logs']
        aliases_only = True
        stacked_on = 'local'
        stacked_type = 'nested'
        usage = 'eb local logs [options ...]'
        arguments = []

    def do_command(self):
        log.print_logs()


class LocalOpenController(AbstractBaseController):
    class Meta:
        label = 'local_open'
        description = strings['local.open.info']
        aliases = ['open']
        aliases_only = True
        stacked_on = 'local'
        stacked_type = 'nested'
        usage = 'eb local open [options ...]'
        arguments = []

    def do_command(self):
        cnt = factory.make_container()
        cnt_viewmodel = ContainerViewModel.from_container(cnt)
        localops.open_webpage(cnt_viewmodel)


class LocalStatusController(AbstractBaseController):
    class Meta:
        label = 'local_status'
        description = strings['local.status.info']
        aliases = ['status']
        aliases_only = True
        stacked_on = 'local'
        stacked_type = 'nested'
        usage = 'eb local status [options ...]'
        arguments = []

    def do_command(self):
        cnt = factory.make_container()
        cnt_viewmodel = ContainerViewModel.from_container(cnt)
        localops.print_container_details(cnt_viewmodel)


class LocalSetEnvController(AbstractBaseController):
    class Meta:
        label = 'local_setenv'
        description = strings['local.setenv.info']
        aliases = ['setenv']
        aliases_only = True
        stacked_on = 'local'
        stacked_type = 'nested'
        usage = 'eb local setenv [VAR_NAME=KEY ...] [options ...]'
        arguments = [
            (['varKey'], dict(action='store', nargs='+',
                              default=[], help=flag_text['local.setenv.vars']))
        ]
        epilog = strings['local.setenv.epilog']

    def do_command(self):
        localops.setenv(self.app.pargs.varKey)


class LocalPrintEnvController(AbstractBaseController):
    class Meta:
        label = 'local_printenv'
        description = strings['local.printenv.info']
        aliases = ['printenv']
        aliases_only = True
        stacked_on = 'local'
        stacked_type = 'nested'
        usage = 'eb local printenv [options ...]'
        arguments = []

    def do_command(self):
        localops.get_and_print_environment_vars()
