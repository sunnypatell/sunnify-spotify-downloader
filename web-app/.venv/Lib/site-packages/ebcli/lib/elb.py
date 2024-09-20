# Copyright 2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
from cement.utils.misc import minimal_logger

from ebcli.lib import aws
from ebcli.objects.exceptions import ServiceError, NotFoundError
from ebcli.resources.statics import elb_names

LOG = minimal_logger(__name__)


def _make_api_call(operation_name, **operation_options):
    return aws.make_api_call('elb', operation_name, **operation_options)


def version(load_balancer_name):
    if 'arn:aws:elasticloadbalancing' in load_balancer_name:
        return elb_names.APPLICATION_VERSION
    return elb_names.CLASSIC_VERSION


def is_classic_load_balancer(load_balancer_name):
    return 'arn:aws:elasticloadbalancing' not in load_balancer_name


def get_health_of_instances(load_balancer_name):
    try:
        result = _make_api_call(
            'describe_instance_health',
            LoadBalancerName=load_balancer_name
        )
    except ServiceError as e:
        raise NotFoundError(e)

    return result['InstanceStates']
