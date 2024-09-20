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

from ebcli.lib import elasticbeanstalk
from ebcli.core import io, fileoperations
from ebcli.objects.environmentsettings import EnvironmentSettings
from ebcli.objects.exceptions import InvalidSyntaxError
from ebcli.resources.strings import prompts, strings
from ebcli.operations import commonops

from urllib.parse import urlparse

from json import dumps, loads, JSONDecodeError

from yaml import safe_dump, safe_load
from yaml.parser import ParserError
from yaml.scanner import ScannerError

import os


def display_environment_configuration(app_name, env_name, output_format="yaml"):
    api_model = elasticbeanstalk.describe_configuration_settings(
        app_name, env_name
    )

    env_settings = EnvironmentSettings(api_model)
    usr_model = env_settings.convert_api_to_usr_model()

    if output_format == "yaml":
        io.echo(safe_dump(usr_model, default_flow_style=False, line_break=os.linesep))
    elif output_format == "json":
        io.echo(dumps(usr_model, indent=4, sort_keys=True, default=str))


def modify_environment_configuration(env_name, usr_modification, nohang, timeout=None):

    if usr_modification.startswith("file:/"):
        parse = urlparse(usr_modification)
        file_path = os.path.abspath(os.path.join(parse.netloc, parse.path))
        usr_modification = fileoperations.get_environment_from_file(env_name, path=file_path)
    else:
        try:
            usr_modification = safe_load(usr_modification)
        except (ScannerError, ParserError):
            try:
                usr_modification = loads(usr_modification)
            except JSONDecodeError:
                raise InvalidSyntaxError('The environment configuration contains invalid syntax. Make sure your input '
                                         'matches one of the supported formats: JSON, YAML')
    changes = []
    if "OptionSettings" in usr_modification:
        changes = EnvironmentSettings.convert_usr_model_to_api(usr_modification["OptionSettings"])
    remove = []
    if "OptionsToRemove" in usr_modification:
        remove = EnvironmentSettings.convert_usr_model_to_api(usr_modification["OptionsToRemove"])
    platform_arn = None
    if "PlatformArn" in usr_modification:
        platform_arn = usr_modification["PlatformArn"]

    if changes == [] and remove == [] and platform_arn is None:
        io.log_warning('No changes made. Exiting.')
        return

    if fileoperations.env_yaml_exists():
        io.echo(strings['config.envyamlexists'])

    commonops.update_environment(env_name, changes, nohang,
                                 remove=remove, timeout=timeout,
                                 solution_stack_name=None,
                                 platform_arn=platform_arn)


def update_environment_configuration(app_name, env_name, nohang,
                                     timeout=None):
    api_model = elasticbeanstalk.describe_configuration_settings(
        app_name, env_name
    )

    env_settings = EnvironmentSettings(api_model)
    usr_model = env_settings.convert_api_to_usr_model()

    file_location = fileoperations.save_env_file(usr_model)
    fileoperations.open_file_for_editing(file_location)

    platform_arn = None

    try:
        usr_model = fileoperations.get_environment_from_file(env_name)
        changes, remove = env_settings.collect_changes(usr_model)
        if api_model['PlatformArn'] != usr_model['PlatformArn']:
            platform_arn = usr_model['PlatformArn']
        fileoperations.delete_env_file(env_name)
    except InvalidSyntaxError:
        io.log_error(prompts['update.invalidsyntax'])
        return

    if not changes and not remove and not platform_arn:
        io.log_warning('No changes made. Exiting.')
        return

    if fileoperations.env_yaml_exists():
        io.echo(strings['config.envyamlexists'])

    commonops.update_environment(env_name, changes, nohang,
                                 remove=remove, timeout=timeout,
                                 solution_stack_name=None,
                                 platform_arn=platform_arn)
