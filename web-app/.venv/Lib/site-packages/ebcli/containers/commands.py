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
import json

from botocore.compat import six
from cement.utils.misc import minimal_logger

from ebcli.core import fileoperations
from ebcli.lib import utils
from ebcli.objects.exceptions import ValidationError, CommandError
from ebcli.resources.strings import strings
from .utils import is_docker_compose_installed


EXPOSE_CMD = 'EXPOSE'
FROM_CMD = 'FROM'
LATEST_TAG = ':latest'
NETWORK_SETTINGS_KEY = 'NetworkSettings'
PORTS_KEY = 'Ports'
HOST_PORT_KEY = 'HostPort'
STATE_KEY = 'State'
RUNNING_KEY = 'Running'
LOG = minimal_logger(__name__)


def pull_img(full_docker_path):
    """
    Pulls a base image found in Dockerfile.
    :param full_docker_path: str: path to the Dockerfile
    :return: None
    """

    img = _get_base_img(full_docker_path)

    if not _is_tag_specified(img):
        img += LATEST_TAG
    _pull_img(img)


def build_img(docker_path, file_path=None):
    """
    Builds a docker image using Dockerfile found in docker path.
    :param docker_path: str: path of dir containing the Dockerfile
    :param file_path: str: optional name of Dockerfile
    :return: str: id of the new image
    """
    img = utils.random_string(6)
    tag = utils.random_string(6)
    img_tag = '{}:{}'.format(img, tag)
    opts = ['-t', img_tag ,'-f', file_path] if file_path else ['-t', img_tag]
    args = ['docker', 'build'] + opts + [docker_path]
    output = _run_live(args)
    return _get_img_id_from_img_tag(img_tag)

def run_container(full_docker_path, image_id, host_port=None,
                  envvars_map=None, volume_map=None, name=None):
    """
    Runs a Docker container. Container port comes from the Dockerfile,
    which is mapped to the given host port.
    :param full_docker_path: str: path to the Dockerfile
    :param image_id: str: id of the image being used to run
    :host_port: str: optional host port. Same as container port by default
    :envvars_map: dict: optional key-val map of environment variables
    :volume_map: dict: optional key-val map of host-container volume mounts
    :name: str: optional name to be assigned to the container
    :return: None
    """

    container_port = _get_container_port(full_docker_path)
    if host_port is None:
        host_port = container_port
    _run_container(image_id, container_port, host_port, envvars_map,
                   volume_map, name)


def rm_container(container_id, force=False):
    """
    Remove a container.
    :param container_id: str: the container's id or name
    :param force: bool: force the removal of the container (SIGKILL)
    :return None
    """

    force_arg = ['-f'] if force else []

    args = ['docker', 'rm'] + force_arg + [container_id]
    _run_quiet(args)


def up(compose_path=None, allow_insecure_ssl=False):
    """
    Build and run the entire app using services defined in docker-compose.yml.
    :param compose_path: str: optional alternate path to docker-compose.yml
    :param allow_insecure_ssl: bool: allow insecure connection to docker registry
    :return None
    """

    file_opt = ['-f', '{}'.format(compose_path)] if compose_path else []
    insecure_ssl_opt = ['--allow-insecure-ssl'] if allow_insecure_ssl else []
    args = file_opt + ['up'] + insecure_ssl_opt

    LOG.debug(args)
    _compose_run(args)


def _compose_run(args):
    if not is_docker_compose_installed():
        raise RuntimeError("Docker Compose is not installed. Please install it and try again.")
    utils.exec_cmd_live_output(['docker','compose'] + args)


def get_container_lowlvl_info(container_id):
    """
    Get a running container's low level info.
    :param container_id: str: the running container's id or name
    :return dict
    """

    args = ['docker', 'inspect', container_id]
    info = json.loads(_run_quiet(args))

    return info[0]


def is_container_existent(container_id):
    """
    Return whether container exists.
    :param container_id: str: the id or name of the container to check
    :return bool
    """

    try:
        get_container_lowlvl_info(container_id)
        return True
    except CommandError:
        return False


def is_running(container_id):
    """
    Return whether container is currently running.
    :param container_id: str: the id or name of the container to check
    :return bool
    """

    try:
        info = get_container_lowlvl_info(container_id)
        return info[STATE_KEY][RUNNING_KEY]
    except CommandError:
        return False


def get_exposed_hostports(container_id):
    """
    Get the host ports we exposed when we ran this container.
    :param container_id: str: the id or name of the running container
    :return list
    """

    # Since we ran the container, we can guarantee that
    # one host port and one or more container ports are exposed.
    # Example of port_map:
    #
    #    {'4848/tcp': None,
    #     '8080/tcp': [{'HostPort': '8080', 'HostIp': '0.0.0.0'}],
    #     '8181/tcp': None}

    try:
        port_map = _get_network_settings(container_id)[PORTS_KEY] or {}
        return utils.flatten([[p[HOST_PORT_KEY] for p in ports]
                             for ports in six.itervalues(port_map) if ports])
    except CommandError:  # Not running
        return []


def version():
    args = ['docker', '--version']
    version_str = _run_quiet(args)
    # Format: Docker version 1.5.0, build a8a31ef
    return version_str.split()[2].strip(',')


def compose_version():
    args = ['docker-compose', '--version']
    # Format: docker-compose 1.1.0
    return _run_quiet(args).split()[-1]


def _get_img_id_from_img_tag(img_tag):
    """
    Get image id for a given image tag
    :param img_tag: str: image tag
    :return image id
    """
    opts = ['-q']
    args = ['docker', 'images'] + opts +[img_tag]
    output = _run_quiet(args)
    return output.split()[0]


def _get_network_settings(container_id):
    info = get_container_lowlvl_info(container_id)
    return info[NETWORK_SETTINGS_KEY]


def _pull_img(img):
    args = ['docker', 'pull', img]
    return _run_live(args)


def _run_container(image_id, container_port, host_port, envvars_map,
                   volume_map, name):
    port_mapping = '{}:{}'.format(host_port, container_port)
    interactive_opt = ['-i']
    pseudotty_opt = ['-t']
    rm_container_on_exit_opt = ['--rm']
    port_opt = ['-p', port_mapping]
    envvar_opt = _get_env_opts(envvars_map)
    volume_opt = _get_volume_opts(volume_map)
    name_opt = ['--name', name] if name else []

    opts = (interactive_opt + pseudotty_opt + rm_container_on_exit_opt +
            port_opt + envvar_opt + volume_opt + name_opt)

    args = ['docker', 'run'] + opts + [image_id]
    return _run_live(args)


def _get_container_port(full_docker_path):
    return _fst_match_in_dockerfile(full_docker_path,
                                    lambda s: s.startswith(EXPOSE_CMD),
                                    strings['local.run.noportexposed'])[1]


def _get_base_img(full_docker_path):
    return _fst_match_in_dockerfile(full_docker_path,
                                    lambda s: s.startswith(FROM_CMD),
                                    strings['local.run.nobaseimg'])[1]


def _fst_match_in_dockerfile(full_docker_path, predicate, not_found_error_msg):
    raw_lines = fileoperations.readlines_from_text_file(full_docker_path)
    stripped_lines = (x.strip() for x in raw_lines)
    try:
        line = next(x for x in stripped_lines if predicate(x))
        return line.split()
    except StopIteration:
        raise ValidationError(not_found_error_msg)


def _is_tag_specified(img_name):
    return ':' in img_name


def _get_env_opts(envvars_map):
    return _get_opts(envvars_map, '--env', '{}={}')


def _get_volume_opts(volume_map):
    return _get_opts(volume_map, '-v', '{}:{}')


def _get_opts(_map, opt_name, val_format):
    _map = _map or {}
    kv_pairs = six.iteritems(_map)
    return utils.flatten([[opt_name, val_format.format(k, v)] for k, v
                          in kv_pairs])


def _run_quiet(args):
    try:
        return utils.exec_cmd_quiet(args)
    except CommandError as e:
        _handle_command_error(e)


def _run_live(args):
    try:
        return utils.exec_cmd_live_output(args)
    except CommandError as e:
        _handle_command_error(e)


def _handle_command_error(e):
    socket_perm_msg = "dial unix /var/run/docker.sock: permission denied."

    if socket_perm_msg in e.output:
        raise CommandError(strings['local.run.socketperms'], e.output, e.code)
    else:
        raise CommandError
