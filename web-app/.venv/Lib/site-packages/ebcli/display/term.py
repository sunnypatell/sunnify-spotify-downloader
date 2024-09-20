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

"""
Dynamic IO / Interactive terminal
"""

import sys
import time

import colorama
from cement.core.exc import CaughtSignal
from cement.utils.misc import minimal_logger

from ebcli.core import io, ebglobals

LOG = minimal_logger(__name__)

terminal = None
counter = 0
total = 1

# Special characters
UP_ARROW = 'Up' if sys.platform.startswith('win') else u'\u25b2'
DOWN_ARROW = 'Dn' if sys.platform.startswith('win') else u'\u25bc'
LEFT_ARROW = 'Left' if sys.platform.startswith('win') else u'\u25c4'
RIGHT_ARROW = 'Right' if sys.platform.startswith('win') else u'\u25ba'


def get_terminal():
    if terminal is None:
        init_terminal()
    return terminal


def init_terminal():
    global terminal
    if terminal:
        return
    else:
        if sys.platform.startswith('win'):
            terminal = WindowsTerminal()

        else:
            from blessed import Terminal
            terminal = Terminal()

        io.echo(terminal.clear())


def reset_terminal():
    global counter, total
    total = counter
    counter = 0


def height():
    init_terminal()
    return terminal.height


def width():
    init_terminal()
    return terminal.width


def underline():
    init_terminal()
    if isinstance(terminal, WindowsTerminal):
        return ''
    else:
        return terminal.underline


def reverse_():
    init_terminal()
    if isinstance(terminal, WindowsTerminal):
        return colorama.Back.WHITE + colorama.Fore.BLACK
    else:
        return terminal.reverse


def underlined(string):
    init_terminal()
    return terminal.underline(string)


def reverse_colors(string):
    init_terminal()
    return terminal.reverse(string)


def echo_line(*strings):
    global counter
    # if total and counter < total:
    echo_on_line(counter, *strings)
    counter += 1


def clear_eos():
    init_terminal()
    if term_is_live():
        return terminal.clear_eos()
    else:
        return ''


def hide_cursor():
    init_terminal()
    io.echo(terminal.hide_cursor(), end='')


def return_cursor_to_normal():
    init_terminal()
    if term_is_live():
        move_cursor(total-1, 1)
    io.echo(terminal.normal_cursor())


def term_is_live():
    if not sys.stdout.isatty():  # pipe
        return False
    if ebglobals.app.pargs.debug:  # Debug mode. Don't overwrite anything
        return False
    return True


def echo_on_line(line_num, *strings):
    init_terminal()
    if term_is_live():
        with terminal.location(x=0, y=line_num):
            io.echo(terminal.clear_eol())
        with terminal.location(x=0, y=line_num):
            io.echo(*strings)
    else:
        io.echo(*strings)


def get_key(timeout=None):
    init_terminal()
    with terminal.cbreak():
        return terminal.inkey(timeout=timeout)


def move_cursor(line_num, column_num):
    io.echo(terminal.move(line_num, column_num), end='')


class WindowsTerminal(object):
    def __init__(self):
        colorama.init()
        self.win32 = colorama.win32
        self.normal = colorama.Style.RESET_ALL
        self.bold = colorama.Style.BRIGHT

    @property
    def height(self):
        return self.get_terminal_size()[0]-1

    @property
    def width(self):
        return self.get_terminal_size()[1]-1

    def clear(self):
        return '\033[2J\033[1;1f'

    def get_terminal_size(self):
        import shutil
        try:
            size = shutil.get_terminal_size()
            return size.lines, size.columns
        except AttributeError:
            screen = self._get_screen_info()
            window = screen.srWindow
            h = window.Bottom - window.Top
            w = window.Right - window.Left

            return h or 80, w or 25

    def _get_screen_info(self):
        return self.win32.GetConsoleScreenBufferInfo()

    def _get_cursor_pos(self):
        csbi = self._get_screen_info()
        position = csbi.dwCursorPosition
        return position.X, position.Y

    def _get_view_borders(self):
        csbi = self._get_screen_info()
        window = csbi.srWindow
        return window.Top, window.Left, window.Bottom, window.Right

    def underline(self, string):
        LOG.debug('Windows does not support underline. Doing nothing')
        return string

    def reverse(self, string):
        """
        Windows doesn't support reverse. But since you cant change
        terminal colors on windows, we can safely assume that
        white background and black text will be a reverse
        Its not quite reverse on powershell, but it works
        """
        return io.on_color('white', io.color('black', string))

    def clear_eos(self):
        # print spaces till the end of the screen
        pos = self._get_cursor_pos()
        borders = self._get_view_borders()

        string = ''
        current_line = pos[1]
        height = borders[2] - 1

        while current_line < height:
            string += self.clear_eol() + '\n'
            current_line += 1

        return string

    def clear_eol(self):
        # print spaces till the end of the line
        size = self.get_terminal_size()
        return ' ' * (size[1] - 1)

    def hide_cursor(self):
        return ''

    def normal_cursor(self):
        return ''

    def location(self, x=0, y=0):
        """
        In order to use 'with' you need an object
         with an __enter__ and __exit__ method
        """
        class TermLocation(object):
            def __init__(self, term):
                self.term = term
                self.saved_position = None

            def __enter__(self):
                self.saved_position = self.term._get_cursor_pos()
                print(self.term.move(y, x))

            def __exit__(self, exc_type, exc_val, exc_tb):
                # Return cursor state
                print(self.term.move(self.saved_position[1], self.saved_position[0]))

        return TermLocation(self)

    def move(self, y, x):
        return '\x1b[{y};{x}H'.format(y=y+1, x=x+1)

    def cbreak(self):

        class CBreak(object):
            def __enter__(self):
                pass

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        return CBreak()

    def inkey(self, timeout=None):
        # Since get_key is a single method, we will just do the cbreak
        # and input stuff in a single method.
        # We should ever need inkey without cbreak

        if sys.version_info[0] >= 3:
            from msvcrt import kbhit, getwch as _getch
        else:
            from msvcrt import kbhit, getch as _getch

        def readInput():
            start_time = time.time()
            while True:
                if kbhit():
                    return _getch()
                if (time.time() - start_time) > timeout:
                    return None

        key = readInput()
        if not key:
            return None

        if key == '\x03':
            # Ctrl C
            raise CaughtSignal(2, None)

        elif key == '\x1c':
            # Ctrl \
            sys.exit(1)

        elif key == '\xe0':
            # Its an arrow key, get next symbol
            next_key = _getch()
            if next_key == 'H':
                return Val(name='KEY_UP', code=259)
            elif next_key == 'K':
                return Val(name='KEY_LEFT', code=260)
            elif next_key == 'P':
                return Val(name='KEY_DOWN', code=258)
            elif next_key == 'M':
                return Val(name='KEY_RIGHT', code=261)

        elif key == '\x1b':
            return Val(name='KEY_ESCAPE', code=361)
        elif key == '\x0d':
            return Val(name='KEY_ENTER', code=362)

        else:
            return Val(key=key)


class Val(object):
    # mimics terminals inkey val object
    def __init__(self, key=None, name=None, code=None):
        self.key = key
        self.name = name
        self.code = code

    def __eq__(self, other):
        if isinstance(other, Val):
            if other.name == self.name and \
                    other.code == self.code and \
                    str(other) == str(self):
                return True
        elif isinstance(other, str):
            return str(self) == other
        else:
            return False

    def __str__(self):
        return self.key or ''

    @property
    def is_sequence(self):
        return self.key is None
