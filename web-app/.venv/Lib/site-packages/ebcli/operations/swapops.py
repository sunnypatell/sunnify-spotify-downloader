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

from ebcli.lib import elasticbeanstalk
from ebcli.operations import commonops


def cname_swap(source_env, dest_env):
    request_id = elasticbeanstalk.swap_environment_cnames(source_env, dest_env)

    commonops.wait_for_success_events(
        request_id,
        timeout_in_minutes=1,
        sleep_time=2
    )
