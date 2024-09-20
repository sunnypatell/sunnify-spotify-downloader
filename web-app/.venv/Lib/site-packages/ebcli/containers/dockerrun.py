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

from ebcli.core import fileoperations
from ebcli.objects.exceptions import ValidationError
from ebcli.resources.strings import strings


AUTH_BUCKET_KEY = 'Bucket'
AUTH_KEY = 'Authentication'
AUTHKEY_KEY = 'Key'
CONTAINER_PORT_KEY = 'ContainerPort'
IMG_NAME_KEY = 'Name'
IMG_KEY = 'Image'
IMG_UPDATE_KEY = 'Update'
JSON_FALSE = 'false'
LOGGING_KEY = 'Logging'
PORTS_KEY = 'Ports'
VERSION_ONE = '1'
VERSION_KEY = 'AWSEBDockerrunVersion'
VERSION_TWO = '2'


def validate_dockerrun_v1(dockerrun, is_used_to_make_dockerfile):
    """
    Validates given Dockerrun.aws.json version, and that if no Dockerfile
    exists, Image.Name and Ports[0].ContainerPort exists.
    :param dockerrun: dict: dictionary representation of Dockerrun.aws.json
    :param is_used_to_make_dockerfile: bool: whether used to make Dockerfile
    :return: None
    """

    if dockerrun is None:
        return

    if _get_version(dockerrun) != VERSION_ONE:
        raise ValidationError(strings['local.invaliddockerrunversion'])

    if not is_used_to_make_dockerfile:
        return

    if IMG_KEY not in dockerrun or IMG_NAME_KEY not in dockerrun[IMG_KEY]:
        raise ValidationError(strings['local.missingdockerrunimage'])

    elif PORTS_KEY not in dockerrun:
        raise ValidationError(strings['local.missingdockerrunports'])

    elif CONTAINER_PORT_KEY not in dockerrun[PORTS_KEY][0]:
        raise ValidationError(strings['local.missingdockerruncontainerport'])


def validate_dockerrun_v2(dockerrun):

    if dockerrun is None:
        raise ValidationError(strings['local.missingdockerrun'])

    elif _get_version(dockerrun) != VERSION_TWO:
        raise ValidationError(strings['local.invaliddockerrunversion'])


def require_docker_pull(dockerrun):
    """
    Whether 'docker pull' is necessary. Return True if and only if
    Dockerrun.aws.json Image.Update value is not false.
    :param dockerrun: dict: dictionary representation of Dockerrun.aws.json
    :return: bool
    """

    return (dockerrun is None or IMG_KEY not in dockerrun or
            dockerrun[IMG_KEY].get(IMG_UPDATE_KEY) != JSON_FALSE)


def get_dockerrun(dockerrun_path):
    """
    Return dict representation of Dockerrun.aws.json in dockerrun_path
    Return None if Dockerrun doesn't exist at that path.
    :param dockerrun_path: str: full path to Dockerrun.aws.json
    :return: dict
    """

    try:
        return fileoperations.get_json_dict(dockerrun_path)
    except ValueError:
        raise ValidationError(strings['local.invalidjson'])
    except IOError:  # Dockerrun.aws.json doesn't exist
        return None


def require_auth_download(dockerrun):
    """
    Return whether Authentication.Key and Authentication.Bucket is provided
    in Dockerrun.aws.json, in which case we have to pull down the bucket.
    :param dockerrun: dict: dictionary representation of Dockerrun.aws.json
    :return: bool
    """
    if dockerrun is None:
        return False

    try:
        get_auth_key(dockerrun)
        get_auth_bucket_name(dockerrun)
        return True
    except KeyError:
        return False


def get_auth_key(dockerrun):
    """
    Get Authentication.Key value of dockerrun.
    :param dockerrun: dict: dictionary representation of Dockerrun.aws.json
    :return: str
    """
    if _get_version(dockerrun) == VERSION_ONE:
        authkey_key = AUTHKEY_KEY
    else:
        authkey_key = AUTHKEY_KEY.lower()

    return _get_auth(dockerrun)[authkey_key]


def get_auth_bucket_name(dockerrun):
    """
    Get Authentication.Bucket value of dockerrun.
    :param dockerrun: dict: dictionary representation of Dockerrun.aws.json
    :return: str
    """

    if _get_version(dockerrun) == VERSION_ONE:
        auth_bucket_key = AUTH_BUCKET_KEY
    else:
        auth_bucket_key = AUTH_BUCKET_KEY.lower()

    return _get_auth(dockerrun)[auth_bucket_key]


def get_logdir(dockerrun):
    """
    Get Logging value of dockerrun.
    :param dockerrun: dict: dictionary representation of Dockerrun.aws.json
    :return: str
    """

    return dockerrun.get(LOGGING_KEY) if dockerrun else None


def get_base_img(dockerrun):
    return dockerrun[IMG_KEY][IMG_NAME_KEY]


def get_exposed_port(dockerrun):
    return dockerrun[PORTS_KEY][0][CONTAINER_PORT_KEY]


def _get_auth(dockerrun):
    if _get_version(dockerrun) == VERSION_ONE:
        auth_key = AUTH_KEY
    else:
        auth_key = AUTH_KEY.lower()

    return dockerrun[auth_key]


def _get_version(dockerrun):
    if VERSION_KEY in dockerrun:
        return str(dockerrun[VERSION_KEY])
    else:
        return None
