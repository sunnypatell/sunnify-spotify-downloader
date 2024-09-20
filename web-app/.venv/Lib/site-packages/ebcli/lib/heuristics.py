# Copyright 2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
from ebcli.core.fileoperations import program_is_installed
import glob
import os


def find_platform_family():
    if smells_of_docker() or smells_of_multi_container_docker():
        return 'Docker'
    if smells_of_python():
        return 'Python'
    if smells_of_ruby():
        return 'Ruby'
    if smells_of_php():
        return 'PHP'
    if smells_of_node_js():
        return 'Node.js'
    if smells_of_iis():
        return '.NET on Windows Server'
    if smells_of_tomcat():
        return 'Tomcat'

    # If there is just an index.html, PHP will work
    if has_index_html():
        return 'PHP'

    return None


def smells_of_multi_container_docker():
    dockerrun_file = dockerrun.get_dockerrun('Dockerrun.aws.json')
    if dockerrun_file and dockerrun_file.get('AWSEBDockerrunVersion') in (2, '2'):
        return True


def smells_of_docker():
    """
    True if the current directory has a docker file
    'Dockerfile' or 'Dockerrun.aws.json' should exist in the root directory
    """
    return _contains_file_types('Dockerfile', 'Dockerrun.aws.json')


def smells_of_python():
    """
    True if directory has a .py file or a requirements.txt file
    """
    return _contains_file_types('*.py', 'requirements.txt')


def smells_of_ruby():
    """
    True if directory has a .rb file or a Gemfile
    """
    return _contains_file_types('*.rb', 'Gemfile')


def smells_of_php():
    """
    True if directory has a .php file
    """
    return _contains_file_types('*.php')


def has_index_html():
    """
    True if directory contains index.html
    """
    return _contains_file_types('index.html')


def directory_is_empty():
    """
    Directory contains no files or folders (ignore dot-files)
    """
    lst = [f for f in os.listdir('./') if not f.startswith('.')]
    if len(lst) < 1:
        return True
    else:
        return False


def smells_of_node_js():
    """
    JS files are too common in web apps, so instead we just look for the package.json file
    True is directory has a package.json file
    """
    return _contains_file_types('package.json')


def smells_of_iis():
    """
    True if directory contains a systemInfo.xml
    """
    return _contains_file_types('systemInfo.xml')


def smells_of_tomcat():
    """
    True if directory has a jsp file or a WEB-INF directory
    """

    if has_tomcat_war_file():
        return True
    return _contains_file_types('*.jsp', 'WEB-INF')


def has_tomcat_war_file():
    """
    True if there is a war file located at ./build/lib/*.war
    """
    return _contains_file_types('build/libs/*.war')


def has_platform_definition_file():
    """
    True if there is a file called 'platform.yaml' in the workspace root
    """
    return _contains_file_types('platform.yaml')


def is_boot2docker_installed():
    return program_is_installed('boot2docker')


def _get_file_list(*args):
    lst = []
    for a in args:
        lst += glob.glob(a)
    return lst


def _contains_file_types(*args):
    lst = _get_file_list(*args)
    if lst:
        return True
    else:
        return False
