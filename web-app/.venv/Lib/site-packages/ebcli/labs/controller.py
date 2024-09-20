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
from ebcli.core import io
from ebcli.labs.quicklink import QuicklinkController
from ebcli.labs.download import DownloadController
from ebcli.labs.convertdockerrun import ConvertDockerrunController
from ebcli.labs.cleanupversions import CleanupVersionsController
from ebcli.labs.cloudwatchsetup import CloudWatchSetUp
from ebcli.labs.setupssl import SetupSSLController


class LabsController(AbstractBaseController):
    class Meta:
        label = 'labs'
        description = strings['labs.info']
        usage = AbstractBaseController.Meta.usage.\
            replace('{cmd}', 'labs {cmd}')
        arguments = []

    def do_command(self):
        self.app.args.print_help()

    def complete_command(self, commands):
        if len(commands) == 1:
            labels = [c.Meta.label for c in self._get_child_controllers()]
            io.echo(*(label.replace('_', '-') for label in labels))
        elif len(commands) > 1:
            controllers = self._get_child_controllers()
            for c in controllers:
                if commands[1] == c.Meta.label.replace('_', '-'):
                    c().complete_command(commands[1:])

    @staticmethod
    def _get_child_controllers():
        return [
            QuicklinkController,
            DownloadController,
            ConvertDockerrunController,
            CleanupVersionsController,
            SetupSSLController,
            CloudWatchSetUp
        ]

    @classmethod
    def _add_to_handler(cls, handler):
        handler.register(cls)
        for c in cls._get_child_controllers():
            handler.register(c)
