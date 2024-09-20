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


class Event(object):
    def __init__(
            self,
            app_name=None,
            environment_name=None,
            event_date=None,
            message=None,
            platform=None,
            request_id=None,
            severity=None,
            version_label=None,
    ):
        self.app_name = app_name
        self.environment_name = environment_name
        self.event_date = event_date
        self.message = message
        self.platform = platform
        self.request_id = request_id
        self.severity = severity
        self.version_label = version_label

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    def __ne__(self, other):
        return self.__hash__() != other.__hash__()

    def __hash__(self):
        """
        __hash__ method for `OptionSetting` to enable comparison of sets of `OptionSetting`s objects.
        :return: a hash of the `tuple` of the `OptionSetting` attributes
        """
        return hash(
            (
                self.app_name,
                self.environment_name,
                self.event_date,
                self.message,
                self.platform,
                self.request_id,
                self.severity,
                self.version_label
            )
        )

    @classmethod
    def json_to_event_objects(cls, json):
        events = []
        for event in json:
            events.append(
                Event(
                    app_name=event.get('ApplicationName'),
                    environment_name=event.get('EnvironmentName'),
                    event_date=event.get('EventDate'),
                    message=event.get('Message'),
                    platform=event.get('PlatformArn'),
                    request_id=event.get('RequestId'),
                    severity=event.get('Severity'),
                    version_label=event.get('VersionLabel')
                )
            )

        return events


class CFNEvent(object):
    def __init__(
            self,
            stack_id=None,
            event_id=None,
            stack_name=None,
            logical_resource_id=None,
            physical_resource_id=None,
            resource_type=None,
            timestamp=None,
            resource_status=None,
            resource_status_reason=None,
            resource_properties=None,
            client_request_token=None,
    ):
        self.stack_id = stack_id
        self.event_id = event_id
        self.stack_name = stack_name
        self.logical_resource_id = logical_resource_id
        self.physical_resource_id = physical_resource_id
        self.resource_type = resource_type
        self.timestamp = timestamp
        self.resource_status = resource_status
        self.resource_status_reason = resource_status_reason
        self.resource_properties = resource_properties
        self.client_request_token = client_request_token

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    def __ne__(self, other):
        return self.__hash__() != other.__hash__()

    def __hash__(self):
        """
        __hash__ method for `OptionSetting` to enable comparison of sets of `OptionSetting`s objects.
        :return: a hash of the `tuple` of the `OptionSetting` attributes
        """
        return hash(
            (
                self.stack_id,
                self.event_id,
                self.stack_name,
                self.logical_resource_id,
                self.physical_resource_id,
                self.resource_type,
                self.timestamp,
                self.resource_status,
                self.resource_status_reason,
                self.resource_properties,
                self.client_request_token
            )
        )

    def happened_after(self, other_datetime):
        return self.timestamp.replace(tzinfo=None) > other_datetime.replace(tzinfo=None)

    @classmethod
    def json_to_event_objects(cls, json):
        events = []
        for event in json:
            events.append(
                CFNEvent(
                    stack_id=event.get('StackId'),
                    event_id=event.get('EventId'),
                    stack_name=event.get('StackName'),
                    logical_resource_id=event.get('LogicalResourceId'),
                    physical_resource_id=event.get('PhysicalResourceId'),
                    resource_type=event.get('ResourceType'),
                    timestamp=event.get('Timestamp'),
                    resource_status=event.get('ResourceStatus'),
                    resource_status_reason=event.get('ResourceStatusReason'),
                    resource_properties=event.get('ResourceProperties'),
                    client_request_token=event.get('ClientRequestToken')
                )
            )

        return events
