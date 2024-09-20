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
import os.path

from cement.utils.misc import minimal_logger

from ebcli.core import fileoperations, io
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.core.ebglobals import Constants
from ebcli.lib import utils, elasticbeanstalk, codecommit, aws
from ebcli.objects.sourcecontrol import SourceControl
from ebcli.objects.platform import PlatformBranch, PlatformVersion
from ebcli.objects.solutionstack import SolutionStack
from ebcli.objects import solutionstack
from ebcli.operations import statusops

from ebcli.objects.exceptions import (
    InvalidProfileError,
    NoRegionError,
    NotInitializedError,
    ServiceError,
    ValidationError,
)
from ebcli.operations import (
    commonops,
    gitops,
    initializeops,
    platformops,
    solution_stack_ops,
    sshops,
)
from ebcli.operations.tagops import tagops
from ebcli.resources.strings import strings, flag_text, prompts, alerts

LOG = minimal_logger(__name__)


class InitController(AbstractBaseController):
    class Meta:
        label = 'init'
        description = strings['init.info']
        arguments = [
            (['application_name'], dict(
                help=flag_text['init.name'], nargs='?', default=[])),
            (['-m', '--modules'], dict(help=flag_text['init.module'], nargs='*')),
            (['-p', '--platform'], dict(help=flag_text['init.platform'])),
            (['-k', '--keyname'], dict(help=flag_text['init.keyname'])),
            (['-i', '--interactive'], dict(
                action='store_true', help=flag_text['init.interactive'])),
            (['--source'], dict(help=flag_text['init.source'])),
            (['--tags'], dict(help=flag_text['create.tags']))
        ]
        usage = 'eb init <application_name> [options ...]'
        epilog = strings['init.epilog']

    def do_command(self):
        commonops.raise_if_inside_platform_workspace()

        interactive = self.app.pargs.interactive
        region_name = self.app.pargs.region
        noverify = self.app.pargs.no_verify_ssl
        keyname = self.app.pargs.keyname
        profile = self.app.pargs.profile
        platform = self.app.pargs.platform
        source = self.app.pargs.source
        app_name = self.app.pargs.application_name
        modules = self.app.pargs.modules
        force_non_interactive = _customer_is_avoiding_interactive_flow(
            self.app.pargs)
        tags = self.app.pargs.tags

        # The user specifies directories to initialize
        if modules and len(modules) > 0:
            self.initialize_multiple_directories(
                modules,
                app_name,
                region_name,
                interactive,
                force_non_interactive,
                keyname,
                profile,
                noverify,
                platform
            )
            return

        fileoperations.touch_config_folder()
        region_name = commonops.set_region_for_application(interactive, region_name, force_non_interactive, platform)
        commonops.set_up_credentials(profile, region_name, interactive)
        app_name = get_app_name(app_name, interactive, force_non_interactive)
        default_env = set_default_env(interactive, force_non_interactive)
        tags = tagops.get_and_validate_tags(tags)

        platform_arn, keyname_of_existing_application = create_app_or_use_existing_one(app_name, default_env, tags)
        platform = _determine_platform(
            customer_provided_platform=platform,
            existing_app_platform=platform_arn,
            force_interactive=interactive and not force_non_interactive)

        handle_buildspec_image(platform, force_non_interactive)

        prompt_codecommit = should_prompt_customer_to_opt_into_codecommit(
            force_non_interactive,
            region_name,
            source
        )
        repository, branch = None, None
        if prompt_codecommit:
            repository, branch = configure_codecommit(source)
        initializeops.setup(app_name, region_name, platform, dir_path=None, repository=repository, branch=branch)
        configure_keyname(platform, keyname, keyname_of_existing_application, interactive, force_non_interactive)
        fileoperations.write_config_setting('global', 'include_git_submodules', True)
        if noverify:
            fileoperations.write_config_setting('global', 'no-verify-ssl', True)

    def initialize_multiple_directories(
            self,
            modules,
            app_name,
            region,
            interactive,
            force_non_interactive,
            keyname,
            profile,
            noverify,
            platform
    ):
        application_created = False
        cwd = os.getcwd()
        for module in modules:
            if os.path.exists(module) and os.path.isdir(module):
                os.chdir(module)
                fileoperations.touch_config_folder()

                # Region should be set once for all modules
                region = region or commonops.set_region_for_application(interactive, region, force_non_interactive)
                commonops.set_up_credentials(profile, region, interactive)

                # App name should be set once for all modules
                if not app_name:
                    # Switching back to the root dir will suggest the root dir name
                    # as the application name
                    os.chdir(cwd)
                    app_name = get_app_name(None, interactive, force_non_interactive)
                    os.chdir(module)

                if noverify:
                    fileoperations.write_config_setting('global', 'no-verify-ssl', True)

                default_env = '/ni' if force_non_interactive else None

                if not application_created:
                    platform_arn, keyname_of_existing_application = commonops.create_app(
                        app_name,
                        default_env=default_env
                    )
                    application_created = True
                else:
                    platform_arn, keyname_of_existing_application = commonops.pull_down_app_info(
                        app_name,
                        default_env=default_env
                    )
                io.echo('\n--- Configuring module: {0} ---'.format(module))
                module_platform = _determine_platform(
                    customer_provided_platform=platform,
                    existing_app_platform=platform_arn,
                    force_interactive=interactive)

                initializeops.setup(app_name, region, module_platform)
                configure_keyname(module_platform, keyname, keyname_of_existing_application, interactive, force_non_interactive)
                os.chdir(cwd)


def _get_application_name_interactive():
    app_list = elasticbeanstalk.get_application_names()
    file_name = fileoperations.get_current_directory_name()
    new_app = False
    if len(app_list) > 0:
        io.echo()
        io.echo('Select an application to use')
        new_app_option = '[ Create new Application ]'
        app_list.append(new_app_option)
        try:
            default_option = app_list.index(file_name) + 1
        except ValueError:
            default_option = len(app_list)
        app_name = utils.prompt_for_item_in_list(app_list,
                                                 default=default_option)
        if app_name == new_app_option:
            new_app = True

    if len(app_list) == 0 or new_app:
        io.echo()
        io.echo('Enter Application Name')
        unique_name = utils.get_unique_name(file_name, app_list)
        app_name = io.prompt_for_unique_name(unique_name, app_list)

    return app_name


# Code Commit repository setup methods
def get_repository_interactive():
    source_control = SourceControl.get_source_control()
    # Give list of code commit repositories to use
    new_repo = False
    repo_list = codecommit.list_repositories()["repositories"]

    current_repository = source_control.get_current_repository()
    current_repository = current_repository or fileoperations.get_current_directory_name()

    # If there are existing repositories prompt the user to pick one
    # otherwise set default as the file name
    if len(repo_list) > 0:
        repo_list = list(map(lambda r: r["repositoryName"], repo_list))
        io.echo()
        io.echo('Select a repository')
        new_repo_option = '[ Create new Repository ]'
        repo_list.append(new_repo_option)

        try:
            default_option = repo_list.index(current_repository) + 1
        except ValueError:
            default_option = len(repo_list)
        repo_name = utils.prompt_for_item_in_list(repo_list,
                                                 default=default_option)
        if repo_name == new_repo_option:
            new_repo = True

    # Create a new repository if the user specifies or there are no existing repositories
    if len(repo_list) == 0 or new_repo:
        io.echo()
        io.echo('Enter Repository Name')
        unique_name = utils.get_unique_name(current_repository, repo_list)
        repo_name = io.prompt_for_unique_name(unique_name, repo_list)

        create_codecommit_repository(repo_name)

    return repo_name


def create_codecommit_repository(repo_name):
    # Create the repository if we get here
    codecommit.create_repository(repo_name, "Created with EB CLI")
    io.echo("Successfully created repository: {0}".format(repo_name))


def setup_codecommit_remote_repo(repository, source_control):
    result = codecommit.get_repository(repository)
    remote_url = result['repositoryMetadata']['cloneUrlHttp']
    source_control.setup_codecommit_remote_repo(remote_url=remote_url)


def create_codecommit_branch(source_control, branch_name):
    current_commit = source_control.get_current_commit()

    # Creating the branch requires that we setup the remote branch first
    # to ensure the code commit branch is synced with the local branch
    if current_commit is None:
        # TODO: Test on windows for weird empty returns with the staged files
        staged_files = source_control.get_list_of_staged_files()
        if not staged_files:
            source_control.create_initial_commit()
        else:
            LOG.debug("Cannot create placeholder commit because there are staged files: {0}".format(staged_files))
            io.echo("Could not set create a commit with staged files; cannot setup CodeCommit branch without a commit")
            return None

    source_control.setup_new_codecommit_branch(branch_name=branch_name)
    io.echo("Successfully created branch: {0}".format(branch_name))


def get_branch_interactive(repository):
    source_control = SourceControl.get_source_control()
    # Give list of code commit branches to use
    new_branch = False
    branch_list = codecommit.list_branches(repository)["branches"]
    current_branch = source_control.get_current_branch()

    # If there are existing branches prompt the user to pick one
    if len(branch_list) > 0:
        io.echo('Select a branch')
        new_branch_option = '[ Create new Branch with local HEAD ]'
        branch_list.append(new_branch_option)
        try:
            default_option = branch_list.index(current_branch) + 1
        except ValueError:
            default_option = len(branch_list)
        branch_name = utils.prompt_for_item_in_list(branch_list,
                                                    default=default_option)
        if branch_name == new_branch_option:
            new_branch = True

    # Create a new branch if the user specifies or there are no existing branches

    if len(branch_list) == 0 or new_branch:
        new_branch = True
        io.echo()
        io.echo('Enter Branch Name')
        io.echo('***** Must have at least one commit to create a new branch with CodeCommit *****')
        unique_name = utils.get_unique_name(current_branch, branch_list)
        branch_name = io.prompt_for_unique_name(unique_name, branch_list)

    # Setup git to push to this repo
    result = codecommit.get_repository(repository)
    remote_url = result['repositoryMetadata']['cloneUrlHttp']
    source_control.setup_codecommit_remote_repo(remote_url=remote_url)

    if len(branch_list) == 0 or new_branch:
        LOG.debug("Creating a new branch")
        try:
            create_codecommit_branch(source_control, branch_name)
        except ServiceError:
            io.echo("Could not set CodeCommit branch with the current commit, run with '--debug' to get the full error")
            return None
    elif not new_branch:
        LOG.debug("Setting up an existing branch")
        succesful_branch = source_control.setup_existing_codecommit_branch(branch_name)
        if not succesful_branch:
            io.echo("Could not set CodeCommit branch, run with '--debug' to get the full error")
            return None

    return branch_name


def configure_codecommit(source):
    source_location, repository, branch = utils.parse_source(source)
    source_control = SourceControl.get_source_control()

    if not source_location:
        should_continue = io.get_boolean_response(text=prompts['codecommit.usecc'], default=True)
        if not should_continue:
            LOG.debug("Denied option to use CodeCommit, continuing initialization")
            return repository, branch

    # Setup git config settings for code commit credentials
    source_control.setup_codecommit_cred_config()
    repository, branch = establish_codecommit_repository_and_branch(repository, branch, source_control, source_location)

    return repository, branch


def configure_keyname(solution, keyname, keyname_of_existing_app, interactive, force_non_interactive):
    if 'IIS' not in solution:
        keyname = get_keyname(keyname, keyname_of_existing_app, interactive, force_non_interactive)

        if keyname == -1:
            keyname = None

        fileoperations.write_config_setting(
            'global',
            'default_ec2_keyname',
            keyname
        )


def create_app_or_use_existing_one(app_name, default_env, tags):
    if elasticbeanstalk.application_exist(app_name):
        return commonops.pull_down_app_info(app_name, default_env=default_env)
    else:
        return commonops.create_app(app_name, default_env=default_env, tags=tags)


def directory_is_already_associated_with_a_branch():
    return gitops.git_management_enabled()


def extract_solution_stack_from_env_yaml():
    env_yaml_platform = fileoperations.get_platform_from_env_yaml()
    if env_yaml_platform:
        platform = solutionstack.SolutionStack(env_yaml_platform).platform_shorthand
        return platform


def get_app_name(customer_specified_app_name, interactive, force_non_interactive):
    if customer_specified_app_name:
        return customer_specified_app_name

    try:
        app_name = fileoperations.get_application_name(default=None)
    except NotInitializedError:
        app_name = None

    if force_non_interactive and not interactive:
        return fileoperations.get_current_directory_name()
    elif interactive or not app_name:
        return _get_application_name_interactive()
    return app_name


def get_keyname(keyname, keyname_of_existing_app, interactive, force_non_interactive):
    keyname_passed_through_command_line = not not keyname
    keyname = keyname or keyname_of_existing_app
    if not keyname:
        try:
            keyname = commonops.get_default_keyname()
        except NotInitializedError:
            keyname = None

    if force_non_interactive and not interactive:
        return keyname

    if (
            (interactive and not keyname_passed_through_command_line)
            or (not keyname and not force_non_interactive)
    ):
        keyname = sshops.prompt_for_ec2_keyname()
    elif keyname != -1:
        commonops.upload_keypair_if_needed(keyname)

    return keyname


def handle_buildspec_image(solution, force_non_interactive):
    if not fileoperations.build_spec_exists():
        return None

    build_spec = fileoperations.get_build_configuration()
    
    if not force_non_interactive and build_spec and build_spec.image is None:
        LOG.debug("Buildspec file is present but image does not exist. Attempting to fill best guess.")
        platform_image = initializeops.get_codebuild_image_from_platform(solution)

        if not platform_image:
            io.echo("No images found for platform: {platform}".format(platform=solution))
            return None

        if isinstance(platform_image[0], dict):
            if len(platform_image) == 1:
                io.echo(strings['codebuild.latestplatform'].replace('{platform}', solution))
                selected_image = platform_image[0]
            else:
                io.echo(prompts['codebuild.getplatform'].replace('{platform}', solution))
                selected = int(utils.prompt_for_index_in_list([image['description'] for image in platform_image]))
                
                if selected is not None and 0 <= selected < len(platform_image):
                    selected_description = platform_image[selected]['description']
                else:
                    LOG.error("Invalid selection.")
                    return None

                matching_images = [image for image in platform_image if selected_description == image['description']]

                if not matching_images:
                    LOG.error(f"No matching images found for selected description: {selected}")
                    return None

                selected_image = matching_images[0]
            fileoperations.write_buildspec_config_header('Image', selected_image['name'])

    return None



def set_default_env(interactive, force_non_interactive):
    if force_non_interactive:
        return '/ni'

    if not interactive:
        try:
            return commonops.get_current_branch_environment()
        except NotInitializedError:
            pass


def establish_codecommit_branch(repository, branch, source_control, source_location):
    if branch is None:
        branch = get_branch_interactive(repository)
    else:
        try:
            codecommit.get_branch(repository, branch)
        except ServiceError as ex:
            if source_location:
                create_codecommit_branch(source_control, branch)
            else:
                io.log_error(strings['codecommit.nobranch'])
                raise ex
        source_control.setup_existing_codecommit_branch(branch)

    return branch


def establish_codecommit_repository(repository, source_control, source_location):
    if repository is None:
        repository = get_repository_interactive()
    else:
        try:
            setup_codecommit_remote_repo(repository, source_control)
        except ServiceError as ex:
            if source_location:
                create_codecommit_repository(repository)
                setup_codecommit_remote_repo(repository, source_control)
            else:
                io.log_error(strings['codecommit.norepo'])
                raise ex
    return repository


def establish_codecommit_repository_and_branch(repository, branch, source_control, source_location):
    repository = establish_codecommit_repository(repository, source_control, source_location)
    branch = establish_codecommit_branch(repository, branch, source_control, source_location)

    return repository, branch


def should_prompt_customer_to_opt_into_codecommit(
        force_non_interactive,
        region_name,
        source
):
    source_location, repository, branch = utils.parse_source(source)

    if force_non_interactive:
        return False
    elif not codecommit.region_supported():
        if source_location:
            io.log_warning(strings['codecommit.badregion'])
        return False
    elif not fileoperations.is_git_directory_present():
        io.echo(strings['codecommit.nosc'])
        return False
    elif not fileoperations.program_is_installed('git'):
        io.echo(strings['codecommit.nosc'])
        return False
    elif directory_is_already_associated_with_a_branch():
        return False

    return True


def _customer_is_avoiding_interactive_flow(command_args):
    return not not command_args.platform


def _determine_platform(
    customer_provided_platform=None,
    existing_app_platform=None,
    force_interactive=False,
):
    platform = None

    if not force_interactive:
        if customer_provided_platform:
            platform = platformops.get_platform_for_platform_string(
                customer_provided_platform)

        if not platform:
            try:
                platform = platformops.get_configured_default_platform()
            except NotInitializedError:
                # If the directory is not initialized we can safely continue
                # to get the platform from other sources
                pass

        if existing_app_platform and not platform:
            platform = PlatformVersion(existing_app_platform).hydrate(
                elasticbeanstalk.describe_platform_version)

        if not platform and fileoperations.env_yaml_exists():
            platform = extract_solution_stack_from_env_yaml()
            if platform:
                io.echo(strings['init.usingenvyamlplatform'].replace('{platform}', platform))

    if not platform:
        platform = platformops.prompt_for_platform()

    if isinstance(platform, PlatformVersion):
        statusops.alert_platform_status(platform)
        if customer_provided_platform == platform.platform_arn:
            return platform.platform_arn
        return platform.platform_branch_name or platform.platform_name
    if isinstance(platform, PlatformBranch):
        statusops.alert_platform_branch_status(platform)
        return platform.branch_name
    if isinstance(platform, SolutionStack):
        return platform.platform_shorthand
    return platform
