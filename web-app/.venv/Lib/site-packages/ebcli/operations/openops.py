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

from ebcli.resources.statics import namespaces, option_names
from ebcli.lib import elasticbeanstalk
from ebcli.operations import commonops


def open_app(app_name, env_name):
    env = elasticbeanstalk.get_environment(app_name=app_name, env_name=env_name)
    settings = elasticbeanstalk.describe_configuration_settings(
        app_name, env_name)

    option_settings = settings.get('OptionSettings', [])
    http_port = elasticbeanstalk.get_option_setting(
        option_settings,
        namespaces.LOAD_BALANCER,
        option_names.LOAD_BALANCER_HTTP_PORT)

    if http_port == 'OFF':
        ssl = True
    else:
        ssl = False

    commonops.open_webpage_in_browser(env.cname, ssl=ssl)
