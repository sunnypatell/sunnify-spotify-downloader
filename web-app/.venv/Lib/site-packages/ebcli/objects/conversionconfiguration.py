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

from abc import ABCMeta, abstractmethod


class ConversionConfiguration:
    def __init__(self, api_model):
        """
        This abstract class is the top layer for a class that takes in raw API response
        and will modify it for other uses.
        :param api_model: API response from AWS
        """
        self.api_model = api_model
        pass

    __metaclass__ = ABCMeta

    @abstractmethod
    def collect_changes(self, usr_model):
        """
        Grabs all the pairs in the usr_model that are different and returns just the
        changes ready to be put into a request.
        :param usr_model: User model, key-value style
        :return: Api model with only the changes in it
        """
        pass

    @abstractmethod
    def convert_api_to_usr_model(self):
        """
        Converts the saved api model to a User model as a key-value system and remove
        unwanted entries
        :return: A user model, key-value style
        """
        pass

    def _copy_api_entry(self, key_name, usr_model):
        """
        Copies the given key-value from the api model into the given user model
        :param key_name: key name of the pair we want to copy
        :param usr_model: user model we want to add to
        """
        usr_model[key_name] = self.api_model[key_name]
