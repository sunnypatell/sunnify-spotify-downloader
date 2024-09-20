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
from ebcli.core import fileoperations


class PathConfig(object):
    COMPOSE_FILENAME = 'docker-compose.yml'
    DOCKERCFG_FILENAME = '.dockercfg'
    DOCKERIGNORE_FILENAME = '.dockerignore'
    DOCKERFILE_FILENAME = 'Dockerfile'
    DOCKERRUN_FILENAME = 'Dockerrun.aws.json'
    LOCAL_STATE_FILENAME = '.localstate'
    NEW_DOCKERFILE_FILENAME = 'Dockerfile.local'
    ROOT_LOCAL_LOGS_DIRNAME = 'local'

    @staticmethod
    def docker_proj_path():
        return fileoperations.get_project_root()

    @classmethod
    def dockerfile_path(cls):
        return fileoperations.project_file_path(cls.DOCKERFILE_FILENAME)

    @classmethod
    def new_dockerfile_path(cls):
        return fileoperations.get_eb_file_full_location(cls.NEW_DOCKERFILE_FILENAME)

    @classmethod
    def dockerignore_path(cls):
        return fileoperations.project_file_path(cls.DOCKERIGNORE_FILENAME)

    @classmethod
    def logdir_path(cls):
        return fileoperations.get_logs_location(cls.ROOT_LOCAL_LOGS_DIRNAME)

    @classmethod
    def dockerrun_path(cls):
        return fileoperations.project_file_path(cls.DOCKERRUN_FILENAME)

    @classmethod
    def compose_path(cls):
        return fileoperations.get_eb_file_full_location(cls.COMPOSE_FILENAME)

    @classmethod
    def local_state_path(cls):
        return fileoperations.get_eb_file_full_location(cls.LOCAL_STATE_FILENAME)

    @classmethod
    def dockerfile_exists(cls):
        return fileoperations.project_file_exists(cls.DOCKERFILE_FILENAME)

    @classmethod
    def dockerrun_exists(cls):
        return fileoperations.project_file_exists(cls.DOCKERRUN_FILENAME)
