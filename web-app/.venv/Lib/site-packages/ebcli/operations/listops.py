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

from ebcli.lib import aws, utils, elasticbeanstalk
from ebcli.core import io
from ebcli.operations import commonops


def list_env_names(app_name, verbose, all_apps):
    region = aws.get_region_name()

    if verbose:
        io.echo('Region:', region)

    if all_apps:
        for app_name in elasticbeanstalk.get_application_names():
            list_env_names_for_app(app_name, verbose)
    else:
        list_env_names_for_app(app_name, verbose)


def list_env_names_for_app(app_name, verbose):
    current_env = commonops.get_current_branch_environment()
    env_names = elasticbeanstalk.get_environment_names(app_name)
    env_names.sort()

    if verbose:
        io.echo('Application:', app_name)
        io.echo('    Environments:', len(env_names))
        for e in env_names:
            instances = commonops.get_instance_ids(e)
            if e == current_env:
                e = '* ' + e

            io.echo('       ', e, ':', instances)

    else:
        for i in range(0, len(env_names)):
            if env_names[i] == current_env:
                env_names[i] = '* ' + env_names[i]

        if len(env_names) <= 10:
            for e in env_names:
                io.echo(e)
        else:
            utils.print_list_in_columns(env_names)
