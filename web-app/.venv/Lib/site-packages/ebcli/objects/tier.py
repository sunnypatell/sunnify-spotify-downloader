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
from ebcli.objects.exceptions import NotFoundError


class Tier(object):

    TIER_MAP = {
        'webserver': (lambda: Tier('WebServer', 'Standard', '1.0')),
        'webserver/standard': (lambda: Tier('WebServer', 'Standard', '1.0')),
        'worker': (lambda: Tier('Worker', 'SQS/HTTP', '')),
        'worker/sqs/http': (lambda: Tier('Worker', 'SQS/HTTP', '')),
    }

    @staticmethod
    def get_all_tiers():
        lst = [
            Tier('WebServer', 'Standard', '1.0'),
            Tier('Worker', 'SQS/HTTP', ''),
        ]
        return lst

    def __init__(self, name, typ, version, elb_type=None):
        self.name = name
        self.type = typ
        self.version = version
        self.elb_type = elb_type

    def to_dict(self):
        json = {
            'Name': self.name,
            'Type': self.type,
        }

        if self.version:
            json['Version'] = self.version

        return json

    def __str__(self):
        s = self.name + '-' + self.type
        if self.version:
            s += '-' + self.version
        return s

    def __eq__(self, other):
        if not isinstance(other, Tier):
            return False

        return self.name.lower() == other.name.lower()

    @classmethod
    def get_default(cls):
        return cls.TIER_MAP['webserver']()

    @classmethod
    def from_raw_string(cls, customer_input):
        try:
            return cls.TIER_MAP[customer_input.lower().strip()]()
        except KeyError:
            raise NotFoundError('Provided tier "{}" does not appear to be valid'.format(customer_input))

    def is_webserver(self):
        return self.name.lower() == 'webserver'

    def is_worker(self):
        return self.name.lower() == 'worker'

    @classmethod
    def looks_like_worker_tier(cls, customer_input):
        return cls.from_raw_string(customer_input) == cls.from_raw_string('worker')

    @classmethod
    def looks_like_webserver_tier(cls, customer_input):
        return cls.from_raw_string(customer_input) == cls.from_raw_string('webserver')
