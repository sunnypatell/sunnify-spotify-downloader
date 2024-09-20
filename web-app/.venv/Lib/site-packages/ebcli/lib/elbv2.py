# Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
import time

from cement.utils.misc import minimal_logger

from ebcli.lib import aws
from ebcli.objects.exceptions import ServiceError, NotFoundError

LOG = minimal_logger(__name__)


def _make_api_call(operation_name, **operation_options):
    return aws.make_api_call('elbv2', operation_name, **operation_options)


def get_instance_healths_from_target_groups(target_group_arns):
    instance_healths = []
    for arn in target_group_arns:
        try:
            result = _make_api_call('describe_target_health', TargetGroupArn=arn)

            for description in result['TargetHealthDescriptions']:
                instance_healths.append({
                    'InstanceId': description['Target']['Id'],
                    'State': description['TargetHealth'].get('State', ''),
                    'Description': description['TargetHealth'].get('Description', ''),
                    'Reason': description['TargetHealth'].get('Reason', '')
                })

        except ServiceError as e:
            raise NotFoundError(e)

    return instance_healths


def get_target_group_healths(target_group_arns):
    results = {}
    for arn in target_group_arns:
        try:
            results[arn] = _make_api_call('describe_target_health', TargetGroupArn=arn)
        except ServiceError as e:
            raise NotFoundError(e)

    return results


def get_target_groups_for_load_balancer(load_balancer_arn):
    try:
        return _make_api_call(
            'describe_target_groups',
            LoadBalancerArn=load_balancer_arn
        )['TargetGroups']
    except ServiceError as e:
        raise NotFoundError(e)


def get_listeners_for_load_balancer(load_balancer_arn):
    return _make_api_call(
            'describe_listeners',
            LoadBalancerArn=load_balancer_arn
        )


def describe_load_balancers(load_balancer_name):
    return _make_api_call(
            'describe_load_balancers',
            Names=load_balancer_name
        )


def _sleep_to_prevent_elbv2_throttling():
    time.sleep(0.5)
