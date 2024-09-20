# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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


class LogStream(object):
    def __init__(
            self,
            name,
            creation_time
    ):
        self.name = name
        self.creation_time = creation_time

    def __lt__(self, other):
        return self.creation_time < other.creation_time

    @classmethod
    def log_stream_objects_from_json(cls, json):
        log_streams = list()
        for log_stream in json:
            log_streams.append(
                LogStream(
                    name=log_stream['logStreamName'],
                    creation_time=log_stream['creationTime']
                )
            )

        return sorted(log_streams)
