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
from botocore.compat import six

from ebcli.containers.envvarcollector import EnvvarCollector
from ebcli.containers.pathconfig import PathConfig
from ebcli.core import fileoperations, io
from ebcli.lib import utils
from ebcli.operations import commonops, envvarops
from ebcli.resources.strings import strings
cPickle = six.moves.cPickle


class LocalState(object):
    """
    Class used for storing local state in a file.
    """

    def __init__(self, envvarcollector):
        self.envvarcollector = envvarcollector

    def dumps(self, path):
        fileoperations.write_to_data_file(data=cPickle.dumps(self, protocol=2),
                                          location=path)

    @classmethod
    def loads(cls, path):
        try:
            data = fileoperations.read_from_data_file(path)
            return cPickle.loads(data)
        except IOError:
            return cls(EnvvarCollector())

    @classmethod
    def get_envvarcollector(cls, path):
        return cls.loads(path).envvarcollector

    @classmethod
    def save_envvarcollector(cls, envvarcollector, path):
        localstate = cls.loads(path)
        localstate.envvarcollector = envvarcollector
        localstate.dumps(path)


def print_container_details(cnt_viewmodel):
    """
    Dispalays information about all the services of container.
    :param cnt_viewmodel: ContainerViewModel: contains view info about container
    :return: None
    """

    io.echo('Platform:', cnt_viewmodel.soln_stk)

    for i, service_info in enumerate(cnt_viewmodel.service_infos):
        _print_service_details(service_info)

        if i != len(cnt_viewmodel.service_infos) - 1:
            io.echo()


def open_webpage(cnt_viewmodel):
    """
    Open the webpage at container ip and host port we exposed when we ran this container.
    Raise error if container not running and prompt user to choose host port if multiple
    host ports exposed under this container.
    :param cnt_viewmodel: ContainerViewModel: contains view info about container
    :return: None
    """

    if not cnt_viewmodel.is_running():
        raise RuntimeError(strings['local.open.nocontainer'])

    # Get container id, exposed host port pairs
    cid_hostports = cnt_viewmodel.get_cid_hostport_pairs()
    num_exposed_hostports = cnt_viewmodel.num_exposed_hostports()

    if num_exposed_hostports == 1:
        _, host_port = cid_hostports[0]

    elif num_exposed_hostports > 1:
        io.echo()
        io.echo('Select a container applcation to open')
        io.echo()

        disp = ['Container {}, host port {}'.format(cid, p) for cid, p in cid_hostports]
        ind = utils.prompt_for_index_in_list(disp)

        _, host_port = cid_hostports[ind]

    else:
        raise RuntimeError(strings['local.open.noexposedport'])

    url = '{}:{}'.format(cnt_viewmodel.ip, host_port)
    commonops.open_webpage_in_browser(url)


def _print_service_details(service_info):
    exposed_host_ports_str = ', '.join(service_info.hostports) or None
    urls = ', '.join(service_info.get_urls()) or None

    io.echo('Container name:', service_info.cid)
    io.echo('Container ip:', service_info.ip)
    io.echo('Container running:', service_info.is_running)
    io.echo('Exposed host port(s):', exposed_host_ports_str)
    io.echo('Full local URL(s):', urls)


def get_and_print_environment_vars(pathconfig=PathConfig):
    envvars_map = LocalState.get_envvarcollector(pathconfig.local_state_path()).map
    envvarops.print_environment_vars(envvars_map)


def setenv(var_list, pathconfig=PathConfig):
    setenv_env = LocalState.get_envvarcollector(pathconfig.local_state_path())
    opt_env = EnvvarCollector.from_list(var_list)
    merged_env = setenv_env.merge(opt_env)

    LocalState.save_envvarcollector(merged_env.filtered(),
                                    pathconfig.local_state_path())
