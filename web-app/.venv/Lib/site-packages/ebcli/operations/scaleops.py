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
from ebcli.resources.strings import prompts
from ebcli.operations import commonops


def scale(app_name, env_name, number, confirm, timeout=None):
    options = []
    env = elasticbeanstalk.describe_configuration_settings(
        app_name, env_name
    )['OptionSettings']

    namespace = 'aws:elasticbeanstalk:environment'
    setting = next((n for n in env if n["Namespace"] == namespace), None)
    value = setting['Value']
    if value == 'SingleInstance':
        if not confirm:
            io.echo(prompts['scale.switchtoloadbalance'])
            io.log_warning(prompts['scale.switchtoloadbalancewarn'])
            switch = io.get_boolean_response()
            if not switch:
                return

        options.append({'Namespace': namespace,
                        'OptionName': 'EnvironmentType',
                        'Value': 'LoadBalanced'})

    namespace = 'aws:autoscaling:asg'
    max = 'MaxSize'
    min = 'MinSize'

    for name in [max, min]:
        options.append(
            {
                'Namespace': namespace,
                'OptionName': name,
                'Value': str(number)
            }
        )
    request_id = elasticbeanstalk.update_environment(env_name, options)

    commonops.wait_for_success_events(
        request_id,
        timeout_in_minutes=timeout or 5,
        can_abort=True
    )
