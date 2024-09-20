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
import sys

from ebcli.core import io
from ebcli.lib import elasticbeanstalk
from ebcli.resources.strings import strings
from ebcli.objects.exceptions import EBCLIException
from ebcli.objects.environment import Environment
from ebcli.operations.commonops import wait_for_success_events
from ebcli.operations.tagops.taglist import TagList, list_of_keys_of


class InvalidAttemptToModifyTagsError(EBCLIException):
    """ One or more of the tags specified by the user to create
    using `eb tags --add` already exist
    """
    pass


def raise_validation_error(
        problematic_key_set,
        problem_message,
        exception_class
):
    """
    Method raises given a `problem_message` when an action of `action_type`
    could not be performed.

    :param problematic_key_set: a list of keys, the presence or absence
                                of which triggered the exception
    :param problem_message: reason for the exception
    :param exception_class: exception class to be raised when there
    :return: None
    """
    stringified_keys = '{0}  '.format(linesep).join(sorted(problematic_key_set))

    tags_error_message = '{problem_message}{linesep}{linesep}  {stringified_keys}{linesep}'.format(
        problem_message=problem_message,
        linesep=linesep,
        stringified_keys=stringified_keys
    )

    raise exception_class(tags_error_message)


def unicode_decode_keys(keys):
    if sys.version_info < (3, 0):
        return [key.decode('utf-8') for key in keys]
    return keys


def validate_additions(taglist):
    """
    Validates that the list of tags specified to be added do not
    already exist. If one or more tags already exist, it generates a
    `AttemptToCreatePreexistingTagsError` exception.
    :return: None
    """
    preexisting_keys = list_of_keys_of(taglist.current_list)
    keys_of_tags_to_create = unicode_decode_keys(list_of_keys_of(taglist.additions))

    preexisting_key_set = set(preexisting_keys).intersection(keys_of_tags_to_create)

    if preexisting_key_set:
        raise_validation_error(
            problematic_key_set=preexisting_key_set,
            problem_message=strings['tags.tag_keys_already_exist'],
            exception_class=InvalidAttemptToModifyTagsError
        )


def validate_deletions(taglist):
    """
    Validates that the list of tags specified to be deleted currently
    exist. If one or more tags do not already exist, it generates a
    `InvalidAttemptToModifyTagsError` exception.
    :return: None
    """
    preexisting_keys = list_of_keys_of(taglist.current_list)
    keys_of_tags_to_delete = unicode_decode_keys(taglist.deletions)

    non_existent_key_set = list(set(keys_of_tags_to_delete) - set(preexisting_keys))

    if non_existent_key_set:
        raise_validation_error(
            problematic_key_set=non_existent_key_set,
            problem_message=strings['tags.tag_keys_dont_exist_for_deletion'],
            exception_class=InvalidAttemptToModifyTagsError
        )


def validate_updates(taglist):
    """
    Validates that the list of tags specified to be updated currently
    exist. If one or more tags do not already exist, it generates a
    `InvalidAttemptToModifyTagsError` exception.
    :return: None
    """
    preexisting_keys = list_of_keys_of(taglist.current_list)
    keys_of_tags_to_update = unicode_decode_keys(list_of_keys_of(taglist.updates))

    non_existent_key_set = list(set(keys_of_tags_to_update) - set(preexisting_keys))

    if non_existent_key_set:
        raise_validation_error(
            problematic_key_set=non_existent_key_set,
            problem_message=strings['tags.tag_keys_dont_exist_for_update'],
            exception_class=InvalidAttemptToModifyTagsError
        )


class TagOps(object):
    """
    Tag Operations class that delegates the tasks of validating syntax and uniqueness
    of tags, and performing EB API calls to other classes.
    """
    def __init__(self, resource_arn, verbose):
        self.resource_arn = resource_arn
        self.taglist = None
        self.verbose = verbose

    def retrieve_taglist(self):
        if self.taglist is None:
            self.taglist = TagList(elasticbeanstalk.list_tags_for_resource(self.resource_arn))

    def list_tags(self):
        self.retrieve_taglist()

        if self.taglist.current_list:
            self.taglist.print_tags(self.resource_arn)

    def update_tags(self, resource_type=Environment):
        request_id = elasticbeanstalk.update_tags_for_resource(
            self.resource_arn,
            self.taglist.additions + self.taglist.updates,
            self.taglist.deletions
        )

        if resource_type == Environment:
            wait_for_success_events(request_id)

        if self.verbose:
            self.__communicate_changes_to_stdout()

    def handle_addition_string(self, addition_string):
        """
        Passes on string of the form 'key=value,..." to TagList
        which will maintain a list of keys specified for addition
        :param addition_string: a string of the form 'key=value,...'
        :return: None
        """
        self.retrieve_taglist()

        self.taglist.populate_add_list(addition_string)

        validate_additions(self.taglist)

    def handle_deletion_string(self, deletion_string):
        """
        Passes on string of the form 'key,..." to TagList
        which will maintain a list of keys specified for deletion
        :param deletion_string: a string of the form 'key,...'
        :return: None
        """
        self.retrieve_taglist()

        self.taglist.populate_delete_list(deletion_string)
        validate_deletions(self.taglist)

    def handle_update_string(self, update_string):
        """
        Passes on string of the form 'key=value,..." to TagList
        which will maintain a list of keys specified for update
        :param update_string: a string of the form 'key=value,...'
        :return: None
        """
        self.retrieve_taglist()

        self.taglist.populate_update_list(update_string)

        validate_updates(self.taglist)

    def __communicate_changes_to_stdout(self):
        """
        Print changes to STDOUT.
        :return: None
        """
        keys_to_update = list_of_keys_of(self.taglist.updates)
        additions = [
            addition for addition in self.taglist.additions
            if addition['Key'] not in keys_to_update
        ]
        deletions = self.taglist.deletions
        updates = self.taglist.updates

        if additions:
            io.echo('Added Tags:')
            io.echo(
                linesep.join(
                    [
                        "  Key: '{0}'  Value: '{1}'".format(
                            addition['Key'],
                            addition['Value']
                        ) for addition in additions
                    ]
                )
            )
            io.echo('')

        if deletions:
            io.echo('Deleted Tags:')
            io.echo(linesep.join(["  Key: '{0}'".format(deletion) for deletion in deletions]))
            io.echo('')

        if updates:
            io.echo('Updated Tags:')
            io.echo(
                linesep.join(
                    [
                        "  Key: '{0}'  Value: '{1}'".format(
                            update['Key'],
                            update['Value']
                        ) for update in updates
                    ]
                )
            )
            io.echo('')


def get_and_validate_tags(addition_string):
    if not addition_string:
        return []

    taglist = TagList([])
    taglist.populate_add_list(addition_string)
    validate_additions(taglist)

    return taglist.additions
