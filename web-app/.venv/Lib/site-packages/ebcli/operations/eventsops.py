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

import os

import time
from ebcli.core import io
from ebcli.lib import elasticbeanstalk
from ebcli.objects.exceptions import EndOfTestError
from ebcli.operations import commonops


def print_events(app_name, env_name, follow, platform_arn=None):
    if follow:
        follow_events(app_name, env_name, platform_arn)
    else:
        events = elasticbeanstalk.get_new_events(
            app_name, env_name, None, platform_arn=platform_arn)

        data = []
        for event in reversed(events):
            data.append(commonops.get_event_string(event, long_format=True))
        io.echo_with_pager(os.linesep.join(data))


def follow_events(app_name, env_name, platform_arn=None):
    last_time = None
    streamer = io.get_event_streamer()
    try:
        while True:
            events = elasticbeanstalk.get_new_events(
                app_name, env_name, None, platform_arn=platform_arn, last_event_time=last_time
            )

            for event in reversed(events):
                message = commonops.get_event_string(event, long_format=True)
                streamer.stream_event(message)
                last_time = event.event_date

            _sleep()
    except EndOfTestError:
        pass
    finally:
        streamer.end_stream()


def _sleep():
    time.sleep(4)
