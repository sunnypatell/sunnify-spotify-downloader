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

from ebcli.containers import commands, compat
from ebcli.containers.abstractcontainer import AbstractContainer
from ebcli.lib import utils


class ContainerViewModel(object):
    """
    Container data used to display information.
    """

    def __init__(self, soln_stk, ip, service_infos):
        """
        :param soln_stk: SolutionStack: environment's solution stack
        :param ip: str: container ip
        :param service_infos: list: services running under this container
        """

        self.soln_stk = soln_stk
        self.ip = ip
        self.service_infos = service_infos

    def get_cids(self):
        return six.iterkeys(self.get_cid_hostports_map())

    def get_cid_hostports_map(self):
        return {s.cid: s.hostports for s in self.service_infos}

    def get_cid_hostport_pairs(self):
        return utils.flatten([[(cid, p) for p in hostports]
                             for cid, hostports
                             in six.iteritems(self.get_cid_hostports_map())])

    def is_running(self):
        return any(s.is_running for s in self.service_infos)

    def num_exposed_hostports(self):
        return sum(s.num_exposed_hostports() for s in self.service_infos)

    @classmethod
    def from_container(cls, container):
        """
        Converts a container to ContainerViewModel.
        :param container: Container/MultiContainer: container being converted
        :return ContainerViewModel
        """

        soln_stk = container.soln_stk
        cids = _get_cids(container)
        container.is_running()
        ip = compat.container_ip()
        services = [ServiceInfo(cid=cid,
                                ip=ip,
                                is_running=commands.is_running(cid),
                                hostports=commands.get_exposed_hostports(cid))
                    for cid in cids]

        return cls(soln_stk, ip, services)


class ServiceInfo(object):
    """
    A service running under a Container or MultiContainer
    """

    def __init__(self, cid, ip, is_running, hostports):
        """
        :param cid: str: the container name/id
        :param ip: str: the ip the service is running
        :param is_running: bool: whether the service is running
        :param hostports: list: all host ports that are exposed
        """

        self.cid = cid
        self.is_running = is_running
        self.ip = ip
        self.hostports = hostports

    def get_urls(self):
        return ['{}:{}'.format(self.ip, hp) for hp in self.hostports]

    def num_exposed_hostports(self):
        return len(self.hostports)


def _get_cids(c):
    return [c.get_name()] if isinstance(c, AbstractContainer) else c.list_services()
