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
import argparse
import os
import re
import pkg_resources
import random
import string
import sys
import textwrap
import time
from datetime import datetime

from dateutil import tz, parser

from botocore.compat import six
from cement.ext.ext_logging import LoggingLogHandler
from cement.utils.misc import minimal_logger
from subprocess import Popen, PIPE, STDOUT

from ebcli.resources.strings import prompts
from ebcli.objects.exceptions import CommandError, InvalidOptionsError
from ebcli.core import io

urllib = six.moves.urllib
LOG = minimal_logger(__name__)

camel_to_snake_pattern = re.compile(r'(?<!^)(?=[A-Z])')


def camel_to_snake(string):
    return camel_to_snake_pattern.sub('_', string).lower()


def convert_dict_from_camel_to_snake(dictionary, recursive=True):
    converted_dict = dict()
    for orig_key in dictionary:
        new_key = camel_to_snake(orig_key)
        orig_value = dictionary[orig_key]
        new_value = (
            convert_dict_from_camel_to_snake(orig_value)
            if recursive and isinstance(orig_value, dict)
            else orig_value)
        converted_dict[new_key] = new_value

    return converted_dict


def pick(dictionary, keys):
    result = dict()

    for key in keys:
        if key in dictionary:
            result[key] = dictionary[key]

    return result


def prompt_for_item_in_list(lst, default=1):
    ind = prompt_for_index_in_list(lst, default)
    return lst[ind]


def prompt_for_index_in_list(lst, default=1):
    lst = list(lst)

    if default is None:
        input_text = prompts['common.inputtext']
    else:
        input_text = prompts['common.inputtext.default'].format(default)

    for x in range(0, len(lst)):
        io.echo(str(x + 1) + ')', lst[x])

    while True:
        try:
            default = default or 0
            choice = int(io.prompt(
                input_text, default=default))
            if not (0 < choice <= len(lst)):
                raise ValueError
            else:
                break
        except ValueError:
            io.echo('Sorry, that is not a valid choice. '
                    'Please choose a number between 1 and ' +
                    str(len(lst)) + '.')

    io.echo()
    return choice - 1


def get_unique_name(name, current_uniques):
    base_name = name

    number = 2
    while base_name in current_uniques:
        base_name = name + str(number)
        number += 1

    return base_name


def mask_vars(key, value):
    if (
            re.match('.*_CONNECTION_STRING', key)
            or key == 'AWS_ACCESS_KEY_ID'
            or key == 'AWS_SECRET_KEY'
    ) and value is not None:
        value = "*****"

    return key, value


def print_list_in_columns(lst):
    """
    This function is currently only intended for environmant names,
    which are guaranteed to be 23 characters or less.
    :param lst: List of env names
    """
    if sys.stdout.isatty():
        lst = list_to_columns(lst)
        for x in range(0, len(lst[0])):
            line = []
            for i in range(0, len(lst)):
                try:
                    line.append(lst[i][x])
                except IndexError:
                    pass

            io.echo_and_justify(42, *line)
    else:
        for i in lst:
            io.echo(i)


def list_to_columns(lst):
    COLUMN_NUM = 3
    assert len(lst) > COLUMN_NUM, "List size must be greater than {0}".\
        format(COLUMN_NUM)
    remainder = len(lst) % COLUMN_NUM
    column_size = len(lst) // COLUMN_NUM
    if remainder != 0:
        column_size += 1
    colunms = [[] for i in range(0, COLUMN_NUM)]
    index = 0
    stop = column_size
    for x in range(0, COLUMN_NUM):
        colunms[x] += lst[index:stop]
        index = stop
        stop += column_size
    return colunms


def url_encode(data):
    return urllib.parse.quote(data)


def get_delta_from_now_and_datetime(date):
    return datetime.now(tz.tzlocal()) - get_local_time(date)


def get_local_time(utctime):
    if isinstance(utctime, str):
        utctime = parser.parse(utctime)

    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    utctime = utctime.replace(tzinfo=from_zone)
    return utctime.astimezone(to_zone)


def get_local_time_as_string(utctime):
    localtime = get_local_time(utctime)
    return localtime.strftime("%Y-%m-%d %H:%M:%S")


def is_ssh():
    return "SSH_CLIENT" in os.environ or "SSH_TTY" in os.environ


def static_var(varname, value):
    def decorate(func):
        setattr(func, varname, value)
        return func
    return decorate


def exec_cmd(args, live_output=True):
    """
    Execute a child program (args) in a new process. Displays
    live output by default.
    :param args: list: describes the command to be run
    :param live_output: bool: whether to print live output
    :return str: child program output
    """

    LOG.debug(' '.join(args))

    process = Popen(args, stdout=PIPE, stderr=STDOUT)
    output = []

    for line in iter(process.stdout.readline, b''):
        line = line.decode('utf-8')
        if line != os.linesep:
            if live_output:
                sys.stdout.write(line)
                sys.stdout.flush()
            else:
                LOG.debug(line)

        output.append(line)

    process.stdout.close()
    process.wait()

    returncode = process.returncode
    error_msg = 'Exited with return code {}'.format(returncode)
    output_str = ''.join(output)

    if returncode:
        raise CommandError(error_msg, output_str, returncode)
    return output_str


exec_cmd_live_output = exec_cmd


def exec_cmd_quiet(args):
    return exec_cmd(args, False)


def anykey(d):
    """
    Return any key in dictionary.
    :param d: dict: dictionary
    :return object
    """
    return next(six.iterkeys(d))


def last_modified_file(filepaths):
    """
    Return the most recently modified file.
    :param filepaths: list: paths to files
    :return str
    """

    return max(filepaths, key=os.path.getmtime)


def get_data_from_url(url, timeout=20):
    return urllib.request.urlopen(url, timeout=timeout).read()


def print_from_url(url):
    result = get_data_from_url(url)
    io.echo(result)


def parse_version(version_string):
    """
    Parse string as a verison object for comparison
    Example: parse_version('1.9.2') > parse_version('1.9.alpha')
    See docs for pkg_resource.parse_version as this is just a wrapper
    """
    return pkg_resources.parse_version(version_string)


def save_file_from_url(url, location, filename):
    result = get_data_from_url(url)

    os.path.isdir(location) or os.makedirs(location)

    file_location = os.path.join(location, filename)
    with open(file_location, 'wb') as data_file:
        data_file.write(result)

    return file_location


# http://stackoverflow.com/a/5164027
def prettydate(d):
    """
    Return a human readable str of how long d was compared to now.
    :param d: datetime/float: datetime or unix timestamp
    :return str
    """

    if isinstance(d, float):
        d = datetime.utcfromtimestamp(d)

    diff = datetime.utcnow() - d
    s = diff.seconds
    if diff.days > 7 or diff.days < 0:
        return d.strftime('%d %b %y')
    elif diff.days == 1:
        return '1 day ago'
    elif diff.days > 1:
        return '{0} days ago'.format(diff.days)
    elif s <= 1:
        return 'just now'
    elif s < 60:
        return '{0} seconds ago'.format(s)
    elif s < 120:
        return '1 minute ago'
    elif s < 3600:
        return '{0} minutes ago'.format(s // 60)
    elif s < 7200:
        return '1 hour ago'
    else:
        return '{0} hours ago'.format(s // 3600)


def merge_dicts(low_priority, high_priority):
    """
    Return a new dict that is a merge of low_priority and high_priority dicts.
    When keys collide, takes the value of higher_priority dict.
    :param low_priority: dict: shallow dictionary
    :param high_priority: dict: shallow dictionary
    :return dict
    """

    result_dict = low_priority.copy()
    result_dict.update(high_priority)
    return result_dict


def check_source(value):
    match = re.match(r"([^/]+/[^/]+/[^/]+)", value)
    if match is None or len(value.split("/")) > 3:
        raise argparse.ArgumentTypeError(
            "%s is a invalid source. Example source would be something like: codecommit/repo/branch" % value)
    return value


def parse_source(source):
    source_location, repository, branch = None, None, None
    if source:
        split_source = source.split('/')
        source_location = split_source[0].lower()
        raise_if_source_location_is_not_codecommit(source_location)

        if len(split_source) > 1:
            repository = split_source[1]
            branch = '/'.join(split_source[2:])

    return source_location, repository, branch


def raise_if_source_location_is_not_codecommit(source_location):
    if source_location != 'codecommit':
        raise InvalidOptionsError(
            'Source location "{0}" is not supported by the EBCLI'.format(source_location)
        )


def encode_to_ascii(unicode_value):
    empty_string = ""
    if unicode_value is None:
        return empty_string
    return unicode_value.encode('ascii', 'ignore')


def decode_bytes(value):
    if sys.version_info[0] >= 3:
        if isinstance(value, bytes):
            try:
                value = value.decode('utf8')
            except:
                value = value.decode('utf-8', 'replace')
    return value


def monkey_patch_warn():
    def warn(self, msg, namespace=None, **kw):
        """
        Monkey-patch to call `warning` rather than `warn` on logger objects (which
        are of type `logging.Logger`) because `warn` is going to be deprecated.
        """
        kwargs = self._get_logging_kwargs(namespace, **kw)
        self.backend.warning(msg, **kwargs)
    LoggingLogHandler.warn = warn


def flatten(list_):
    """
    Method returns a new list that is a one-dimensional flattening of `list_` (recursively)
    :param list_: an object of instance-type `list` composed of zero or more elements each
                of which may in turn be n-dimensional lists.
    :return: a new list that is a one-dimensional flattening of `list_`
    """
    flattened_list = []
    for element in list_:
        if isinstance(element, list):
            flattened_list.extend(element)
        else:
            flattened_list.append(element)

    while [element for element in flattened_list if isinstance(element, list)]:
        flattened_list = flatten(flattened_list)

    return flattened_list


def left_padded_string(text, padding=0):
    """
    Method returns a modified version of `text` with `padding` number of space
    characters prepended.
    :param text: a string to prepend spaces to
    :param padding: the number of space characters to prepend to `text`
    :return: a modified version of `text` with `padding` number of space
             characters prepended.
    """
    try:
        padding = int(padding)
    except ValueError:
        padding = 0

    padding = 0 if padding < 0 else padding

    return ' ' * padding + text


def longest_string(strings):
    """
    Method returns the longest string from a list of strings
    :param strings: a list of string objects
    :return: the longest string from a `strings`
    """
    return max(strings, key=len)


def padded_line(text, padding=0):
    """
    Method returns a modified version of `text` with `padding` number of space
    characters prepended and the '\n' character appended.
    :param text: a string to prepend spaces to
    :param padding: the number of space characters to prepend to `text`
    :return: a modified version of `text` with `padding` number of space
             characters prepended.
    """
    return left_padded_string(text, padding=padding) + '\n'


def padded_list(candidate, reference_list):
    """
    Method creates a `list` where the first element is `candidate` and the rest
    `len(reference_list) - 1` elements are empty strings (''s).

    This is operation is useful when trying to construct tables where empty
    strings can represent empty cells.

    :param candidate: a list of strings
    :param reference_list: another list such that `candidate` should match it in
                           terms of number of elements
    :return: [text] + [''] * (len(reference_list) - 1)]
    """
    if not reference_list:
        raise AttributeError('The reference_list argument must be non-empty.'.format(reference_list))
    pad_length = len(reference_list) - len(candidate)
    return candidate + [''] * pad_length


def random_string(length=4):
    """
    Method generates a random 10-character string from the alphabet (downcase)
    :return: a random 10-character string from the alphabet (downcase)
    """
    return ''.join(
        [
            random.choice(string.ascii_lowercase + string.digits)
            for _ in range(length)
        ]
    )


def right_padded_string(text, padding=0):
    """
    Method returns a modified version of `text` with `padding` number of space
    characters appended.
    :param text: a string to append spaces to
    :param padding: the number of space characters to append to `text`
    :return: a modified version of `text` with `padding` number of space
             characters appended.
    """
    try:
        padding = int(padding)
    except ValueError:
        padding = 0

    padding = 0 if padding < 0 else padding

    return text + ' ' * padding


def row_wrapper(string_width_mappings, padding=3):
    """
    Method returns a wrapped version of a list of strings expected to be columnar
    fashion.
    :param string_width_mappings: a list of dicts of the form:

                {
                    'string': ...,
                    'width': ...
                }

            such as:

                [
                    {
                        'string': '2018-08-12 18:36:42',
                        'width': 19
                    },
                    {
                        'string': 'MY_RESOURCE_STATE',
                        'width': 35
                    },
                    {
                        'string': 'SomeResourceDeployment47fc2d5f9d (AWS::SomeResource::Instance)\n'
                                  'The API gateway, SomeResourceDeployment47fc2d5f9d, was successfully built',
                        'width': 67
                    },
                ]

    :param padding: the number of space characters to insert between columns
    :return: a wrapped version of row of strings expressed as a list of strings
             such that no string occupied more than the stipulated number of
             characters. For the input shown above, the following is returned:

                [
                    '2018-08-12 18:36:42   MY_RESOURCE_STATE   SomeResourceDeployment47fc2d5f9d (AWS::SomeResource::Instance)',
                    '                                          The API gateway, SomeResourceDeployment47fc2d5f9d, was        ',
                    '                                          successfully built                                            ',
                ]
    """
    wrapped_strings = list()
    longest_column = list()

    for mapping in string_width_mappings:
        wrapped_string = textwrap.wrap(mapping['string'], mapping['width'])
        if len(wrapped_string) > len(longest_column):
            longest_column = wrapped_string
        wrapped_strings.append(wrapped_string)

    number_of_columns = len(wrapped_strings)
    for i in range(number_of_columns):
        wrapped_strings[i] = padded_list(wrapped_strings[i], longest_column)
        max_width = string_width_mappings[i]['width']
        for j in range(len(wrapped_strings[i])):
            if len(wrapped_strings[i][j]) < max_width:
                wrapped_strings[i][j] = right_padded_string(
                    wrapped_strings[i][j],
                    padding=max_width - len(wrapped_strings[i][j])
                )

    __wrapped_strings = list()
    for row in range(len(longest_column)):
        __wrapped_strings += [
            (' ' * padding).join(
                [
                    column[row] for column in wrapped_strings
                ]
            )
        ]
    return __wrapped_strings


def sleep(sleep_time=5):
    time.sleep(sleep_time)


def datetime_utcnow():
    return datetime.utcnow()


def prevent_throttling():
    time.sleep(0.5)


def index_of(iterable, value, key=None):
    """
    Function returns the index of an iterable within a list.
    :param iterable: The iterable to look within
    :param value: The value to find
    :param key: A Function that is used to extract a comparison key from each list element
    """

    if key is None:
        generator = (i for i, x in enumerate(iterable) if x == value)
    elif not callable(key):
        raise TypeError("'{}' object is not callable".format(type(key).__name__))
    else:
        generator = (i for i, x in enumerate(iterable) if key(x) == value)

    return next(generator, -1)
