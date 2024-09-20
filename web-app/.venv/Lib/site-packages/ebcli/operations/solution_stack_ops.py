# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
from cement.utils.misc import minimal_logger

from ebcli.core import io
from ebcli.lib import elasticbeanstalk, heuristics, utils
from ebcli.objects.exceptions import NotFoundError
from ebcli.objects.platform import PlatformVersion
from ebcli.objects.solutionstack import SolutionStack
from ebcli.operations import commonops, platform_version_ops
from ebcli.resources.strings import alerts, prompts

CUSTOM_PLATFORM_OPTION = 'Custom Platform'

LOG = minimal_logger(__name__)


def get_default_solution_stack():
    return commonops.get_config_setting_from_branch_or_default('default_platform')


def get_all_solution_stacks():
    return elasticbeanstalk.get_available_solution_stacks()


def find_solution_stack_from_string(solution_string, find_newer=False):
    """
    Method returns a SolutionStack object representing the given `solution_string`.

    If the `solution_string` matches ARNs and complete names of solution stacks, the exact
    match is returned. In the event when there are multiple matches, the latest version is
    returned.

    :param solution_string: A string in one of the following (case-insensitive) forms:
        - PlatformArn:
            - EB-managed: 'arn:aws:elasticbeanstalk:us-west-2::platform/Multi-container
                            Docker running on 64bit Amazon Linux/2.8.0'
            - Custom: arn:aws:elasticbeanstalk:us-west-2:123412341234:platform/
                        custom_platform/1.0.0
        - complete name: '64bit Amazon Linux 2017.03 v2.7.5 running Multi-container Docker
                            17.03.2-ce (Generic)'
        - shorthand: 'Multi-container Docker 17.03.2-ce (Generic)'
        - language name: 'Multi-container Docker'
        - pythonified shorthand: 'multi-container-docker-17.03.2-ce-(generic)'
    :param find_newer: If solution_string is a complete name or a PlatformArn that uniquely
                        matches a solution stack or platform, find the newest version of the
                        solution stack.

    :return: A SolutionStack object representing the latest version of the `solution_string`.
            In case of a custom platform, the return value is a PlatformVersion object.
    """

    # Compare input with PlatformARNs
    match = None
    if PlatformVersion.is_eb_managed_platform_arn(solution_string):
        if find_newer:
            match = platform_version_ops.get_latest_eb_managed_platform(solution_string)
        else:
            match = platform_arn_to_solution_stack(solution_string)
    elif PlatformVersion.is_custom_platform_arn(solution_string):
        if find_newer:
            match = platform_version_ops.get_latest_custom_platform_version(solution_string)
        else:
            match = platform_version_ops.find_custom_platform_version_from_string(solution_string)

    # Compare input with complete SolutionStack name and retrieve latest SolutionStack
    # in the series if `find_newer` is set to True
    if not match:
        available_solution_stacks = elasticbeanstalk.get_available_solution_stacks()

        match = SolutionStack.match_with_complete_solution_string(available_solution_stacks, solution_string)
        if match and find_newer:
            language_name = SolutionStack(solution_string).language_name
            match = SolutionStack.match_with_solution_string_language_name(
                available_solution_stacks,
                language_name
            )

    # Compare input with other forms
    for solution_string_matcher in [
        SolutionStack.match_with_solution_string_shorthand,
        SolutionStack.match_with_solution_string_language_name,
        SolutionStack.match_with_pythonified_solution_string,
    ]:
        if not match:
            match = solution_string_matcher(available_solution_stacks, solution_string)

    # Compare input with custom platform names
    if not match:
        match = platform_version_ops.find_custom_platform_version_from_string(solution_string)

    if not match:
        raise NotFoundError(alerts['platform.invalidstring'].format(solution_string))

    return match


def platform_arn_to_solution_stack(platform_arn):
    """
    Method determines the EB-managed solution stack represented by a PlatformArn

    :param platform_arn: PlatformArn of a solution stack
    :return: SolutionStack representing the PlatformArn if it an EB-managed platform, otherwise None
    """
    if not PlatformVersion.is_eb_managed_platform_arn(platform_arn):
        return

    platform_description = elasticbeanstalk.describe_platform_version(platform_arn)

    return SolutionStack(platform_description['SolutionStackName'])


def prompt_for_solution_stack_version(matching_language_versions):
    """
    Method prompts customer to pick a solution stack version, given a set of platform
    versions of a language

    :param matching_language_versions: A list of platform versions of a language to allow
            the customer to choose from.

                e.g. Given Platform, Ruby, the following options will be presented
                    1. Ruby 2.4 (Passenger standalone)
                    2. Ruby 2.4 (Puma)
                    3. ...

    :return: A string representing te platform version the customer would like to use.
    """
    io.echo()
    io.echo(prompts['sstack.version'])
    language_versions_to_display = [version['PlatformShorthand'] for version in matching_language_versions]

    return utils.prompt_for_item_in_list(language_versions_to_display)


def resolve_language_version(chosen_language_name, solution_stacks):
    """
    Method determines the list of platform versions matching a platform name and
    returns a SolutionStack object representing the platform version the customer
    would like to use.

    :param chosen_language_name: Name of language the customer would like to use
    :param solution_stacks: A list of SolutionStack objects to assemble the list
    of related platform versions from.

    :return: A SolutionStack object representing customer's choice of language
    version.
    """
    matching_language_versions = SolutionStack.group_solution_stacks_by_platform_shorthand(
        solution_stacks,
        language_name=chosen_language_name
    )

    if len(matching_language_versions) > 1:
        version = prompt_for_solution_stack_version(matching_language_versions)
    else:
        version = matching_language_versions[0]['PlatformShorthand']

    for language_version in matching_language_versions:
        if language_version['PlatformShorthand'] == version:
            return language_version['SolutionStack']
