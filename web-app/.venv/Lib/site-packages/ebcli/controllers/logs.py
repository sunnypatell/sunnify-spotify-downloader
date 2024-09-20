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
import argparse
from cement.utils.misc import minimal_logger

from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.objects.exceptions import InvalidOptionsError
from ebcli.operations import logsops
from ebcli.resources.statics import logs_operations_constants
from ebcli.resources.strings import strings, flag_text

LOG = minimal_logger(__name__)


class LogsController(AbstractBaseController):
    class Meta:
        argument_formatter = argparse.RawTextHelpFormatter
        label = 'logs'
        description = strings['logs.info']
        usage = AbstractBaseController.Meta.usage.replace('{cmd}', label)
        arguments = AbstractBaseController.Meta.arguments + [
            (['-a', '--all'], dict(
                action='store_true', help=flag_text['logs.all'])),
            (['-z', '--zip'], dict(
                action='store_true', help=flag_text['logs.zip'])),
            (['-i', '--instance'], dict(help=flag_text['logs.instance'])),
            (['-g', '--log-group'], dict(help=flag_text['logs.log-group'])),
            (['-cw', '--cloudwatch-logs'], dict(help=flag_text['logs.cloudwatch_logs'], nargs='?',
                                                choices=['enable', 'disable'], type=str.lower, const='enable')),
            (['-cls', '--cloudwatch-log-source'], dict(help=flag_text['logs.cloudwatch_log_source'])),
            (['--stream'], dict(action='store_true',
                                help=flag_text['logs.stream'])),

        ]
        epilog = strings['logs.epilog']

    def do_command(self):
        self.env_name = self.get_env_name()
        self.app_name = self.get_app_name()
        self.log_group = self.app.pargs.log_group
        self.instance = self.app.pargs.instance
        self.all = self.app.pargs.all
        self.zip = self.app.pargs.zip
        self.cloudwatch_logs = self.app.pargs.cloudwatch_logs
        self.cloudwatch_log_source = self.app.pargs.cloudwatch_log_source
        self.stream = self.app.pargs.stream

        self.__raise_if_incompatible_arguments_are_present()

        if self.cloudwatch_logs:
            self.__modify_log_streaming()
        elif self.stream:
            self.__stream_cloudwatch_logs()
        else:
            self.__get_logs()

    def __get_logs(self):
        """
        Determines whether to:
            - retrieve logs from CloudWatch or Beanstalk
                - from CloudWatch when log-streaming to CloudWatch is enabled
                - from Beanstalk when log-streaming to CloudWatch is disabled
            - retrieve instance or environment-health logs
                - instance logs when --cloudwatch-log-source is 'instance' or None
                - environment-health logs when --cloudwatch-log-source is 'environment-health'
                - all other values for --cloudwatch-log-source will result in an exception being thrown
            - determine whether to tail the logs, or to download them as a zip file or regular log files
        """
        info_type = logsops.resolve_log_result_type(self.zip, self.all)
        should_zip_logs = self.zip

        if self.cloudwatch_log_source == logs_operations_constants.LOG_SOURCES.ENVIRONMENT_HEALTH_LOG_SOURCE:
            logsops.raise_if_environment_health_log_streaming_is_not_enabled(self.app_name, self.env_name)

            logsops.retrieve_cloudwatch_environment_health_logs(
                self.__normalized_log_group_name(),
                info_type,
                do_zip=should_zip_logs,
            )
        elif self.cloudwatch_log_source == logs_operations_constants.LOG_SOURCES.INSTANCE_LOG_SOURCE:
            logsops.raise_if_instance_log_streaming_is_not_enabled(self.app_name, self.env_name)

            self.__retrieve_cloudwatch_instance_logs(info_type, should_zip_logs)
        elif self.cloudwatch_log_source:
            raise InvalidOptionsError(strings['logs.cloudwatch_log_source_argumnent_is_invalid_for_retrieval'])
        elif logsops.instance_log_streaming_enabled(self.app_name, self.env_name):
            self.__retrieve_cloudwatch_instance_logs(info_type, should_zip_logs)
        else:
            logsops.retrieve_beanstalk_logs(
                self.env_name,
                info_type,
                do_zip=should_zip_logs,
                instance_id=self.instance
            )

    def __modify_log_streaming(self):
        self.cloudwatch_log_source = self.cloudwatch_log_source or logs_operations_constants.LOG_SOURCES.INSTANCE_LOG_SOURCE
        if self.cloudwatch_logs in ['enable', None]:
            logsops.enable_cloudwatch_logs(self.app_name, self.env_name, self.cloudwatch_log_source)
        elif self.cloudwatch_logs == 'disable':
            logsops.disable_cloudwatch_logs(self.app_name, self.env_name, self.cloudwatch_log_source)

    def __normalized_log_group_name(self):
        return logsops.normalize_log_group_name(
            self.env_name,
            self.log_group,
            self.cloudwatch_log_source
        )

    def __retrieve_cloudwatch_instance_logs(self, info_type, should_zip_logs):
        logsops.retrieve_cloudwatch_instance_logs(
            self.__normalized_log_group_name(),
            info_type,
            do_zip=should_zip_logs,
            specific_log_stream=self.instance
        )

    def __raise_if_incompatible_arguments_are_present(self):
        if self.all and self.instance:
            raise InvalidOptionsError(strings['logs.all_argument_and_instance_argument'])

        if self.all and self.zip:
            raise InvalidOptionsError(strings['logs.all_argument_and_zip_argument'])

        if self.cloudwatch_logs and self.log_group:
            raise InvalidOptionsError(strings['logs.cloudwatch_logs_argument_and_log_group_argument'])

        if self.cloudwatch_logs and self.instance:
            raise InvalidOptionsError(strings['logs.cloudwatch_logs_argument_and_instance_argument'])

        if self.cloudwatch_logs and self.all:
            raise InvalidOptionsError(strings['logs.cloudwatch_logs_argument_and_all_argument'])

        if self.cloudwatch_logs and self.zip:
            raise InvalidOptionsError(strings['logs.cloudwatch_logs_argument_and_zip_argument'])

        if self.cloudwatch_log_source and self.cloudwatch_log_source not in [
                logs_operations_constants.LOG_SOURCES.ALL_LOG_SOURCES,
                logs_operations_constants.LOG_SOURCES.INSTANCE_LOG_SOURCE,
                logs_operations_constants.LOG_SOURCES.ENVIRONMENT_HEALTH_LOG_SOURCE,
        ]:
            raise InvalidOptionsError(
                strings['logs.cloudwatch_log_source_argumnent_is_invalid_for_enabling_streaming']
            )

        if (
                self.cloudwatch_log_source == logs_operations_constants.LOG_SOURCES.ENVIRONMENT_HEALTH_LOG_SOURCE
                and self.instance
        ):
            raise InvalidOptionsError(strings['logs.health_and_instance_argument'])

        if (
                self.cloudwatch_log_source == logs_operations_constants.LOG_SOURCES.ENVIRONMENT_HEALTH_LOG_SOURCE
                and self.log_group
        ):
            raise InvalidOptionsError(strings['logs.log_group_and_environment_health_log_source'])

        if self.cloudwatch_log_source == logs_operations_constants.LOG_SOURCES.ALL_LOG_SOURCES and self.stream:
            raise InvalidOptionsError(strings['logs.cloudwatch_log_source_argumnent_is_invalid_for_enabling_streaming'])

    def __stream_cloudwatch_logs(self):
        self.cloudwatch_log_source = self.cloudwatch_log_source or logs_operations_constants.LOG_SOURCES.INSTANCE_LOG_SOURCE
        if self.cloudwatch_log_source == logs_operations_constants.LOG_SOURCES.INSTANCE_LOG_SOURCE:
            if not logsops.instance_log_streaming_enabled(self.app_name, self.env_name):
                raise InvalidOptionsError(strings['logs.instance_log_streaming_disabled'].format(self.env_name))

            logsops.stream_instance_logs_from_cloudwatch(
                log_group=self.__normalized_log_group_name(),
                specific_log_stream=self.instance
            )

        if self.cloudwatch_log_source == logs_operations_constants.LOG_SOURCES.ENVIRONMENT_HEALTH_LOG_SOURCE:
            if not logsops.environment_health_streaming_enabled(self.app_name, self.env_name):
                raise InvalidOptionsError(strings['logs.environment_health_log_streaming_disabled'].format(self.env_name))

            logsops.stream_instance_logs_from_cloudwatch(log_group=self.__normalized_log_group_name())
