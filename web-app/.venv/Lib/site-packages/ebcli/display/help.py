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


from ebcli.core import io
from ebcli.display.table import Table, Column
from ebcli.display import term


class HelpTable(Table):
    def __init__(self):
        super(HelpTable, self).__init__('help')
        self.visible = False
        self.columns = [
            Column('Key', 18, 'key', 'none'),
            Column('Action', 0, 'action', 'none'),
        ]
        self.data = []
        self.set_up_help_data_rows()

    def set_data(self, table_data):
        pass

    def set_up_help_data_rows(self):
        self.set_up_standard_rows()
        self.set_up_views()
        self.add_help_text(['H'], 'This help menu')
        self.add_section('')

    def set_up_standard_rows(self):
        self.add_help_text(['up', 'down', 'home', 'end'], 'Scroll vertically')
        self.add_help_text(['left', 'right'], 'Scroll horizontally')
        self.add_help_text(['F'], 'Freeze/unfreeze data')
        self.add_help_text(['X'], 'Replace instance')
        self.add_help_text(['B'], 'Reboot instance')
        self.add_help_text(['<', '>'], 'Move sort column left/right')
        self.add_help_text(['-', '+'], 'Sort order descending/ascending')
        self.add_help_text(['P'], 'Save health snapshot data file')
        self.add_help_text(['Z'], 'Toggle color/mono mode')
        self.add_help_text(['Q'], 'Quit this program')

    def set_up_views(self):
        self.add_section('')
        self.add_section('Views')
        self.add_help_text(['1'], 'All tables/split view')
        self.add_help_text(['2'], 'Health status table')
        self.add_help_text(['3'], 'Request summary table')
        self.add_help_text(['4'], 'CPU%/Load table')
        self.add_help_text(['5'], 'Deployment summary table')

    def add_section(self, section_name):
        self.add_help_line(term.underlined(section_name), ' ')

    def add_help_text(self, keys, action_text):
        line = ','.join(keys)
        justify_length = self.columns[0].size - len(line)
        for index, key in enumerate(keys):
            keys[index] = io.bold(key)
        line = ','.join(keys) + ' '*justify_length
        self.add_help_line(line, action_text)

    def add_help_line(self, key, action):
        self.data.append({'key': key, 'action': action})


class ViewlessHelpTable(HelpTable):
    def set_up_views(self):
        pass
