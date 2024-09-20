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
from ebcli.lib import utils, elasticbeanstalk, aws
from ebcli.objects.exceptions import NotSupportedError
from ebcli.operations import commonops


def open_console(app_name, env_name):
    if utils.is_ssh():
        raise NotSupportedError('The console command is not supported'
                                ' in an ssh type session')

    env = None
    if env_name is not None:
        env = elasticbeanstalk.get_environment(app_name=app_name, env_name=env_name)

    region = aws.get_region_name()
    if env is not None:
        page = 'environment/dashboard'
    else:
        page = 'application/overview'

    app_name = utils.url_encode(app_name)

    console_url = 'console.aws.amazon.com/elasticbeanstalk/home?'
    console_url += 'region=' + region
    console_url += '#/' + page + '?applicationName=' + app_name

    if env is not None:
        console_url += '&environmentId=' + env.id

    commonops.open_webpage_in_browser(console_url, ssl=True)
