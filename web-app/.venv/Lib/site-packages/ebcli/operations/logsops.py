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
import calendar
from datetime import datetime
import os
import threading
import time
import traceback

from cement.utils.misc import minimal_logger
from six import iteritems

from ebcli.core import fileoperations, io
from ebcli.lib import elasticbeanstalk, utils, cloudwatch
from ebcli.lib.aws import MaxRetriesError
from ebcli.resources.strings import strings, prompts
from ebcli.resources.statics import namespaces, option_names, logs_operations_constants
from ebcli.objects.exceptions import InvalidOptionsError, NotFoundError, ServiceError
from ebcli.operations import commonops

LOG = minimal_logger(__name__)
TAIL_LOG_SIZE = 100
BEANSTALK_LOG_PREFIX = '/aws/elasticbeanstalk'


def beanstalk_log_group_builder(env_name, log_group_name=None):
    """
    Method constructs normalizes the `log_group_name` passed in by the customer.

    :param env_name: current environment being used
    :param log_group_name: One of the following
        - None: the method defaults to using '/aws/elasticbeanstalk/<`env_name`>' as
          the `log_group_name` in this case
        - '/aws/elasticbeanstalk/<`env_name`>/<log_group_name>': the `log_group_name`
          is used as is
        - '<log_group_name>': '/aws/elasticbeanstalk/<`env_name`>' is prefixed to the
          `log_group_name`

    :return: a normalized `log_group_name`
    """
    log_group_name = log_group_name or deployment_logs_log_group_name(env_name)

    if not log_group_name.startswith(cloudwatch_log_group_prefix_for_environment(env_name)):
        log_group_name = '{0}/{1}/{2}'.format(
            BEANSTALK_LOG_PREFIX, env_name, log_group_name
        ).replace("//", "/")

    return log_group_name


def cloudwatch_log_group_prefix_for_environment(env_name):
    """
    Generates the CloudWatch logGroup prefix for the environment, `env_name`.
    :param env_name: An Elastic Beanstalk environment name
    :return: A CloudWatch logGroup name prefix of the form /aws/elasticbeanstalk/<`env_name`>
    """
    return '{0}/{1}'.format(BEANSTALK_LOG_PREFIX, env_name)


def cloudwatch_log_group_for_environment_health_streaming(env_name):
    """
    Generates the environment-health.log CloudWatch logGroup name for the environment, `env_name`.
    :param env_name: An Elastic Beanstalk environment name
    :return: A CloudWatch logGroup name prefix of the form /aws/elasticbeanstalk/<`env_name`>
    """
    return '{0}/{1}'.format(cloudwatch_log_group_prefix_for_environment(env_name), 'environment-health.log')


def cloudwatch_log_stream_names(log_group, log_stream_name_prefix):
    """
    Returns all of the logStream names associated with `log_group` with the
    prefix, `log_stream_name_prefix` if one is specified
    :param log_group: A CloudWatch logGroup whose logStream names to retrieve
    :param log_stream_name_prefix: A prefix to filter logStream names by
    :return: All of the logStream names associated with `log_group`
             with the prefix, `log_stream_name_prefix` if one
    is specified
    """
    return cloudwatch.get_all_stream_names(
        log_group_name=log_group,
        log_stream_name_prefix=log_stream_name_prefix
    )


def deployment_logs_log_group_name(env_name):
    """
    Determines the default deployment logGroup for the environment, `env_name`
    :param env_name: An Elastic Beanstalk environment name
    :return: 'var/log/eb-activity.log' if the environment is using a
             non-Windows platform, 'EBDeploy-Log' otherwise
    """
    environment = elasticbeanstalk.get_environment(env_name=env_name)
    if 'windows' in environment.platform.name.lower():
        log_group_suffix = 'EBDeploy-Log'
    # TODO: The logic here is we judge if platform is beyond or equal to Amazon Linux 2 - if it is we use "var/log/eb-engine.log" otherwise we use 'var/log/eb-activity.log'
    # However the problem is Amazon Linux 1 platform naming does not have a fixed pattern, which is hard to write if statement
    # Therefore we have to judge by 'Amazon Linux 2/' or 'Amazon Linux 2023/' which follows a fixed naming pattern
    # We should resolve this tech debt by investigating the naming pattern of Amazon linux 1 platform. Luckily there
    # will be no more new Amazon Linux 1 platforms so once we figured out a pattern, we would solve the issues forever.
    elif 'Amazon Linux 2/' in environment.platform.name or 'Amazon Linux 2023/' in environment.platform.name:
        log_group_suffix = "var/log/eb-engine.log"
    else:
        log_group_suffix = 'var/log/eb-activity.log'

    return cloudwatch_log_group_prefix_for_environment(env_name) + '/' + log_group_suffix


def disable_cloudwatch_logs(app_name, env_name, cloudwatch_log_source):
    """
    Disables CloudWatch log-streaming for the given environment if the required streaming of the
    specified `cloudwatch_log_source`s is not already disabled
    :param app_name: application name
    :param env_name: environment name
    :param cloudwatch_log_source: the source of logs. Defaults to 'instance' if value is 'None'.
        Use
            - 'instance' to disable instance log0streaming
            - 'health' to disable health transition log-streaming
            - 'all': disable streaming of all CloudWatch log sources
    :return None
    """
    cloudwatch_log_source = cloudwatch_log_source or logs_operations_constants.LOG_SOURCES.INSTANCE_LOG_SOURCE
    configuration_settings = elasticbeanstalk.describe_configuration_settings(app_name, env_name)
    option_settings = []
    timeout = 5

    if cloudwatch_log_source in [
        logs_operations_constants.LOG_SOURCES.INSTANCE_LOG_SOURCE,
        logs_operations_constants.LOG_SOURCES.ALL_LOG_SOURCES
    ]:
        if instance_log_streaming_enabled(app_name, env_name, config_settings=configuration_settings):
            option_settings.append(_instance_log_streaming_option_setting(disable=True))
            io.echo(strings['cloudwatch_instance_log_streaming.disable'])
            timeout = 15
        else:
            io.echo(strings['cloudwatch_instance_log_streaming.already_disabled'])

    if cloudwatch_log_source in [
        logs_operations_constants.LOG_SOURCES.ENVIRONMENT_HEALTH_LOG_SOURCE,
        logs_operations_constants.LOG_SOURCES.ALL_LOG_SOURCES
    ]:
        if environment_health_streaming_enabled(app_name, env_name, config_settings=configuration_settings):
            io.echo(strings['cloudwatch_environment_health_log_streaming.disable'])
            option_settings.append(_environment_health_log_streaming_option_setting(disable=True))
        else:
            io.echo(strings['cloudwatch_environment_health_log_streaming.already_disabled'])

    if option_settings:
        commonops.update_environment(env_name, changes=option_settings, nohang=False, timeout=timeout)


def enable_cloudwatch_logs(app_name, env_name, cloudwatch_log_source):
    """
    Enables CloudWatch log-streaming for the given environment if the required streaming of the
    specified `cloudwatch_log_source`s is not already enabled
    :param app_name: application name
    :param env_name: environment name
    :param cloudwatch_log_source: the source of logs. Defaults to 'instance' if value is 'None'.
        Use
            - 'instance' to enable instance log0streaming
            - 'health' to enable health transition log-streaming
            - 'all': enable streaming of all CloudWatch log sources
    :return None
    """
    cloudwatch_log_source = cloudwatch_log_source or logs_operations_constants.LOG_SOURCES.INSTANCE_LOG_SOURCE

    configuration_settings = elasticbeanstalk.describe_configuration_settings(app_name, env_name)
    option_settings = []
    timeout = 5

    if cloudwatch_log_source in [
        logs_operations_constants.LOG_SOURCES.ALL_LOG_SOURCES,
        logs_operations_constants.LOG_SOURCES.INSTANCE_LOG_SOURCE
    ]:
        if not instance_log_streaming_enabled(app_name, env_name, config_settings=configuration_settings):
            timeout = 15
            option_settings.append(_instance_log_streaming_option_setting())
            io.echo(strings['cloudwatch_instance_log_streaming.enable'])
        else:
            io.echo(strings['cloudwatch_instance_log_streaming.already_enabled'])

    if cloudwatch_log_source in [
        logs_operations_constants.LOG_SOURCES.ALL_LOG_SOURCES,
        logs_operations_constants.LOG_SOURCES.ENVIRONMENT_HEALTH_LOG_SOURCE,
    ]:
        _raise_if_environment_is_not_using_enhanced_health(configuration_settings)

        if not environment_health_streaming_enabled(
                app_name,
                env_name,
                config_settings=configuration_settings
        ):
            option_settings.append(_environment_health_log_streaming_option_setting())
            io.echo(strings['cloudwatch_environment_health_log_streaming.enable'])
        else:
            io.echo(strings['cloudwatch_environment_health_log_streaming.already_enabled'])

    if not option_settings:
        return

    _echo_link_to_cloudwatch_console(env_name)

    commonops.update_environment(env_name, changes=option_settings, nohang=False, timeout=timeout)


def environment_health_streaming_enabled(app_name, env_name, config_settings=None):
    """
    Checks if health transition streaming is enabled for the given environment
    :param app_name: application name
    :param env_name: environment name
    :param config_settings: the raw response of a call to describe_configuration_settings
    :return: boolean if the given environment has health transition streaming enabled
    """
    config_settings = config_settings or elasticbeanstalk.describe_configuration_settings(app_name, env_name)
    stream_enabled = elasticbeanstalk.get_specific_configuration(
        config_settings,
        namespaces.CLOUDWATCH_ENVIRONMENT_HEALTH_LOGS,
        option_names.CLOUDWATCH_ENVIRONMENT_HEALTH_LOGS_ENABLED
    )

    return stream_enabled == 'true'


def get_cloudwatch_log_stream_events(log_group_name, stream_name, num_log_events=None):
    """
    Gets log events from CloudWatch and appends them to a single string to output with each line prefixed with
    the stream name.

    :param log_group_name: cloudwatch logGroup
    :param stream_name: cloudwatch stream name
    :param num_log_events: number of log events to retrieve; default is
                           cloudwatch's max: 10k or 1MB of messages
    :return: single string will all log events concatenated together
    """
    full_log = []
    full_log_blob = ''
    try:
        response = cloudwatch.get_log_events(log_group_name, stream_name, limit=num_log_events)

        for event in response.get('events', []):
            message = event.get('message')
            full_log.append('[{stream_name}] {message}'.format(stream_name=stream_name, message=message))

        full_log_blob = os.linesep.join(full_log)

    except ServiceError as e:
        LOG.debug('Received service error {}'.format(e))
    except Exception as e:
        LOG.debug('Exception raised: ' + str(e))
        LOG.debug(traceback.format_exc())

    return full_log_blob


def get_cloudwatch_messages(
        log_group_name,
        stream_name,
        formatter,
        next_token,
        start_time,
        messages_handler,
        sleep_time=10
):
    """
    Polls periodically the logStream `stream_name` until interrupted through a
    KeyboardInterrupt or an unexpected exception
    :param log_group_name: A CloudWatch logGroup in which the logStream `stream_name`
                           exists
    :param stream_name: A CloudWatch logStream to poll
    :param formatter: The object that formats the output to be displayed in the terminal
    :param next_token: The token for the next set of items to return
    :param start_time: The start of the time range, expressed as the number of
                       milliseconds after Jan 1, 1970 00:00:00 UTC.
                       Events with a time stamp earlier than this time are not included.
    :param messages_handler:
    :param sleep_time: Time in seconds to sleep before polling CloudWatch for newer events
    :return: None
    """
    while True:
        try:
            messages, next_token, start_time = _get_cloudwatch_messages(
                log_group_name,
                stream_name,
                formatter,
                next_token,
                start_time
            )
            if messages:
                messages_handler(messages)
            else:
                break
        except ServiceError as e:
            io.log_error(e)
            break
        except Exception as e:
            LOG.debug('Exception raised: ' + str(e))
            LOG.debug(traceback.format_exc())
        except KeyboardInterrupt:
            break

        _wait_to_poll_cloudwatch(sleep_time)
        start_time = _updated_start_time()


def get_instance_log_url_mappings(env_name, info_type):
    """
    Retrieves mappings of Beanstalk instance ids to S3 URLs on which logs are stored.
    :param env_name: An Elastic Beanstalk environment name
    :param info_type: The type of information to request. Possible values: tail, bundle
    :return: mappings of Beanstalk instance ids to S3 URLs
    """
    result = elasticbeanstalk.retrieve_environment_info(env_name, info_type)

    instance_id_list = dict()

    for log in result['EnvironmentInfo']:
        instance_id = log['Ec2InstanceId']
        url = log['Message']
        instance_id_list[instance_id] = url

    return instance_id_list


def get_logs(env_name, info_type, do_zip=False, instance_id=None):
    """
    Obtains the set of logs from ElasticBeanstalk for the environment `env_name` from ElasticBeanstalk
    (and not CloudWatch) for the environment, `env_name` and determines whether to tail it or bundle/zip
    it.
    :param env_name: An Elastic Beanstalk environment name
    :param info_type: The type of information to request. Possible values: tail, bundle
    :param do_zip: Whether the information retrieved should be zipped; works only with info_type 'bundle'
    :param instance_id: The specific EC2 instance associated with `env_name` whose log information to retrieve
    :return: None
    """
    instance_id_list = get_instance_log_url_mappings(env_name, info_type)

    if instance_id:
        instance_id_list = _updated_instance_id_list(instance_id_list, instance_id)

    if info_type == logs_operations_constants.INFORMATION_FORMAT.BUNDLE:
        _handle_bundle_logs(instance_id_list, do_zip)
    else:
        _handle_tail_logs(instance_id_list)


def instance_log_streaming_enabled(app_name, env_name, config_settings=None):
    """
    Checks if log streaming is enabled for the given environment
    :param app_name: application name
    :param env_name: environment name
    :param config_settings: the raw response of a call to describe_configuration_settings
    :return: boolean if the given environment has log streaming enabled
    """
    config_settings = (
        config_settings or
        elasticbeanstalk.describe_configuration_settings(app_name, env_name)
    )
    stream_enabled = elasticbeanstalk.get_specific_configuration(
        config_settings,
        namespaces.CLOUDWATCH_LOGS,
        option_names.STREAM_LOGS
    )

    return stream_enabled == 'true'


def normalize_log_group_name(env_name, log_group=None, cloudwatch_log_source=None):
    """
    Converts the given (potentially None) `log_group` name to a value that can be
    consumed by `describe_log_groups`.
    :param env_name: An Elastic Beanstalk environment name
    :param log_group: A value for the logGroup name specified by the customer, which
                      is potentially None
    :param cloudwatch_log_source: Name of the log source `log_group` belongs to. One among:
                                  instance, environment-health
    :return: A normalized logGroup name
    """
    if (
            not cloudwatch_log_source
            or cloudwatch_log_source == logs_operations_constants.LOG_SOURCES.INSTANCE_LOG_SOURCE
    ):
        log_group = beanstalk_log_group_builder(env_name, log_group)
    elif cloudwatch_log_source == logs_operations_constants.LOG_SOURCES.ENVIRONMENT_HEALTH_LOG_SOURCE:
        if log_group:
            raise InvalidOptionsError(
                strings['logs.log_group_and_environment_health_log_source']
            )
        log_group = beanstalk_log_group_builder(
            env_name,
            cloudwatch_log_group_for_environment_health_streaming(env_name)
        )
    else:
        raise InvalidOptionsError(
            strings[
                'logs.cloudwatch_log_source_argumnent_is_invalid_for_retrieval'
            ].format(cloudwatch_log_source)
        )

    return log_group


def paginate_cloudwatch_logs(platform_name, version, formatter=None):
    """
    Method periodically polls CloudWatch get_log_events to retrieve the logs for the
    logStream `version` within the logGroup
    defined by `version`
    :param platform_name: A CloudWatch logGroup in which the logStream `version` exists
    :param version: A CloudWatch logStream to poll
    :param formatter: The object that formats the output to be displayed in the terminal
    :return: None
    """
    log_group_name = _get_platform_builder_group_name(platform_name)
    next_token = None
    start_time = None
    messages_handler = (lambda messages: io.echo_with_pager(os.linesep.join(messages)))

    get_cloudwatch_messages(
        log_group_name,
        version,
        formatter,
        next_token,
        start_time,
        messages_handler,
        sleep_time=4
    )


def raise_if_instance_log_streaming_is_not_enabled(app_name, env_name):
    """
    Raises if CloudWatch instance log streaming is not enabled for the environment, `env_name`
    :param app_name: An Elastic Beanstalk application name
    :param env_name: An Elastic Beanstalk environment name contained within `app_name`
    :return: None
    """
    if not instance_log_streaming_enabled(app_name, env_name):
        raise InvalidOptionsError(strings['logs.instance_log_streaming_disabled'].format(env_name))


def raise_if_environment_health_log_streaming_is_not_enabled(app_name, env_name):
    """
    Raises if CloudWatch environment-health log streaming is not enabled for the environment, `env_name`
    :param app_name: An Elastic Beanstalk application name
    :param env_name: An Elastic Beanstalk environment name contained within `app_name`
    :return: None
    """
    if not environment_health_streaming_enabled(app_name, env_name):
        raise InvalidOptionsError(strings['logs.environment_health_log_streaming_disabled'].format(env_name))


def resolve_log_result_type(zip_argument, all_argument):
    """
    Determines whether logs should be tailed or bundled.
    :param zip_argument: Whether the customer has requested a zipped version of the logs
    :param all_argument: Whether the customer has requested the logs for all the instances
    :return: The `info_type` which is one among 'bundle' and 'tail'
    """
    if zip_argument or all_argument:
        return logs_operations_constants.INFORMATION_FORMAT.BUNDLE
    else:
        return logs_operations_constants.INFORMATION_FORMAT.TAIL


def retrieve_beanstalk_logs(env_name, info_type, do_zip=False, instance_id=None):
    """
    Obtains the set of logs from ElasticBeanstalk for the environment `env_name`.
    :param env_name: An Elastic Beanstalk environment name
    :param info_type: The type of information to request. Possible values: tail, bundle
    :param do_zip: Whether the information retrieved should be zipped; works only with info_type 'bundle'
    :param instance_id: The specific EC2 instance associated with `env_name` whose log information to retrieve
    :return: None
    """
    result = elasticbeanstalk.request_environment_info(env_name, info_type)

    request_id = result['ResponseMetadata']['RequestId']
    io.echo(prompts['logs.retrieving'])

    commonops.wait_for_success_events(
        request_id,
        timeout_in_minutes=2,
        sleep_time=1,
        stream_events=False,
        log_events=True
    )

    get_logs(env_name, info_type, do_zip=do_zip, instance_id=instance_id)


def retrieve_cloudwatch_instance_logs(
        log_group,
        info_type,
        do_zip=False,
        specific_log_stream=None
):
    """
    Retrieves CloudWatch logs for all the environment instances for the `log_group`
    unless `specific_log_stream` is specified.
    :param log_group: CloudWatch logGroup
    :param info_type:
        tail: to get the last 100 lines and returns the result to the terminal
        'bundle': get all of the logs and save them to a dir under
        .elasticbeanstalk/logs/
    :param do_zip: If True, zip the logs for the user
    :param specific_log_stream: Get logs for specific stream
    """
    retrieve_cloudwatch_logs(
        log_group,
        info_type,
        do_zip,
        specific_log_stream=specific_log_stream
    )


def retrieve_cloudwatch_environment_health_logs(
        log_group,
        info_type,
        do_zip=False
):
    """
    Retrieves the environment health information identified by the `log_group` from CloudWatch
    :param log_group: CloudWatch logGroup
    :param info_type:
        tail: to get the last 100 lines and returns the result to the terminal
        'bundle': get all of the logs and save them to a dir under .elasticbeanstalk/logs/
    :param do_zip: If True, zip the logs for the user
    :return:
    """
    retrieve_cloudwatch_logs(
        log_group,
        info_type,
        do_zip,
        specific_log_stream=None,
        cloudwatch_log_source=logs_operations_constants.LOG_SOURCES.ENVIRONMENT_HEALTH_LOG_SOURCE
    )


def retrieve_cloudwatch_logs(
        log_group,
        info_type,
        do_zip=False,
        specific_log_stream=None,
        cloudwatch_log_source=logs_operations_constants.LOG_SOURCES.INSTANCE_LOG_SOURCE
):
    """
    Retrieves CloudWatch logs for every stream under `log_group` unless `specific_log_stream` is specified.
    :param log_group: CloudWatch logGroup
    :param info_type:
        tail: to get the last 100 lines and returns the result to the terminal
        'bundle': get all of the logs and save them to a dir under .elasticbeanstalk/logs/
    :param do_zip: If True, zip the logs for the user
    :param specific_log_stream: Get logs for specific stream
    :param cloudwatch_log_source: the cloudwatch-log-source to pull from: instance or environment-health
    """
    log_streams = cloudwatch.get_all_stream_names(
        log_group_name=log_group,
        log_stream_name_prefix=specific_log_stream
    )

    if info_type == logs_operations_constants.INFORMATION_FORMAT.BUNDLE:
        logs_location = _setup_logs_folder(cloudwatch_log_source)

        for log_stream in log_streams:
            full_logs = get_cloudwatch_log_stream_events(log_group, log_stream)
            _write_full_logs_to_file(full_logs, logs_location, log_stream)

        if do_zip:
            _zip_logs_location(logs_location)
        else:
            _attempt_update_symlink_to_latest_logs_retrieved(logs_location)
    else:
        stream_logs_in_terminal(log_group, log_streams)


def stream_environment_health_logs_from_cloudwatch(
        sleep_time=10,
        log_group=None,
        specific_log_stream=None
):
    """
    Method streams CloudWatch logs to the terminal for the logGroup given. Since it
    is possible that the logGroup might match multiple logGroups, multiple threads
    can be spawned to switch between streams to display all of them on the same terminal.

    :param sleep_time: sleep time to refresh the logs from cloudwatch
    :param log_group: cloudwatch logGroup
    :param specific_log_stream: since all of our log streams are instance ids we require
                                this if we want a single stream
    """
    streamer = io.get_event_streamer()
    streamer.prompt = ' -- {0} -- (Ctrl+C to exit)'.format(log_group)
    start_time = None
    log_stream_names = cloudwatch_log_stream_names(log_group, specific_log_stream)

    if not log_stream_names:
        return

    latest_log_stream_name = log_stream_names[-1]
    other_log_stream_names = log_stream_names[:-1]

    for log_stream_name in other_log_stream_names:
        _create_log_stream_for_log_group(log_group, log_stream_name, streamer, sleep_time, start_time)
        _delay_subsequent_stream_creation()

    while True:
        _create_log_stream_for_log_group(log_group, latest_log_stream_name, streamer, sleep_time, start_time)
        _wait_to_poll_cloudwatch()


def stream_instance_logs_from_cloudwatch(
        sleep_time=10,
        log_group=None,
        specific_log_stream=None
):
    """
    Method streams CloudWatch logs to the terminal for the logGroup given.
    Since it is possible that the logGroup might match multiple logGroups,
    multiple threads can be spawned to switch between streams to display
    all of them on the same terminal.

    :param sleep_time: sleep time to refresh the logs from cloudwatch
    :param log_group: cloudwatch logGroup
    :param specific_log_stream: since all of our log streams are instance ids
                                we require this if we want a single stream
    """
    streamer = io.get_event_streamer()
    streamer.prompt = ' -- {0} -- (Ctrl+C to exit)'.format(log_group)

    start_time = None
    while True:
        log_group_names = set(cloudwatch_log_stream_names(log_group, specific_log_stream))

        for log_group_name in log_group_names:
            _create_log_stream_for_log_group(log_group, log_group_name, streamer, sleep_time, start_time)
            _delay_subsequent_stream_creation()

        _wait_to_poll_cloudwatch()

        start_time = _updated_start_time()


def stream_logs_in_terminal(log_group, log_streams):
    """
    Prints logs of each of the `log_streams` to terminal using a scoll-able pager as opposed to printing all
    available information at once.
    :param log_group: name of the CloudWatch log group within which to find `stream_name`
    :param log_streams: the list of log streams belonging to the `log_group` whose events to print to terminal
    :return: None
    """
    all_logs = ''
    for log_stream in log_streams:
        tail_logs = get_cloudwatch_log_stream_events(
            log_group,
            log_stream,
            num_log_events=TAIL_LOG_SIZE
        )
        all_logs += '{linesep}{linesep}============= ' \
                    '{log_stream} - {log_group} ==============' \
                    '{linesep}{linesep}'.format(
                        log_stream=str(log_stream),
                        log_group=log_group,
                        linesep=os.linesep
                    )
        all_logs += tail_logs

    io.echo_with_pager(all_logs)


def stream_platform_logs(platform_name, version, streamer=None, sleep_time=4, log_name=None, formatter=None):
    """
    Streams the logs of a custom platform
    :param platform_name: A CloudWatch logGroup in which the logStream `version` exists
    :param version: A CloudWatch logStream to poll
    :param streamer: The object that streams events to the terminal
    :param sleep_time: Time in seconds to sleep before polling CloudWatch for newer events
    :param log_name: A name used to identify the blob of output in the terminal for the logStream
    :param formatter: The object that formats the output to be displayed in the terminal
    :return: None
    """
    log_group_name = _get_platform_builder_group_name(platform_name)
    wait_for_log_group_to_come_into_existence(log_group_name, sleep_time)
    streamer = streamer or io.get_event_streamer()

    if log_name:
        streamer.prompt = ' -- Streaming logs for %s -- (Ctrl+C to exit)' % log_name

    stream_single_stream(log_group_name, version, sleep_time, None, formatter)


def stream_single_stream(
        log_group_name,
        stream_name,
        sleep_time=4,
        start_time=None,
        formatter=None,
):
    """
    Method periodically polls CloudWatch get_log_events to retrieve the logs for the `stream_name`
    within the logGroup defined by `log_group_name`
    :param log_group_name: A CloudWatch logGroup in which `stream_name` exists
    :param stream_name: The CloudWatch logStream to get events from
    :param streamer: The object that streams events to the terminal
    :param sleep_time: Time in seconds to sleep before polling CloudWatch for newer events
    :param start_time: The start of the time range, expressed as the number of milliseconds
                       after Jan 1, 1970 00:00:00 UTC.
        Events with a time stamp earlier than this time are not included.
    :param formatter: The object that formats the output to be displayed in the terminal
    :return: None
    """
    def messages_handler(messages):
        messages = '{linesep}{linesep}============= ' \
                   '{log_stream} - {log_group} ==============' \
                   '{linesep}{linesep}{messages}'.format(
                        log_stream=stream_name,
                        log_group=log_group_name,
                        linesep=os.linesep,
                        messages=os.linesep.join(messages)
                   )
        io.echo(messages)

    get_cloudwatch_messages(log_group_name, stream_name, formatter, None, start_time, messages_handler)

    _wait_to_poll_cloudwatch(sleep_time)


def wait_for_log_group_to_come_into_existence(log_group_name, sleep_time=10):
    while not cloudwatch.log_group_exists(log_group_name):
        _wait_to_poll_cloudwatch(sleep_time)


def _attempt_update_symlink_to_latest_logs_retrieved(logs_location):
    if not getattr(os, 'symlink', None):
        LOG.debug("Couldn't create symlink to latest logs retrieved")

        return

    io.echo(strings['logs.location'].replace('{location}', logs_location))
    latest_symlink_location = os.path.join(
        os.path.dirname(logs_location),
        'latest'
    )

    try:
        if os.path.islink(latest_symlink_location):
            os.unlink(latest_symlink_location)
        os.symlink(logs_location, latest_symlink_location)
        io.echo('Updated symlink at', latest_symlink_location)
    except OSError:
        pass


def _create_log_stream_for_log_group(log_group, stream_name, streamer, sleep_time, start_time=None):
    cloudwatch_log_stream = threading.Thread(
        target=stream_single_stream,
        args=(log_group, stream_name, sleep_time, start_time,),
    )
    cloudwatch_log_stream.daemon = True
    cloudwatch_log_stream.start()


def _delay_subsequent_stream_creation():
    time.sleep(0.2)


def _download_logs_for_all_instances(instance_id_list, logs_location):
    for instance_id, url in iteritems(instance_id_list):
        zip_location = utils.save_file_from_url(
            url,
            logs_location,
            instance_id + '.zip'
        )
        instance_folder = os.path.join(logs_location, instance_id)
        fileoperations.unzip_folder(zip_location, instance_folder)
        fileoperations.delete_file(zip_location)


def _echo_link_to_cloudwatch_console(env_name):
    region = commonops.get_default_region()
    if region in ['cn-north-1', 'cn-northwest-1']:
        cw_link_regionalized = strings['cloudwatch-logs.bjslink']
    else:
        cw_link_regionalized = strings['cloudwatch-logs.link']

    io.echo(cw_link_regionalized.replace('{region}', region).replace('{env_name}', env_name))


def _environment_health_log_streaming_option_setting(disable=False):
    """
    Returns a dict representation of the environment-health log streaming option setting
    :param disable: True if the intention is to disable the option setting
    :return: A dict representation of the instance log streaming option setting
    """
    return elasticbeanstalk.create_option_setting(
        namespaces.CLOUDWATCH_ENVIRONMENT_HEALTH_LOGS,
        option_names.CLOUDWATCH_ENVIRONMENT_HEALTH_LOGS_ENABLED,
        'false' if disable else 'true'
    )


def _get_cloudwatch_messages(
        log_group_name,
        stream_name,
        formatter=None,
        next_token=None,
        start_time=None
):
    messages = []
    response = None
    latest_event_timestamp = start_time

    try:
        response = cloudwatch.get_log_events(
            log_group_name,
            stream_name,
            next_token=next_token,
            start_time=start_time
        )

    except MaxRetriesError as e:
        LOG.debug('Received max retries')
        io.echo(e.message())
        time.sleep(1)

    if response and response.get('events'):
        for event in response.get('events'):
            message = event.get('message').encode('utf8', 'replace')

            if formatter:
                timestamp = event.get('timestamp')

                if timestamp:
                    latest_event_timestamp = timestamp

                formatted_message = formatter.format(message, stream_name)
            else:
                formatted_message = '[{1}] {0}'.format(message, stream_name)

            messages.append(formatted_message)
        next_token = response.get('nextForwardToken')

    return messages, next_token, latest_event_timestamp


def __get_full_path_for_instance_logs(logs_location, instance_id):
    return '{0}/{1}.log'.format(logs_location, instance_id)


def _get_platform_builder_group_name(platform_name):
    """
    Returns the logGroup name of associated with the custom platform identified by `platform_name`
    :param platform_name: A custom platform whose logs to stream
    :return:
    """
    return '/aws/elasticbeanstalk/platform/{}'.format(platform_name)


def _handle_bundle_logs(instance_id_list, do_zip):
    logs_folder_name = _timestamped_directory_name()
    logs_location = fileoperations.get_logs_location(logs_folder_name)
    _download_logs_for_all_instances(instance_id_list, logs_location)
    fileoperations.set_user_only_permissions(logs_location)

    if do_zip:
        _handle_log_zipping(logs_location)
    else:
        io.echo(strings['logs.location'].replace('{location}',
                                                 logs_location))
        _attempt_update_symlink_to_latest_logs_retrieved(logs_location)


def _handle_log_zipping(logs_location):
    logs_zip = logs_location + '.zip'
    fileoperations.zip_up_folder(logs_location, logs_zip)
    fileoperations.delete_directory(logs_location)

    fileoperations.set_user_only_permissions(logs_zip)
    io.echo(
        strings['logs.location'].replace(
            '{location}',
            logs_zip
        )
    )


def _handle_tail_logs(instance_id_list):
    data = []
    for instance_id, url in iteritems(instance_id_list):
        data.append('============= ' + str(instance_id) + ' ==============')
        log_result = utils.get_data_from_url(url)
        data.append(utils.decode_bytes(log_result))
    io.echo_with_pager(os.linesep.join(data))


def _instance_log_streaming_option_setting(disable=False):
    return elasticbeanstalk.create_option_setting(
        namespaces.CLOUDWATCH_LOGS,
        option_names.STREAM_LOGS,
        'false' if disable else 'true'
    )


def _raise_if_environment_is_not_using_enhanced_health(configuration_settings):
    option_settings = configuration_settings.get('OptionSettings')
    health_type = elasticbeanstalk.get_option_setting(
        option_settings,
        namespaces.HEALTH_SYSTEM,
        option_names.SYSTEM_TYPE
    )

    if health_type != 'enhanced':
        raise InvalidOptionsError(
            strings[
                'cloudwatch_environment_health_log_streaming.enhanced_health_not_found'
            ]
        )


def _setup_logs_folder(cloudwatch_log_source):
    if cloudwatch_log_source == logs_operations_constants.LOG_SOURCES.INSTANCE_LOG_SOURCE:
        logs_folder_name = _timestamped_directory_name()
    else:
        if not os.path.exists(
                fileoperations.get_logs_location(
                    logs_operations_constants.LOG_SOURCES.ENVIRONMENT_HEALTH_LOG_SOURCE
                )
        ):
            os.mkdir(
                fileoperations.get_logs_location(
                    logs_operations_constants.LOG_SOURCES.ENVIRONMENT_HEALTH_LOG_SOURCE
                )
            )

        logs_folder_name = os.path.join(
            logs_operations_constants.LOG_SOURCES.ENVIRONMENT_HEALTH_LOG_SOURCE,
            _timestamped_directory_name()
        )

    os.mkdir(fileoperations.get_logs_location(logs_folder_name))

    return fileoperations.get_logs_location(logs_folder_name)


def _timestamped_directory_name():
    return datetime.now().strftime("%y%m%d_%H%M%S")


def _updated_start_time():
    return calendar.timegm(datetime.utcnow().timetuple()) * 1000


def _updated_instance_id_list(instance_id_list, instance_id):
    try:
        return {
            instance_id: instance_id_list[instance_id]
        }
    except KeyError:
        raise NotFoundError(strings['beanstalk-logs.badinstance'].format(instance_id))


def _wait_to_poll_cloudwatch(sleep_time=10):
    time.sleep(sleep_time)


def _write_full_logs_to_file(full_logs, logs_location, instance_id):
    full_filepath = __get_full_path_for_instance_logs(logs_location, instance_id)
    with open(full_filepath, 'w+') as log_file:
        log_file.write(full_logs)

    fileoperations.set_user_only_permissions(full_filepath)


def _zip_logs_location(logs_location):
    fileoperations.zip_up_folder(logs_location, logs_location + '.zip')
    fileoperations.delete_directory(logs_location)

    logs_location += '.zip'
    fileoperations.set_user_only_permissions(logs_location)
    io.echo(strings['logs.location'].replace('{location}', logs_location))
