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
import re
import sys
from semantic_version import Version

from cement.utils.misc import minimal_logger

from ebcli.containers import commands
from ebcli.core import fileoperations
from ebcli.lib import heuristics, utils
from ebcli.resources.strings import strings
from ebcli.objects.exceptions import CommandError


LOG = minimal_logger(__name__)
SUPPORTED_DOCKER_V = '1.6.0'
SUPPORTED_BOOT2DOCKER_V = '1.6.0'
LOCALHOST = '127.0.0.1'
EXPORT = 'export'
BOOT2DOCKER_RUNNING = 'running'
DOCKER_HOST = 'DOCKER_HOST'
DOCKER_CERT_PATH = 'DOCKER_CERT_PATH'
DOCKER_TLS_VERIFY = 'DOCKER_TLS_VERIFY'


def container_ip():
    """
    Return the ip address that local containers are or will be running on.
    :return str
    """
    return LOCALHOST


def is_windows():
    return 'win32' in str(sys.platform).lower()


def remove_leading_zeros_from_version(version_string):
    # regex explaination: remove zeroes if both:
    # 1. the start of string (major version) or following a '.'
    # 2. followed by some other digit
    return re.sub(r'((?<=\.)|^)[0]+(?=\d+)', r'', version_string)
