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

import os
import random
import time
import warnings

import botocore
import botocore.exceptions
import botocore.parsers
import botocore.session
from botocore.config import Config
from botocore.loaders import Loader
from cement.utils.misc import minimal_logger

from ebcli import __version__
from ebcli.lib.botopatch import apply_patches
from ebcli.lib.utils import static_var
from ebcli.objects.exceptions import ServiceError, NotAuthorizedError, \
    CredentialsError, NoRegionError,  ValidationError, \
    InvalidProfileError, ConnectionError, AlreadyExistsError, NotFoundError, \
    NotAuthorizedInRegionError
from ebcli.resources.strings import strings

LOG = minimal_logger(__name__)

BOTOCORE_DATA_FOLDER_NAME = 'botocoredata'

_api_clients = {}
_profile = None
_profile_env_var = 'AWS_EB_PROFILE'
_id = None
_key = None
_region_name = None
_verify_ssl = True
_endpoint_url = None
_debug = False

apply_patches()


def _flush():
    # Should be used for resetting tests only
    global _api_clients, _profile, _id, _key, _region_name, _verify_ssl
    _api_clients = {}
    _get_botocore_session.botocore_session = None
    _profile = None
    _id = None
    _key = None
    _region_name = None
    _verify_ssl = True


def set_session_creds(id, key):
    global _api_clients, _id, _key
    _id = id
    _key = key

    # invalidate all old clients
    _api_clients = {}


def set_profile(profile):
    global _profile, _api_clients
    _profile = profile

    # Invalidate session and old clients
    _get_botocore_session.botocore_session = None
    _api_clients = {}


def get_profile():
    if _profile is not None:
        return _profile
    from ebcli.operations import commonops
    return commonops.get_default_profile(require_default=True)


def set_region(region_name):
    global _region_name
    _region_name = region_name

    # Invalidate session and old clients
    _get_botocore_session.botocore_session = None


def set_endpoint_url(endpoint_url):
    global _endpoint_url
    _endpoint_url = endpoint_url


def no_verify_ssl():
    global _verify_ssl
    _verify_ssl = False


def set_profile_override(profile):
    global _profile_env_var
    set_profile(profile)
    _profile_env_var = None


def set_debug():
    global _debug
    _debug = True


def _set_user_agent_for_session(session):
    session.user_agent_name = 'eb-cli'
    session.user_agent_version = __version__


def _get_data_loader():
    # Creates a botocore data loader that loads custom data files
    # FIRST, creating a precedence for custom files.
    data_folder = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                               BOTOCORE_DATA_FOLDER_NAME)

    return Loader(extra_search_paths=[data_folder, Loader.BUILTIN_DATA_PATH],
                  include_default_search_paths=False)


def _get_client(service_name):
    aws_access_key_id = _id
    aws_secret_key = _key
    if service_name in _api_clients:
        return _api_clients[service_name]

    session = _get_botocore_session()
    if service_name == 'elasticbeanstalk':
        endpoint_url = _endpoint_url
    else:
        endpoint_url = None
    try:
        LOG.debug('Creating new Botocore Client for ' + str(service_name))
        client = session.create_client(service_name,
                                       endpoint_url=endpoint_url,
                                       aws_access_key_id=aws_access_key_id,
                                       aws_secret_access_key=aws_secret_key,
                                       verify=_verify_ssl,
                                       config=Config(signature_version='s3v4'))

    except botocore.exceptions.ProfileNotFound as e:
        raise InvalidProfileError(e)
    LOG.debug('Successfully created session for ' + service_name)

    _api_clients[service_name] = client
    return client


@static_var('botocore_session', None)
def _get_botocore_session():
    if _get_botocore_session.botocore_session is None:
        LOG.debug('Creating new Botocore Session')
        LOG.debug('Botocore version: {0}'.format(botocore.__version__))
        session = botocore.session.get_session({
            'profile': (None, _profile_env_var, _profile, None),
        })
        session.set_config_variable('region', _region_name)
        session.set_config_variable('profile', _profile)
        session.register_component('data_loader', _get_data_loader())
        _set_user_agent_for_session(session)
        _get_botocore_session.botocore_session = session
        if _debug:
            session.set_debug_logger()

    return _get_botocore_session.botocore_session


def get_region_name():
    return _region_name


def get_credentials():
    client_creds = _get_client('elasticbeanstalk')._request_signer._credentials
    return botocore.credentials.Credentials(
        access_key=client_creds.access_key,
        secret_key=client_creds.secret_key,
    )


def make_api_call(service_name, operation_name, **operation_options):
    operation = _set_operation(service_name, operation_name)
    aggregated_error_message = []
    max_attempts = 10

    region = _region_name
    if not region:
        region = 'default'

    attempt = 0
    while True:
        attempt += 1
        if attempt > 1:
            LOG.debug('Retrying -- attempt #' + str(attempt))
        _sleep(_get_delay(attempt))
        try:
            LOG.debug('Making api call: (' +
                      service_name + ', ' + operation_name +
                      ') to region: ' + region + ' with args:' + str(operation_options))
            response_data = operation(**operation_options)
            status = response_data['ResponseMetadata']['HTTPStatusCode']
            LOG.debug('API call finished, status = ' + str(status))
            if response_data:
                LOG.debug('Response: ' + str(response_data))

            return response_data

        except botocore.exceptions.ClientError as e:
            _handle_response_code(e.response, attempt, aggregated_error_message)
        except botocore.parsers.ResponseParserError as e:
            LOG.debug('Botocore could not parse response received')
            if attempt > max_attempts:
                raise MaxRetriesError(
                    'Max retries exceeded for ResponseParserErrors'
                    + os.linesep.join(aggregated_error_message)
                )

            aggregated_error_message.insert(attempt, str(e))
        except botocore.exceptions.NoCredentialsError:
            LOG.debug('No credentials found')
            raise CredentialsError('Operation Denied. You appear to have no'
                                   ' credentials')
        except botocore.exceptions.PartialCredentialsError as e:
            LOG.debug('Credentials incomplete')
            raise CredentialsError(str(e))

        except (botocore.exceptions.ValidationError,
                botocore.exceptions.ParamValidationError) as e:
            raise ValidationError(str(e))

        except botocore.exceptions.EndpointConnectionError as e:
            LOG.debug(e)
            raise

        except botocore.exceptions.BotoCoreError:
            LOG.error('Botocore Error')
            raise

        except IOError as error:
            if hasattr(error.args[0], 'reason') and str(error.args[0].reason) == \
                    '[Errno -2] Name or service not known':
                raise ConnectionError()

            LOG.error('Error while contacting Elastic Beanstalk Service')
            LOG.debug('error:' + str(error))
            raise ServiceError(error)


def _handle_response_code(response_data, attempt, aggregated_error_message):
    max_attempts = 10

    LOG.debug('Response: ' + str(response_data))
    status = response_data['ResponseMetadata']['HTTPStatusCode']
    LOG.debug('API call finished, status = ' + str(status))
    try:
        message = str(response_data['Error']['Message'])
    except KeyError:
        message = ""
    if status == 400:
        error = _get_400_error(response_data, message)
        if isinstance(error, ThrottlingError):
            LOG.debug('Received throttling error')
            if attempt > max_attempts:
                raise MaxRetriesError('Max retries exceeded for '
                                      'throttling error')
        else:
            raise error
    elif status == 403:
        LOG.debug('Received a 403')
        if not message:
            message = 'Are your permissions correct?'
        if _region_name == 'cn-north-1':
            raise NotAuthorizedInRegionError('Operation Denied. ' + message +
                                             '\n' +
                                             strings['region.china.credentials'])
        else:
            raise NotAuthorizedError('Operation Denied. ' + message)
    elif status == 404:
        LOG.debug('Received a 404')
        raise NotFoundError(message)
    elif status == 409:
        LOG.debug('Received a 409')
        raise AlreadyExistsError(message)
    elif status in (500, 503, 504):
        LOG.debug('Received 5XX error')
        retry_failure_message = \
            'Received 5XX error during attempt #{0}\n   {1}\n'.format(
                str(attempt),
                message
            )

        aggregated_error_message.insert(attempt, retry_failure_message)

        if attempt > max_attempts:
            _handle_500_error(('\n').join(aggregated_error_message))
    else:
        raise ServiceError('API Call unsuccessful. '
                           'Status code returned ' + str(status))


def _set_operation(service_name, operation_name):
    try:
        client = _get_client(service_name)
    except botocore.exceptions.UnknownEndpointError as e:
        raise NoRegionError(e)
    except botocore.exceptions.PartialCredentialsError as e:
        LOG.debug('Credentials incomplete')
        raise CredentialsError('Your credentials are not complete. Error: {0}'
                               .format(e))
    except botocore.exceptions.NoRegionError:
        raise NoRegionError()

    if not _verify_ssl:
        warnings.filterwarnings("ignore")

    return getattr(client, operation_name)


def _get_delay(attempt_number):
    if attempt_number == 1:
        return 0
    # Exponential backoff
    rand_int = random.randrange(0, 2**attempt_number)
    delay = rand_int * 0.05  # delay time is 50 ms
    LOG.debug('Sleeping for ' + str(delay) + ' seconds.')
    return delay


def _get_400_error(response_data, message):
    code = response_data['Error']['Code']
    LOG.debug('Received a 400 Error')
    if code == 'InvalidParameterValue':
        return InvalidParameterValueError(message)
    elif code == 'InvalidQueryParameter':
        return InvalidQueryParameterError(message)
    elif code.startswith('Throttling'):
        return ThrottlingError(message)
    elif code.startswith('ResourceNotFound'):
        return NotFoundError(message)
    elif code.startswith('TooManyPlatformsException'):
        return TooManyPlatformsError(message)
    elif code.startswith('TooManyConfigurationTemplatesException'):
        message = [
            'Your request cannot be completed. You have reached the maximum',
            'number of saved configuration templates. Learn more about service',
            'limits: http://docs.aws.amazon.com/general/latest/gr/aws_service_limits.html'
        ]
        return TooManyConfigurationTemplatesException(' '.join(message))
    else:
        return ServiceError(message, code=code)


def _handle_500_error(aggregated_error_message):
    raise MaxRetriesError('Max retries exceeded for '
                          'service error (5XX)\n' +
                          aggregated_error_message)


def _sleep(delay):
    time.sleep(delay)


class InvalidParameterValueError(ServiceError):
    pass


class InvalidQueryParameterError(ServiceError):
    pass


class ThrottlingError(ServiceError):
    pass


class MaxRetriesError(ServiceError):
    pass


class TooManyPlatformsError(ServiceError):
    pass


class TooManyConfigurationTemplatesException(ServiceError):
    pass
