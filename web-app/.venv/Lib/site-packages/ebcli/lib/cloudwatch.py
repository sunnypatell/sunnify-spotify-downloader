# Copyright 2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

from ebcli.lib import aws
from ebcli.objects.log_stream import LogStream


def _make_api_call(operation_name, **operation_options):
    return aws.make_api_call('logs', operation_name, **operation_options)


def get_all_stream_names(log_group_name, log_stream_name_prefix=None):
    """
    Return all stream names under the log group.
    param: log_group_name: str
    """
    streams = describe_log_streams(
        log_group_name=log_group_name,
        log_stream_name_prefix=log_stream_name_prefix,
    )

    streams = streams or {}

    return [
        log_stream.name
        for log_stream
        in LogStream.log_stream_objects_from_json(streams.get('logStreams', []))
    ]


def get_log_events(log_group_name, log_stream_name, next_token=None,
                   start_from_head=False, start_time=None, end_time=None,
                   limit=None):

    params = dict(logGroupName=log_group_name, logStreamName=log_stream_name)

    if next_token is not None:
        params['nextToken'] = next_token

    if start_from_head is not None:
        params['startFromHead'] = start_from_head

    if start_time is not None:
        params['startTime'] = start_time

    if end_time is not None:
        params['endTime'] = end_time

    if limit is not None:
        params['limit'] = limit

    return _make_api_call('get_log_events', **params)


def describe_log_streams(
        limit=None,
        log_group_name=None,
        log_stream_name_prefix=None,
        next_token=None
):
    params = dict()

    if log_group_name:
        params['logGroupName'] = log_group_name

    if log_stream_name_prefix:
        params['logStreamNamePrefix'] = log_stream_name_prefix

    if next_token:
        params['nextToken'] = next_token

    if limit:
        params['limit'] = limit

    return _make_api_call('describe_log_streams', **params)


def log_group_exists(log_group_name):
    response = _make_api_call('describe_log_groups', logGroupNamePrefix=log_group_name)

    return len(response['logGroups']) > 0
