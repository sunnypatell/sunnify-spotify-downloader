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
from ebcli.operations import restoreops
from ebcli.resources.strings import strings, flag_text


class RestoreController(AbstractBaseController):
    class Meta(AbstractBaseController.Meta):
        label = 'restore'
        description = strings['restore.info']
        arguments = [
            (
                ['environment_id'],
                dict(
                    action='store',
                    nargs='?',
                    default=[],
                    help=flag_text['restore.env']
                )
            ),
            (['--timeout'], dict(type=int, help=flag_text['general.timeout'])),
        ]
        usage = AbstractBaseController.Meta.usage.replace(
            '{cmd}',
            label
        ).replace(
            'environment_name',
            'environment_id'
        )

    def do_command(self):
        self.env_id = self.app.pargs.environment_id
        self.timeout = self.app.pargs.timeout

        if self.env_id:
            restoreops.restore(self.env_id, self.timeout)
        else:
            self.interactive_restore_environment()

    def interactive_restore_environment(self):
        """
        Interactive mode which allows user to see previous
        environments and allow a choice to restore one.
        Run when the user supplies no arguments.
        """
        environments = restoreops.get_restorable_envs(self.get_app_name())
        restoreops.display_environments(environments)
