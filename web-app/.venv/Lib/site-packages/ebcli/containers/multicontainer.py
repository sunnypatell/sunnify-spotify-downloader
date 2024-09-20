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
from ebcli.containers import commands
from ebcli.containers import compose
from ebcli.containers import dockerrun
from ebcli.core import fileoperations
from ebcli.objects.exceptions import CommandError


class MultiContainer(object):
    """
    Immutable class used to run Multi-containers.
    """

    PROJ_NAME = 'elasticbeanstalk'

    def __init__(self, fs_handler, soln_stk, opt_env, allow_insecure_ssl=False):
        """
        Constructor for MultiContainer.
        :param fs_handler: MultiContainerFSHandler: manages file operations
        :param soln_stk: SolutionStack: the solution stack
        :param opt_env: EnvvarCollector: Optional env (--envvars) variables to add and remove
        :param allow_insecure_ssl: bool: allow insecure connection to docker registry
        """

        self.fs_handler = fs_handler
        self.pathconfig = fs_handler.pathconfig
        self.soln_stk = soln_stk
        self.opt_env = opt_env
        self.allow_insecure_ssl = allow_insecure_ssl

    def start(self):
        self._containerize()
        self._remove()
        self._up()

    def validate(self):
        dockerrun.validate_dockerrun_v2(self.fs_handler.dockerrun)

    def is_running(self):
        return any(commands.is_running(cid) for cid in self.list_services())

    def list_services(self):
        compose_path = self.pathconfig.compose_path()
        compose_dict = fileoperations._get_yaml_dict(compose_path)
        services = compose.iter_services(compose_dict)

        # This is the way docker-compose names the containers/services
        return ['{}_{}_1'.format(self.PROJ_NAME, s) for s in services]

    def _containerize(self):
        opt_env = self.opt_env
        setenv_env = self.fs_handler.get_setenv_env()
        # merged_env contains env. variables from "eb local --envvars x=y ..." and
        # "eb local setenv a=b ..." but not ones in Dockerrun.aws.json
        merged_env = setenv_env.merge(opt_env)

        self.fs_handler.make_docker_compose(merged_env)

    def _up(self):
        commands.up(compose_path=self.pathconfig.compose_path(),
                    allow_insecure_ssl=self.allow_insecure_ssl)

    def _remove(self):
        for service in self.list_services():
            try:
                commands.rm_container(service, force=True)
            except CommandError:
                pass
