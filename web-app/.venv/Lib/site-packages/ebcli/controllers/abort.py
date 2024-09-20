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
from ebcli.resources.strings import strings, prompts
from ebcli.objects.exceptions import NotFoundError
from ebcli.core import io
from ebcli.lib import utils
from ebcli.operations import abortops


class AbortController(AbstractBaseController):
    class Meta:
        label = 'abort'
        description = strings['abort.info']
        usage = AbstractBaseController.Meta.usage.replace('{cmd}', label)

    def do_command(self):
        app_name = self.get_app_name()
        env_name = self.get_env_name(noerror=True)
        provided_env_name = bool(self.app.pargs.environment_name)

        if not provided_env_name:
            envs = abortops.get_abortable_envs(app_name)
            if len(envs) < 1:
                raise NotFoundError(strings['abort.noabortableenvs'])
            if len(envs) == 1:
                env_name = envs[0].name
            else:
                io.echo()
                io.echo(prompts['abort.envprompt'])
                env_name = utils.prompt_for_item_in_list(envs).name
        else:
            pass

        abortops.abort_operation(env_name)
