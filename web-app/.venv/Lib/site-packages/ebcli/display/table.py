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

from ebcli. core import io
from ebcli.display import term

from cement.utils.misc import minimal_logger

LOG = minimal_logger(__name__)


class Table(object):
    def __init__(self, name, columns=None, screen=None):
        self.name = name
        self.columns = columns or []
        self.visible = True
        self.data = None
        self.width = None
        self.screen = screen
        self.first_column = 0
        self.vertical_offset = 0
        self.visible_rows = 0
        self.header_size = 2
        self.shift_col = 0

    def set_shift_col(self, offset):
        self.shift_col = offset

    def draw(self, num_of_rows, table_data):
        self.width = term.width()
        if not self.visible:
            return
        self.set_data(table_data)
        self.visible_rows = num_of_rows
        if self.vertical_offset > self.get_max_offset():
            self.vertical_offset = self.get_max_offset()
        self.first_column = min(self.screen.horizontal_offset + 1,
                                len(self.columns) - 1)

        self.draw_header_row()
        self.draw_rows()

    def set_data(self, table_data):
        self.data = table_data

    HEADER_SPACE_NEEDED = 16
    HEADER_WIDTH = 11
    MAX_DESCRIPTION = 100

    def draw_header_row(self):
        t = term.get_terminal()
        labels = [' ']
        width = self.width
        for c in [0] + list(range(self.first_column, len(self.columns))):
            column = self.columns[c]
            column_size = column.size
            if column_size is None:
                column_size = self.get_widest_data_length_in_column(self.columns[c]) + 2
                # special case for Description column this should be the same for all
                # description columns, allows very large descriptions that we are able
                # to scroll through.
                if column.name == 'Description' and column_size > self.MAX_DESCRIPTION:
                    column_size = self.MAX_DESCRIPTION
                column.fit_size = column_size
            header = justify_and_trim(column.name, column_size, column.justify)
            if (self.screen.sort_index and
                    self.screen.sort_index[1] == c and  # Sort column
                    self.name == self.screen.sort_index[0] and  # sort table
                    len(' '.join(labels)) < width):  # Column is on screen
                format_string = '{n}{b}{u}{data}{n}{r}'
                header = format_string.replace('{data}', header)
                width += len(format_string) - 6
            labels.append(header)

        header_text = justify_and_trim(' '.join(labels), width, 'left')

        # header title
        if header_text[-Table.HEADER_SPACE_NEEDED:].isspace():
            header_text = (header_text[:-Table.HEADER_SPACE_NEEDED] + '  {n}{b} ' +
                           justify_and_trim(self.name, Table.HEADER_WIDTH, 'right') + ' {r} ')
        header_text = header_text.format(n=t.normal, b=t.bold, u=term.underline(),
                                         r=term.reverse_())
        header_text += t.normal

        term.echo_line(term.reverse_colors(header_text))

    def draw_rows(self):
        first_row_index = self.first_row_index()
        last_row_index = self.last_row_index()

        for r in range(first_row_index, last_row_index):
            row_data = self.get_row_data(self.data[r])
            term.echo_line(' '.join(row_data))

        self.draw_info_line(first_row_index, last_row_index)

    def draw_info_line(self, first_row_index, last_row_index):
        line = u' '
        if last_row_index < len(self.data):
            # Show down arrow
            line += u' {}'.format(term.DOWN_ARROW)
        else:
            line += u'  '
        if first_row_index != 0:
            # Show up arrow
            line += u' {}'.format(term.UP_ARROW)
        term.echo_line(line)

    def first_row_index(self):
        return self.vertical_offset

    def last_row_index(self):
        return min(len(self.data),
                   self.visible_rows + self.vertical_offset)

    def get_row_data(self, data):
        row_data = [
            self.get_color_data(data)
        ]
        for c in [0] + list(range(self.first_column, len(self.columns))):
            column = self.columns[c]
            if column.key == 'Description' and self.shift_col > 0:
                c_data = self.shift_description_data(data, column)
            else:
                c_data = self.get_column_data(data, column)
            row_data.append(
                c_data
            )

        return row_data

    def get_column_data(self, data, column):
        c_data = justify_and_trim(
            self.ascii_string(data.get(column.key, '-')),
            column.size or column.fit_size,
            column.justify,
            column.key, self.shift_col)
        return c_data

    def shift_description_data(self, data, column):
        c_data = justify_and_trim(
            str(data.get(column.key, '-')[(self.shift_col):]),
            column.size or column.fit_size,
            column.justify,
            column.key, self.shift_col)
        return c_data

    def get_widest_data_length_in_column(self, column):
        max_size = len(str(column.name))
        for r in range(self.first_row_index(), self.last_row_index()):
            column_key = self.ascii_string(self.data[r].get(column.key))
            len_row_data = self.ascii_length(column_key)
            if len_row_data > max_size:
                max_size = len_row_data
        return max_size

    def ascii_string(self, data):
        try:
            return str(data)
        except UnicodeEncodeError:
            return data

    def ascii_length(self, data):
        try:
            return len(str(data))
        except UnicodeEncodeError:
            return int(len(data) * 1.5)

    def get_color_data(self, data):
        if self.screen.mono:
            return data.get('Color', ' ')[:1]
        else:
            return io.on_color(data.get('Color', 'RESET'), ' ')

    def scroll_down(self, reverse=False):
        if reverse and (self.vertical_offset > 0):
            last_id = self.get_row_id(self.first_row_index())
            self.vertical_offset -= 1
            new_id = self.get_row_id(self.first_row_index())
        elif not reverse and self.vertical_offset < self.get_max_offset():
            last_id = self.get_row_id(self.last_row_index() - 1)
            self.vertical_offset += 1
            new_id = self.get_row_id(self.last_row_index() - 1)
        else:
            return None

        if new_id != last_id:  # Return id if became visible
            return new_id
        else:
            return None

    def scroll_to_id(self, id, reverse=False):
        if id in self.get_visible_row_ids():
            return
        new_id = None
        while new_id != id:
            new_id = self.scroll_down(reverse)
            if new_id is None:
                return

    def get_max_offset(self):
        return max(len(self.data) - self.visible_rows, 0)

    def scroll_to_end(self):
        self.vertical_offset = self.get_max_offset()

    def scroll_to_beginning(self):
        self.vertical_offset = 0

    def get_row_id(self, row_index):
        try:
            row = self.data[row_index]
        except IndexError:
            raise IndexError('Can not access index:{}'.format(row_index))
        return row.get('InstanceId')

    def get_visible_row_ids(self):
        ids = set()
        for r in range(self.first_row_index(), self.last_row_index()):
            ids.add(self.data[r].get('InstanceId', ''))
        return ids


def justify_and_trim(string, justify_size, justify_side, key=None, shift_col=0):
    if justify_side == 'right':
        s = string.rjust(justify_size)
    else:
        s = string.ljust(justify_size)
        # Special case where 'Description' column needs trimming in versions table
        if key is not None and key == 'Description':
            if len(s) > justify_size:
                s = _add_arrow(s, justify_size - 1, u'\u25B6', '>')
            if shift_col > 0:
                s = _add_arrow(s, 0, u'\u25C0', '<', s[1:])
    if justify_side == 'none':
        return s
    return s[:justify_size]


def _add_arrow(string, index, arrow1, arrow2, rest_of_string=''):
    try:
        s = string[:index] + arrow1 + rest_of_string
    except UnicodeError:
        LOG.debug("Bad unicode translation.")
        s = string[:index] + arrow2
        pass
    return s


class Column(object):
    def __init__(self, name=None, size=6, key=None, justify=None, sort_key=None):
        self.name = name
        self.size = size
        self.fit_size = size
        self.key = key
        self.justify = justify
        self.sort_key = sort_key or self.key
