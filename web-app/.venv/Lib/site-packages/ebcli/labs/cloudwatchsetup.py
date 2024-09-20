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
import shutil

from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.resources.strings import strings, flag_text
from ebcli.core import io, fileoperations


CWFILES_DIRNAME = 'cloudwatchfiles'
CWFILES_DIR_PATH = os.path.join(os.path.dirname(
    os.path.realpath(__file__)),
    CWFILES_DIRNAME
)


class CloudWatchSetUp(AbstractBaseController):
    class Meta:
        label = 'setup-cloudwatchlogs'
        aliases = ['setup-cwl']
        stacked_on = 'labs'
        stacked_type = 'nested'
        description = strings['cloudwatch-setup.info']
        usage = 'eb labs setup-cloudwatchlogs [options ...]'
        arguments = [
            (['--remove'], dict(help=flag_text['labs.cwl.remove'], action='store_true'))
        ]

    def do_command(self):
        cwfile_dir = CWFILES_DIR_PATH

        ebextension_dir = fileoperations.project_file_path('.ebextensions')

        if self.app.pargs.remove:
            return remove_cwl_extensions(cwfile_dir, ebextension_dir)

        if not os.path.isdir(ebextension_dir):
            os.makedirs(ebextension_dir)

        for file_name in os.listdir(cwfile_dir):
            source_file = os.path.join(cwfile_dir, file_name)
            destination = os.path.join(ebextension_dir, file_name)

            if fileoperations.file_exists(destination):
                io.log_error(strings['cloudwatch-setup.alreadysetup']
                             .format(filename=destination))
            shutil.copy(source_file, destination)

        io.echo(strings['cloudwatch-setup.text'])


def remove_cwl_extensions(cwfile_dir, ebextension_dir):
    for file_name in os.listdir(cwfile_dir):
        try:
            os.remove(os.path.join(ebextension_dir, file_name))
        except:
            io.log_warning('Ebextension {} already removed'.format(file_name))

    io.echo(strings['cloudwatch-setup.removetext'])
