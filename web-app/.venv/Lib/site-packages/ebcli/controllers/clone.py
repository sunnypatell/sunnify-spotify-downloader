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
from ebcli.resources.strings import strings, flag_text, prompts
from ebcli.core import io
from ebcli.operations import cloneops, solution_stack_ops
from ebcli.lib import utils, elasticbeanstalk
from ebcli.controllers.create import get_cname_from_customer, get_and_validate_envars
from ebcli.operations.tagops import tagops
from ebcli.objects.exceptions import InvalidOptionsError, AlreadyExistsError
from ebcli.objects.requests import CloneEnvironmentRequest


class CloneController(AbstractBaseController):
    class Meta(AbstractBaseController.Meta):
        label = 'clone'
        description = strings['clone.info']
        arguments = [
            (['environment_name'], dict(action='store', nargs='?', help=flag_text['clone.env'])),
            (['-n', '--clone_name'], dict(help=flag_text['clone.name'])),
            (['-c', '--cname'], dict(help=flag_text['clone.cname'])),
            (['--scale'], dict(type=int, help=flag_text['clone.scale'])),
            (['--tags'], dict(help=flag_text['clone.tags'])),
            (['--envvars'], dict(help=flag_text['create.envvars'])),
            (['-nh', '--nohang'], dict(action='store_true',
                                       help=flag_text['clone.nohang'])),
            (['--timeout'], dict(type=int, help=flag_text['general.timeout'])),
            (['--exact'], dict(action='store_true', help=flag_text['clone.exact'])),
        ]
        usage = 'eb clone <environment_name> (-n CLONE_NAME) [options ...]'

    def do_command(self):
        app_name = self.get_app_name()
        env_name = self.get_env_name()
        clone_name = self.app.pargs.clone_name
        cname = self.app.pargs.cname
        scale = self.app.pargs.scale
        nohang = self.app.pargs.nohang
        tags = self.app.pargs.tags
        envvars = self.app.pargs.envvars
        exact = self.app.pargs.exact
        timeout = self.app.pargs.timeout
        provided_clone_name = clone_name is not None
        platform = None

        env = elasticbeanstalk.get_environment(app_name=app_name, env_name=env_name)
        tier = env.tier
        if 'worker' in tier.name.lower() and cname:
            raise InvalidOptionsError(strings['worker.cname'])

        if cname:
            if not elasticbeanstalk.is_cname_available(cname):
                raise AlreadyExistsError(strings['cname.unavailable'].
                                         replace('{cname}', cname))

        tags = tagops.get_and_validate_tags(tags)
        envvars = get_and_validate_envars(envvars)

        if not clone_name:
            if len(env_name) < 16:
                unique_name = env_name + '-clone'
            else:
                unique_name = 'my-cloned-env'

            env_list = elasticbeanstalk.get_environment_names(app_name)

            unique_name = utils.get_unique_name(unique_name, env_list)

            clone_name = io.prompt_for_environment_name(
                default_name=unique_name,
                prompt_text='Enter name for Environment Clone'
            )

        if tier.name.lower() == 'webserver':
            if not cname and not provided_clone_name:
                cname = get_cname_from_customer(clone_name)
            elif not cname:
                cname = None

        if not exact:
            if not provided_clone_name:
                latest = solution_stack_ops.find_solution_stack_from_string(
                    env.platform.name,
                    find_newer=True
                )

                if latest != env.platform:
                    io.echo()
                    io.echo(prompts['clone.latest'])
                    lst = ['Latest  (' + str(latest) + ')',
                           'Same    (' + str(env.platform) + ')']
                    result = utils.prompt_for_item_in_list(lst)
                    if result == lst[0]:
                        platform = latest
                else:
                    platform = latest
            else:
                platform = solution_stack_ops.find_solution_stack_from_string(
                    env.platform.name,
                    find_newer=True
                )
                if platform != env.platform:
                    io.log_warning(prompts['clone.latestwarn'])

        clone_request = CloneEnvironmentRequest(
            app_name=app_name,
            env_name=clone_name,
            original_name=env_name,
            cname=cname,
            platform=platform,
            scale=scale,
            tags=tags,
        )

        clone_request.option_settings += envvars

        cloneops.make_cloned_env(
            clone_request,
            nohang=nohang,
            timeout=timeout
        )
