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
from ebcli.objects.exceptions import ServiceError, AlreadyExistsError, \
    NotFoundError
from ebcli.resources.strings import responses

LOG = minimal_logger(__name__)


def _make_api_call(operation_name, **operation_options):
    return aws.make_api_call('ec2', operation_name, **operation_options)


def get_key_pairs():
    result = _make_api_call('describe_key_pairs')
    return result['KeyPairs']


def import_key_pair(keyname, key_material):
    try:
        result = _make_api_call(
            'import_key_pair',
            KeyName=keyname,
            PublicKeyMaterial=key_material
        )
    except ServiceError as e:
        if e.message.endswith('already exists.'):
            raise AlreadyExistsError(e.message)
        else:
            raise

    return result


def describe_instances(instance_ids):
    result = _make_api_call('describe_instances',
                            InstanceIds=instance_ids)

    instances = []
    for r in result.get('Reservations', {}):
        for i in r.get('Instances', {}):
            instances.append(i)
    return instances


def describe_instance(instance_id):
    result = describe_instances([instance_id])

    try:
        return result[0]
    except (IndexError, NotFoundError):
        raise NotFoundError('Instance {0} not found.'.format(instance_id))


def has_default_vpc():
    result = _make_api_call('describe_account_attributes',
                            AttributeNames=['default-vpc'])
    default_vpc = None
    for attribute in result['AccountAttributes']:
        if attribute['AttributeName'] == 'default-vpc':
            try:
                default_vpc = attribute['AttributeValues'][0]['AttributeValue']
            except (KeyError, IndexError):
                default_vpc = None

    if default_vpc and default_vpc.lower() != 'none':
        return True
    else:
        return False


def revoke_ssh(security_group_id):
    try:
        _make_api_call(
            'revoke_security_group_ingress',
            GroupId=security_group_id,
            IpProtocol='tcp',
            ToPort=22,
            FromPort=22,
            CidrIp='0.0.0.0/0'
        )
    except ServiceError as e:
        if e.message.startswith(responses['ec2.sshalreadyopen']):
            pass
        else:
            raise


def authorize_ssh(security_group_id):
    try:
        _make_api_call(
            'authorize_security_group_ingress',
            GroupId=security_group_id,
            IpProtocol='tcp',
            ToPort=22,
            FromPort=22,
            CidrIp='0.0.0.0/0'
        )
    except ServiceError as e:
        if e.code == 'InvalidPermission.Duplicate':
            pass
        else:
            raise


def describe_security_group(security_group_id):
    result = _make_api_call('describe_security_groups',
                            GroupIds=[security_group_id])
    if result and len(result['SecurityGroups']) < 1:
        raise NotFoundError('Security Group {} not found.'
                            .format(security_group_id))
    return result['SecurityGroups'][0]


def terminate_instance(instance_id):
    return _make_api_call('terminate_instances',
                          InstanceIds=[instance_id])


def reboot_instance(instance_id):
    return _make_api_call('reboot_instances',
                          InstanceIds=[instance_id])
