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
import re

from six import iteritems

from ebcli.core import io
from ebcli.lib import elasticbeanstalk, utils
from ebcli.objects.exceptions import InvalidSyntaxError
from ebcli.operations import commonops
from ebcli.resources.strings import strings


def get_and_print_environment_vars(app_name, env_name):
    settings = elasticbeanstalk.describe_configuration_settings(
        app_name, env_name
    )['OptionSettings']
    namespace = 'aws:elasticbeanstalk:application:environment'
    environment_variables = {
        setting['OptionName']: setting['Value'] for setting in settings if setting["Namespace"] == namespace
    }
    print_environment_vars(environment_variables)


def __strip_leading_and_trailing_double_quotes(string):
    if len(string) > 0 and string[0] == '"':
        string = string[1:]

    if len(string) > 0 and string[-1] == '"':
        string = string[:-1]

    return string


def sanitize_environment_variables_from_customer_input(environment_variables_input):
    """
    Returns a list of the sanitized key-value pairs in the `environment_variables_input` string,
    where pairs are comma-separated, by removing leading and trailing spaces and double quotes
    from and the key and value of each pair.

    :param environment_variables_input: a string of the form "KEY_1=VALUE_1,...,KYE_N=VALUE_N"
    :return: a list of the sanitized key-value pairs
    """
    if not environment_variables_input:
        return []

    key_value_pairs = environment_variables_input.split(',')

    environment_variables = []
    for key_value_pair in key_value_pairs:
        if '=' not in key_value_pair:
            raise InvalidSyntaxError(strings['setenv.invalidformat'])

        environment_variable, value = key_value_pair.split('=', 1)
        environment_variable = environment_variable.strip().strip('"')

        value = value.strip()
        value = __strip_leading_and_trailing_double_quotes(value)

        if not environment_variable:
            raise InvalidSyntaxError(strings['setenv.invalidformat'])

        environment_variables.append('='.join([environment_variable, value]))

    return environment_variables


def create_environment_variables_list(environment_variables, as_option_settings=True):
    """
    Returns a pair of environment variables to add and remove from a list of
    sanitized environment variables.

    If `as_option_settings` is set to `True`, the list of environment variables
    to add is transformed into option settings in the
    'aws:elasticbeanstalk:application:environment' namespace.

    :param environment_variables: a list of the sanitized environment variables
                                  specified in the format KEY_i=VALUE_i
    :param as_option_settings: boolean indicating whether to transform
                               `environment_variables` into option settings
    :return: a pair of environment variables to add and remove in the format
             dictated by `as_option_settings`
    """
    namespace = 'aws:elasticbeanstalk:application:environment'

    options = dict()
    options_to_remove = set()
    for environment_variable_string in environment_variables:
        if (
            not re.match(r'^[\w\\_.:/+@-][^="]*=.*$', environment_variable_string)
            or '=' not in environment_variable_string
        ):
            raise InvalidSyntaxError(strings['setenv.invalidformat'])

        environment_variable, value = environment_variable_string.split('=', 1)

        if value:
            options[environment_variable] = value
        else:
            options_to_remove.add(environment_variable)

    if as_option_settings:
        option_dict = options
        options = list()
        remove_list = options_to_remove
        options_to_remove = list()
        for environment_variable, value in iteritems(option_dict):
            options.append(
                dict(
                    Namespace=namespace,
                    OptionName=environment_variable,
                    Value=value
                )
            )

        for environment_variable in remove_list:
            options_to_remove.append(
                dict(
                    Namespace=namespace,
                    OptionName=environment_variable
                )
            )

    return options, options_to_remove


def print_environment_vars(environment_variables):
    if environment_variables:
        io.echo(' Environment Variables:')

    for environment_variable, value in iteritems(environment_variables):
        environment_variable, value = utils.mask_vars(environment_variable, value)
        io.echo('    ', environment_variable, '=', value)


def setenv(app_name, env_name, var_list, timeout=None):

    options, options_to_remove = create_environment_variables_list(var_list)

    request_id = elasticbeanstalk.update_environment(env_name, options,
                                                     remove=options_to_remove)

    if timeout is None:
        timeout = 4

    commonops.wait_for_success_events(request_id,
                                      timeout_in_minutes=timeout,
                                      can_abort=True)
