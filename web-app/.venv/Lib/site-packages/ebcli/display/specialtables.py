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
from copy import copy

from ebcli.core import io
from ebcli.display.table import Table, justify_and_trim
from ebcli.display import term
"""
Special table for request summary
"""


class RequestTable(Table):
    def __init__(self, name, columns=None, screen=None):
        super(RequestTable, self).__init__(name, columns, screen)
        self.header_size = 3

    def draw_header_row(self):
        super(RequestTable, self).draw_header_row()

        # now draw overall summary
        full_data = self.screen.data
        totals = full_data.get('environment')

        totals['InstanceId'] = '  Overall'
        # We can just draw a single row, but use environment data
        row_data = self.get_row_data(totals)
        term.echo_line(io.bold(' '.join(row_data)))


class StatusTable(RequestTable):

    def __init__(self, name, columns=None, screen=None):
        super(StatusTable, self).__init__(name, columns, screen)
        self.header_size = 3

    def draw(self, rows, table_data):
        data = self.expand_rows(table_data)
        super(StatusTable, self).draw(rows, data)

    CAUSE_SCROLL_FACTOR = 5

    def get_column_data(self, data, column):
        if data.get('Copy', False) and column.key != 'Cause':
            d = ' '
        else:
            d = str(data.get(column.key, '-'))

        if (
            column.key == 'Cause'
            and self.screen.horizontal_offset > self.screen.max_columns
        ):
            cause_scroll = (
                self.screen.horizontal_offset
                - self.screen.max_columns
            ) * StatusTable.CAUSE_SCROLL_FACTOR
            d = d[cause_scroll:]

        c_data = justify_and_trim(
            d,
            column.size or column.fit_size,
            column.justify)
        if 'Overall' in data.get('InstanceId'):
            c_data = io.bold(c_data)
        return c_data

    def expand_rows(self, data):
        new_data = list()
        total = copy(self.screen.data['environment'])
        total['InstanceId'] = '  Overall'
        causes = total.get('Causes', [])
        for i in range(1, len(causes)):
            c = causes[i]
            total_copy = copy(total)
            total_copy['Cause'] = c
            total_copy['Copy'] = True
            new_data.append(total_copy)

        for instance in data:
            new_data.append(instance)
            causes = instance.get('Causes', [])
            for i in range(1, len(causes)):
                c = causes[i]
                instance_copy = copy(instance)
                instance_copy['Cause'] = c
                instance_copy['Copy'] = True
                new_data.append(instance_copy)
        return new_data
