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
from datetime import datetime
import os

from ebcli.containers import dockerrun
from ebcli.core import fileoperations, io
from ebcli.lib import utils
from ebcli.resources.strings import strings


HOST_LOGS_DIRNAME = 'local'
LATEST_LOGS_DIRNAME = 'latest'
HOST_LOG_FILENAME_PATTERN = "%y%m%d_%H%M%S%f"


def get_log_volume_map(root_log_dir, dockerrun_dict):
    """
    Return host log path to container log path mapping if Logging is provided
    in the dockerrun, and otherwise return empty dict.
    :param root_log_dir: str: the root local logs directory
    :param dockerrun_dict: dict: Dockerrun.aws.json as dict
    :return: dict
    """

    if not dockerrun_dict:
        return {}
    host_log = new_host_log_path(root_log_dir)
    container_log = dockerrun.get_logdir(dockerrun_dict)
    return {host_log: container_log} if container_log else {}


def new_host_log_path(root_log_dir):
    """
    Return the host log path that will be used to make the new local logs dir.
    Format is like .elasticbeanstalk/logs/local/150318_132014410947/
    :param root_log_dir: str: the root local logs directory
    :return: str
    """

    return os.path.join(root_log_dir,
                        datetime.now().strftime(HOST_LOG_FILENAME_PATTERN))


def make_logdirs(root_log_dir, new_local_dir):
    """
    Create new_local_dir and make a symlink 'latest' that points to
    that new_local_dir inside root_log_dir.
    :param root_log_dir: str: path to root local logs directory
    :param new_local_dir: str: path to new host log
    :return: None
    """

    if not os.path.exists(root_log_dir):
        os.makedirs(root_log_dir)
        fileoperations.set_all_unrestricted_permissions(root_log_dir)

    # Remove write and execute permissions from GRP and OTH from
    # the enclosing directory to prevent outside access.
    enclosing_directory = os.path.dirname(root_log_dir)
    fileoperations.remove_execute_access_from_group_and_other_users(enclosing_directory)

    os.makedirs(new_local_dir)
    fileoperations.set_all_unrestricted_permissions(new_local_dir)
    _symlink_new_log_dir(root_log_dir, new_local_dir)


def print_logs():
    """
    Print the path to root local logs directory, the most recently written
    local logs directory and the path to 'latest' symlink.
    :return: None
    """

    root_log = fileoperations.get_logs_location(HOST_LOGS_DIRNAME)
    last_local_logs = _get_last_local_logs(root_log)
    timestamp = os.path.getmtime(last_local_logs) if last_local_logs else None

    _print_logs(root_log, last_local_logs, timestamp)


def _print_logs(root_log, last_local_logs=None, timestamp=None):
    if os.path.isdir(root_log):
        io.echo(strings['local.logs.location'].format(location=root_log))

    if last_local_logs and not fileoperations.directory_empty(last_local_logs):
        prettydate = utils.prettydate(timestamp)
        msg = strings['local.logs.lastlocation'].format(prettydate=prettydate,
                                                        location=last_local_logs)
        io.echo(msg)
        io.echo(strings['local.logs.symlink'].format(symlink=_symlink_path(root_log)))
    else:
        io.echo(strings['local.logs.nologs'])


def _get_last_local_logs(root_log):
    if os.path.isdir(root_log):
        all_log_paths = [os.path.join(root_log, n) for n in os.listdir(root_log)]
        non_sym_paths = [p for p in all_log_paths if not os.path.islink(p)]
        if non_sym_paths:
            return utils.last_modified_file(non_sym_paths)
    return None


def _symlink_new_log_dir(root_log_dir, new_local_dir):
    latest_symlink_path = _symlink_path(root_log_dir)

    try:
        os.unlink(latest_symlink_path)
    except OSError:
        pass
    try:
        os.symlink(new_local_dir, latest_symlink_path)
    except OSError:
        pass


def _symlink_path(root_log_dir):
    return os.path.join(root_log_dir, LATEST_LOGS_DIRNAME)
