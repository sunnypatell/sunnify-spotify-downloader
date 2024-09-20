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


from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.resources.strings import strings
from ebcli.core import io
from ebcli.lib import elasticbeanstalk, aws
from botocore.compat import six
urllib = six.moves.urllib


class QuicklinkController(AbstractBaseController):
    class Meta:
        label = 'quicklink'
        stacked_on = 'labs'
        stacked_type = 'nested'
        description = strings['quicklink.info']
        usage = AbstractBaseController.Meta.usage.replace('{cmd}', label)
        epilog = strings['quicklink.epilog']

    def do_command(self):
        app_name = self.get_app_name()
        env_name = self.get_env_name()

        get_quick_link(app_name, env_name)


def get_quick_link(app_name, env_name):
    env = elasticbeanstalk.get_environment(app_name=app_name, env_name=env_name)
    settings = elasticbeanstalk.describe_configuration_settings(
        app_name, env_name)
    option_settings = settings['OptionSettings']

    environment_type = elasticbeanstalk.get_option_setting(
        option_settings, 'aws:elasticbeanstalk:environment', 'EnvironmentType')
    instance_type = elasticbeanstalk.get_option_setting(
        option_settings, 'aws:autoscaling:launchconfiguration', 'InstanceType')

    link = 'https://console.aws.amazon.com/elasticbeanstalk/home?'
    region = aws.get_region_name()
    link += 'region=' + urllib.parse.quote(region)
    link += '#/newApplication'
    link += '?applicationName=' + urllib.parse.quote(app_name)
    link += '&solutionStackName=' + urllib.parse.quote(env.platform.platform_shorthand)
    link += '&tierName=' + env.tier.name
    if environment_type:
        link += '&environmentType=' + environment_type
    if env.version_label:
        app_version = elasticbeanstalk.get_application_versions(
            app_name, version_labels=[env.version_label])['ApplicationVersions'][0]
        source_bundle = app_version['SourceBundle']
        source_url = 'https://s3.amazonaws.com/' + source_bundle['S3Bucket'] + \
                     '/' + source_bundle['S3Key']
        link += '&sourceBundleUrl=' + source_url
    if instance_type:
        link += '&instanceType=' + instance_type

    link = _add_database_options(link, option_settings)
    link = _add_vpc_options(link, option_settings)

    io.echo(link)


def _add_database_options(link, option_settings):
    namespace = 'aws:rds:dbinstance'
    allocated_storage = elasticbeanstalk.get_option_setting(
        option_settings, namespace, 'DBAllocatedStorage')
    deletion_policy = elasticbeanstalk.get_option_setting(
        option_settings, namespace, 'DBDeletionPolicy')
    engine = elasticbeanstalk.get_option_setting(
        option_settings, namespace, 'DBEngine')
    instance_class = elasticbeanstalk.get_option_setting(
        option_settings, namespace, 'DBInstanceClass')
    multi_az = elasticbeanstalk.get_option_setting(
        option_settings, namespace, 'MultiAZDatabase')

    if allocated_storage:
        link += '&rdsDBAllocatedStorage=' + allocated_storage
    if deletion_policy:
        link += '&rdsDBDeletionPolicy=' + deletion_policy
    if engine:
        link += '&rdsDBEngine=' + engine
    if instance_class:
        link += '&rdsDBInstanceClass=' + instance_class
    if multi_az:
        link += '&rdsMultiAZDatabase=' + multi_az

    return link


def _add_vpc_options(link, option_settings):
    vpc_id = elasticbeanstalk.get_option_setting(
        option_settings, 'aws:ec2:vpc', 'VPCId')
    if vpc_id:
        link += '&withVpc=true'
    return link
