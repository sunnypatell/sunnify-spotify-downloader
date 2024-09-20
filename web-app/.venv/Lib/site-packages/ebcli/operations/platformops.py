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
from datetime import datetime
from shutil import copyfile, move

from semantic_version import Version

from ebcli.core.ebglobals import Constants
from ebcli.core import io, fileoperations
from ebcli.lib import elasticbeanstalk, heuristics, s3, utils
from ebcli.objects.exceptions import (
    InvalidPlatformVersionError,
    NotFoundError,
    PlatformWorkspaceEmptyError,
    ValidationError
)
from ebcli.objects.platform import PlatformVersion, PlatformBranch
from ebcli.operations import (
    logsops,
    commonops,
    platform_branch_ops,
    platform_version_ops,
    solution_stack_ops,
)
from ebcli.operations.commonops import _zip_up_project, get_app_version_s3_location
from ebcli.operations.eventsops import print_events
from ebcli.operations.tagops import tagops
from ebcli.resources.statics import (
    namespaces,
    option_names,
    platform_branch_lifecycle_states,
)
from ebcli.resources.regex import PlatformRegExpressions
from ebcli.resources.strings import strings, alerts, prompts


def detect_platform_family(families_set):
    detected_platform_family = heuristics.find_platform_family()

    if detected_platform_family and detected_platform_family in families_set:
        io.echo()
        io.echo(prompts['platform.validate'].format(
            platform=detected_platform_family))
        correct = io.get_boolean_response()

        if correct:
            return detected_platform_family


def get_custom_platform_from_customer(custom_platforms):
    selected_platform_name = prompt_customer_for_custom_platform_name(custom_platforms)

    return resolve_custom_platform_version(custom_platforms, selected_platform_name)


def get_environment_platform(app_name, env_name, want_solution_stack=False):
    env = elasticbeanstalk.get_environment(
        app_name=app_name,
        env_name=env_name,
        want_solution_stack=want_solution_stack
    )
    return env.platform


def get_platform_name_and_version_interactive():
    platforms = platform_version_ops.get_platforms(
        owner=Constants.OWNED_BY_SELF, platform_version="latest")
    platform_list = list(platforms)

    file_name = fileoperations.get_current_directory_name()
    new_platform = False
    version = None

    if len(platform_list) > 0:
        io.echo()
        io.echo('Select a platform to use')
        new_platform_option = '[ Create new Platform ]'
        platform_list.append(new_platform_option)
        try:
            default_option = platform_list.index(file_name) + 1
        except ValueError:
            default_option = len(platform_list)
        platform_name = utils.prompt_for_item_in_list(platform_list, default=default_option)
        if platform_name == new_platform_option:
            new_platform = True
        else:
            version = platforms[platform_name]

    if len(platform_list) == 0 or new_platform:
        io.echo()
        io.echo('Enter Platform Name')
        unique_name = utils.get_unique_name(file_name, platform_list)
        platform_name = io.prompt_for_unique_name(unique_name, platform_list)

    return platform_name, version


def get_version_status(version):
    platform_name = fileoperations.get_platform_name()

    if version is None:
        version = fileoperations.get_platform_version()

    if version is None:
        version = platform_version_ops.get_latest_platform_version(platform_name)
        fileoperations.update_platform_version(version)

    if version is None:
        raise InvalidPlatformVersionError(strings['exit.nosuchplatformversion'])

    arn = platform_version_ops.version_to_arn(version)

    _, platform_name, platform_version = PlatformVersion.arn_to_platform(arn)

    platform = platform_version_ops.describe_custom_platform_version(
        platform_arn=arn,
        owner=Constants.OWNED_BY_SELF,
        platform_name=platform_name,
        platform_version=platform_version,
    )

    if not platform:
        raise InvalidPlatformVersionError(strings['exit.nosuchplatformversion'])

    created = platform.get('DateCreated')
    description = platform.get('Description')
    maintainer = platform.get('Maintainer')
    status = platform.get('PlatformStatus')
    updated = platform.get('DateUpdated')
    framework_name = platform.get('FrameworkName')
    framework_version = platform.get('FrameworkVersion')
    os_name = platform.get('OperatingSystemName')
    os_version = platform.get('OperatingSystemVersion')
    language_name = platform.get('ProgrammingLanguageName')
    language_version = platform.get('ProgrammingLanguageVersion')
    supported_tiers = platform.get('SupportedTierList')

    io.echo('Platform: ', arn)
    io.echo('Name: ', platform_name)
    io.echo('Version: ', version)
    io.echo('Maintainer: ', maintainer) if maintainer else None
    io.echo('Description: ', description) if description else None
    io.echo('Framework: ', framework_name) if framework_name else None
    io.echo('Framework: ', framework_name) if framework_name else None
    io.echo('Framework Version: ', framework_version) if framework_version else None
    io.echo('Operating System: ', os_name) if os_name else None
    io.echo('Operating System Version: ', os_version) if os_version else None
    io.echo('Programming Language: ', language_name) if language_name else None
    io.echo('Programming Language Version: ', language_version) if language_version else None
    io.echo('Supported Tiers: ', supported_tiers) if supported_tiers else None
    io.echo('Status: ', status)
    io.echo('Created: ', created)
    io.echo('Updated: ', updated)


def generate_version_to_arn_mappings(custom_platforms, specified_platform_name):
    version_to_arn_mappings = {}
    for custom_platform in custom_platforms:
        custom_platform_name = PlatformVersion.get_platform_name(custom_platform)
        if custom_platform_name == specified_platform_name:
            version_to_arn_mappings[PlatformVersion.get_platform_version(custom_platform)] = custom_platform

    return version_to_arn_mappings


def get_configured_default_platform():
    return commonops.get_config_setting_from_branch_or_default('default_platform')


def get_platform_for_platform_string(platform_string):
    if PlatformVersion.is_valid_arn(platform_string):
        return PlatformVersion(platform_string).hydrate(
            elasticbeanstalk.describe_platform_version)

    if platform_branch_ops.is_platform_branch_name(platform_string):
        return platform_version_ops.get_preferred_platform_version_for_branch(platform_string)

    return solution_stack_ops.find_solution_stack_from_string(platform_string)


def group_custom_platforms_by_platform_name(custom_platforms):
    return sorted(
        set(
            [
                PlatformVersion.get_platform_name(custom_platform)
                for custom_platform in custom_platforms
            ]
        )
    )


def list_nonretired_platform_families():
    """
    Provides a list of all platform branches that contain
    branches that are not retired.
    """
    branches = platform_branch_ops.list_nonretired_platform_branches()
    families = platform_branch_ops.collect_families_from_branches(branches)

    return families


def prompt_customer_for_custom_platform_name(custom_platforms):
    custom_platform_names_to_display = group_custom_platforms_by_platform_name(custom_platforms)

    return utils.prompt_for_item_in_list(custom_platform_names_to_display)


def prompt_customer_for_custom_platform_version(version_to_arn_mappings):
    custom_platform_versions_to_display = sorted(version_to_arn_mappings.keys())
    io.echo()
    io.echo(prompts['sstack.version'])
    chosen_custom_platform_version = utils.prompt_for_item_in_list(custom_platform_versions_to_display)

    return version_to_arn_mappings[chosen_custom_platform_version]


def prompt_for_platform_family(include_custom=False):
    families = list_nonretired_platform_families()
    families.sort()

    detected_platform_family = detect_platform_family(families)

    if detected_platform_family:
        return detected_platform_family

    if include_custom:
        families.append(prompts['platformfamily.prompt.customplatform'])

    io.echo(prompts['platformfamily.prompt'])
    return utils.prompt_for_item_in_list(families, default=None)


def prompt_for_platform_branch(family):
    branches = platform_branch_ops.list_nonretired_platform_branches()
    branches = [branch for branch in branches if branch['PlatformName'] == family]
    branches = _sort_platform_branches_for_prompt(branches)

    if len(branches) == 1:
        return PlatformBranch.from_platform_branch_summary(branches[0])

    branch_display_names = [_generate_platform_branch_prompt_text(branch) for branch in branches]
    default = utils.index_of(
        branches,
        value=platform_branch_lifecycle_states.SUPPORTED,
        key=lambda b: b['LifecycleState'])

    if default == -1:
        default = None
    else:
        default += 1

    io.echo(prompts['platformbranch.prompt'])
    index = utils.prompt_for_index_in_list(branch_display_names, default=default)
    return PlatformBranch.from_platform_branch_summary(branches[index])


def prompt_for_platform():
    custom_platform_versions = platform_version_ops.list_custom_platform_versions()
    enable_custom_platform_prompt = not not custom_platform_versions

    platform_family = prompt_for_platform_family(include_custom=enable_custom_platform_prompt)

    if platform_family == prompts['platformfamily.prompt.customplatform']:
        return get_custom_platform_from_customer(custom_platform_versions)

    return prompt_for_platform_branch(platform_family)


def resolve_custom_platform_version(
        custom_platforms,
        selected_platform_name
):
    version_to_arn_mappings = generate_version_to_arn_mappings(
        custom_platforms,
        selected_platform_name
    )

    custom_platform_versions = []
    for custom_platform_version in version_to_arn_mappings.keys():
        custom_platform_versions.append(Version(custom_platform_version))

    if len(custom_platform_versions) > 1:
        chosen_custom_platform_arn = prompt_customer_for_custom_platform_version(
            version_to_arn_mappings
        )
    else:
        chosen_custom_platform_arn = custom_platforms[0]

    return PlatformVersion(chosen_custom_platform_arn)


def set_platform(platform_name, platform_version=None, verify=True):

    if verify:
        arn = _name_to_arn(platform_name)

        _, platform_name, platform_version = PlatformVersion.arn_to_platform(arn)

    fileoperations.update_platform_name(platform_name)
    fileoperations.update_platform_version(platform_version)

    io.echo(strings['platformset.version'])

    try:
        get_version_status(platform_version)
    except InvalidPlatformVersionError:
        io.echo(strings['platformset.newplatform'] % platform_name)


def set_workspace_to_latest():
    platform_name = fileoperations.get_platform_name()

    version = platform_version_ops.get_latest_platform_version(platform_name, owner=Constants.OWNED_BY_SELF)
    fileoperations.update_platform_version(version)

    if version is not None:
        io.echo(strings['platformset.version'])
        get_version_status(version)


def show_platform_events(follow, version):
    platform_name = fileoperations.get_platform_name()

    if version is None:
        version = fileoperations.get_platform_version()

        if version is None:
            raise InvalidPlatformVersionError(strings['exit.nosuchplatformversion'])

        platform = platform_version_ops.describe_custom_platform_version(
            platform_name=platform_name,
            platform_version=version,
            owner=Constants.OWNED_BY_SELF
        )

        if platform is None:
            raise InvalidPlatformVersionError(strings['exit.nosuchplatformversion'])

        arn = platform['PlatformArn']
    else:
        arn = platform_version_ops.version_to_arn(version)

    print_events(follow=follow, platform_arn=arn, app_name=None, env_name=None)


def _generate_platform_branch_prompt_text(branch):
    name = branch['BranchName']
    lifecycle_state = branch['LifecycleState']

    if lifecycle_state == platform_branch_lifecycle_states.SUPPORTED:
        return name

    return '{} ({})'.format(branch['BranchName'], branch['LifecycleState'])


def _name_to_arn(platform_name):
    arn = None
    if PlatformRegExpressions.VALID_PLATFORM_NAME_FORMAT.match(platform_name):
        arn = platform_version_ops.get_platform_arn(platform_name, "latest", owner=Constants.OWNED_BY_SELF)
    elif PlatformVersion.is_valid_arn(platform_name):
        arn = platform_name
    elif PlatformRegExpressions.VALID_PLATFORM_SHORT_FORMAT.match(platform_name):
        match = PlatformRegExpressions.VALID_PLATFORM_SHORT_FORMAT.match(platform_name)
        platform_name, platform_version = match.group(1, 2)
        arn = platform_version_ops.get_platform_arn(platform_name, platform_version, owner=Constants.OWNED_BY_SELF)

    if not arn:
        raise InvalidPlatformVersionError(strings['exit.nosuchplatform'])

    return arn


def _sort_platform_branches_for_prompt(branches):
    lifecycle_sort_values = {
        platform_branch_lifecycle_states.SUPPORTED: 3,
        platform_branch_lifecycle_states.BETA: 2,
        platform_branch_lifecycle_states.DEPRECATED: 1,
    }

    return sorted(
        branches,
        key=lambda b: (
            lifecycle_sort_values.get(b['LifecycleState'], 0),
            float(b['BranchOrder'] or 'inf')
        ),
        reverse=True,
    )
