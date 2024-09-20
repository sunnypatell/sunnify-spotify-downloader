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

import abc
import hashlib

from ebcli.containers import commands
from ebcli.containers import dockerrun
from ebcli.containers import log
from ebcli.objects.exceptions import CommandError
from ebcli.lib import utils


class AbstractContainer(object):
    """
    Abstract class subclassed by PreconfiguredContainer and GenericContainer.
    Container holds all of the data and most of the functionality needed to
    run a Docker container locally.
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, fs_handler, soln_stk, container_cfg,
                 opt_env=None, host_port=None):
        """
        Constructor for Container.
        :param fs_handler: ContainerFSHandler: manages container related files
        :param soln_stk: SolutionStack: environment's solution stack
        :param container_cfg: dict: container_config.json as dict
        :param opt_env: EnvvarCollector: Optional env (--envvars) variables to add and remove
        :param host_port: str: optional host port. Same as container port by default
        """

        self.fs_handler = fs_handler
        self.pathconfig = fs_handler.pathconfig
        self.soln_stk = soln_stk
        self.container_cfg = container_cfg
        self.opt_env = opt_env
        self.host_port = host_port

    def start(self):
        """
        Ensure .elasticbeanstalk/* ignored in .dockerignore, containerize app
        by adding Dockerfile if user doesn't provide one, then pull, build, and
        run the container.
        :return None
        """

        if self.fs_handler.require_append_dockerignore():
            self.fs_handler.append_dockerignore()

        if self.fs_handler.require_new_dockerfile():
            self._containerize()

        if self._require_pull():
            self._pull()

        self._remove()
        img_id = self._build()
        self._run(img_id)

    def validate(self):
        """
        Validates the container is configured properly.
        :return None
        """
        pass

    def final_envvars(self):
        setenv_env = self.fs_handler.get_setenv_env()
        merged = setenv_env.merge(self.opt_env).filtered()
        return merged.map

    def get_name(self, hash_obj=hashlib.sha1):
        """
        Return the name that is or will be assigned to this container.
        :return str
        """

        hash_key = self.pathconfig.docker_proj_path().encode('utf-8')
        return hash_obj(hash_key).hexdigest()

    def is_running(self):
        return commands.is_running(self.get_name())

    @abc.abstractmethod
    def _containerize(self, destination_dockerfile=None):
        """
        Make a Dockerfile to destiantion path used for when user doesn't
        provide a Dockerfile.
        :param destination_dockerfile: str: full path to destination Dockerfile
        :return None
        """
        pass

    def _get_full_docker_path(self):
        """
        Return the full path to the Dockerfile we will be using for pulling
        and building Docker images.
        :return str
        """

        if self.pathconfig.dockerfile_exists():
            return self.pathconfig.dockerfile_path()
        else:
            return self.pathconfig.new_dockerfile_path()

    def _require_pull(self):
        return dockerrun.require_docker_pull(self.fs_handler.dockerrun)

    def _pull(self):
        return commands.pull_img(self._get_full_docker_path())

    def _build(self):
        return commands.build_img(self.pathconfig.docker_proj_path(),
                                  self._get_full_docker_path())

    def _run(self, img_id):
        log_volume_map = self._get_log_volume_map()
        if log_volume_map:
            log.make_logdirs(self.pathconfig.logdir_path(), utils.anykey(log_volume_map))

        return commands.run_container(full_docker_path=self._get_full_docker_path(),
                                      image_id=img_id,
                                      envvars_map=self.final_envvars(),
                                      host_port=self.host_port,
                                      volume_map=log_volume_map,
                                      name=self.get_name())

    def _get_log_volume_map(self):
        return log.get_log_volume_map(self.pathconfig.logdir_path(),
                                      self.fs_handler.dockerrun)

    def _remove(self):
        try:
            commands.rm_container(self.get_name(), force=True)
        except CommandError:
            pass
