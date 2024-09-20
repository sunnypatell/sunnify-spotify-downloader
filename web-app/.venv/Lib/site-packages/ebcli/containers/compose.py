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

from botocore.compat import six

from ebcli.containers.envvarcollector import EnvvarCollector


AWSEB_LOGS = 'awseb-logs-'
COMPOSE_CMD_KEY = 'command'
COMPOSE_ENV_KEY = 'environment'
COMPOSE_IMG_KEY = 'image'
COMPOSE_LINKS_KEY = 'links'
COMPOSE_PORTS_KEY = 'ports'
COMPOSE_VOLUMES_KEY = 'volumes'
CONTAINER_DEF_CMD_KEY = 'command'
CONTAINER_DEF_CONTAINERPORT_KEY = 'containerPort'
CONTAINER_DEF_ENV_KEY = 'environment'
CONTAINER_DEF_ENV_NAME_KEY = 'name'
CONTAINER_DEF_ENV_VALUE_KEY = 'value'
CONTAINER_DEF_HOSTPORT_KEY = 'hostPort'
CONTAINER_DEF_IMG_KEY = 'image'
CONTAINER_DEF_KEY = 'containerDefinitions'
CONTAINER_DEF_LINKS_KEY = 'links'
CONTAINER_DEF_NAME_KEY = 'name'
CONTAINER_DEF_PORT_MAPPINGS_KEY = 'portMappings'
CONTAINER_PATH_KEY = 'containerPath'
CONTAINER_DEF_PRIVILEGED_KEY = 'privileged'
LOCAL_CONTAINER_DEF_KEY = 'localContainerDefinitions'
MOUNT_POINTS = 'mountPoints'
READ_ONLY_KEY = 'readOnly'
READ_ONLY_VOLUME = ':ro'
SOURCE_VOLUME_KEY = 'sourceVolume'
VAR_APP_CURRENT = '/var/app/current/'
VOLUMES_KEY = 'volumes'
VOLUMES_NAME_KEY = 'name'
VOLUMES_HOST_KEY = 'host'
VOLUMES_SOURCE_PATH_KEY = 'sourcePath'


iter_services = six.iterkeys


def compose_dict(dockerrun, docker_proj_path, host_log, high_priority_env):
    """
    Return a docker-compose.yml representation as dict translated from the info
    provided in Dockerrun.aws.json.
    :param dockerrun: dict: dictionary representation of Dockerrun.aws.json
    :param docker_proj_path: str: path of the project directory
    :param host_log: str: path to the root host logs
    :param high_priority_env: EnvvarCollector: Contains environment variables to add and remove
    :return dict
    """

    # Service is to docker-compose.yml as container definition
    # is to Dockerrun.aws.json. We want to turn definition -> service
    services = {}
    definitions = (dockerrun.get(CONTAINER_DEF_KEY, []) +
                   dockerrun.get(LOCAL_CONTAINER_DEF_KEY, []))

    # Maps 'volume name' to local path
    # E.x.: proxy-static -> /workspace/eb-project/proxy/html
    volume_map = _get_volume_map(dockerrun.get(VOLUMES_KEY, []), docker_proj_path)

    for definition in definitions:
        _add_service(services, definition, volume_map, host_log, high_priority_env)

    return services


def _add_service(services, definition, volume_map, host_log, high_priority_env):
    realname = definition[CONTAINER_DEF_NAME_KEY]
    img = definition[CONTAINER_DEF_IMG_KEY]
    links = definition.get(CONTAINER_DEF_LINKS_KEY, [])
    command = definition.get(CONTAINER_DEF_CMD_KEY, [])
    dockerrun_port_mappings = definition.get(CONTAINER_DEF_PORT_MAPPINGS_KEY, [])
    ports = _get_port_maps(dockerrun_port_mappings)
    remote_mountpoints = definition.get(MOUNT_POINTS, [])
    definition_env = EnvvarCollector(_get_definition_envvars(definition))
    merged_envvars = definition_env.merge(high_priority_env).filtered().map
    privileged = definition.get(CONTAINER_DEF_PRIVILEGED_KEY, None)

    service = {COMPOSE_IMG_KEY: img}

    if command:
        service[COMPOSE_CMD_KEY] = command

    if ports:
        service[COMPOSE_PORTS_KEY] = ports

    if links:
        service[COMPOSE_LINKS_KEY] = ['{}:{}'.format(_fakename(n), n)
                                      for n in links]
    if merged_envvars:
        service[COMPOSE_ENV_KEY] = merged_envvars

    if privileged is not None:
        service[CONTAINER_DEF_PRIVILEGED_KEY] = privileged

    volumes = []
    for mp in remote_mountpoints:
        src_vol = mp[SOURCE_VOLUME_KEY]
        container_path = mp[CONTAINER_PATH_KEY]
        read_only = mp.get(READ_ONLY_KEY)

        if src_vol in volume_map:
            src_path = volume_map[src_vol]

        elif src_vol.startswith(AWSEB_LOGS):
            dirname = src_vol[len(AWSEB_LOGS):]
            src_path = os.path.join(host_log, dirname)

            os.makedirs(src_path)
        else:
            continue

        volume = '{}:{}'.format(src_path, container_path)
        if read_only:
            volume += READ_ONLY_VOLUME
        volumes.append(volume)

    if volumes:
        service[COMPOSE_VOLUMES_KEY] = volumes

    # alias the container names because '-' character is not allowed for service
    # names in docker-compose.yml
    services[_fakename(realname)] = service


def _get_port_maps(dockerrun_port_mappings):
    port_maps = []

    for m in dockerrun_port_mappings:
        hostport = m[CONTAINER_DEF_HOSTPORT_KEY]
        containerport = m[CONTAINER_DEF_CONTAINERPORT_KEY]
        port_map = '{}:{}'.format(hostport, containerport)
        port_maps.append(port_map)

    return port_maps


def _get_volume_map(volumes, docker_proj_path):
    vmap = {}

    for volume in volumes:
        name = volume[VOLUMES_NAME_KEY]
        source_path = volume[VOLUMES_HOST_KEY][VOLUMES_SOURCE_PATH_KEY]

        if source_path.startswith(VAR_APP_CURRENT):
            local_relative_path = source_path[len(VAR_APP_CURRENT):]
            local_source_path = os.path.join(docker_proj_path, local_relative_path)
        else:
            local_source_path = source_path

        vmap[name] = local_source_path
    return vmap


def _fakename(realname):
    # docker-compose service names must be alphanumeric
    return ''.join(c for c in realname if c.isalnum())


def _get_definition_envvars(definition):
    return {e[CONTAINER_DEF_ENV_NAME_KEY]: e[CONTAINER_DEF_ENV_VALUE_KEY] for e
            in definition.get(CONTAINER_DEF_ENV_KEY, [])}
