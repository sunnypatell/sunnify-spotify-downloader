# Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
from ebcli.core import fileoperations, io
from ebcli.lib import aws, codecommit
from ebcli.objects.exceptions import CommandError, ValidationError
from ebcli.objects.sourcecontrol import SourceControl

from ebcli.operations import commonops

LOG = minimal_logger(__name__)


def git_management_enabled():
    return get_default_branch() and get_default_repository()


def get_config_setting_from_current_environment_or_default(key_name):
    setting = get_setting_from_current_environment(key_name)

    return setting or fileoperations.get_config_setting('global', key_name)


def write_setting_to_current_environment_or_default(keyname, value):
    env_name = commonops.get_current_branch_environment()
    if env_name is None:
        fileoperations.write_config_setting('global', keyname, value)
    else:
        fileoperations.write_config_setting('environment-defaults', env_name, {keyname: value})


def get_setting_from_current_environment(keyname):
    env_name = commonops.get_current_branch_environment()
    env_dict = fileoperations.get_config_setting('environment-defaults', env_name)

    if env_dict:
        return env_dict.get(keyname)


def set_branch_default_for_global(branch_name):
    fileoperations.write_config_setting('global', 'branch', branch_name)


def set_repo_default_for_global(repo_name):
    fileoperations.write_config_setting('global', 'repository', repo_name)


def set_branch_default_for_current_environment(branch_name):
    write_setting_to_current_environment_or_default('branch', branch_name)


def set_repo_default_for_current_environment(repo_name):
    write_setting_to_current_environment_or_default('repository', repo_name)


def get_branch_default_for_current_environment():
    return get_config_setting_from_current_environment_or_default('branch')


def get_repo_default_for_current_environment():
    return get_config_setting_from_current_environment_or_default('repository')


def get_default_branch():
    result = get_branch_default_for_current_environment()
    if result:
        return result
    LOG.debug('Branch not found')


def get_default_repository():
    result = get_repo_default_for_current_environment()
    if result:
        return result
    LOG.debug('Repository not found')


def initialize_codecommit():
    source_control = SourceControl.get_source_control()
    try:
        source_control_setup = source_control.is_setup()
    except CommandError:
        source_control_setup = False

    if not source_control_setup:
        io.log_error("Cannot setup CodeCommit because there is no Source Control setup")
        return

    if codecommit.region_supported():
        codecommit_setup = print_current_codecommit_settings()
        if codecommit_setup:
            should_continue = io.get_boolean_response(
                text='Do you wish to continue?',
                default=True)
            if not should_continue:
                return

        source_control.setup_codecommit_cred_config()

        from ebcli.controllers import initialize
        repository = initialize.get_repository_interactive()
        branch = initialize.get_branch_interactive(repository)

        set_repo_default_for_current_environment(repository)
        set_branch_default_for_current_environment(branch)
    else:
        io.log_error("The region {0} is not supported by CodeCommit".format(aws.get_region_name()))


def disable_codecommit():
    LOG.debug("Denied option to use CodeCommit removing default values")
    set_repo_default_for_current_environment(None)
    set_branch_default_for_current_environment(None)
    fileoperations.write_config_setting('global', 'repository', None)
    fileoperations.write_config_setting('global', 'branch', None)
    LOG.debug("Disabled CodeCommit for use with EB CLI")


def print_current_codecommit_settings():
    default_branch = get_default_branch()
    default_repo = get_default_repository()
    codecommit_setup = default_repo or default_branch
    if codecommit_setup:
        io.echo("Current CodeCommit setup:")
        io.echo("  Repository: " + str(default_repo))
        io.echo("  Branch: " + str(default_branch))
    return codecommit_setup
