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

from ebcli.lib import elasticbeanstalk
from ebcli.display.data_poller import DataPoller
from ebcli.display.screen import Screen
from ebcli.display.traditional import TraditionalHealthScreen, TraditionalHealthDataPoller
from ebcli.display.help import HelpTable, ViewlessHelpTable
from ebcli.display import term
from ebcli.display.table import Column, Table
from ebcli.display.specialtables import RequestTable, StatusTable
from ebcli.objects.platform import PlatformVersion
from ebcli.objects.exceptions import NotSupportedError
from ebcli.objects.solutionstack import SolutionStack
from ebcli.resources.statics import namespaces, option_names, option_values

LOG = minimal_logger(__name__)


def display_interactive_health(
        app_name,
        env_name,
        refresh,
        mono,
        default_view
):
    env = elasticbeanstalk.describe_configuration_settings(app_name, env_name)
    health_type = elasticbeanstalk.get_option_setting(
        env.get('OptionSettings'),
        namespaces.HEALTH_SYSTEM,
        option_names.SYSTEM_TYPE)

    if health_type == option_values.SYSTEM_TYPE__ENHANCED:
        LOG.debug('Platform has enhanced health capabilities')

        poller = DataPoller
        screen = Screen()
        platform = (
            PlatformVersion(env['PlatformArn'])
            if env.get('PlatformArn') else SolutionStack(env['SolutionStackName'])
        )
        create_health_tables(screen, platform)
    elif env['Tier']['Name'] == 'WebServer':
        LOG.debug('Platform has basic health capabilities')

        poller = TraditionalHealthDataPoller
        screen = TraditionalHealthScreen()
        create_traditional_health_tables(screen)
    else:
        raise NotSupportedError('The health dashboard is currently not supported for this environment.')

    poller = poller(app_name, env_name)
    poller.start_background_polling()

    try:
        screen.start_screen(poller, env, refresh,
                            mono=mono, default_table=default_view)
    finally:
        term.return_cursor_to_normal()


def create_health_tables(screen, platform):
    LOG.debug('Adding tables the `eb health` screen')

    is_windows_platform = 'windows' in platform.name.lower()

    screen.add_table(StatusTable('health', columns=[
        Column('instance-id', None, 'InstanceId', 'left'),
        Column('status', 10, 'HealthStatus', 'left', 'status_sort'),
        Column('cause', None, 'Cause', 'none'),
    ]))
    screen.add_table(RequestTable('requests', columns=[
        Column('instance-id', None, 'InstanceId', 'left'),
        Column('r/sec', 6, 'requests', 'left'),
        Column('%2xx', 6, 'Status2xx', 'right', 'Status2xx_sort'),
        Column('%3xx', 6, 'Status3xx', 'right', 'Status3xx_sort'),
        Column('%4xx', 6, 'Status4xx', 'right', 'Status4xx_sort'),
        Column('%5xx', 6, 'Status5xx', 'right', 'Status5xx_sort'),
        Column('p99 ', 9, 'P99', 'right', 'P99_sort'),
        Column('p90 ', 8, 'P90', 'right', 'P90_sort'),
        Column('p75', 7, 'P75', 'right', 'P75_sort'),
        Column('p50', 7, 'P50', 'right', 'P50_sort'),
        Column('p10', 7, 'P10', 'right', 'P10_sort'),
    ]))

    screen.add_table(Table('cpu', columns=[
        Column('instance-id', None, 'InstanceId', 'left'),
        Column('type', None, 'InstanceType', 'left'),
        Column('az', None, 'AvailabilityZone', 'left'),
        Column('running', 10, 'running', 'left', 'LaunchedAt')]))

    requests_table = screen.tables[-1]
    if not is_windows_platform:
        requests_table.columns += [
            Column('load 1', 7, 'load1', 'right'),
            Column('load 5', 7, 'load5', 'right')
        ]

    cpu_table = screen.tables[-1]
    if is_windows_platform:
        cpu_table.columns += [
            Column('% user time', 12, 'User', 'right'),
            Column('% privileged time', 20, 'Privileged', 'right'),
            Column('% idle time', 12, 'Idle', 'right'),
        ]
    else:
        cpu_table.columns += [
            Column('user %', 11, 'User', 'right'),
            Column('nice %', 7, 'Nice', 'right'),
            Column('system %', 9, 'System', 'right'),
            Column('idle %', 7, 'Idle', 'right'),
            Column('iowait %', 10, 'IOWait', 'right'),
        ]

    if platform.has_healthd_group_version_2_support:
        screen.add_table(Table('deployments', columns=[
            Column('instance-id', None, 'InstanceId', 'left'),
            Column('status', None, 'DeploymentStatus', 'left'),
            Column('id', None, 'DeploymentId', 'left'),
            Column('version', None, 'DeploymentVersion', 'left'),
            Column('ago', None, 'TimeSinceDeployment', 'left'),
        ]))
    screen.add_help_table(HelpTable())

    LOG.debug('Added {} tables to `eb health` screen'.format(len(screen.tables)))


def create_traditional_health_tables(screen):
    screen.add_table(Table('health', columns=[
        Column('instance-id', 19, 'id', 'left'),
        Column('EC2 Health', 15, 'health', 'left'),
        Column('ELB State', 15, 'state', 'left'),
        Column('ELB description', 40, 'description', 'none'),
    ]))
    screen.add_help_table(ViewlessHelpTable())
