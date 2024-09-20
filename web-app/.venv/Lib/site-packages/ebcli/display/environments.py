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

from ebcli.lib.utils import get_local_time
from ebcli.resources.strings import prompts, responses
from ebcli.display import term
from ebcli.core import io

from datetime import datetime, timedelta
from cement.utils.misc import minimal_logger
from botocore.compat import six
from ebcli.display.data_poller import format_time_since, DataPoller
from ebcli.display.screen import Screen
from ebcli.lib import utils
from ebcli.objects.exceptions import NotFoundError, ValidationError
from ebcli.resources.strings import strings

Queue = six.moves.queue.Queue
LOG = minimal_logger(__name__)
TABLE_DATA_KEY = 'environments'


class EnvironmentScreen(Screen):
    def __init__(self, poller=None, header_text='Environments'):
        super(EnvironmentScreen, self).__init__()
        self.empty_row = 1
        self.poller = poller
        self.request_id = None
        self.header_text = header_text

    def draw_banner_info_lines(self, lines):
        if lines > 2:
            term.echo_line(self.header_text)
            lines -= 1
        return lines

    def draw_banner(self, lines, data):
        return self.draw_banner_info_lines(lines)

    def start_version_screen(self, data, table):
        """"Turn on and populate table 'environments' in screen with data"""
        pages = True
        term.hide_cursor()
        self.turn_on_table(table)
        self.data = data
        if not pages:
            self.draw(TABLE_DATA_KEY)
            term.reset_terminal()
        else:
            # Timeout at 19 minutes of inactivity since API's NextToken disappears at 20
            self.idle_time = datetime.now()
            timediff = timedelta(minutes=19)
            while (datetime.now() - self.idle_time) < timediff:
                try:
                    self.draw(TABLE_DATA_KEY)
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
        text = u' (Commands: {q}uit, {r}estore, {down} {up})' \
            .format(q=io.bold('Q'), r=io.bold('R'),
                    down=term.DOWN_ARROW, up=term.UP_ARROW)
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
                elif char == 'R':
                    return self.restore(t)
                elif val.name == 'KEY_DOWN':  # Down arrow
                    self._get_more_pages(t)
                elif val.name == 'KEY_UP':  # Up arrow
                    self._get_less_pages(t)

    MAX_SHIFT = 99
    LENGTH_SHIFT = 3

    def _get_more_pages(self, t):
        self.data = self.poller.get_next_page_data()
        self.tables[0].shift_col = 0
        self.flusher(t)

    def _get_less_pages(self, t):
        self.data = self.poller.get_previous_page_data()
        self.tables[0].shift_col = 0
        self.flusher(t)

    def restore(self, t):
        """Return true upon successful completion, false if there was an exception"""
        save = self.prompt_and_action(prompts['restore.prompt'], self.restore_environment_num)
        self.flusher(t)
        return save

    def flusher(self, t):
        with t.location(y=self.empty_row, x=0):
            sys.stdout.flush()
            io.echo(t.clear_eos(), '')
            return

    def restore_environment_num(self, environment_number):
        """Take in user input as a string,
        convert it to a decimal,
        get the environment that the user input matches,
        and attempt to restore that environment.
        """
        environment_number = int(environment_number)  # raises InvalidOperation Exception
        environments = self.poller.all_environments
        e_len = len(environments)
        if environment_number > e_len or environment_number < 1:
            raise IndexError
        environment = environments[e_len - environment_number]
        env_id = environment.get(u'EnvironmentId')
        should_exit_display = True
        if env_id:
            self.flusher(term.get_terminal())
            prompt_text = prompts['restore.selectedenv'].format(
                env_id=env_id,
                app=utils.encode_to_ascii(environment.get('ApplicationName')),
                desc=utils.encode_to_ascii(environment.get('Description')),
                cname=utils.encode_to_ascii(environment.get('CNAME')),
                version=utils.encode_to_ascii(environment.get('VersionLabel')),
                platform=utils.encode_to_ascii(environment.get('SolutionStackName')),
                dat_term=environment.get('DateUpdated'))
            should_restore = io.get_boolean_response(prompt_text, default=True)

            if not should_restore:
                io.echo(responses['restore.norestore'])
                time.sleep(1)
                should_exit_display = False
                return should_exit_display

            from ebcli.operations import restoreops
            # restore specified environment
            self.request_id = restoreops.restore(env_id)
            return should_exit_display

        # Exception should never get thrown
        else:
            raise Exception


class EnvironmentDataPoller(DataPoller):
    max_restore_age = 42

    def __init__(self, all_environments):
        super(EnvironmentDataPoller, self).__init__(None, None)
        self.next_token = None
        self.list_len_left = len(all_environments)
        self.history = []
        self.environments = []
        self.curr_page = 0
        self.all_environments = all_environments

    PAGE_LENGTH = 10

    def get_environment_data(self):
        """
        Gets environments for the current page

        :returns data object with one keys: environment
        """

        if self.list_len_left <= 0:
            raise NotFoundError(strings['restore.no_env'])

        current_item = self.curr_page * self.PAGE_LENGTH
        new_page_environments = self.all_environments[
            current_item: current_item + self.PAGE_LENGTH
        ]
        # Modify the data to make it appropriate for output, save the environment
        # list and decrement the number of
        #   environments left to process, i.e. that are not in our cache
        self.prep_version_data(new_page_environments)
        # Append processed data to our cache
        self.history.append(self.environments)
        return self.get_table_data()

    def prep_version_data(self, page_table_data):
        """
        Modifies certain parameters of the given environments in order to display them
        nicely. This method also decrements the total number of environments left to
        process,

        :param page_table_data: list of environments to process
        """
        self.environments = []
        if self.list_len_left < self.PAGE_LENGTH:
            page_range = self.list_len_left
        else:
            page_range = self.PAGE_LENGTH
        for x in range(page_range):
            page_table_data[x]['DeployNum'] = self.list_len_left - x
            if isinstance(page_table_data[x][u'DateUpdated'], datetime):
                page_table_data[x][u'SinceCreated'] = format_time_since(page_table_data[x][u'DateUpdated'])
                page_table_data[x][u'DateUpdated'] = get_local_time(page_table_data[x][u'DateUpdated']) \
                    .strftime("%Y/%m/%d %H:%M %Z")
            else:
                page_table_data[x][u'SinceCreated'] = None
                page_table_data[x][u'DateUpdated'] = None
            self.environments.append(page_table_data[x])
        self.list_len_left -= page_range
        self.environments = page_table_data

    def get_next_page_data(self):
        """
        Either retrieves the next page of environments from the cache or processes the next page via
        @get_environment_data()

        :return: next page data, list of environments
        """
        self.curr_page += 1
        # If the customer tries to get more items than we have just return the current
        if len(self.all_environments) < self.curr_page * self.PAGE_LENGTH:
            self.curr_page -= 1
            data = self.get_table_data()
        # Page is cached in local history return that page
        elif self.curr_page < len(self.history):
            self.environments = self.history[self.curr_page]
            data = self.get_table_data()
        # Must retrieve next page from our environments
        else:
            data = self.get_environment_data()
        return data

    def get_previous_page_data(self):
        # we should always have a cache of the last page, if it's 0 then just return the current
        """
        Always retrieves previous list of environments from the cache
        :return: previous page data, list of environments
        """
        if self.curr_page > 0:
            self.curr_page -= 1
            self.environments = self.history[self.curr_page]
        return self.get_table_data()

    def get_table_data(self):
        return {
                TABLE_DATA_KEY: self.environments
                }
