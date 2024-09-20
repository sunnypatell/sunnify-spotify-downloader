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
from datetime import datetime, timedelta

from cement.utils.misc import minimal_logger

from ebcli.lib import aws, utils
from ebcli.objects.exceptions import EBCLIException
from ebcli.objects.event import CFNEvent

LOG = minimal_logger(__name__)


def _make_api_call(operation_name, **operation_options):
    return aws.make_api_call('cloudformation', operation_name, **operation_options)



def events(stack_name, start_time=None):
    LOG.debug('Inside describe_stack_events api wrapper')

    next_token = None
    _events = []

    while True:
        if next_token:
            result = _make_api_call(
                'describe_stack_events',
                StackName=stack_name,
                NextToken=next_token
            )
        else:
            result = _make_api_call('describe_stack_events', StackName=stack_name)

        _events.extend(CFNEvent.json_to_event_objects(result['StackEvents']))
        next_token = result.get('NextToken')

        if not next_token:
            break

        if start_time and _events and not _events[-1].happened_after(start_time):
            break
        utils.prevent_throttling()

    if start_time:
        return [event for event in _events if event.happened_after(start_time)]
    return _events


def get_template(stack_name):
    result = _make_api_call('get_template',
                            StackName=stack_name)
    return result


def describe_stacks(stack_name=None):
    kwargs = dict()
    if stack_name:
        kwargs['StackName'] = stack_name
    response = _make_api_call('describe_stacks', **kwargs)
    next_token = response.get('NextToken')
    all_stacks = response['Stacks']
    while next_token:
        utils.sleep(sleep_time=0.5)
        response = _make_api_call('describe_stacks',NextToken=next_token)
        all_stacks.extend(response['Stacks'])
        next_token = response.get('NextToken')
    return all_stacks


def stack_names():
    all_stacks = describe_stacks()

    return [stack['StackName'] for stack in all_stacks]


def wait_until_stack_exists(stack_name, timeout=120):
    """
    Given a template name, wait until stack is successfully created
    or 'timeout' seconds have elapsed.
    :param stack_name: name of the CloudFormation stack whose creation is pending
    :param timeout: number of seconds after which to stop polling 'DescribeStacks'
    :return:
    """
    LOG.debug('Inside describe_stacks api wrapper')

    stack_exists = False
    start_time = datetime.now()

    while not stack_exists:
        if (datetime.now() - start_time) > timedelta(timeout):
            raise CFNTemplateNotFound(
                "Could not find CFN stack, '{stack_name}'.".format(stack_name=stack_name)
            )

        all_stacks = describe_stacks()

        if [stack for stack in all_stacks if stack['StackName'] == stack_name]:
            stack_exists = True
        else:
            utils.sleep()


class CFNTemplateNotFound(EBCLIException):
    """
    Exception class to raise when a CFN stack is not found
    """
