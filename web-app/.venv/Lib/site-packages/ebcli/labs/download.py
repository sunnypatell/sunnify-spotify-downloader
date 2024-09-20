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

from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.resources.strings import strings
from ebcli.objects.exceptions import NotFoundError
from ebcli.core import io, fileoperations
from ebcli.lib import elasticbeanstalk, s3, heuristics, cloudformation, utils


class DownloadController(AbstractBaseController):
    class Meta:
        label = 'download'
        stacked_on = 'labs'
        stacked_type = 'nested'
        description = strings['download.info']
        usage = AbstractBaseController.Meta.usage.replace('{cmd}', label)

    def do_command(self):
        app_name = self.get_app_name()
        env_name = self.get_env_name()

        download_source_bundle(app_name, env_name)


def download_source_bundle(app_name, env_name):
    env = elasticbeanstalk.get_environment(app_name=app_name, env_name=env_name)
    if env.version_label and env.version_label != 'Sample Application':
        app_version = elasticbeanstalk.get_application_versions(
            app_name,
            version_labels=[env.version_label]
        )['ApplicationVersions'][0]

        source_bundle = app_version['SourceBundle']
        bucket_name = source_bundle['S3Bucket']
        key_name = source_bundle['S3Key']
        io.echo('Downloading application version...')
        data = s3.get_object(bucket_name, key_name)
        filename = get_filename(key_name)
    else:
        template = cloudformation.get_template('awseb-' + env.id + '-stack')
        try:
            url = template['TemplateBody']['Parameters']['AppSource']['Default']
        except KeyError:
            raise NotFoundError('Can not find app source for environment')
        utils.get_data_from_url(url)
        io.echo('Downloading application version...')
        data = utils.get_data_from_url(url, timeout=30)
        filename = 'sample.zip'

    fileoperations.make_eb_dir('downloads/')
    location = fileoperations.get_eb_file_full_location(
        'downloads/' + filename)
    fileoperations.write_to_data_file(location, data)
    io.echo('Application version downloaded to:', location)

    cwd = os.getcwd()
    try:
        fileoperations.ProjectRoot.traverse()
        if heuristics.directory_is_empty():
            io.echo('Unzipping application version as project files.')
            fileoperations.unzip_folder(location, os.getcwd())
            io.echo('Done.')
    finally:
        os.chdir(cwd)


def get_filename(url):
    pattern = re.compile('^(?:.*[/])*([^/]+)$')
    matcher = re.match(pattern, url)
    return matcher.group(1).strip()
