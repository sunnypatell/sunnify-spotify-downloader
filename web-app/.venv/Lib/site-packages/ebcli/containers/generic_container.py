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

from ebcli.containers import dockerrun
from ebcli.containers.abstractcontainer import AbstractContainer
from ebcli.objects.exceptions import NotFoundError
from ebcli.resources.strings import strings


class GenericContainer(AbstractContainer):
    """
    Immutable class used for running Generic Docker containers.
    """

    def validate(self):
        if (
            not self.pathconfig.dockerfile_exists()
            and not self.pathconfig.dockerrun_exists()
        ):
            raise NotFoundError(strings['local.filenotfound'])
        dockerrun.validate_dockerrun_v1(
            self.fs_handler.dockerrun,
            not self.pathconfig.dockerfile_exists()
        )

    # This gets called if user only provides Dockerrun.aws.json and not Dockerfile
    def _containerize(self):
        self.fs_handler.make_dockerfile()
