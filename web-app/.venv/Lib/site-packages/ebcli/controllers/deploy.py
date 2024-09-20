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

from os import path, chdir, getcwd

from cement.utils.misc import minimal_logger

from ebcli.core import io, hooks, fileoperations
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.lib import elasticbeanstalk, utils
from ebcli.objects.exceptions import InvalidOptionsError
from ebcli.operations import commonops, deployops, composeops, statusops
from ebcli.resources.strings import strings, flag_text, alerts
from ebcli.resources.statics import platform_branch_lifecycle_states

LOG = minimal_logger(__name__)


class DeployController(AbstractBaseController):
    class Meta(AbstractBaseController.Meta):
        label = 'deploy'
        description = strings['deploy.info']
        arguments = [
            (['environment_name'], dict(
                action='store', nargs='?', default=[],
                help=flag_text['deploy.env'])),
            (['--modules'], dict(help=flag_text['deploy.modules'], nargs='*')),
            (['-g', '--env-group-suffix'], dict(help=flag_text['deploy.group_suffix'])),
            (['--version'], dict(help=flag_text['deploy.version'])),
            (['-l', '--label'], dict(help=flag_text['deploy.label'])),
            (['-m', '--message'], dict(help=flag_text['deploy.message'])),
            (['-nh', '--nohang'], dict(
                action='store_true', help=flag_text['deploy.nohang'])),
            (['--staged'], dict(
                action='store_true', help=flag_text['deploy.staged'])),
            (['--timeout'], dict(type=int, help=flag_text['general.timeout'])),
            (['--source'], dict(help=flag_text['deploy.source'])),
            (['-p', '--process'], dict(
                action='store_true', help=flag_text['deploy.process'])),
            ]
        usage = AbstractBaseController.Meta.usage.replace('{cmd}', label)

    def do_command(self):
        self.timeout = self.app.pargs.timeout
        self.nohang = self.app.pargs.nohang
        if self.nohang:
            self.timeout = 0
        if self.app.pargs.modules:
            self.multiple_app_deploy()
            return

        self.message = self.app.pargs.message
        self.staged = self.app.pargs.staged
        self.source = self.app.pargs.source
        self.app_name = self.get_app_name()
        self.env_name = self.get_env_name()
        self.version = self.app.pargs.version
        self.label = self.app.pargs.label
        self.process = self.app.pargs.process
        group_name = self.app.pargs.env_group_suffix

        _check_env_lifecycle_state(self.env_name)

        if self.version and (self.message or self.label):
            raise InvalidOptionsError(strings['deploy.invalidoptions'])

        process_app_versions = fileoperations.env_yaml_exists() or self.process

        deployops.deploy(self.app_name, self.env_name, self.version, self.label,
                         self.message, group_name=group_name, process_app_versions=process_app_versions,
                         staged=self.staged, timeout=self.timeout, source=self.source)

    def multiple_app_deploy(self):
        missing_env_yaml = []
        top_dir = getcwd()

        for module in self.app.pargs.modules:
            if not path.isdir(path.join(top_dir, module)):
                continue

            chdir(path.join(top_dir, module))

            if not fileoperations.env_yaml_exists():
                missing_env_yaml.append(module)

            chdir(top_dir)

        if len(missing_env_yaml) > 0:
            module_list = ''
            for module_name in missing_env_yaml:
                module_list = module_list + module_name + ', '
            io.echo(strings['deploy.modulemissingenvyaml'].replace('{modules}', module_list[:-2]))

            return

        self.compose_deploy()

    def compose_deploy(self):
        app_name = None
        modules = self.app.pargs.modules
        group_name = self.app.pargs.env_group_suffix

        env_names = []
        stages_version_labels = {}
        stages_env_names = {}

        top_dir = getcwd()
        for module in modules:
            if not path.isdir(path.join(top_dir, module)):
                io.log_error(strings['deploy.notadirectory'].replace('{module}', module))
                continue

            chdir(path.join(top_dir, module))

            if not group_name:
                group_name = commonops.get_current_branch_group_suffix()
            if group_name not in stages_version_labels.keys():
                stages_version_labels[group_name] = []
                stages_env_names[group_name] = []

            if not app_name:
                app_name = self.get_app_name()

            io.echo('--- Creating application version for module: {0} ---'.format(module))

            hooks.set_region(None)
            hooks.set_ssl(None)
            hooks.set_profile(None)

            if not app_name:
                app_name = self.get_app_name()

            process_app_version = fileoperations.env_yaml_exists()
            version_label = commonops.create_app_version(app_name, process=process_app_version)

            stages_version_labels[group_name].append(version_label)

            environment_name = fileoperations.get_env_name_from_env_yaml()

            if environment_name is not None:
                commonops.set_environment_for_current_branch(environment_name.
                                                             replace('+', '-{0}'.
                                                                     format(group_name)))

                env_name = commonops.get_current_branch_environment()
                stages_env_names[group_name].append(env_name)
                env_names.append(env_name)
            else:
                io.echo(strings['deploy.noenvname'].replace('{module}', module))

                stages_version_labels[group_name] = [
                    v for v in stages_version_labels[group_name]
                    if v != version_label
                ]

            chdir(top_dir)

        if len(stages_version_labels) > 0:
            for stage in stages_version_labels.keys():
                request_id = composeops.compose_no_events(app_name, stages_version_labels[stage],
                                                          group_name=stage)
                if request_id is None:
                    io.log_error("Unable to compose modules.")
                    return

                commonops.wait_for_compose_events(request_id, app_name, env_names, self.timeout)
        else:
            io.log_warning(strings['compose.novalidmodules'])


def _check_env_lifecycle_state(env_name):
    env = elasticbeanstalk.get_environment(env_name=env_name)
    statusops.alert_environment_status(env)
