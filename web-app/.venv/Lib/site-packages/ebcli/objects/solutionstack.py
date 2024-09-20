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
from collections import OrderedDict

import pkg_resources
from cement.utils.misc import minimal_logger

LOG = minimal_logger(__name__)
LANGUAGE_VERSION_REGEX = re.compile(r'\d+[.\d]*')
OS_BITNESS_REGEX = re.compile(r'^\d+')
OS_VERSION_REGEX = re.compile(r'\d{4}\.\d{2}')
PLATFORM_VERSION_REGEX = re.compile(r'v\d+\.\d+\.\d+')
PLATFORM_CLASS_REGEX = re.compile(r'running (\w.*)')
SERVER_REGEX = re.compile(r'(.*)\srunning.*')
SOLUTION_STACK_ORDER_INDEX = {
    'Node.js': 1,
    'PHP': 2,
    'Python': 3,
    'Ruby': 4,
    'Tomcat': 5,
    'IIS': 6,
    'Docker': 7,
    'Multi-container Docker': 8,
    'GlassFish': 9,
    'Go': 10,
    'Java': 11,
    'Corretto (BETA)': 12,
    'Packer': 13,
}

class SolutionStack(object):
    def __init__(self, ss_string):
        """
        :param ss_string: a string representing a solution stack returned in the
            response to the `ListAvailableSolutionStacks` API call.

            e.g '64bit Amazon Linux 2017.03 v2.7.2 running Docker 17.03.1-ce'
        """
        self.name = ss_string

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return self.__dict__ != other.__dict__

    def __lt__(self, other):
        """
        Method compares `self` with `other` SolutionStack using the a series of rules
        to determine which of the two should **appear before** the other.

        e.g.

        - Node.js SolutionStacks (SS) will appear before Ruby SS by virtue of
        their relative SOLUTION_STACK_ORDER_INDEX
        - Ruby 2.4 SS will appear before Ruby 2.3 SS
        - Python 3.4 SS will appear before Python 3.4 (Preconfigured Docker) SS
        - Tomcat 8 Java 8 SS will appear before Tomcat 8 Java 7 SS
        - v2.2.2 SS will appear before v2.2.1 SS
        - 2017.02 SS will appear before 2017.01 SS
        - 64bit SS will appear before 32bit SS

        :param other: `other` SolutionStack to compare with

        :return: `True`, if `self` is '<' `other`, else `False`
        """
        try:
            if SOLUTION_STACK_ORDER_INDEX[self.language_name] \
                    != SOLUTION_STACK_ORDER_INDEX[other.language_name]:
                return SOLUTION_STACK_ORDER_INDEX[self.language_name] \
                       < SOLUTION_STACK_ORDER_INDEX[other.language_name]

            if self.language_version != other.language_version:
                return self.language_version > other.language_version

            if 'Preconfigured' in other.name and 'Preconfigured' not in self.name:
                return True
            if 'Preconfigured' in self.name and 'Preconfigured' not in other.name:
                return False

            if self.language_name in ['Tomcat', 'GlassFish']:
                if self.secondary_language_version != other.secondary_language_version:
                    return self.secondary_language_version > other.secondary_language_version

            if self.platform_version != other.platform_version:
                return self.platform_version > other.platform_version

            if 'Amazon' in self.name and 'Debian' in other.name:
                return True
            elif 'Debain' in self.name and 'Amazon' in other.name:
                return False

            if self.operating_system_version != other.operating_system_version:
                return self.operating_system_version > other.operating_system_version

            if self.os_bitness != other.os_bitness:
                return self.os_bitness > other.os_bitness

            if self.language_name == 'Ruby':
                return 'Passenger' in self.name

            if self.language_name == 'IIS':
                # prefer to Windows Server 2016 to Windows Server Core 2016
                return 'Windows Server Core' not in self.name

            return True
        except Exception:
            return True

    @property
    def has_healthd_group_version_2_support(self):
        """
        Method determines whether HealthD V2 support is available for the solution stack

        :return: True, if HeadlthD V2 support is available, False otherwise
        """
        return self.platform_version >= pkg_resources.parse_version('v2.0.10')

    @property
    def has_healthd_support(self):
        """
        Method determines whether HealthD support is available for the solution stack

        :return: True, if HealthD support is available, False otherwise
        """
        return self.platform_version >= pkg_resources.parse_version('v2.0.0')

    @property
    def language_name(self):
        """
        Method extracts and returns the language name from the `platform_shorthand`.
        e.g. If the `platform_shorthand` is 'GlassFish 4.1 Java 8 (Preconfigured - Docker)',
                the language_name is 'Glassfish'

        :return: The language name represented by the SolutionStack
        """
        if 'Multi-container Docker' in self.name:
            return 'Multi-container Docker'

        if '64bit Amazon Linux 2 ' in self.name and 'running Docker' in self.name:
            return 'Docker running on 64bit Amazon Linux 2'

        shorthand = self.platform_shorthand.split(' ')[0]

        if '(BETA)' in self.name:
            shorthand = shorthand + ' (BETA)'

        return shorthand

    @property
    def language_version(self):
        """
        Method extracts the language version from the SolutionStack name. If there is a trailing '-ce'
        as in the case of 'Docker 17.03.1-ce', method returns the dotted numeric part only.

        e.g. If the SolutionStack represents '64bit Amazon Linux 2017.03 v2.7.2 running Docker 17.03.1-ce',
                the operating_system_version is '17.3.1'

        :return: The language version represented by the SolutionStack
        """

        return pkg_resources.parse_version(self.__language_version())

    @property
    def operating_system_version(self):
        """
        Method extracts the OS version of the Platform AMI from the SolutionStack name
        e.g. If the SolutionStack represents '64bit Amazon Linux 2017.03 v2.7.2 running Docker 17.03.1-ce',
                the operating_system_version is 2017.03

        :return: OS version of the Platform if one is present in the SolutionStack name
                if not, then a version representing 0000.01
        """
        match = re.search(OS_VERSION_REGEX, self.name)
        operating_system_version_string = match.group(0) if match else '0000.01'

        return pkg_resources.parse_version(operating_system_version_string)

    @property
    def os_bitness(self):
        """
        Method extracts the bitness of the Platform AMI from the SolutionStack name
        e.g. If the SolutionStack represents '64bit Amazon Linux 2017.03 v2.7.2 running Docker 17.03.1-ce',
                the bitness is 64

        :return: OS bitness of the Platform in integer form
        """
        match = re.search(OS_BITNESS_REGEX, self.name)

        return int(match.group(0)) if match else None

    @property
    def platform_shorthand(self):
        """
        Method extracts the part of the SolutionStack name with the language name,
        and language version, but without details about OS bitness. In other words,
        everything after the work 'running' in the solution stack name is returned.

        e.g. If the SolutionStack represents '64bit Amazon Linux 2017.03 v2.7.2 running Docker 17.03.1-ce',
            the platform shorthand is 'Docker 17.03.1-ce'

        :return: substring of the SolutionStack name containing the language name,
            and the language version, if they are present, else the full name of the
            SolutionStack.

        """
        match = re.search(PLATFORM_CLASS_REGEX, self.name)
        shorthand = match.groups(0)[0] if match else self.name
        if not '(BETA)' in shorthand and '(BETA)' in self.name:
            shorthand = shorthand + ' (BETA)'

        return shorthand

    @property
    def platform_version(self):
        """
        Method extracts the version of the platform from the SolutionStack name
        :return: Version of the platform if one is present in the SolutionStack name,
                else a PlatformVersion representing 'v0.0.0'
        """
        match = re.search(PLATFORM_VERSION_REGEX, self.name)
        platform_version_string = match.group(0) if match else 'v0.0.1'

        return pkg_resources.parse_version(platform_version_string)

    def pythonify(self):
        """
        Method down-cases the `platform_shorthand` of `self` and replaces the
        spaces in it with hyphens.
        e.g. 'Tomcat 8 Java 8' would be converted to 'tomcat-8-java-8'

        :return: down-cased, hyphen-separated format of the SolutionStack shorthand
        """
        return self.platform_shorthand.lower().replace(' ', '-').replace('---', '-')

    @property
    def secondary_language_version(self):
        """
        Method extracts the language name from the `platform_shorthand`.
        e.g. If the `platform_shorthand` is 'GlassFish 4.1 Java 8 (Preconfigured - Docker)',
                the secondary_language_version is '8'

        :return: The language name represented by the SolutionStack
        """
        return pkg_resources.parse_version(self.__language_version(match_number=1))

    @property
    def server_name(self):
        """
        Method extracts the substring containing OS Bitness, OS name, OS version, and platform version
        from the SolutionStack name

        e.g. If the SolutionStack represents '64bit Amazon Linux 2017.03 v2.7.2 running Docker 17.03.1-ce',
                the server name is '64bit Amazon Linux 2017.03 v2.7.2'

        :return: substring containing OS Bitness, OS name, OS version, and platform version
        """
        match = re.search(SERVER_REGEX, self.name)

        return match.group(0)

    @classmethod
    def json_to_solution_stack_array(cls, json):
        """
        Method converts a JSON array of solution stacks into a list of SolutionStacks.

        :return: A list of SolutionStacks
        """
        solution_stacks = []

        for solution_stack in json:
            solution_stacks.append(SolutionStack(solution_stack))

        return solution_stacks

    @classmethod
    def group_solution_stacks_by_platform_shorthand(
            cls,
            solution_stacks,
            language_name=None
    ):
        """
        Method deduplicates SolutionStacks. Two SolutionStacks are considered "similar" if their
        `platform_shorthand`s match.

        e.g. The following SolutionStacks are similar as they represent both Docker 17.03.1:
            - '64bit Amazon Linux 2017.03 v2.7.2 running Docker 17.03.1-ce'
            - '64bit Amazon Linux 2017.03 v2.7.1 running Docker 17.03.1-ce'

        All potential matches except the first are eliminated from the final list.

        :param solution_stacks: A list of SolutionStack objects to group by platform_shorthands
        :param language_name: An optional language_name to filter the action of grouping by

        :return: A list of dictionary objects mapping `platform_shorthand`s to SolutionStack objects
        """
        grouped_solution_stacks = OrderedDict()
        for solution_stack in solution_stacks:
            if language_name and solution_stack.language_name != language_name:
                continue

            if not grouped_solution_stacks.get(solution_stack.platform_shorthand):
                grouped_solution_stacks[solution_stack.platform_shorthand] = {
                        'PlatformShorthand': solution_stack.platform_shorthand,
                        'LanguageName': solution_stack.language_name,
                        'SolutionStack': solution_stack.name
                    }

        return list(grouped_solution_stacks.values())

    @classmethod
    def group_solution_stacks_by_language_name(cls, solution_stacks):
        """
        Method deduplicates SolutionStacks. Two SolutionStacks are considered "similar"
        if their `language_names`s match.

        e.g. The following SolutionStacks are "similar" as they represent both Ruby:
            - '64bit Amazon Linux 2017.03 v2.4.3 running Ruby 2.0 (Puma)',
            - '64bit Amazon Linux 2017.03 v2.4.3 running Ruby 2.3 (Passenger Standalone)',

        All potential matches except the first are eliminated from the final list.

        :param solution_stacks: A list of SolutionStack objects to group by language_name
        :return: A list of dictionary objects mapping `language_name`s to SolutionStack objects
        """
        grouped_solution_stacks = OrderedDict()
        for solution_stack in solution_stacks:
            other_language_name = solution_stack.language_name

            if not grouped_solution_stacks.get(other_language_name):
                grouped_solution_stacks[solution_stack.language_name] = {
                        'LanguageName': solution_stack.language_name,
                        'SolutionStack': solution_stack.name
                    }

        return list(grouped_solution_stacks.values())

    @classmethod
    def match_with_complete_solution_string(
            cls,
            solution_stack_list,
            complete_solution_stack_name
    ):
        """
        Method returns a SolutionStack object representing the `complete_solution_stack_name`
        if it is found in `solution_stack_list`

        :param solution_stack_list: A list of SolutionStack objects to search in
        :param complete_solution_stack_name: The complete name of a solution stack as returned
                by `eb platform --list verbose`

        :return: A SolutionStack object representing the input solution stack
        """
        for solution_stack in solution_stack_list:
            if solution_stack.name.lower() == complete_solution_stack_name.lower():
                return solution_stack

    @classmethod
    def match_with_solution_string_shorthand(
            cls,
            solution_stack_list,
            platform_shorthand
    ):
        """
        Method returns a SolutionStack object representing the `platform_shorthand`
        if it is found in `solution_stack_list`

        :param solution_stack_list: A list of SolutionStack objects to search in
        :param platform_shorthand: the shorthand of a solution stack.
            e.g. PHP 7.0, Python 3.4, etc

        :return: A SolutionStack object representing the input solution stack
        """
        for solution_stack in solution_stack_list:
            if solution_stack.platform_shorthand.lower() == platform_shorthand.lower():
                return solution_stack

    @classmethod
    def match_with_solution_string_language_name(
            cls,
            solution_stack_list,
            language_name
    ):
        """
        Method returns a SolutionStack object representing the `platform_shorthand`
        if it is found in `solution_stack_list`

        :param solution_stack_list: list of SolutionStack objects to search in
        :param language_name: a valid language name such as Ruby, Python, Node.js, etc

        :return: A SolutionStack object representing the input language name
        """
        solution_stack_list = sorted(solution_stack_list)
        for solution_stack in solution_stack_list:
            if solution_stack.language_name.lower() == language_name.lower():
                return solution_stack

    @classmethod
    def match_with_pythonified_solution_string(
            cls,
            solution_stack_list,
            pythonified_solution_string
    ):
        """
        Method returns a SolutionStack object representing the `pythonified_solution_string`
        if it is found in `solution_stack_list`

        :param solution_stack_list: list of SolutionStack objects to search in
        :param pythonified_solution_string: the shorthand of a solution stack as returned
            by `eb platform list`.
            e.g. ruby-2.0-(passenger-standalone)

        :return: A SolutionStack object representing the input solution stack
        """
        for solution_stack in solution_stack_list:
            if solution_stack.pythonify() == pythonified_solution_string.lower():
                return solution_stack

    def __language_version(self, match_number=0):
        """
        Private method returns a the version number of language. If there are multiple versions,
         method returns the `match_number` to retrieve the specific occurrence.
         e.g. given `platform_shorthand` == 'GlassFish 4.1 Java 8 (Preconfigured - Docker)'
                if `match_number` == 0, method returns 4.1
                if `match_number` == 1, method returns 8

        :param match_number: the occurrence of a version number to return
        :return: a version number in string form
        """
        splits = self.platform_shorthand.strip().split(' ')
        _match_number = 0
        version_string = '0.0.1'

        for split in splits:
            match = re.search(LANGUAGE_VERSION_REGEX, split)
            if match:
                if _match_number == match_number:
                    if split[-3:] == '-ce':
                        version_string = split[:-3]
                    else:
                        version_string = split

                    break

                _match_number += 1

        return version_string
