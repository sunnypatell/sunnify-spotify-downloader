# Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.s
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

import time
import sys

from decimal import InvalidOperation
from ebcli.objects.platform import PlatformVersion
from ebcli.display import term
import errno
from datetime import timedelta, datetime
from copy import copy
from collections import OrderedDict

from cement.utils.misc import minimal_logger
from cement.core.exc import CaughtSignal
from botocore.compat import six

from ebcli.objects.solutionstack import SolutionStack
from ebcli.core import io, fileoperations
from ebcli.lib import utils, ec2
from ebcli.objects.exceptions import ServiceError, ValidationError, NotFoundError

LOG = minimal_logger(__name__)


class Screen(object):
    def __init__(self):
        self.term = None
        self.tables = []
        self.vertical_offset = 0
        self.horizontal_offset = 0
        self.max_columns = 5
        self.help_table = None
        self.mono = False
        self.data = None
        self.sort_index = None
        self.last_table = 'split'
        self.sort_reversed = False
        self.empty_row = 4
        self.refresh = False
        self.env_data = None
        self.frozen = False

    def add_table(self, table):
        table.screen = self
        self.tables.append(table)

    def add_help_table(self, table):
        table.screen = self
        self.tables.append(table)
        self.help_table = table

    def start_screen(self, poller, env_data, refresh, mono=False,
                     default_table='split'):
        self.mono = mono
        self.env_data = env_data
        self.refresh = refresh
        term.hide_cursor()
        self.turn_on_table(default_table)

        # Timeout at 2 hours of inactivity
        self.idle_time = datetime.now()
        timediff = timedelta(hours=2)
        while (datetime.now() - self.idle_time) < timediff:
            try:
                self.get_data(poller)
                if not self.data:
                    return
                self.draw('instances')
                term.reset_terminal()
                if not refresh:
                    return
                should_exit = self.handle_input()
                if should_exit:
                    return

            except IOError as e:
                if e.errno == errno.EINTR:  # Sometimes thrown while sleeping
                    continue
                else:
                    raise

    def get_data(self, poller):
        if not self.frozen:
            self.data = poller.get_fresh_data()

    def draw(self, key):
        """Formats and draws banner and tables in screen.
        :param key is 'instances' for health tables and 'app_versions' for versions table.
        """
        self.data = self.sort_data(self.data)
        n = term.height() - 1
        n = self.draw_banner(n, self.data)
        term.echo_line()
        n -= 2  # Account for empty lines before and after tables
        visible_count = 0
        for table in self.tables:
            if table.visible:
                visible_count += 1
                n -= table.header_size
        if visible_count != 0:
            visible_rows = n // visible_count
            if visible_rows > 0:  # Dont show tables if no visible rows.
                self.max_columns = max([len(t.columns)
                                        for t in self.tables if t.visible]) - 1
                for table in self.tables:
                    table.draw(visible_rows, self.data[key])

        self.show_help_line()

    def handle_input(self):
        t = term.get_terminal()
        with t.cbreak():  # Get input
            val = t.inkey(timeout=.5)
            if val:
                self.idle_time = datetime.now()
                char = str(val).upper()
                LOG.debug('Got val: {0}, {1}, {2}.'
                          .format(val, val.name, val.code))
                # io.echo('Got val: {},,  {}, {}.'.format(val, val.name, val.code))
                # time.sleep(3)
                if char == 'Q':
                    if self.help_table.visible:
                        self.turn_on_table(self.last_table)
                    else:
                        return True  # Exit command
                elif char == 'X':
                    self.replace_instance_view()
                elif char == 'B':
                    self.reboot_instance_view()
                elif char == '1':
                    self.turn_on_table('split')
                elif char == '2':
                    self.turn_on_table('health')
                elif char == '3':
                    self.turn_on_table('requests')
                elif char == '4':
                    self.turn_on_table('cpu')
                elif char == '5':
                    self.turn_on_table('deployments')
                elif char == 'H':
                    self.show_help()
                elif char == 'F':
                    self.toggle_freeze()
                elif char == 'P':
                    self.snapshot_file_view()
                elif char == 'Z':
                    self.mono = not self.mono
                elif char == '>':
                    self.move_sort_column_right()
                elif char == '<':
                    self.move_sort_column_left()
                elif char == '-':
                    self.sort_reversed = True
                elif char == '+':
                    self.sort_reversed = False
                # Scrolling
                elif val.name == 'KEY_DOWN':  # Down arrow
                    self.scroll_down()
                elif val.name == 'KEY_UP':  # Up arrow
                    self.scroll_down(reverse=True)
                elif val.name == 'KEY_LEFT':  # Left arrow
                    self.scroll_over(reverse=True)
                elif val.name == 'KEY_RIGHT':  # Right arrow
                    self.scroll_over()
                elif val.name == 'KEY_END':  # End
                    for table in self.tables:
                        table.scroll_to_end()
                elif val.name == 'KEY_HOME':  # Home
                    for table in self.tables:
                        table.scroll_to_beginning()

                # If in help window (not main screen) these keys exit
                elif self.help_table.visible and val.code == 361:  # ESC KEY
                    self.turn_on_table(self.last_table)

    def turn_on_table(self, key):
        # Activate correct tables
        for table in self.tables:
            if key in {'split', table.name}:
                table.visible = True
            else:
                table.visible = False

        # Activate Help table
        if key in {'health_help'}:
            self.help_table.visible = True
        else:
            self.help_table.visible = False
            # Reset state if change in table
            if key != self.last_table:
                self.sort_index = None
                self.last_table = key

        # Reset scroll
        self.horizontal_offset = 0
        for table in self.tables:
            table.vertical_offset = 0

    def snapshot_file_view(self):
        data_repr = self.data
        current_time = datetime.now().strftime("%y%m%d-%H%M%S")
        filename = 'health-snapshot-' + current_time + '.json'
        filelocation = fileoperations.get_eb_file_full_location(filename)
        fileoperations.write_json_dict(data_repr, filelocation)

        t = term.get_terminal()
        with t.location(y=self.empty_row, x=2):
            io.echo(io.bold('Snapshot file saved at: .elasticbeanstalk/'
                            + filename), end=' ')
            sys.stdout.flush()
            time.sleep(4)

    def prompt_and_action(self, prompt_string, action):
        id = ''
        t = term.get_terminal()
        io.echo(t.normal_cursor(), end='')
        # Move cursor to specified empty row
        with t.location(y=self.empty_row, x=2), t.cbreak():
            io.echo(io.bold(prompt_string), end=' ')
            sys.stdout.flush()
            val = None
            while not val or val.name not in {'KEY_ESCAPE', 'KEY_ENTER'}:
                val = t.inkey(timeout=.5)
                if val is None:
                    continue
                elif val.is_sequence is False:
                    id += str(val)
                    sys.stdout.write(str(val))
                    sys.stdout.flush()
                elif val.name == 'KEY_DELETE':  # Backspace
                    if len(id) > 0:
                        id = id[:-1]
                        sys.stdout.write(str(t.move_left) + t.clear_eol)
                        sys.stdout.flush()

        term.hide_cursor()
        if val.name == 'KEY_ESCAPE' or not id:
            return False
        with t.location(y=self.empty_row, x=2):
            sys.stdout.flush()
            io.echo(t.clear_eol(), end='')
            try:
                should_exit_display = action(id)
                if should_exit_display is None:
                    should_exit_display = True
                return should_exit_display
            except (ServiceError, ValidationError, NotFoundError) as e:
                # Error messages that should be shown directly to user
                io.log_error(e.message)
                time.sleep(4)  # Leave screen stable for a little
                return False
            except (IndexError, InvalidOperation, ValueError) as e:
                if self.poller.all_app_versions:  # Error thrown in versions table
                    max_input = len(self.poller.all_app_versions)
                    io.log_error("Enter a number between 1 and " + str(max_input) + ".")
                else:
                    io.log_error(e)
                time.sleep(4)
                return False
            except CaughtSignal as sig:
                if sig.signum == 2:
                    LOG.debug("Caught SIGINT and exiting gracefully from action")
                    return True
            except Exception as e:  # Should never get thrown
                LOG.debug(
                    "Exception thrown: {0},{1}. Something strange happened "
                    "and the request could not be completed.".format(
                        type(e),
                        str(e)
                    )
                )
                io.log_error("Something strange happened and the request could not be completed.")
                time.sleep(4)
                return False

    def reboot_instance_view(self):
        self.prompt_and_action('instance-ID to reboot:', ec2.reboot_instance)

    def replace_instance_view(self):
        self.prompt_and_action(
            'instance-ID to replace:',
            ec2.terminate_instance
        )

    def toggle_freeze(self):
        self.frozen = not self.frozen

    def move_sort_column_right(self):
        tables = [t for t in self.tables if t.visible]
        if self.sort_index:
            table_name, column_index = self.sort_index
            table_index = _get_table_index(tables, table_name)
            if len(tables[table_index].columns) > column_index + 1:
                self.sort_index = (table_name, column_index + 1)
            elif len(tables) > table_index + 1:
                self.sort_index = (tables[table_index + 1].name, 0)
            else:
                self.sort_index = (tables[0].name, 0)
        else:
            self.sort_index = (tables[0].name, 0)

    def move_sort_column_left(self):
        tables = [t for t in self.tables if t.visible]
        if self.sort_index:
            table_name, column_index = self.sort_index
            table_index = _get_table_index(tables, table_name)
            if column_index - 1 >= 0:
                self.sort_index = (table_name, column_index - 1)
            elif table_index - 1 >= 0:
                new_sort_table = tables[table_index - 1]
                new_sort_column = len(new_sort_table.columns) - 1
                self.sort_index = (new_sort_table.name, new_sort_column)
            else:
                new_sort_table = tables[len(tables) - 1]
                new_sort_column = len(new_sort_table.columns) - 1
                self.sort_index = (new_sort_table.name, new_sort_column)
        else:
            self.sort_index = (tables[0].name, 0)

    def draw_banner_first_line(self, lines, data):
        status = data.get('HealthStatus', 'Unknown')
        refresh_time = data.get('RefreshedAt', None)
        if refresh_time is None:
            timestamp = '-'
            countdown = ' ( now )'
        else:
            timestamp = utils.get_local_time_as_string(refresh_time)
            delta = utils.get_delta_from_now_and_datetime(refresh_time)
            diff = 11 - delta.seconds
            if not self.refresh:
                countdown = ''
            elif self.frozen:
                countdown = ' (frozen +{})'.format(delta.seconds)
            elif diff < 0:
                countdown = ' ( now )'
            else:
                countdown = " ({} secs)".format(diff)
        env_name = data.get('EnvironmentName')
        pad_length = (
            term.width()
            - len(env_name)
            - len(timestamp)
            - len(countdown)
            - 1
        )
        if lines > 2:
            banner = io.bold(' {env_name}{status}{time}{cd} ') \
                .format(env_name=env_name,
                        status=status.center(pad_length),
                        time=timestamp,
                        cd=countdown,
                        )
            if not self.mono:
                banner = io.on_color(data.get('Color', 'Grey'), banner)
            term.echo_line(banner)

            lines -= 1
        return lines

    def draw_banner(self, lines, data):
        data = data['environment']
        lines = self.draw_banner_first_line(lines, data)
        return self.draw_banner_info_lines(lines, data)

    def draw_banner_info_lines(self, lines, data):
        if lines > 2:
            tier_type = self.env_data['Tier']['Name']
            tier = '{}'.format(tier_type)

            try:
                platform_arn = self.env_data['PlatformArn']
                platform_version = PlatformVersion(platform_arn)
                platform = ' {}/{}'.format(
                    platform_version.platform_shorthand,
                    platform_version.platform_version
                )
            except KeyError:
                solutionstack = SolutionStack(self.env_data['SolutionStackName'])
                platform = ' {}'.format(solutionstack.platform_shorthand)

            term.echo_line('{tier}{pad}{platform} '.format(
                tier=tier,
                platform=platform,
                pad=' '*(term.width() - len(tier) - len(platform))
            ))

            lines -= 1
        if lines > 3:
            # Get instance health count
            instance_counts = OrderedDict([
                ('total', data.get('Total', 0)),
                ('ok', data.get('Ok', 0)),
                ('warning', data.get('Warning', 0)),
                ('degraded', data.get('Degraded', 0)),
                ('severe', data.get('Severe', 0)),
                ('info', data.get('Info', 0)),
                ('pending', data.get('Pending', 0)),
                ('unknown', data.get('Unknown', 0) + data.get('NoData', 0)),
            ])
            column_size = max(len(k) for k in instance_counts) + 1
            term.echo_line(
                ''.join((s.center(column_size) for s in instance_counts))
            )
            term.echo_line(
                ''.join(
                    (
                        io.bold((str(v).center(column_size)))
                        for k, v in six.iteritems(instance_counts)
                    )
                )
            )
            lines -= 2

        return lines

    def scroll_down(self, reverse=False):
        visible_tables = [t for t in self.tables if t.visible]

        if len(visible_tables) < 1:
            return

        # assumes the first table will always be the largest
        if not visible_tables[0].data:
            return

        # Scroll first table
        scrolled = visible_tables[0].scroll_down(reverse=reverse)
        if scrolled:
            for i in range(1, len(visible_tables)):
                assert len(visible_tables[0].data) >= len(visible_tables[i].data),'First table should be the largest'
                visible_tables[i].scroll_to_id(scrolled, reverse=reverse)

    def scroll_over(self, reverse=False):
        if reverse and self.horizontal_offset > 0:
            self.horizontal_offset -= 1
        elif not reverse:
            # remove bounds check on upper limit to allow for text scrolling in causes
            self.horizontal_offset += 1

    def show_help(self):
        self.turn_on_table('health_help')

    def show_help_line(self):
        if self.help_table.visible:
            text = '(press Q or ESC to return)'
        elif self.refresh:
            text = u' (Commands: {h}elp,{q}uit, {down} {up} {left} {right})'\
                .format(h=io.bold('H'), q=io.bold('Q'),
                        down=term.DOWN_ARROW, up=term.UP_ARROW,
                        left=term.LEFT_ARROW, right=term.RIGHT_ARROW)
        else:
            text = u''
        term.echo_line(text)
        term.echo_line(term.clear_eos())

    def sort_data(self, data):
        new_data = copy(data)
        if self.sort_index:
            table_name, column_index = self.sort_index
            sort_table = next((t for t in self.tables if t.name == table_name))
            sort_key = sort_table.columns[column_index].sort_key

            new_data['instances'].sort(key=lambda x: x.get(sort_key, '-'),
                                       reverse=self.sort_reversed)
        return new_data


def _get_table_index(tables, table_name):
    for i, table in enumerate(tables):
        if table.name == table_name:
            return i
    return 0
