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
from ebcli.containers import containerops
from ebcli.containers import dockerrun
from ebcli.containers import log
from ebcli.containers.abstractcontainer import AbstractContainer
from ebcli.objects.exceptions import ValidationError


class PreconfiguredContainer(AbstractContainer):
    """
    Immutable class used for running Preconfigured Docker containers.
    """

    def validate(self):
        if self.pathconfig.dockerfile_exists():
            _validate_preconfig_dockerfile(self.soln_stk,
                                           self.container_cfg,
                                           self.pathconfig.dockerfile_path())
        dockerrun.validate_dockerrun_v1(self.fs_handler.dockerrun, False)

    def _containerize(self):
        self.fs_handler.copy_dockerfile(self.soln_stk, self.container_cfg)

    def _get_log_volume_map(self):
        log_volume_map = super(PreconfiguredContainer, self)._get_log_volume_map()

        if log_volume_map:  # User provided Logging in Dockerrun.aws.json
            return log_volume_map
        else:
            host_log = log.new_host_log_path(self.pathconfig.logdir_path())
            cont_log = containerops.get_runtime_default_log_path(self.soln_stk,
                                                                 self.container_cfg)
            return {host_log: cont_log}


def _validate_preconfig_dockerfile(soln_stk, container_config,
                                   full_docker_path):
    """
    Validates that the Dockerfile found at full_docker_path has the correct
    Docker base image that matches runtime Docker image appropriate for this
    solution stack. For example, the given solution stack:

    64bit Debian jessie v1.2.0 running GlassFish 4.1 Java 8 (Preconfigured - Docker)

    must have

    glassfish-runtime-4.1-jdk8 base image in the Dockerfile.

    :param soln_stk: SolutionStack: the solution stack
    :param container_config: dict: container_config.json as dict
    :param full_docker_path: str: path to the Dockerfile
    :return: bool
    """

    container_info = containerops._get_preconfig_info(soln_stk,
                                                      container_config)
    expected_img = container_info[containerops.RUNTIME_IMG_KEY]
    actual_img = commands._get_base_img(full_docker_path)
    err_msg = ('Invalid base Docker img in Dockerfile. Expected {} but got {}'
               .format(expected_img, actual_img))
    if actual_img != expected_img:
        raise ValidationError(err_msg)
