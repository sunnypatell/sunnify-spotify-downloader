# Copyright 2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
Apply botocore fixes as monkey patches.
This allows us to use any version of botocore.
"""
import datetime
import time

from dateutil import tz
from botocore import parsers


def fix_botocore_to_pass_response_date():
    """
    Patch botocore so that it includes the Date of the response in the meta
    data
    """
    LOG = parsers.LOG

    def parse(self, response, shape):
        """Parse the HTTP response given a shape.

        :param response: The HTTP response dictionary.  This is a dictionary
            that represents the HTTP request.  The dictionary must have the
            following keys, ``body``, ``headers``, and ``status_code``.

        :param shape: The model shape describing the expected output.
        :return: Returns a dictionary representing the parsed response
            described by the model.  In addition to the shape described from
            the model, each response will also have a ``ResponseMetadata``
            which contains metadata about the response, which contains at least
            two keys containing ``RequestId`` and ``HTTPStatusCode``.  Some
            responses may populate additional keys, but ``RequestId`` will
            always be present.

        """
        LOG.debug('Response headers: %s', response['headers'])
        LOG.debug('Response body:\n%s', response['body'])
        if response['status_code'] >= 301:
            parsed = self._do_error_parse(response, shape)
        else:
            parsed = self._do_parse(response, shape)
        if isinstance(parsed, dict) and 'ResponseMetadata' in parsed:
            parsed['ResponseMetadata']['HTTPStatusCode'] = (
                response['status_code'])

            # BEGIN PATCH
            # Here we inject the date
            parsed['ResponseMetadata']['date'] = (
                response['headers']['date']
            )
            # END PATCH
        return parsed

    parsers.ResponseParser.parse = parse


def apply_patches():
    fix_botocore_to_pass_response_date()
