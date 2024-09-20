# Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import re

from cement.utils.misc import minimal_logger

from ebcli.lib import aws
from ebcli.core import io
from ebcli.objects.exceptions import ServiceError
from botocore.exceptions import EndpointConnectionError

LOG = minimal_logger(__name__)


def _make_api_call(operation_name, **operation_options):
    try:
        result = aws.make_api_call('codebuild', operation_name, **operation_options)
    except ServiceError as ex:
        if ex.code == 'AccessDeniedException':
            io.echo(
                "EB CLI does not have the right permissions to access CodeBuild.\n"
                "To learn more, see Docs: https://docs-aws.amazon.com/codebuild/"
                "latest/userguide/auth-and-access-control-permissions-reference.html"
            )
        raise ex
    except EndpointConnectionError:
        LOG.debug(
            "Caught endpoint timeout for CodeBuild."
            " We are assuming this is because they are not supported in that region yet."
        )
        raise ServiceError("Elastic Beanstalk does not support AWS CodeBuild in this region.")
    return result


def batch_get_builds(ids):
    params = dict(ids=ids)
    result = _make_api_call('batch_get_builds', **params)
    return result


def list_curated_environment_images():
    """
    This raw method will get all curated images managed by CodeBuild. We will
    return an array of image dictionaries of the most recent Beanstalk platform
    version available. So in the end what will be returned is a single image for
    each available platform from CodeBuild.
    :return: array of image dictionaries
    """
    regex_search_version = r"AWS ElasticBeanstalk - (.*?)v([0-9]+\.[0-9]+\.[0-9]+)"
    result = _make_api_call('list_curated_environment_images')
    beanstalk_images = []
    for platform in result['platforms']:
        for language in platform['languages']:
            languages_by_platform_version = {}
            for image in language['images']:
                if 'ElasticBeanstalk'.encode(errors='ignore') in image['description'].encode(errors='ignore'):
                    matches = re.search(regex_search_version, image['description'])

                    # Get the Platform version for the current image
                    current_version = int(matches.group(2).replace(".", ""))

                    # Set the description to to something nicer than the full description from CodeBuild
                    image['description'] = matches.group(1)

                    # Append the image to the correct array with the Platform version as the key
                    if current_version in languages_by_platform_version.keys():
                        current_value = languages_by_platform_version[current_version]
                        current_value.append(image)
                    else:
                        current_value = [image]
                    languages_by_platform_version[current_version] = current_value

            # Add the image dictionaries of the highest available platform version for the current language
            if languages_by_platform_version:
                beanstalk_images += languages_by_platform_version[max(languages_by_platform_version.keys())]

    return beanstalk_images
