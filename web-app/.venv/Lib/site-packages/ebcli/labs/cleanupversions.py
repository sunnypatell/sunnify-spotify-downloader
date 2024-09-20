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

from operator import itemgetter

from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.resources.strings import strings
from ebcli.lib import elasticbeanstalk, utils
from ebcli.core import io
from ebcli.objects.exceptions import ServiceError


class CleanupVersionsController(AbstractBaseController):
    class Meta:
        label = 'cleanup-versions'
        stacked_on = 'labs'
        stacked_type = 'nested'
        description = strings['cleanup-versions.info']
        usage = 'eb labs cleanup-versions [options...]'
        arguments = AbstractBaseController.Meta.arguments + [
            (['--num-to-leave'], dict(
                action='store', type=int, default=10, metavar='NUM',
                help='number of unused versions to leave DEFAULT=10')),
            (['--older-than'], dict(
                action='store', type=int, default=60, metavar='DAYS',
                help='delete only versions older than x days DEFAULT=60')),
            (['--force'], dict(action='store_true',
                               help='don\'t prompt for confirmation'))
        ]

    def do_command(self):
        app_name = self.get_app_name()
        num_to_leave = self.app.pargs.num_to_leave
        older_than = self.app.pargs.older_than
        force = self.app.pargs.force

        envs = elasticbeanstalk.get_app_environments(app_name)
        versions_in_use = [e.version_label for e in envs]

        app_versions = elasticbeanstalk.get_application_versions(app_name)['ApplicationVersions']
        app_versions.sort(key=itemgetter('DateUpdated'), reverse=True)

        app_versions = [v for v in app_versions if v['VersionLabel'] not in versions_in_use]

        total_num_unused_versions = len(app_versions)

        if total_num_unused_versions < num_to_leave:
            io.echo(
                'Not enough unused application version to leave behind {0}; '
                'No application versions to delete.'.format(num_to_leave)
            )
            return

        app_versions = [v for v in app_versions if
                        utils.get_delta_from_now_and_datetime(
                            v['DateUpdated']).days > older_than]

        app_versions = app_versions[num_to_leave:]

        if app_versions:
            if not force:
                response = io.get_boolean_response(
                    '{} application versions will be deleted. '
                    'Continue?'.format(len(app_versions))
                )
                if not response:
                    return
        else:
            io.echo('No application versions to delete.')
            return

        for version in app_versions:
            label = version['VersionLabel']
            try:
                elasticbeanstalk.delete_application_version(app_name, label)
            except ServiceError as e:
                io.log_warning('Error deleting version {0}. Error: {1}'
                               .format(label, e.message))
