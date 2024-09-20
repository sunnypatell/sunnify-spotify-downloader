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

from ebcli.lib.iam import get_role
from ebcli.objects.conversionconfiguration import ConversionConfiguration
from ebcli.objects.exceptions import ServiceError, InvalidOptionsError, NotFoundError
from ebcli.resources.strings import strings

DEFAULT_LIFECYCLE_SERVICE_ROLE = 'aws-elasticbeanstalk-service-role'
DEFAULT_ARN_STRING = 'REPLACE_WITH_ARN'
DEFAULT_LIFECYCLE_CONFIG = {
    u'VersionLifecycleConfig': {
        u'MaxCountRule': {
            u'DeleteSourceFromS3': False,
            u'Enabled': False,
            u'MaxCount': 200
        },
        u'MaxAgeRule': {
            u'DeleteSourceFromS3': False,
            u'Enabled': False,
            u'MaxAgeInDays': 180
        }
    }
}


class LifecycleConfiguration(ConversionConfiguration):
    def collect_changes(self, usr_model):
        """
        Because we can't remove options from the lifecycle config we can only
        add to them so we just take the direct user model and apply that.
        :param usr_model: User model, key-value style
        :return: api_model
        """
        if 'ServiceRole' in usr_model['Configurations']:
            service_role = usr_model['Configurations']['ServiceRole'].split('/')[-1]
            try:
                get_role(service_role)
            except (NotFoundError, ServiceError):
                raise InvalidOptionsError(strings['lifecycle.invalidrole'].replace('{role}', service_role))
        return usr_model['Configurations']

    def convert_api_to_usr_model(self):
        """
        Convert an api model to a User model as a key-value system and remove
        unwanted entries, we will place a default Service Role if there is
        none present to begin with.
        :return: a user model
        """

        usr_model = dict()
        self._copy_api_entry('ApplicationName', usr_model)
        self._copy_api_entry('DateUpdated', usr_model)
        if 'ResourceLifecycleConfig' in self.api_model:
            usr_model['Configurations'] = self.api_model['ResourceLifecycleConfig']
        else:
            usr_model['Configurations'] = DEFAULT_LIFECYCLE_CONFIG

        if 'ServiceRole' not in usr_model['Configurations']:
            try:
                role = get_role(DEFAULT_LIFECYCLE_SERVICE_ROLE)
                if u'Arn' in role:
                    arn = role[u'Arn']
                else:
                    arn = DEFAULT_ARN_STRING
            except (NotFoundError, ServiceError):
                arn = DEFAULT_ARN_STRING

            usr_model['Configurations']['ServiceRole'] = arn

        return usr_model
