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
from cement.utils.misc import minimal_logger

from ebcli.core import fileoperations, io
from ebcli.lib import elasticbeanstalk, heuristics, aws, codebuild
from ebcli.objects.exceptions import CredentialsError, NotAuthorizedError
from ebcli.objects.sourcecontrol import SourceControl
from ebcli.resources.strings import strings
from ebcli.core.ebglobals import Constants

LOG = minimal_logger(__name__)


def setup(
        app_name,
        region,
        solution,
        workspace_type=Constants.WorkSpaceTypes.APPLICATION,
        platform_name=None,
        platform_version=None,
        instance_profile=None,
        dir_path=None,
        repository=None,
        branch=None):

    setup_directory(
        app_name,
        region,
        solution,
        workspace_type=workspace_type,
        platform_name=platform_name,
        platform_version=platform_version,
        instance_profile=instance_profile,
        dir_path=dir_path,
        repository=repository,
        branch=branch)

    if (
        solution is not None
        and 'tomcat' in solution.lower()
        and heuristics.has_tomcat_war_file()
    ):
        war_file = fileoperations.get_war_file_location()
        fileoperations.write_config_setting('deploy', 'artifact', war_file)

    setup_ignore_file()


def setup_directory(
        app_name,
        region,
        solution,
        workspace_type,
        platform_name,
        platform_version,
        instance_profile,
        dir_path=None,
        repository=None,
        branch=None):

    io.log_info('Setting up .elasticbeanstalk directory')
    fileoperations.create_config_file(
        app_name,
        region,
        solution,
        workspace_type,
        platform_name,
        platform_version,
        instance_profile,
        dir_path=dir_path,
        repository=repository,
        branch=branch)


def setup_ignore_file():
    io.log_info('Setting up ignore file for source control')
    sc = fileoperations.get_config_setting('global', 'sc')

    if not sc:
        source_control = SourceControl.get_source_control()
        source_control.set_up_ignore_file()
        sc_name = source_control.get_name()
        fileoperations.write_config_setting('global', 'sc', sc_name)


def get_codebuild_image_from_platform(platform):
    platform_images = []  # Store multiple matches in a list
    beanstalk_images = codebuild.list_curated_environment_images()

    # Log the entire list for debugging purposes
    LOG.debug("Fetched beanstalk_images: {}".format(beanstalk_images))

    # Validate that beanstalk_images is a list of dictionaries
    if not isinstance(beanstalk_images, list) or not all(isinstance(i, dict) for i in beanstalk_images):
        LOG.error("Unexpected format for beanstalk_images. Expected a list of dictionaries.")
        return []

    for image in beanstalk_images:
        if 'description' in image and platform in image['description']:
            platform_images.append(image)

    # If no platform-specific images found, return all images
    if not platform_images:
        LOG.debug("No matching platform images found. Returning all images.")
        return beanstalk_images

    LOG.debug("Searching for images for platform '{0}'. Found: {1}".format(platform, platform_images))

    return platform_images
