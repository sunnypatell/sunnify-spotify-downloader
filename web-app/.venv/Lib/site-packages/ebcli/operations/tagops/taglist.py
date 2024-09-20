# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
from os import linesep
import re
import sys

from ebcli.core import io
from ebcli.objects.exceptions import EBCLIException
from ebcli.resources.strings import strings


def column_length(list_of_tags):
    """
    Given a list of tags(strings), method returns the length of
    the longest tag key(string)

    :param list_of_tags: list of tags of the form {'Key': key, 'Value': value}
    :return: length of longest tag (string)
    """
    list_of_keys = list_of_keys_of(list_of_tags)

    return len(max(list_of_keys, key=len))


def list_of_keys_of(list_of_tags):
    """
    Given a list of tags (key-value pairs), method returns the
    list of keys.

    :param list_of_tags: list of tags of the form {'Key': key, 'Value': value}
    :return: list of keys of tags
    """
    return [tag["Key"] for tag in list_of_tags]


class ArgumentSyntaxValidator(object):
    """
    Class responsible for validating that there are no unnecessary characters
    in the tags specified to be created, deleted, and updated.
    """
    class InvalidTagKeyError(EBCLIException):
        """
        Raised when the key of a tag is invalid
        """

    class InvalidTagValueError(EBCLIException):
        """
        Raised when the value of a tag is invalid
        """

    @classmethod
    def validate_key_value_pair(cls, tag):
        """
        Method that validates key-value pairs of form "key=value" are legal.
        :param tag: a key-value pair(string) of the form "key=value"
        :return: A further sanitized, and validated tuple of key, and value
        """
        # Ensure key is not blank
        if not len(tag) or tag[0] == '=':
            raise cls.InvalidTagKeyError(strings['tags.tag_key_cant_be_blank'])

        # Ensure value is not blank
        if tag[-1] == '=' or '=' not in tag:
            raise cls.InvalidTagValueError(strings['tags.tag_value_cant_be_blank'])

        # Remove whitespace around the "key" and "value"
        key, value = [member.strip() for member in tag.split('=', 1)]

        cls.validate_key(key)

        if len(value) > 255:
            raise cls.InvalidTagValueError(
                (linesep * 2).join(
                    [
                        strings['tags.tag_value_max_length_exceeded'],
                        value
                    ]
                )
            )

        value_regex_matcher = cls.__tag_component_regex_matcher(value)
        if not cls.__tag_component_regex_search(value_regex_matcher, value):
            raise cls.InvalidTagValueError(strings['tags.invalid_tag_value'].format(value))

        return key, value

    @classmethod
    def validate_key(cls, key):
        """
        Method that validates keys represented as strings are legal
        :param key: a string representation of a key
        """
        if len(key) > 127:
            raise cls.InvalidTagKeyError(
                (linesep * 2).join(
                    [
                        strings['tags.tag_key_max_length_exceeded'],
                        key
                    ]
                )
            )

        key_regex_matcher = cls.__tag_component_regex_matcher(key)

        if not cls.__tag_component_regex_search(key_regex_matcher, key):
            raise cls.InvalidTagKeyError(strings['tags.invalid_tag_key'].format(key))

    @classmethod
    def __tag_component_regex_matcher(cls, value):
        if sys.version_info < (3, 0):
            return re.compile(
                r'^[\w\s.:\\/+=@-]{'
                + str(len(value.decode('utf-8')))
                + '}', re.UNICODE)
        else:
            return re.compile(
                r'^[\w\s.:\\/+=@-]{'
                + str(len(value)) + '}'
            )

    @classmethod
    def __tag_component_regex_search(cls, regex_matcher, component):
        if sys.version_info < (3, 0):
            return re.search(regex_matcher, component.decode('utf-8'))
        else:
            return re.search(regex_matcher, component)


class TagListValidator(object):
    """
    Class to validate that the keys specified across --add, --delete,
    and --update are unique.
    """
    class DuplicateKeyError(EBCLIException):
        """ One or more of the tags specified by the user to create, delete,
        or update have already been specified in the present `eb tags ...`
        command"""
        pass

    def __init__(self, taglist, key):
        self.taglist = taglist
        self.additions = [
            addition for addition in taglist.additions
            if addition['Key'] not in taglist.updates
        ]
        self.deletions = taglist.deletions
        self.updates = taglist.updates
        self.key = key

    def validate_key_for_addition_is_unique(self):
        """
        Validates key hasn't already been specified for addition in the additions list
        :param key: a key (string) of a tag that is specified to be added
        """
        self.__raise_if_key_present_in_list(
            list_of_keys_of(self.additions),
            'tags.duplicate_key_in_add_list'
        )

    def validate_key_for_deletion_is_unique(self):
        """
        Validates key hasn't already been specified for update in the updates list or for
        deletion in the deletions list.
        :param key: a key (string) of a tag that is specified to be updated
        """
        self.__raise_if_key_present_in_list(
            self.deletions,
            'tags.duplicate_key_in_delete_list'
        )
        self.__raise_if_key_present_in_list(
            list_of_keys_of(self.updates),
            'tags.duplicate_key_in_update_list'
        )

    def validate_key_for_update_is_unique(self):
        """
        Validates key hasn't already been specified for update in the updates list or for
        deletion in the deletions list.
        :param key: a key (string) of a tag that is specified to be updated
        """
        self.__raise_if_key_present_in_list(
            list_of_keys_of(self.updates),
            'tags.duplicate_key_in_update_list'
        )
        self.__raise_if_key_present_in_list(
            self.deletions,
            'tags.duplicate_across_delete_and_update_lists'
        )

    def __raise_if_key_present_in_list(self, key_list, error_label):
        if self.key in key_list:
            duplicate_key_error_message = ''.join(
                [
                    strings[error_label].format(self.key),
                    linesep
                ]
            )

            raise self.DuplicateKeyError(duplicate_key_error_message)


class TagList(object):
    """
    Class to represent the values specified to `eb tags` to
    --add, --delete, and --update, as lists.
    """
    @classmethod
    def sanitized_tags(cls, argument_string):
        """
        Method that strips unwanted trailing characters from a key/key-value
        pair string.
        :param argument_string: a string of type key=value or key
        :return: a sanitized version of the argument_string
        """
        argument_string = argument_string.strip().strip('"').strip("'")

        return [member.strip() for member in argument_string.split(',')]

    def __init__(self, current_list):
        self.current_list = current_list

        self.additions = []
        self.deletions = []
        self.updates = []

    def print_tags(self, resource_arn):
        """
        Method to print the list of "Key" and "Value" pairs in columnar format.
        :return: None
        """
        print("Showing tags for resource '{1}':".format(linesep, resource_arn))
        io.echo('')

        ideal_column_length = column_length(self.current_list) + 3
        io.echo(
            ''.join(
                key_value_string.ljust(ideal_column_length)
                for key_value_string in ['Key', 'Value']
            )
        )
        io.echo('')

        for tag in self.current_list:
            io.echo(
                (
                    ''.join(
                        key_value.ljust(ideal_column_length)
                        for key_value in [tag['Key'], tag['Value']]
                    )
                ).strip()
            )

    def populate_add_list(self, addition_string):
        """
        Given a command line argument value that has the form
        `key1=value1,...`, transforms it into the form
        `[{'Key': key, 'Value': value}, ...]`

        :param addition_string: A string of the form `key1=value1,...`
        :return: None
        :side-effect: populates `self.additions` with a list of key-value pairs
        """
        tags_to_add = self.sanitized_tags(addition_string)

        for tag in tags_to_add:
            key, value = ArgumentSyntaxValidator.validate_key_value_pair(tag)

            TagListValidator(self, key).validate_key_for_addition_is_unique()

            self.additions.append(
                {
                    'Key': key,
                    'Value': value
                }
            )

    def populate_delete_list(self, deletion_string):
        """
         Given a command line argument value that has the form
        `key1,...`, transforms it into the form [`key1`,...]`

        :param deletion_string: A string of the form `key1=value1,...`
        :return: None
        :side-effect: populates `self.deletions` with a list of keys
        """
        keys_to_delete = self.sanitized_tags(deletion_string)

        for key in keys_to_delete:
            ArgumentSyntaxValidator.validate_key(key)

            TagListValidator(self, key).validate_key_for_deletion_is_unique()

            self.deletions.append(key)

    def populate_update_list(self, update_string):
        """
        Given a command line argument value that has the form
        `key1=value1,...`, transforms it into the form
        `[{'Key': key, 'Value': value}, ...]`

        :param update_string: A string of the form `key1=value1,...`
        :return: None
        :side-effect: populates `self.updates` with a list of key-value pairs
        """
        tags_to_update = self.sanitized_tags(update_string)

        for tag in tags_to_update:
            key, value = ArgumentSyntaxValidator.validate_key_value_pair(tag)

            TagListValidator(self, key).validate_key_for_update_is_unique()

            self.updates.append(
                {
                    'Key': key,
                    'Value': value
                }
            )
