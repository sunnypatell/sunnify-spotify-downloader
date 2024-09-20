# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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

from ebcli.core import io
from ebcli.resources.strings import prompts, strings


def get_spot_instance_types_from_customer(interactive, enable_spot):
    """
    Prompt customer to specify their desired instances types if they
    selected enabled spot requests from the interactive flow.

    :param interactive: True/False depending on whether operating in the interactive mode or not
    :param enable_spot: False/True depending on user has set --enable-spot to true or false
    :return: list of comma separated instance types
    """
    if not interactive or not enable_spot:
        return
    io.echo(prompts['spot.instance_types_prompt'])
    return prompt_for_instance_types()


def get_spot_request_from_customer(interactive):
    """
    Prompt customer to select if they would like to enable spot requests if
    operating in the interactive mode.

    Selection defaults to 'No' when provided with blank input.
    :param interactive: True/False depending on whether operating in the interactive mode or not
    :return: selected value for if to enable spot requests or not: True/False
    """
    if not interactive:
        return
    io.echo()
    return io.get_boolean_response(
        text=prompts['spot.enable_spot_prompt'],
        default=False)


def prompt_for_instance_types():
    """
    Method accepts the user's choice of instance types to be used for spot fleet request

    :return: user's choice of whether the spot request should be enabled
    """
    instance_types = io.prompt(strings['spot.instance_type_defaults_notice'])
    io.echo()
    return instance_types
