# Copyright 2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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

import re
import warnings
import getpass
import sys
import logging

import colorama
import pydoc
from botocore.compat import six
from six import print_
from six.moves import input

from ebcli.core import ebglobals
from ebcli.objects.exceptions import ValidationError
from ebcli.resources.strings import prompts, strings

LOG = logging.getLogger(__name__)


def term_is_colorable():
    return sys.stdout.isatty()


def bold(string):
    s = _convert_to_string(string)
    if term_is_colorable():
        colorama.init()
        return colorama.Style.BRIGHT + s + colorama.Style.NORMAL
    else:
        return s


def _remap_color(color):
    if color.upper() == 'ORANGE':
        return 'YELLOW'
    if color.upper() in {'GREY', 'GRAY'}:
        return 'WHITE'
    return color


def color(color, string):
    s = _convert_to_string(string)
    if term_is_colorable():
        colorama.init()
        color = _remap_color(color)
        color_code = getattr(colorama.Fore, color.upper())
        return color_code + s + colorama.Fore.RESET
    else:
        return s


def on_color(color, string):
    s = _convert_to_string(string)
    if term_is_colorable():
        colorama.init()
        color = _remap_color(color)
        color_code = getattr(colorama.Back, color.upper())
        return color_code + s + colorama.Back.RESET
    else:
        return s


def echo_and_justify(justify, *args):
    s = ''.join(s.ljust(justify) for s in _convert_to_strings(args))
    print_(s.rstrip())


def echo(*args, **kwargs):
    if 'sep' not in kwargs:
        kwargs['sep'] = ' '
    print_(*_convert_to_strings(args), **kwargs)


def _convert_to_strings(list_of_things):
    for data in list_of_things:
        yield _convert_to_string(data)


def _convert_to_string(data):
    scalar_types = six.string_types + six.integer_types
    if isinstance(data, six.binary_type):
        if sys.version_info[0] >= 3:
            return data.decode('utf8')
        else:
            return data
    elif isinstance(data, six.text_type):
        if sys.version_info[0] >= 3:
            return data
        else:
            try:
                return data.encode('utf8')
            except:
                return data.encode('utf8', 'replace')
    elif isinstance(data, scalar_types) or hasattr(data, '__str__'):
        return str(data)
    else:
        LOG.error('echo called with an unsupported data type')
        LOG.debug('data class = ' + data.__class__.__name__)


def log_alert(message):
    echo('Alert:', message)


def log_info(message):
    try:
        ebglobals.app.log.info(message)
    except AttributeError:
        echo('INFO: {}'.format(message))


def log_warning(message):
    try:
        ebglobals.app.log.warn(message)
    except AttributeError:
        echo(bold(color('red', 'WARN: {}'.format(message))))


def log_error(message):
    try:
        if ebglobals.app.pargs.debug:
            ebglobals.app.log.error(message)
        else:
            echo(bold(color('red', 'ERROR: {}'.format(message))))
    except AttributeError:
        echo(bold(color('red', 'ERROR: {}'.format(message))))


def get_input(output, default=None):
    try:
        import readline
    except ImportError:
        pass

    output = next(_convert_to_strings([output]))
    result = _get_input(output)

    return result or default


def _get_input(output):
    return input(output + ': ').strip()


def echo_with_pager(output):
    pydoc.pager(output)


def prompt(output, default=None):
    return get_input('(' + output + ')', default)


def prompt_for_unique_name(default, unique_list):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')

        assert default not in unique_list, 'Default name is not unique'

        while True:
            result = prompt('default is "' + default + '"', default=default)
            if result in unique_list:
                echo('Sorry that name already exists, try another.')
            else:
                break

        return result


def prompt_for_environment_name(default_name='myEnv',
                                prompt_text='Enter Environment Name'):
    """ Validate env_name: Spec says:
     Constraint: Must be from 4 to 40 characters in length.
       The name can contain only letters, numbers, and hyphens.
      It cannot start or end with a hyphen.
    """
    constraint_pattern = '^[a-z0-9][a-z0-9-]{2,38}[a-z0-9]$'

    if not re.match(constraint_pattern, default_name):
        if not re.match('^[a-zA-Z0-9].*', default_name):
            default_name = 'eb-' + default_name
        default_name = default_name.replace('_', '-')
        default_name = re.sub('[^a-z0-9A-Z-]', '', default_name)
        if len(default_name) > 40:
            default_name = default_name[:39]
        if not re.match('.*[a-zA-Z0-9]$', default_name):
            default_name += '0'

    while True:
        echo(prompt_text)
        env_name = prompt('default is ' + default_name)
        if not env_name:
            return default_name
        if re.match(constraint_pattern, env_name.lower()):
            break
        else:
            echo('Environment name must be 4 to 40 characters in length. It '
                 'can only contain letters, numbers, and hyphens. It can not '
                 'start or end with a hyphen')

    return env_name


def get_pass(output):
    while True:
        result = getpass.getpass(output + ': ')
        if result == getpass.getpass('Retype password to confirm: '):
            return result
        else:
            echo()
            log_error('Passwords do not match')


def validate_action(output, expected_input):
    result = get_input(output)

    if result != expected_input:
        raise ValidationError(prompts['terminate.nomatch'])


def prompt_for_cname(default=None):
    while True:
        echo('Enter DNS CNAME prefix')
        if default:
            cname = prompt('default is ' + default)
        else:
            cname = prompt('defaults to an auto-generated value')
        if not cname:
            return default
        if re.match('^[a-z0-9][a-z0-9-]{2,61}[a-z0-9]$', cname.lower()):
            break
        else:
            echo('CNAME must be 4 to 63 characters in length. It can'
                 ' only contain letters, numbers, and hyphens. It can not '
                 'start or end with a hyphen')

    return cname


def update_upload_progress(progress):
    """
    Displays or updates a console progress bar
    :param progress: Accepts a float between 0 and 1.
        Any int will be converted to a float.
        A value under 0 represents a 'halt'.
        A value at 1 or bigger represents 100%
    """
    barLength = 50  # Modify this to change the length of the progress bar
    status = ""
    if isinstance(progress, int):
        progress = float(progress)
    if not isinstance(progress, float):
        progress = 0
        status = "error: progress var must be float\r\n"
    if progress < 0:
        progress = 0
        status = "Halt...\r\n"
    if progress >= 1:
        progress = 1
        status = "Done...\r\n"
    block = int(round(barLength*progress))
    progress = int(round(progress * 100))
    text = "\rUploading: [{0}] {1}% {2}".format(
        "#"*block + "-"*(barLength-block), progress, status)
    sys.stdout.write(text)
    sys.stdout.flush()


def get_boolean_response(text=None, default=True):
    if not isinstance(default, bool):
        raise TypeError('get_boolean_response() named argument \'default\' must '
                        'be a bool, not {}'.format(type(default).__name__))

    prompt_message = ''
    default_string = 'y' if default else 'n'
    prompt_value_options = '(Y/n)' if default else '(y/N)'

    if text:
        prompt_message = text + ' '

    prompt_message += prompt_value_options
    response = get_input(prompt_message, default=default_string).lower()

    while response not in ('y', 'n', 'yes', 'no'):
        echo(
            strings['prompt.invalid'],
            strings['prompt.yes-or-no']
        )
        response = get_input(prompt_value_options, default=default_string).lower()

    if response in ('y', 'yes'):
        return True
    else:
        return False


def get_event_streamer():
    if sys.stdout.isatty():
        return EventStreamer()
    else:
        return PipeStreamer()


class EventStreamer(object):
    def __init__(self):
        self.prompt = strings['events.streamprompt']
        self.unsafe_prompt = strings['events.unsafestreamprompt']
        self.eventcount = 0

    def stream_event(self, message, safe_to_quit=True):
        """
        Streams an event so a prompt is displayed at the bottom of the stream
        :param safe_to_quit: this determines which static event prompt to show to the user
        :param message: message to be streamed
        """
        length = len(self.prompt)
        echo('\r', message.ljust(length), sep='')
        if safe_to_quit:
            echo(self.prompt, end='')
        else:
            echo(self.unsafe_prompt, end='')

        sys.stdout.flush()
        self.eventcount += 1

    def end_stream(self):
        """
         Removes the self.prompt from the screen
        """
        if self.eventcount < 1:
            return
        length = len(self.prompt) + 3  # Cover up "^C" character as well
        print_('\r'.ljust(length))


class PipeStreamer(EventStreamer):
    """ Really just a wrapper for EventStreamer
    We dont want to actually do any "streaming" if
    a pipe is being used, so we will just use standard printing
    """
    def stream_event(self, message, safe_to_quit=True):
        echo(message)

    def end_stream(self):
        return
