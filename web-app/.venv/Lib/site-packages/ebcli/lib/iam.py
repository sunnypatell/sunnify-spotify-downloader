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
import re

from cement.utils.misc import minimal_logger

from ebcli.lib import aws
from ebcli.objects.exceptions import AlreadyExistsError

LOG = minimal_logger(__name__)
ACCOUNT_ID_REGEX = re.compile(r'arn:aws:iam::(\d+):.*')


def _make_api_call(operation_name, **operation_options):
    return aws.make_api_call('iam', operation_name, **operation_options)


def account_id():
    user_arn = _make_api_call('get_user')['User']['Arn']

    return re.search(ACCOUNT_ID_REGEX, user_arn).group(1)


def get_instance_profiles():
    result = _make_api_call('list_instance_profiles')
    return result['InstanceProfiles']


def get_roles():
    isTruncated = True
    marker = ''
    roles = []
    while isTruncated:
        if marker == '':
            result = _make_api_call('list_roles')
        else:
            result = _make_api_call('list_roles', Marker=marker)
        isTruncated = result['IsTruncated']
        existing_roles = result['Roles']
        for role in existing_roles:
            roles.append(role)
        if isTruncated:
            marker = result['Marker']

    return roles


def get_role(role_name):
    result = _make_api_call('get_role',
                            RoleName=role_name)
    return result['Role']


def create_instance_profile(profile_name, allow_recreate=True):
    """
    Create IAM instance profile.
    Return profile_name if creation succeeds, None if allowing
    recreate while profile already exists
    """
    try:
        _make_api_call('create_instance_profile',
                       InstanceProfileName=profile_name)
        return profile_name
    except AlreadyExistsError:
        if allow_recreate:
            return None
        else:
            raise


def get_instance_profile_names():
    profiles = get_instance_profiles()
    lst = []
    for profile in profiles:
        lst.append(profile['InstanceProfileName'])

    return lst


def get_role_names():
    roles = get_roles()
    lst = []
    for role in roles:
        lst.append(role['RoleName'])

    return lst


def add_role_to_profile(profile, role, allow_recreate=True):
    """ Add role to profile. Swallow AlreadyExistsError if allow_recreate set to True """
    try:
        _make_api_call('add_role_to_instance_profile',
                       InstanceProfileName=profile,
                       RoleName=role)
    except AlreadyExistsError:
        if not allow_recreate:
            raise


def create_role_with_policy(role_name, trust_document, policy_arns, allow_recreate=True):
    """
    This is a higher level function that creates a role, a policy, and attaches
    everything together
    :param role_name: Name of role to create
    :param trust_document: Policy for trusted entities assuming role
    :param policy: User policy that defines allowable actions
    :param allow_recreate: Set to True to ignore AlreadyExistsError
    """
    ret = create_role(role_name, trust_document, allow_recreate=allow_recreate)
    for arn in policy_arns:
        attach_role_policy(role_name, arn)
    return ret


def create_policy(policy_name, policy):
    result = _make_api_call('create_policy',
                            PolicyName=policy_name,
                            PolicyDocument=policy)
    return result['Policy']['Arn']


def attach_role_policy(role_name, policy_arn):
    _make_api_call(
        'attach_role_policy',
        RoleName=role_name,
        PolicyArn=policy_arn
    )


def put_role_policy(role_name, policy_name, policy_json):
    _make_api_call(
        'put_role_policy',
        RoleName=role_name,
        PolicyName=policy_name,
        PolicyDocument=policy_json
    )


def create_role(role_name, document, allow_recreate=True):
    """
    Create IAM role and attach assume role policy.
    Return role_name if creation succeeds, None if allowing
    recreate while role already exists
    """
    try:
        _make_api_call('create_role',
                       RoleName=role_name,
                       AssumeRolePolicyDocument=document)
        return role_name
    except AlreadyExistsError:
        if allow_recreate:
            return None
        else:
            raise


def upload_server_certificate(cert_name, cert, private_key, chain=None):
    kwargs = dict(
        ServerCertificateName=cert_name,
        CertificateBody=cert,
        PrivateKey=private_key
    )
    if chain:
        kwargs['CertificateChain'] = chain

    result = _make_api_call('upload_server_certificate',
                            **kwargs)
    return result['ServerCertificateMetadata']


def get_managed_policy_document(arn):
    policy = _make_api_call('get_policy',
                            PolicyArn=arn)
    policy_version = policy['Policy']['DefaultVersionId']
    details = _make_api_call('get_policy_version',
                             PolicyArn=arn,
                             VersionId=policy_version)
    return details['PolicyVersion']['Document']

def role_exists(role_name):
    """
    Check if a given IAM role exists.
    :param role_name: Name of the IAM role to check.
    :return: True if the role exists, False otherwise.
    """
    roles = get_roles()
    for role in roles:
        if role['RoleName'] == role_name:
            return True
    return False