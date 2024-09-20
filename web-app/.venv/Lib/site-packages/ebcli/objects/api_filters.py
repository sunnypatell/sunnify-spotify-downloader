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


class Filter(object):
    def __init__(self, values, operator='='):
        self.operator = operator
        self.values = values

    def json(self):
        return {
            'Type': self.filter_type,
            'Operator': self.operator,
            'Values': self.values,
        }


class PlatformNameFilter(Filter):
    filter_type = 'PlatformName'


class PlatformOwnerFilter(Filter):
    filter_type = 'PlatformOwner'


class PlatformStatusFilter(Filter):
    filter_type = 'PlatformStatus'


class PlatformVersionFilter(Filter):
    filter_type = 'PlatformVersion'
