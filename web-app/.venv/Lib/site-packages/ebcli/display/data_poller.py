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
from collections import defaultdict
import time
from datetime import datetime, timedelta
from dateutil import tz, parser
import locale
import threading
import traceback

from botocore.compat import six
from cement.utils.misc import minimal_logger
import copy

from ebcli.lib import elasticbeanstalk, utils
from ebcli.lib.aws import InvalidParameterValueError
from ebcli.resources.strings import responses

Queue = six.moves.queue.Queue
LOG = minimal_logger(__name__)


class DataPoller(object):

    def __init__(self, app_name, env_name):
        self.app_name = app_name
        self.env_name = env_name
        self.data_queue = Queue()
        self.data = None
        self.no_instances_time = None
        self.instance_info = defaultdict(dict)

    def get_fresh_data(self):
        new_data = self.data
        while not self.data_queue.empty() or new_data is None:
            # Block on the first call.
            block = new_data is None
            new_data = self.data_queue.get(block=block)

        self.data = new_data
        return new_data

    def start_background_polling(self):
        data_poller_thread = threading.Thread(target=self._poll_for_health_data)
        data_poller_thread.daemon = True
        data_poller_thread.start()

    @staticmethod
    def _get_sleep_time(refresh_time):
        if not refresh_time:
            return 2

        delta = utils.get_delta_from_now_and_datetime(refresh_time)

        countdown = 11 - delta.seconds
        LOG.debug(
            'health time={}. current={}. ({} seconds until next refresh)'.format(
                utils.get_local_time_as_string(refresh_time),
                utils.get_local_time_as_string(datetime.now()),
                countdown
            )
        )

        return max(0.5, min(countdown, 11))  # x in range [0.5, 11]

    def _get_health_data(self):
        environment_health = elasticbeanstalk.get_environment_health(self.env_name)
        instance_health = elasticbeanstalk.get_instance_health(self.env_name)
        LOG.debug('EnvironmentHealth-data:{}'.format(environment_health))
        LOG.debug('InstanceHealth-data:{}'.format(instance_health))

        token = instance_health.get('NextToken', None)

        # Collapse data into flatter tables/dicts
        environment_health = collapse_environment_health_data(environment_health)
        instance_health = collapse_instance_health_data(instance_health)

        while token is not None:
            paged_health = elasticbeanstalk.get_instance_health(
                self.env_name, next_token=token)
            token = paged_health.get('NextToken', None)
            instance_health += collapse_instance_health_data(paged_health)

        # Timeout if 0 instances for more than 15 minutes
        if environment_health['Total'] == 0:
            if self.no_instances_time is None:
                self.no_instances_time = datetime.now()
            else:
                timediff = timedelta(seconds=15 * 60)
                if (datetime.now() - self.no_instances_time) > timediff:
                    return {}
        else:
            self.no_instances_time = None

        # Return all the data as a single object
        data = {'environment': environment_health,
                'instances': instance_health}
        LOG.debug('collapsed-data:{}'.format(data))
        return data

    def _poll_for_health_data(self):
        LOG.debug('Starting data poller child thread')
        while True:
            try:
                data = self._get_health_data()
                self.data_queue.put(data)
                refresh_time = data['environment'].get('RefreshedAt', None)

                sleep_time = self._get_sleep_time(refresh_time)
                LOG.debug('Sleeping for {} second(s)'.format(sleep_time))
                time.sleep(sleep_time)
            except (SystemError, SystemExit, KeyboardInterrupt) as e:
                LOG.debug('Exiting due to: {}'.format(e.__class__.__name__))

                break
            except InvalidParameterValueError as e:
                # Environment no longer exists, exit
                LOG.debug(e)

                break
            except Exception as e:
                if str(e) == responses['health.nodescribehealth']:
                    traceback.print_exc()

                    # Environment probably switching between health monitoring types
                    LOG.debug("Swallowing 'DescribeEnvironmentHealth is not supported' exception")
                    LOG.debug('Nothing to do as environment should be transitioning')

                    break
                else:
                    raise e

        self.data_queue.put({})


def collapse_environment_health_data(environment_health):
    application_metrics = environment_health.get('ApplicationMetrics', {})

    request_count = application_metrics.get('RequestCount', 0)
    latency_dict = application_metrics.pop('Latency', {})

    result = _format_latency_dict(latency_dict, request_count)

    requests_per_second = request_count/10.0
    result['requests'] = requests_per_second
    statuses = application_metrics.pop('StatusCodes', {})

    for k, v in six.iteritems(statuses):
        _convert_data_to_percentage(statuses, k, request_count)
    result.update(statuses)
    result.update(environment_health.pop('ApplicationMetrics', {}))
    total = 0
    for k, v in six.iteritems(environment_health.get('InstancesHealth', {})):
        total += v
    result['Total'] = total
    result.update(environment_health.pop('InstancesHealth', {}))
    result.update(environment_health)

    causes = result.get('Causes', [])
    result['Cause'] = causes[0] if causes else ''

    return result


def collapse_instance_health_data(instances_health):
    instance_list = instances_health.get('InstanceHealthList', [])
    result = list()
    for i in instance_list:
        instance = dict()
        request_count = i.get('ApplicationMetrics', {}) \
            .get('RequestCount', 0)
        latency = i.get('ApplicationMetrics', {}).pop('Latency', {})
        instance.update(_format_latency_dict(latency, request_count))
        instance.update(i.get('ApplicationMetrics', {}).pop('StatusCodes', {}))
        instance.update(i.pop('ApplicationMetrics', {}))

        instance.update(i.get('System', {}).pop('CPUUtilization', {}))
        instance.update(i.pop('System', {}))
        instance.update(i)
        causes = instance.get('Causes', [])
        cause = causes[0] if causes else ''
        instance['Cause'] = cause

        instance['InstanceType'] = i.get('InstanceType')
        if i.get('AvailabilityZone'):
            try:
                instance['AvailabilityZone'] = i.get('AvailabilityZone').rsplit('-', 1)[-1]
            except:
                instance['AvailabilityZone'] = i.get('AvailabilityZone')
        if i.get('Deployment'):
            instance['TimeSinceDeployment'] = format_time_since(i.get('Deployment').get('DeploymentTime'))
            instance['DeploymentId'] = i.get('Deployment').get('DeploymentId')
            instance['DeploymentStatus'] = i.get('Deployment').get('Status')
            instance['DeploymentVersion'] = i.get('Deployment').get('VersionLabel')

        instance['load1'] = instance['LoadAverage'][0] \
            if 'LoadAverage' in instance else '-'
        instance['load5'] = instance['LoadAverage'][1] \
            if 'LoadAverage' in instance else '-'

        instance['launched'] = utils.get_local_time_as_string(instance['LaunchedAt'])
        instance['running'] = format_time_since(instance.get('LaunchedAt'))

        duration = instance.get('Duration', 10)
        instance['requests'] = request_count / (duration * 1.0)

        for key in {'Status_2xx', 'Status_3xx', 'Status_4xx', 'Status_5xx'}:
            _convert_data_to_percentage(
                instance,
                key,
                request_count,
                add_sort_column=True
            )

        # Add status sort index
        instance['status_sort'] = __get_health_sort_order(instance['HealthStatus'])

        result.append(instance)

    return result


def format_float(flt, number_of_places):
    format_string = '{0:.' + str(number_of_places) + 'f}'
    return format_string.format(flt)


def format_time_since(timestamp):
    if not timestamp:
        return '-'

    if isinstance(timestamp, str):
        timestamp = parser.parse(timestamp)
    delta = _datetime_utcnow_wrapper() - timestamp

    days = delta.days
    minutes = delta.seconds // 60
    hours = minutes // 60

    if days > 0:
        return '{0} day{s}'.format(days, s=__plural_suffix(days))
    elif hours > 0:
        return '{0} hour{s}'.format(hours, s=__plural_suffix(hours))
    elif minutes > 0:
        return '{0} min{s}'.format(minutes, s=__plural_suffix(minutes))
    else:
        return '{0} secs'.format(delta.seconds)


def _convert_data_to_percentage(data, index, total, add_sort_column=False):
    if total > 0:
        percent = (data.get(index, 0) / (total * 1.0)) * 100.0
        representation = format_float(percent, 1)
        data[index] = representation

        if add_sort_column:
            data[index + '_sort'] = float(representation)


def _datetime_utcnow_wrapper():
    return datetime.now(tz.tzutc())


def _format_latency_dict(latency_dict, request_count):
    new_dict = copy.copy(latency_dict)
    for k, v in six.iteritems(latency_dict):
        new_dict[k + '_sort'] = v
        representation = format_float(v, 3)

        if (k == 'P99' and request_count < 100) or \
                (k == 'P90' and request_count < 10):
            representation += '*'
        elif k in ['P99', 'P90']:
            representation += ' '
        new_dict[k] = representation

    return new_dict


def __get_health_sort_order(health):
    health_order = dict(
        (v, k) for k, v in enumerate([
            'Severe',
            'Degraded',
            'Unknown',
            'Warning',
            'NoData',
            'No Data',
            'Info',
            'Pending',
            'Ok',
        ])
    )
    return health_order[health]


def __plural_suffix(number):
    return 's' if number > 1 else ''
