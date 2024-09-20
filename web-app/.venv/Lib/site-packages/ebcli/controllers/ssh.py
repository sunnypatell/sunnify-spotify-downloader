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
from ebcli.objects.exceptions import InvalidOptionsError
from ebcli.operations import sshops


class SSHController(AbstractBaseController):
    class Meta:
        label = 'ssh'
        description = strings['ssh.info']
        usage = AbstractBaseController.Meta.usage.replace('{cmd}', label)
        arguments = AbstractBaseController.Meta.arguments + [
            (['-n', '--number'], dict(help=flag_text['ssh.number'], type=int)),
            (['-i', '--instance'], dict(help=flag_text['ssh.instance'])),
            (['-c', '--command'], dict(help=flag_text['ssh.command'], type=str)),
            (['-e', '--custom'], dict(help=flag_text['ssh.custom'], type=str)),
            (['-o', '--keep_open'], dict(
                action='store_true', help=flag_text['ssh.keepopen'])),
            (['--force'], dict(
                action='store_true', help=flag_text['ssh.force'])),
            (['--setup'], dict(
                action='store_true', help=flag_text['ssh.setup'])),
            (['--timeout'], dict(type=int, help=flag_text['ssh.timeout'])),
        ]

    def do_command(self):
        number = self.app.pargs.number
        env_name = self.get_env_name()
        instance = self.app.pargs.instance
        cmd = self.app.pargs.command
        custom_ssh = self.app.pargs.custom
        keep_open = self.app.pargs.keep_open
        force = self.app.pargs.force
        setup = self.app.pargs.setup
        timeout = self.app.pargs.timeout

        if timeout and not setup:
            raise InvalidOptionsError(strings['ssh.timeout_without_setup'])

        sshops.prepare_for_ssh(
                env_name=env_name,
                instance=instance,
                keep_open=keep_open,
                force=force,
                setup=setup,
                number=number,
                custom_ssh=custom_ssh,
                command=cmd,
                timeout=timeout
        )
