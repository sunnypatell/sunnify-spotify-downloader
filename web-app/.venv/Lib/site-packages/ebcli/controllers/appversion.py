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
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.core import fileoperations
from ebcli.lib import elasticbeanstalk as elasticbeanstalk
from ebcli.operations import appversionops
from ebcli.resources.strings import strings, flag_text, alerts
from ebcli.objects.exceptions import InvalidOptionsError


class AppVersionController(AbstractBaseController):
    class Meta(AbstractBaseController.Meta):
        label = 'appversion'
        description = strings['appversion.info']
        arguments = [
            (
                ['--delete', '-d'],
                dict(
                    action='store',
                    help=flag_text['appversion.delete'],
                    metavar='VERSION_LABEL')
            ),
            (['--create', '-c'], dict(action='store_true', help=flag_text['appversion.create'])),
            (['--application', '-a'], dict(help=flag_text['appversion.application'])),
            (['--label', '-l'], dict(help=flag_text['deploy.label'])),
            (['--message', '-m'], dict(help=flag_text['deploy.message'])),
            (['--staged'], dict(
                action='store_true', help=flag_text['appversion.staged'])),
            (['--timeout'], dict(default=5, type=int, help=flag_text['general.timeout'])),
            (['--source'], dict(help=flag_text['appversion.source'])),
            (['--process', '-p'], dict(
                action='store_true', help=flag_text['deploy.process']))
        ]
        usage = 'eb appversion <lifecycle> [options ...]'

    def do_command(self):
        if self.app.pargs.application is not None:
            self.app_name = self.app.pargs.application
        else:
            self.app_name = self.get_app_name()
        self.env_name = self.get_env_name(noerror=True)

        if self.app.pargs.create and self.app.pargs.delete is not None:
            raise InvalidOptionsError(alerts['create.can_not_use_options_together'].format("--create", "--delete"))

        if self.app.pargs.create:
            self.message = self.app.pargs.message
            self.staged = self.app.pargs.staged
            self.source = self.app.pargs.source
            self.label = self.app.pargs.label
            self.timeout = self.app.pargs.timeout
            self.process = self.app.pargs.process or fileoperations.env_yaml_exists()
            appversionops.create_app_version_without_deployment(self.app_name, self.label, self.staged, self.process,
                                                                self.message, self.source, self.timeout)
            return

        if self.app.pargs.delete is not None:
            version_label_to_delete = self.app.pargs.delete
            appversionops.delete_app_version_label(self.app_name, version_label_to_delete)
            return

        self.interactive_list_version()

    def interactive_list_version(self):
        """Interactive mode which allows user to see previous
        versions and allow a choice to:
        - deploy a different version.
        - delete a certain version
        Run when the user supplies no argument to the --delete flag.
        """
        app_versions = elasticbeanstalk.get_application_versions(self.app_name)['ApplicationVersions']
        appversionops.display_versions(self.app_name, self.env_name, app_versions)
