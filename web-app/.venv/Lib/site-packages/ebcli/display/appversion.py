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
import errno
import locale
import sys
import time

from datetime import datetime, timedelta
from cement.utils.misc import minimal_logger
from botocore.compat import six

from ebcli.display.data_poller import format_time_since, DataPoller
from ebcli.display.screen import Screen
from ebcli.core import io
from ebcli.display import term
from ebcli.lib import elasticbeanstalk as elasticbeanstalk
from ebcli.lib.utils import get_local_time
from ebcli.resources.strings import prompts
from ebcli.operations.lifecycleops import interactive_update_lifcycle_policy

Queue = six.moves.queue.Queue
LOG = minimal_logger(__name__)


class VersionScreen(Screen):
    APP_VERSIONS_TABLE_NAME = 'appversion'

    def __init__(self, poller=None):
        super(VersionScreen, self).__init__()
        self.empty_row = 3
        self.poller = poller
        self.request_id = None

    def draw_banner_first_line(self, lines, data):
        if lines > 2:
            app_name = 'Application Name: {}'.format(self.poller.app_name)
            env_name = self.poller.env_name

            if env_name is None:
                env_name = 'No Environment Specified'

            pad_length = term.width() - len(env_name)

            banner = io.bold(' {env_name}{app_name} ') \
                .format(env_name=env_name,
                        app_name=app_name.center(pad_length),
                        )
            if not self.mono:
                banner = io.on_color(data.get('Color', 'Grey'), banner)
            term.echo_line(banner)

            lines -= 1
        return lines

    def draw_banner_info_lines(self, lines, data):
        if lines > 2:
            status = data.get('Status', 'Unknown')
            term.echo_line('Environment Status:', io.bold(status),
                           'Health', io.bold(data.get('Color', 'Unknown')))
            lines -= 1
        if lines > 2:
            term.echo_line('Current version # deployed:',
                           io.bold(data.get('CurrDeployNum', None)),
                           )
            lines -= 1

        return lines

    def start_version_screen(self, data, table):
        """"Turn on and populate table 'versions' in screen with data"""
        pages = True
        term.hide_cursor()
        self.turn_on_table(table)
        self.data = data
        if not pages:
            self.draw('app_versions')
            term.reset_terminal()
        else:
            # Timeout at 19 minutes of inactivity since API's NextToken disappears at 20
            self.idle_time = datetime.now()
            timediff = timedelta(minutes=19)
            while (datetime.now() - self.idle_time) < timediff:
                try:
                    self.draw('app_versions')
                    term.reset_terminal()
                    should_exit = self.handle_input()
                    if should_exit:
                        return

                except IOError as e:
                    if e.errno == errno.EINTR:  # Sometimes thrown while sleeping
                        continue
                    else:
                        raise

    def show_help_line(self):
        text = u' (Commands: {q}uit, {d}elete, {l}ifecycle, {down} {up} {left} {right})'.format(
            q=io.bold('Q'),
            d=io.bold('D'),
            l=io.bold('L'),
            down=term.DOWN_ARROW,
            up=term.UP_ARROW,
            left=term.LEFT_ARROW,
            right=term.RIGHT_ARROW
        )
        term.echo_line(text)

    def handle_input(self):
        t = term.get_terminal()
        with t.cbreak():  # Get input
            val = t.inkey(timeout=.5)
            if val:
                char = str(val).upper()
                LOG.debug('Got val: {0}, {1}, {2}.'
                          .format(val, val.name, val.code))
                if char == 'Q':  # Quit
                    return True  # Exit command
                elif val.code == 361:
                    return True
                # elif char == 'R':
                #     return self.redeploy(t)
                elif char == 'D':
                    return self.delete(t)
                elif char == 'L':
                    return self.interactive_lifecycle(t)
                elif val.name == 'KEY_DOWN':  # Down arrow
                    self._get_more_pages(t)
                elif val.name == 'KEY_UP':  # Up arrow
                    self._get_less_pages(t)
                elif val.name == 'KEY_LEFT':  # Left arrow
                    self.scroll_over(reverse=True)
                elif val.name == 'KEY_RIGHT':  # Right arrow
                    self.scroll_over()

    MAX_SHIFT = 99
    LENGTH_SHIFT = 3

    def scroll_over(self, reverse=False):
        table = self.tables[0]

        if reverse and table.shift_col > 0:
            self.tables[0].shift_col -= self.LENGTH_SHIFT
        elif not reverse and table.shift_col < self.MAX_SHIFT:
            # check if "Description" column data is long enough for scrolling
            if table.get_widest_data_length_in_column(table.columns[4]) > self.MAX_SHIFT - 10:
                table.shift_col += self.LENGTH_SHIFT

    def _get_more_pages(self, t):
        self.data = self.poller.get_next_page_data()
        self.tables[0].shift_col = 0
        self.flusher(t)

    def _get_less_pages(self, t):
        self.data = self.poller.get_previous_page_data()
        self.tables[0].shift_col = 0
        self.flusher(t)

    def delete(self, t):
        """Return true upon successful completion, false if there was an exception"""
        save = self.prompt_and_action(
            prompts['appversion.delete.prompt'].format(
                len(self.poller.all_app_versions)
            ),
            self.delete_app_version_num
        )
        self.flusher(t)
        return save

    def interactive_lifecycle(self, t):
        """Always return back to the table"""
        self.flusher(t)
        io.echo('\n')
        interactive_update_lifcycle_policy(self.poller.app_name)
        time.sleep(4)

    def flusher(self, t):
        with t.location(y=self.empty_row, x=0):
            sys.stdout.flush()
            io.echo(t.clear_eos(), '')
            return

    def delete_app_version_num(self, version_number):
        """Take in user input as a string,
        convert it to a decimal,
        get the version-label that the user input matches,
        and attempt to delete that version.
        """
        version_number = int(version_number)  # raises InvalidOperation Exception
        app_versions = self.poller.all_app_versions
        v_len = len(app_versions)
        if version_number > v_len or version_number < 1:
            raise IndexError
        app_version = app_versions[v_len - version_number]
        version_label = app_version.get(u'VersionLabel')

        from ebcli.operations import appversionops
        should_exit_table = appversionops.delete_app_version_label(self.poller.app_name, version_label)
        time.sleep(4)
        return should_exit_table


class VersionDataPoller(DataPoller):
    def __init__(self, app_name, env_name, all_app_versions):
        super(VersionDataPoller, self).__init__(app_name, env_name)
        self.next_token = None
        self.history = []
        self.curr_page = 0

        self.all_app_versions = all_app_versions
        self.app_versions = []
        self.list_len_left = len(all_app_versions)

        self.env = None
        self.curr_deploy_num = None
        self.env_data = {}

        if self.env_name is not None:
            # If we have a default environment, save current env status into env_data
            self.env = elasticbeanstalk.get_environment(app_name=self.app_name, env_name=self.env_name)
            self.curr_deploy_num = self.get_curr_deploy_num()
            self.env_data = self.get_env_data()

    PAGE_LENGTH = 10

    def get_version_data(self):
        """
        Gets app_versions data by pages. Pages that were already accessed would be
        stored in history

        Then modifies app_versions: add SinceCreated field and format DateCreated
        field for each version in app_versions. Paginates, so appends PAGE_LENGTH
        versions with each call

        :returns data object with two keys: environment and app_versions
        note: environment data would be None if no environment is specified
        """

        if self.list_len_left <= 0:
            return self.get_table_data()

        if self.next_token:
            response = elasticbeanstalk.get_application_versions(
                self.app_name,
                None,
                self.PAGE_LENGTH,
                self.next_token
            )
        else:
            response = elasticbeanstalk.get_application_versions(
                self.app_name,
                None,
                self.PAGE_LENGTH
            )

        new_page_versions = response['ApplicationVersions']
        self.next_token = None
        if u'NextToken' in response:
            self.next_token = response['NextToken']

        self.prep_version_data(new_page_versions)
        self.history.append(self.app_versions)
        self.curr_page += 1

        return self.get_table_data()

    def prep_version_data(self, page_table_data):
        if self.list_len_left < self.PAGE_LENGTH:
            page_range = self.list_len_left
        else:
            page_range = self.PAGE_LENGTH
        for x in range(page_range):
            page_table_data[x]['DeployNum'] = self.list_len_left - x
            if isinstance(page_table_data[x][u'DateCreated'], datetime):
                page_table_data[x][u'SinceCreated'] = format_time_since(page_table_data[x][u'DateCreated'])
                page_table_data[x][u'DateCreated'] = get_local_time(page_table_data[x][u'DateCreated']) \
                    .strftime("%Y/%m/%d %H:%M")
            else:
                page_table_data[x][u'SinceCreated'] = None
                page_table_data[x][u'DateCreated'] = None
        self.list_len_left -= page_range
        self.app_versions = page_table_data

    def get_next_page_data(self):
        if self.curr_page < len(self.history):  # page cached in local memory
            self.curr_page += 1
            self.app_versions = self.history[self.curr_page - 1]
            data = self.get_table_data()
        else:  # must retrieve next page of paginated data
            data = self.get_version_data()
        return data

    def get_previous_page_data(self):
        if self.curr_page > 1:
            self.curr_page -= 1
            self.app_versions = self.history[self.curr_page - 1]
        return self.get_table_data()

    def get_env_data(self):
        return {'EnvironmentName': self.env.name,
                'Color': self.env.health,
                'Status': self.env.status,
                'CurrDeployNum': self.curr_deploy_num,
                }

    def get_table_data(self):
        return {'environment': self.env_data,
                'app_versions': self.app_versions
                }

    def get_curr_deploy_num(self):
        curr_deploy_num = 0
        for x in range(len(self.all_app_versions)):
            if self.all_app_versions[x][u'VersionLabel'] == self.env.version_label:
                curr_deploy_num = len(self.all_app_versions) - x
                break
        return curr_deploy_num
