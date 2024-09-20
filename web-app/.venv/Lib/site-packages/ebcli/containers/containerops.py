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

from os import path

from ebcli.core import fileoperations
from ebcli.lib import elasticbeanstalk
from ebcli.objects.platform import PlatformBranch, PlatformVersion
from ebcli.objects.solutionstack import SolutionStack

CONTAINER_CONFIG_FILENAME = 'container_config.json'
CONTAINERFILES_DIRNAME = 'containerfiles'
CONTAINERFILES_DIR_PATH = path.join(path.dirname(path.realpath(__file__)),
                                    CONTAINERFILES_DIRNAME)
CONTAINER_CONFIG_PATH = path.join(CONTAINERFILES_DIR_PATH,
                                  CONTAINER_CONFIG_FILENAME)
PRECONFIG_CONTAINER_KEY = 'preconfigured_containers'
GENERIC_CONTAINER_KEY = 'generic_containers'
MULTI_CONTAINER_KEY = 'multi_containers'
VERSION_KEY = 'version'
PLATFORM_KEY = 'platform'
PLATFORM_NAME_KEY = 'platform_name'
RUNTIME_IMG_KEY = 'runtime_image'
RUNTIME_DOCKERFILE_KEY = 'runtime_dockerfile'
RUNTIME_DEFAULT_LOG_KEY = 'runtime_default_log'


def is_container(soln_stk, container_config):
    """
    Whether the solution stack runs Docker containers.
    :param soln_stk: SolutionStack: the solution stack
    :param container_config: dict: container_config.json as dict
    :return: bool
    """

    return (is_preconfigured(soln_stk, container_config) or
            is_generic(soln_stk, container_config))


def is_preconfigured(soln_stk, container_config):
    """
    Whether the solution stack runs preconfigured Docker containers.
    :param soln_stk: SolutionStack: the solution stack
    :param container_config: dict: container_config.json as dict
    :return: bool
    """

    return bool(_get_preconfig_info(soln_stk, container_config))


def is_generic(soln_stk, container_config):
    """
    Whether the solution stack runs generic Docker containers.
    :param soln_stk: SolutionStack: the solution stack
    :param container_config: dict: container_config.json as dict
    :return: bool
    """

    expected_platform = container_config[GENERIC_CONTAINER_KEY][PLATFORM_KEY]

    if isinstance(soln_stk, PlatformVersion):
        return expected_platform in soln_stk.platform_shorthand

    return expected_platform == soln_stk.language_name


def is_multi(soln_stk, container_config):
    """
    Whether the solution stack runs Multi Containers
    :param soln_stk: SolutionStack: the solution stack
    :param container_config: dict: container_config.json as dict
    :return: bool
    """

    expected_platform = container_config[MULTI_CONTAINER_KEY][PLATFORM_KEY]

    if isinstance(soln_stk, PlatformVersion):
        return expected_platform in soln_stk.platform_shorthand

    return expected_platform == soln_stk.language_name


def get_configuration(fullpath=CONTAINER_CONFIG_PATH):
    """
    Deserializes the container configuration json file at fullpath as dict.
    :param fullpath: str: path to the container configuration json file
    :return: dict
    """

    return fileoperations.get_json_dict(fullpath)


def get_runtime_default_log_path(soln_stk, container_config):
    """
    Return where we expect logs to be in the container for Preconfigured
    Containers.
    :param soln_stk: SolutionStack: the solution stack
    :param container_config: dict: container_config.json as dict
    :return: str
    """

    cont_info = _get_preconfig_info(soln_stk, container_config)
    return cont_info[RUNTIME_DEFAULT_LOG_KEY]


def _get_preconfig_info(soln_stk, container_config):
    containers = container_config[PRECONFIG_CONTAINER_KEY]
    return next(
        (
            c for c in containers
            if c[VERSION_KEY] == soln_stk.platform_shorthand
            or c[PLATFORM_NAME_KEY] == soln_stk.platform_shorthand
        ), None)


def _get_runtime_dockerfile_path(soln_stk, container_config):
    cont_info = _get_preconfig_info(soln_stk, container_config)
    img_name = cont_info[RUNTIME_DOCKERFILE_KEY]
    return path.join(CONTAINERFILES_DIR_PATH, img_name)
