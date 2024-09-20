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
import re

from ebcli.core import io
from ebcli.lib import elasticbeanstalk, elbv2, utils
from ebcli.objects.exceptions import NotFoundError
from ebcli.resources.statics import elb_names
from ebcli.resources.strings import alerts, flag_text, prompts, strings

VALID_LOAD_BALANCER_NAME_FORMAT = re.compile(r'^([A-Za-z0-9-]+)$')

def get_shared_lb_from_customer(interactive, elb_type, platform, vpc=None):
    """
    Prompt customer to select if they would like to use shared load balancer.
    Selection defaults to 'N'
    Prompt customer to select load balancer from a list, if they selected 'y' for previous prompt
    return: ARN of selected load balancer
    """
    if not interactive or elb_type != elb_names.APPLICATION_VERSION:
        return

    alb_list = elasticbeanstalk.list_application_load_balancers(platform, vpc)
    if not alb_list:
        return

    should_continue = io.get_boolean_response(
         text=prompts['sharedlb.shared_load_balancer_request_prompt'],
         default=False)
    if not should_continue:
        return

    alb_list_display_labels = []
    for load_balancer_arn in alb_list:
        load_balancer_name = parse_load_balancer_name(load_balancer_arn)
        alb_list_display_labels.append(load_balancer_name + ' - ' + load_balancer_arn)

    io.echo(prompts['sharedlb.shared_load_balancer_prompt'])
    selected_index = utils.prompt_for_index_in_list(alb_list_display_labels, default = 1)
    return alb_list[selected_index]


def parse_load_balancer_name(load_balancer_arn):
    """
    Parse name out from load balancer ARN
    Example:
    ARN of load balancer: 'arn:aws:elasticloadbalancing:us-east-1:881508045124:loadbalancer/app/alb-1/72074d479748b405',
    Load balancer name: 'alb-1'
    return: load balancer name
    """
    return load_balancer_arn.split('/')[-2]


def get_shared_lb_port_from_customer(interactive, selected_lb):
    """
    Method accepts load balancer ARN
    Prompt customer to select port from list of listener port
    return: selected listener port
    """
    if not interactive or selected_lb is None:
        return

    result = elbv2.get_listeners_for_load_balancer(selected_lb)
    listener_list = [listener['Port'] for listener in result['Listeners']]
    listener_list.sort()
    default_listener_index = listener_list.index(80)+1 if 80 in listener_list else None

    if len(listener_list) < 1:
        raise NotFoundError(alerts['sharedlb.listener'])
    elif len(listener_list) == 1:
        selected_listener_port = listener_list[0]
    else:
        io.echo(prompts['sharedlb.listener_prompt'])
        selected_listener_port = utils.prompt_for_item_in_list(listener_list, default=default_listener_index)

    return selected_listener_port


def validate_shared_lb_for_non_interactive(shared_lb):
    """
    Method accepts load balancer name or load balancer ARN
    return: load balancer ARN
    """
    if VALID_LOAD_BALANCER_NAME_FORMAT.search(shared_lb):
        load_balancer_arn = get_load_balancer_arn_from_load_balancer_name(shared_lb)
        return load_balancer_arn
    else:
        return shared_lb


def get_load_balancer_arn_from_load_balancer_name(load_balancer_name):
    """
    Method accepts load balancer name
    return: load balancer ARN
    """
    result = elbv2.describe_load_balancers([load_balancer_name])['LoadBalancers']
    load_balancer_arn = result[0].get('LoadBalancerArn')
    return load_balancer_arn
