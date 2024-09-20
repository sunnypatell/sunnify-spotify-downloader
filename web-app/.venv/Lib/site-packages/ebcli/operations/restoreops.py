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

import operator

from datetime import datetime, timedelta

from ebcli.display.help import ViewlessHelpTable
from ebcli.display.table import Table, Column
from ebcli.display.environments import EnvironmentScreen, EnvironmentDataPoller
from ebcli.display import term
from ebcli.core import io
from ebcli.operations import commonops
from ebcli.lib import elasticbeanstalk
from ebcli.lib.aws import InvalidParameterValueError
from ebcli.resources.strings import strings


def validate_restore(env_id):
    """
    Do client side validation because rebuild will rebuild a running environments as well
    """
    env = elasticbeanstalk.get_environment(
        env_id=env_id,
        include_deleted=True,
        deleted_back_to=get_date_cutoff()
    )

    if env.status != 'Terminated':
        raise InvalidParameterValueError(
            'Environment {0} ({1}) is currently {2}, must '
            'be "Terminated" to restore'.format(
                env.name,
                env.id,
                env.status
            )
        )


def restore(env_id, timeout=None):
    validate_restore(env_id)
    try:
        request_id = elasticbeanstalk.rebuild_environment(env_id=env_id)
    except InvalidParameterValueError as e:
        message = e.message.replace('rebuild', 'restore')
        raise InvalidParameterValueError(message)

    commonops.wait_for_success_events(request_id, timeout_in_minutes=timeout, can_abort=True)


def get_restorable_envs(app_name):
    date_cutoff = get_date_cutoff()
    environments = []

    app_envs = elasticbeanstalk.get_raw_app_environments(
        app_name,
        include_deleted=True,
        deleted_back_to=date_cutoff
    )
    for env in app_envs:
        if env['Status'] == 'Terminated':
            environments.append(env)

    environments = sorted(environments, key=operator.itemgetter('DateUpdated'), reverse=True)
    return environments


def get_date_cutoff():
    return datetime.today() - timedelta(days=42)


def display_environments(environments, timeout_in_minutes=5):
    """Displays Environment in birth order in a table.
    Creates poller, screen, and table.
    Displays Deploy#, Version Label, Description, Date Created, Ago.
    Returns the current version deployment number.
    """
    table_header_text = strings['restore.displayheader']
    poller = EnvironmentDataPoller(environments)
    screen = EnvironmentScreen(poller, header_text=table_header_text)
    _create_environment_table(screen)
    data = poller.get_environment_data()

    try:
        screen.start_version_screen(data, 'environments')
        if hasattr(screen, 'request_id') and screen.request_id:
            io.echo("Restoring " + screen.env_id + ".")
            commonops.wait_for_success_events(screen.request_id,
                                              timeout_in_minutes,
                                              can_abort=True)
    finally:
        term.return_cursor_to_normal()


def _create_environment_table(screen):
    """Creates and adds a versions table and a viewless help table to the screen."""
    screen.add_table(Table('environments', columns=[
        Column('#', None, 'DeployNum', 'left'),
        Column('Name', None, 'EnvironmentName', 'left'),
        Column('ID', None, 'EnvironmentId', 'left'),
        Column('Application Version', None, 'VersionLabel', 'left'),
        Column('Date Terminated', None, 'DateUpdated', 'left'),
        Column('Ago', None, 'SinceCreated', 'left'),
    ]))
    screen.add_help_table(ViewlessHelpTable())
