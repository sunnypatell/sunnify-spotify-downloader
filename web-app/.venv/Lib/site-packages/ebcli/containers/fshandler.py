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
import os
import shutil
import yaml

from ebcli.containers import commands
from ebcli.containers import compose
from ebcli.containers import containerops
from ebcli.containers import dockerrun
from ebcli.containers import log
from ebcli.core import fileoperations
from ebcli.operations.localops import LocalState
from ebcli.resources.strings import docker_ignore


class ContainerFSHandler(object):
    """
    Handles Container related file operations.
    """

    def __init__(self, pathconfig, dockerrun):
        """
        Constructor for ContainerFSHandler.
        :param pathconfig: PathConfig: Holds path/existence info
        :param dockerrun: dict: Dockerrun.aws.json as dict
        """

        self.pathconfig = pathconfig
        self.dockerrun = dockerrun

    def require_new_dockerfile(self):
        """
        Return whether we need to make a new Dockerfile since user didn't
        provide one.
        :return bool
        """

        return not self.pathconfig.dockerfile_exists()

    def make_dockerfile(self):
        """
        Create a new Dockerfile using info provided in Dockerrun.aws.json.
        :return None
        """

        destination = self.pathconfig.new_dockerfile_path()

        base_img = dockerrun.get_base_img(self.dockerrun)
        exposed_port = dockerrun.get_exposed_port(self.dockerrun)

        from_line = '{} {}'.format(commands.FROM_CMD, base_img)
        expose_line = '{} {}'.format(commands.EXPOSE_CMD, exposed_port)
        dockerfile_contents = os.linesep.join([from_line, expose_line])

        fileoperations.write_to_text_file(location=destination,
                                          data=dockerfile_contents)

    def require_append_dockerignore(self):
        """
        Return whether we need to append dockerignore because user isn't already
        ignoring .elasticbeanstalk/* (and others) already.
        :return bool
        """

        return _require_append_dockerignore(self.pathconfig.dockerignore_path())

    def append_dockerignore(self):
        """
        Append .dockerignore to include .elasticbeanstalk/* and others.
        :return None
        """

        _append_dockerignore(self.pathconfig.dockerignore_path())

    def copy_dockerfile(self, soln_stk, container_cfg):
        """
        Copies the appropriate Dockerfile (preconfigured Docker) that match the
        given solution stack to given destination. For example, with the given
        solution stack:

        64bit Debian jessie v1.2.0 running GlassFish 4.1 Java 8 (Preconfigured - Docker)

        copy Dockerfile with name

        glassfish-runtime-4.1-jdk8

        to destination_dockerfile.

        :param destination_dockerfile: str: destination Dockerfile location
        :param soln_stk: SolutionStack: solution stack
        :param container_cfg: dict: container_config.json
        :return: None
        """

        assert(containerops.is_preconfigured(soln_stk, container_cfg))

        dfile_path = containerops._get_runtime_dockerfile_path(soln_stk,
                                                               container_cfg)
        shutil.copyfile(dfile_path, self.pathconfig.new_dockerfile_path())

    def get_setenv_env(self):
        return LocalState.get_envvarcollector(self.pathconfig.local_state_path())


class MultiContainerFSHandler(object):
    """
    Handles MultiContainer related file operations.
    """
    def __init__(self, pathconfig, dockerrun):
        """
        Constructor for MultiContainerFSHandler.
        :param pathconfig: PathConfig: Holds path/existence info
        :param dockerrun: dict: Dockerrun.aws.json as dict
        """

        self.pathconfig = pathconfig
        self.dockerrun = dockerrun

    def make_docker_compose(self, env):
        """
        Create docker-compose.yml by using Dockerrun.aws.json.
        :param env: EnvvarCollector: contains envvars map and envvars to remove
        :return None
        """

        hostlog_path = self._make_and_get_new_host_log()
        compose_yaml = yaml.safe_dump(self._get_compose_dict(env, hostlog_path),
                                      default_flow_style=False)
        fileoperations.write_to_text_file(location=self.pathconfig.compose_path(),
                                          data=compose_yaml)

    def _get_compose_dict(self, env, hostlog_path):
        return compose.compose_dict(self.dockerrun,
                                    self.pathconfig.docker_proj_path(),
                                    hostlog_path,
                                    env)

    def get_setenv_env(self):
        return LocalState.get_envvarcollector(self.pathconfig.local_state_path())

    def _make_and_get_new_host_log(self):
        root_log_dir = self.pathconfig.logdir_path()
        hostlog_path = log.new_host_log_path(root_log_dir)
        log.make_logdirs(root_log_dir, hostlog_path)
        return hostlog_path


def _require_append_dockerignore(dockerignore_path):
    if not os.path.isfile(dockerignore_path):
        return True

    lines = fileoperations.readlines_from_text_file(dockerignore_path)
    return all(line.strip() != docker_ignore[0] for line in lines)


def _append_dockerignore(dockerignore_path):
    dockerignore_contents = os.linesep.join(docker_ignore)
    fileoperations.append_to_text_file(dockerignore_path,
                                       dockerignore_contents)
