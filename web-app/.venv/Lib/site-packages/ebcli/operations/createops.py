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
from zipfile import ZipFile

from cement.utils.misc import minimal_logger

from ebcli.operations import gitops, buildspecops, commonops, statusops
from ebcli.operations.tagops import tagops
from ebcli.operations.tagops.taglist import TagList
from ebcli.lib import cloudformation, elasticbeanstalk, heuristics, iam, utils
from ebcli.lib.aws import InvalidParameterValueError
from ebcli.core import io, fileoperations
from ebcli.objects.exceptions import NotAuthorizedError
from ebcli.resources.strings import strings, responses, prompts
from ebcli.resources.statics import iam_attributes
import json

LOG = minimal_logger(__name__)
DEFAULT_ROLE_NAME = 'aws-elasticbeanstalk-ec2-role'
DEFAULT_SERVICE_ROLE_NAME = 'aws-elasticbeanstalk-service-role'

DEFAULT_SERVICE_ROLE_POLICIES = [
    'arn:aws:iam::aws:policy/service-role/AWSElasticBeanstalkEnhancedHealth',
    'arn:aws:iam::aws:policy/AWSElasticBeanstalkManagedUpdatesCustomerRolePolicy'
]


def make_new_env(
        env_request,
        branch_default=False,
        process_app_version=False,
        nohang=False,
        interactive=True,
        timeout=None,
        source=None,
):
    resolve_roles(env_request, interactive)

    build_config = None
    if fileoperations.build_spec_exists():
        build_config = fileoperations.get_build_configuration()
        LOG.debug("Retrieved build configuration from buildspec: {0}".format(build_config.__str__()))

    codecommit_setup = gitops.git_management_enabled()
    if not env_request.sample_application and not env_request.version_label:
        if source is not None:
            io.log_info('Creating new application version using remote source')
            io.echo("Starting environment deployment via remote source")
            env_request.version_label = commonops.create_app_version_from_source(
                env_request.app_name, source, process=process_app_version, label=env_request.version_label,
                build_config=build_config)
            process_app_version = True
        elif codecommit_setup:
            io.log_info('Creating new application version using CodeCommit')
            io.echo("Starting environment deployment via CodeCommit")
            env_request.version_label = \
                commonops.create_codecommit_app_version(env_request.app_name, process=process_app_version,
                                                        build_config=build_config)
            process_app_version = True
        else:
            io.log_info('Creating new application version using project code')
            env_request.version_label = \
                commonops.create_app_version(env_request.app_name, process=process_app_version,
                                             build_config=build_config)

        if build_config is not None:
            buildspecops.stream_build_configuration_app_version_creation(
                env_request.app_name,
                env_request.version_label,
                build_config
            )
        elif process_app_version is True:
            success = commonops.wait_for_processed_app_versions(
                env_request.app_name,
                [env_request.version_label],
                timeout=timeout or 5
            )
            if not success:
                return

    if env_request.version_label is None or env_request.sample_application:
        env_request.version_label = \
            commonops.create_dummy_app_version(env_request.app_name)

    if env_request.key_name:
        commonops.upload_keypair_if_needed(env_request.key_name)

    download_sample_app = None
    if interactive:
        download_sample_app = should_download_sample_app()

    io.log_info('Creating new environment')
    result, request_id = create_env(env_request,
                                    interactive=interactive)

    env_name = result.name

    default_env = commonops.get_current_branch_environment()
    if not default_env or branch_default:
        commonops.set_environment_for_current_branch(env_name)
        if codecommit_setup:
            io.echo("Setting up default branch")
            gitops.set_branch_default_for_current_environment(gitops.get_default_branch())
            gitops.set_repo_default_for_current_environment(gitops.get_default_repository())

    if download_sample_app:
        download_and_extract_sample_app(env_name)

    result.print_env_details(
        io.echo,
        elasticbeanstalk.get_environments,
        elasticbeanstalk.get_environment_resources,
        health=False
    )

    statusops.alert_environment_status(result)

    if nohang:
        return

    io.echo('Printing Status:')

    commonops.wait_for_success_events(request_id,
                                      timeout_in_minutes=timeout)


def should_download_sample_app():
    """
    Method determines whether the present directory is empty. If yes, it allows the user
    to choose to download the sample application that the environment will be launched
    with.

    :return: User's choice of whether the sample application should be downloaded
    """
    if heuristics.directory_is_empty():
        return io.get_boolean_response(
            text=strings['create.sample_application_download_option'],
            default=True)

    return False


def download_and_extract_sample_app(env_name):
    """
    Method orchestrates the retrieval, and extraction of application version.

    :param env_name: The name of the environment whose application version will be downloaded.
    :return: None
    """
    try:
        url = retrieve_application_version_url(env_name)
        zip_file_location = '.elasticbeanstalk/.sample_app_download.zip'
        io.echo('INFO: {}'.format(strings['create.downloading_sample_application']))
        download_application_version(url, zip_file_location)
        ZipFile(zip_file_location, 'r', allowZip64=True).extractall()
        os.remove(zip_file_location)
        io.echo('INFO: {}'.format(strings['create.sample_application_download_complete']))
    except NotAuthorizedError as e:
        io.log_warning('{} Continuing environment creation.'.format(e.message))
    except cloudformation.CFNTemplateNotFound as e:
        io.log_warning('{} Continuing environment creation.'.format(e.message))


def download_application_version(url, zip_file_location):
    """
    Method downloads the application version from the URL, 'url', and
    writes them at the location specified by `zip_file_location`

    :param url: the URL of the application version.
    :param zip_file_location: path on the user's system to write the application version ZIP file to.
    :return: None
    """
    data = utils.get_data_from_url(url, timeout=30)

    fileoperations.write_to_data_file(zip_file_location, data)


def retrieve_application_version_url(env_name):
    """
    Method retrieves the URL of the application version of the environment, 'env_name',
    for the CLI to download from.

    The method waits for the CloudFormation stack associated with `env_name` to come
    into existence, after which, it retrieves the 'url' of the application version.

    :param env_name: Name of the environment that launched with the sample application
    :return: The URL of the application version.
    """
    env = elasticbeanstalk.get_environment(env_name=env_name)
    cloudformation_stack_name = 'awseb-' + env.id + '-stack'
    cloudformation.wait_until_stack_exists(cloudformation_stack_name)
    template = cloudformation.get_template(cloudformation_stack_name)

    url = None
    try:
        url = template['TemplateBody']['Parameters']['AppSource']['Default']
    except KeyError:
        io.log_warning('{}. '.format(strings['cloudformation.cannot_find_app_source_for_environment']))

    return url


def create_env(env_request, interactive=True):
    if env_request.template_name:
        platform = env_request.platform
        env_request.platform = None
    else:
        platform = None
    while True:
        try:
            return elasticbeanstalk.create_environment(env_request)

        except InvalidParameterValueError as e:
            if e.message == responses['app.notexists'].replace(
                        '{app-name}', '\'' + env_request.app_name + '\''):
                commonops.create_app(env_request.app_name)
            elif e.message == responses['create.noplatform']:
                if platform:
                    env_request.platform = platform
                else:
                    raise
            elif interactive:
                LOG.debug('creating env returned error: ' + e.message)
                if re.match(responses['env.cnamenotavailable'], e.message):
                    io.echo(prompts['cname.unavailable'])
                    io.prompt_for_cname()
                elif re.match(responses['env.nameexists'], e.message):
                    io.echo(strings['env.exists'])
                    current_environments = elasticbeanstalk.get_all_environment_names()
                    unique_name = utils.get_unique_name(env_request.env_name,
                                                        current_environments)
                    env_request.env_name = io.prompt_for_environment_name(
                        default_name=unique_name)
                elif e.message == responses['app.notexists'].replace(
                            '{app-name}', '\'' + env_request.app_name + '\''):
                    commonops.create_app(env_request.app_name)
                else:
                    raise
            else:
                raise


def get_service_role():
    try:
        roles = iam.get_role_names()
        if DEFAULT_SERVICE_ROLE_NAME not in roles:
            return None
    except NotAuthorizedError:
        pass

    return DEFAULT_SERVICE_ROLE_NAME


def create_default_service_role():
    """
    Create the default service role
    """
    io.log_info('Creating service role {} with default permissions.'
                .format(DEFAULT_SERVICE_ROLE_NAME))
    trust_document = _get_default_service_trust_document()
    role_name = DEFAULT_SERVICE_ROLE_NAME

    try:
        iam.create_role_with_policy(role_name, trust_document,
                                    DEFAULT_SERVICE_ROLE_POLICIES)
    except NotAuthorizedError as e:
        raise NotAuthorizedError(prompts['create.servicerole.nopermissions']
                                 .format(DEFAULT_SERVICE_ROLE_NAME, e))

    return DEFAULT_SERVICE_ROLE_NAME


def resolve_roles(env_request, interactive):
    """
    Resolves instance-profile and service-role
    :param env_request: environment request
    :param interactive: boolean
    """
    LOG.debug('Resolving roles')

    if (
        not env_request.instance_profile or
        env_request.instance_profile == iam_attributes.DEFAULT_ROLE_NAME
    ) and not env_request.template_name:
        env_request.instance_profile = commonops.create_default_instance_profile()

    if (
        env_request.platform and
        env_request.platform.has_healthd_support and
        not env_request.service_role and
        not env_request.template_name
    ):
        role = get_service_role()
        if role is None:
            if interactive:
                io.echo()
                io.echo(prompts['create.servicerole.info'])
                input = io.get_input(prompts['create.servicerole.view'],
                                     default='')

                if input.strip('"').lower() == 'view':
                    for policy_arn in DEFAULT_SERVICE_ROLE_POLICIES:
                        document = iam.get_managed_policy_document(policy_arn)
                        io.echo(json.dumps(document, indent=4))
                    io.get_input(prompts['general.pressenter'])

            role = create_default_service_role()

        env_request.service_role = role


def _get_default_service_trust_document():
    """
    Just a string representing the service role policy.
    Includes newlines for pretty printing :)
    """
    return """{
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "",
        "Effect": "Allow",
        "Principal": {
            "Service": "elasticbeanstalk.amazonaws.com"
        },
        "Action": "sts:AssumeRole",
        "Condition": {
            "StringEquals": {
                "sts:ExternalId": "elasticbeanstalk"
            }
        }
    }]
}"""

