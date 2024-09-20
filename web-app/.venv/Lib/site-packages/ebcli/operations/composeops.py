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
from ebcli.core import io
from ebcli.operations import commonops


def compose(app_name, version_labels, grouped_env_names, group_name=None,
            nohang=False, timeout=None):

    success = commonops.wait_for_processed_app_versions(app_name, version_labels, timeout=timeout or 10)
    if not success:
        return

    request_id = compose_apps(app_name, version_labels, group_name)

    if nohang:
        return

    commonops.wait_for_compose_events(request_id, app_name, grouped_env_names, timeout)


def compose_apps(app_name, version_labels, group_name=None):
    io.echo('--- Creating modules ---')
    request_id = elasticbeanstalk.compose_environments(app_name, version_labels,
                                                       group_name)
    return request_id


def compose_no_events(app_name, version_labels, group_name=None):
    success = commonops.wait_for_processed_app_versions(app_name, version_labels)
    if not success:
        return None

    return compose_apps(app_name, version_labels, group_name)
