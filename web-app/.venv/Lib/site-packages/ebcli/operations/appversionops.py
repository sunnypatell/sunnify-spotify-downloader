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

from ebcli.core import io, fileoperations
from ebcli.display.appversion import term, VersionScreen, VersionDataPoller
from ebcli.display.table import Table, Column
from ebcli.display.help import ViewlessHelpTable
from ebcli.lib import elasticbeanstalk as elasticbeanstalk
from ebcli.objects.exceptions import ValidationError, NotFoundError
from ebcli.operations import commonops, gitops, buildspecops
from ebcli.resources.strings import prompts, strings

LOG = minimal_logger(__name__)


def create_app_version_without_deployment(app_name, label=None,
                                          staged=False, process=False, description=None, source=None, timeout=5):
    build_config = None
    if fileoperations.build_spec_exists():
        build_config = fileoperations.get_build_configuration()
        LOG.debug("Retrieved build configuration from buildspec: {0}".format(build_config.__str__()))

    if source is not None:
        app_version_label = commonops.create_app_version_from_source(
            app_name,
            source,
            process=process,
            label=label,
            message=description,
            build_config=build_config
        )
        io.echo("Creating application version via specified source.")
        process = True
    elif gitops.git_management_enabled() and not staged:
        app_version_label = commonops.create_codecommit_app_version(
            app_name, process=process, label=label, message=description, build_config=build_config)
        io.echo("Creating application version via CodeCommit.")
        process = True
    else:
        app_version_label = commonops.create_app_version(
            app_name,
            process=process,
            label=label,
            message=description,
            staged=staged,
            build_config=build_config
        )

    if build_config is not None:
        buildspecops.stream_build_configuration_app_version_creation(
            app_name, app_version_label, build_config)
    elif process is True:
        commonops.wait_for_processed_app_versions(
            app_name,
            [app_version_label],
            timeout=timeout
        )


def delete_app_version_label(app_name, version_label):
    if version_label:
        app_versions = elasticbeanstalk.get_application_versions(app_name)['ApplicationVersions']
        if not any(version_label == app_version['VersionLabel'] for app_version in app_versions):
            raise ValidationError(strings['appversion.delete.notfound'].format(app_name, version_label))

        envs = elasticbeanstalk.get_app_environments(app_name)

        versions_in_use = [(e.version_label, e.name) for e in envs]

        used_envs = [version[1] for version in versions_in_use if version[0] == version_label]

        if used_envs:
            raise ValidationError(
                strings['appversion.delete.deployed'].format(
                    version_label,
                    ','.join(used_envs)
                )
            )

        should_delete = io.get_boolean_response(
            text=prompts['appversion.delete.validate'].format(version_label),
            default=True)
        if not should_delete:
            io.echo('Application Version will not be deleted.')
            delete_successful = False
        else:
            elasticbeanstalk.delete_application_version(app_name, version_label)
            io.echo('Application Version deleted successfully.')
            delete_successful = True

        return delete_successful
    else:
        raise NotFoundError(strings['appversion.delete.none'])


def display_versions(app_name, env_name, app_versions, timeout_in_minutes=5):
    """Displays version history in birth order in a table.
    Creates poller, screen, and table.
    Displays Deploy#, Version Label, Description, Date Created, Ago.
    Returns the current version deployment number.
    """
    poller = VersionDataPoller(app_name, env_name, app_versions)
    screen = VersionScreen(poller)
    _create_version_table(screen)
    data = poller.get_version_data()

    try:
        screen.start_version_screen(data, VersionScreen.APP_VERSIONS_TABLE_NAME)
    finally:
        term.return_cursor_to_normal()


def _create_version_table(screen):
    """
    Creates and adds a versions table and a viewless help table to the screen.
    """
    screen.add_table(Table(VersionScreen.APP_VERSIONS_TABLE_NAME, columns=[
        Column('#', None, 'DeployNum', 'left'),
        Column('Version Label', None, 'VersionLabel', 'left'),
        Column('Date Created', None, 'DateCreated', 'left'),
        Column('Age', None, 'SinceCreated', 'left'),
        Column('Description', None, 'Description', 'left'),
    ]))
    screen.add_help_table(ViewlessHelpTable())
