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

import datetime
import time

from cement.utils.misc import minimal_logger
from ebcli.objects.platform import PlatformVersion
from ebcli.resources.statics import elb_names, namespaces, option_names

from ebcli.objects.solutionstack import SolutionStack
from ebcli.objects.exceptions import NotFoundError, InvalidStateError, \
    AlreadyExistsError
from ebcli.lib import aws
from ebcli.lib.aws import InvalidParameterValueError
from ebcli.objects.event import Event
from ebcli.objects.environment import Environment
from ebcli.objects.application import Application
from ebcli.resources.strings import strings, responses

LOG = minimal_logger(__name__)

DEFAULT_ROLE_NAME = 'aws-elasticbeanstalk-ec2-role'


def _make_api_call(operation_name, **operation_options):
    return aws.make_api_call('elasticbeanstalk',
                             operation_name,
                             **operation_options)


def describe_configuration_options(**kwargs):
    LOG.debug('Inside describe_configuration_options api wrapper')
    result = _make_api_call(
        'describe_configuration_options',
        **kwargs
    )
    return result


def list_application_load_balancers(platform, vpc=None):
    platform_arn = str(platform)
    options = []
    option_settings = []
    kwargs = dict()

    option_settings.append({
        'Namespace': namespaces.ENVIRONMENT,
        'OptionName': option_names.LOAD_BALANCER_TYPE,
        'Value': elb_names.APPLICATION_VERSION
    })
    option_settings.append({
        'Namespace': namespaces.ENVIRONMENT,
        'OptionName': option_names.LOAD_BALANCER_IS_SHARED,
        'Value': 'true'
    })
    if vpc:
        if vpc['id']:
            option_settings.append({
                'Namespace': namespaces.VPC,
                'OptionName': option_names.VPC_ID,
                'Value': vpc['id']
            })
        if vpc['ec2subnets']:
            option_settings.append({
                'Namespace': namespaces.VPC,
                'OptionName': option_names.SUBNETS,
                'Value': vpc['ec2subnets']
            })
    options.append({
        'Namespace': namespaces.LOAD_BALANCER_V2,
        'OptionName': option_names.SHARED_LOAD_BALANCER
    })

    kwargs['OptionSettings'] = option_settings
    kwargs['Options'] = options
    kwargs['PlatformArn'] = platform_arn

    describe_configuration_options_result = describe_configuration_options(**kwargs)
    alb_list = next((option["ValueOptions"] for option in describe_configuration_options_result["Options"] if option["Name"] == "SharedLoadBalancer"), None)

    return alb_list


def delete_platform(arn):
    LOG.debug('Inside delete_platform api wrapper')
    return _make_api_call('delete_platform_version',
                          PlatformArn=arn,
                          DeleteResources=True)


def list_platform_branches(filters=None):
    LOG.debug('Inside list_platform_branches api wrapper')
    kwargs = dict()

    if filters:
        kwargs['Filters'] = filters

    next_token = None
    platform_branches = []

    while True:
        next_platform_branches, next_token = _list_platform_branches(**kwargs)
        platform_branches += next_platform_branches

        if next_token is None:
            break
        else:
            kwargs['NextToken'] = next_token

    return platform_branches


def list_platform_versions(filters=None):
    kwargs = dict()

    if filters:
        kwargs['Filters'] = filters

    LOG.debug('Inside list_platform_versions api wrapper')
    platforms, nextToken = _list_platform_versions(kwargs)

    while nextToken:
        time.sleep(0.1)  # To avoid throttling we sleep for 100ms before requesting the next page
        next_platforms, nextToken = _list_platform_versions(kwargs, nextToken)
        platforms = platforms + next_platforms

    return platforms


def describe_platform_version(arn):
    LOG.debug('Inside describe_platform_version api wrapper')
    return _make_api_call('describe_platform_version',
                          PlatformArn=arn)['PlatformDescription']


def _list_platform_branches(**kwargs):
    response = _make_api_call(
        'list_platform_branches',
        **kwargs
    )

    platform_branches = response.get('PlatformBranchSummaryList', [])
    next_token = response.get('NextToken')

    return platform_branches, next_token


def _list_platform_versions(kwargs, nextToken=None):
    if nextToken is not None:
        # Sleep for 100ms before pulling the next page
        time.sleep(0.1)
        kwargs['NextToken'] = nextToken

    response = _make_api_call(
        'list_platform_versions',
        **kwargs
    )

    platforms = response['PlatformSummaryList']
    try:
        nextToken = response['NextToken']
    except KeyError:
        nextToken = None

    return platforms, nextToken


def create_application(app_name, descrip, tags=[]):
    LOG.debug('Inside create_application api wrapper')
    try:
        result = _make_api_call('create_application',
                                ApplicationName=app_name,
                                Tags=tags,
                                Description=descrip)
    except InvalidParameterValueError as e:
        string = responses['app.exists'].replace('{app-name}', app_name)
        if e.message == string:
            raise AlreadyExistsError(e)
        else:
            raise e

    return result


def create_platform_version(
        platform_name,
        version,
        s3_bucket,
        s3_key,
        instance_profile,
        key_name,
        instance_type,
        tags=[],
        vpc=None
):
    kwargs = dict()

    if s3_bucket and s3_key:
        kwargs['PlatformDefinitionBundle'] = {'S3Bucket': s3_bucket, 'S3Key': s3_key}

    if tags is not None:
        kwargs['Tags'] = tags

    option_settings = []

    if instance_profile:
        option_settings.append({
            'Namespace': namespaces.LAUNCH_CONFIGURATION,
            'OptionName': option_names.IAM_INSTANCE_PROFILE,
            'Value': instance_profile
        })
    if key_name:
        option_settings.append({
            'Namespace': namespaces.LAUNCH_CONFIGURATION,
            'OptionName': option_names.EC2_KEY_NAME,
            'Value': key_name
        })
    if instance_type:
        option_settings.append({
            'Namespace': namespaces.LAUNCH_CONFIGURATION,
            'OptionName': option_names.INSTANCE_TYPE,
            'Value': instance_type
        })
    if vpc:
        if vpc['id']:
            option_settings.append({
                'Namespace': namespaces.VPC,
                'OptionName': option_names.VPC_ID,
                'Value': vpc['id']
            })
        if vpc['subnets']:
            option_settings.append({
                'Namespace': namespaces.VPC,
                'OptionName': option_names.SUBNETS,
                'Value': vpc['subnets']
            })
        if vpc['publicip']:
            option_settings.append({
                'Namespace': namespaces.VPC,
                'OptionName': option_names.PUBLIC_IP,
                'Value': 'true'
            })

    option_settings.append({
        'Namespace': namespaces.HEALTH_SYSTEM,
        'OptionName': option_names.SYSTEM_TYPE,
        'Value': 'enhanced'
    })

    option_settings.append({
        'Namespace': namespaces.ENVIRONMENT,
        'OptionName': option_names.SERVICE_ROLE,
        'Value': 'aws-elasticbeanstalk-service-role'
    })

    LOG.debug('Inside create_platform_version api wrapper')
    return _make_api_call('create_platform_version',
                          PlatformName=platform_name,
                          PlatformVersion=version,
                          OptionSettings=option_settings,
                          **kwargs)


def create_application_version(
        app_name,
        vers_label,
        descrip,
        s3_bucket,
        s3_key,
        process=False,
        repository=None,
        commit_id=None,
        build_configuration=None
):
    kwargs = dict()
    kwargs['Process'] = process
    if descrip is not None:
        kwargs['Description'] = descrip
    if s3_bucket and s3_key:
        if build_configuration is None:
            kwargs['SourceBundle'] = {'S3Bucket': s3_bucket,
                                      'S3Key': s3_key}
        else:
            kwargs['SourceBuildInformation'] = {'SourceType': 'Zip',
                                                'SourceRepository': 'S3',
                                                'SourceLocation': "{0}/{1}".format(s3_bucket, s3_key)}
    elif repository and commit_id:
        kwargs['SourceBuildInformation'] = {
            'SourceType': 'Git',
            'SourceRepository': 'CodeCommit',
            'SourceLocation': "{0}/{1}".format(repository, commit_id)
        }
        kwargs['Process'] = True

    if build_configuration is not None:
        kwargs['BuildConfiguration'] = {"CodeBuildServiceRole": build_configuration.service_role,
                                        "Image": build_configuration.image,
                                        "ComputeType": build_configuration.compute_type,
                                        "TimeoutInMinutes": build_configuration.timeout}
        kwargs['Process'] = True

    LOG.debug('Inside create_application_version api wrapper')
    return _make_api_call('create_application_version',
                          ApplicationName=app_name,
                          VersionLabel=vers_label,
                          **kwargs)


def create_environment(environment):
    """
    Creates an Elastic Beanstalk environment
    """
    LOG.debug('Inside create_environment api wrapper')

    kwargs = environment.convert_to_kwargs()

    if environment.database:
        region = aws.get_region_name()

        kwargs['TemplateSpecification'] = {
            'TemplateSnippets': [
                {'SnippetName': 'RdsExtensionEB',
                 'Order': 10000,
                 'SourceUrl': 'https://s3.amazonaws.com/'
                              'elasticbeanstalk-env-resources-' + region +
                              '/eb_snippets/rds/rds.json'}
            ]
        }

    result = _make_api_call('create_environment', **kwargs)

    env = Environment.json_to_environment_object(result)
    request_id = result['ResponseMetadata']['RequestId']
    return env, request_id


def clone_environment(clone):
    LOG.debug('Inside clone_environment api wrapper')

    kwargs = clone.convert_to_kwargs()

    kwargs['TemplateSpecification'] = \
        {'TemplateSource': {'EnvironmentName': clone.original_name}}

    result = _make_api_call('create_environment', **kwargs)

    environment = Environment.json_to_environment_object(result)
    request_id = result['ResponseMetadata']['RequestId']
    return environment, request_id


def delete_application(app_name):
    LOG.debug('Inside delete_application api wrapper')
    result = _make_api_call('delete_application',
                            ApplicationName=app_name)
    return result['ResponseMetadata']['RequestId']


def delete_application_version(app_name, version_label):
    LOG.debug('Inside delete_application_version api wrapper')
    result = _make_api_call('delete_application_version',
                            ApplicationName=app_name,
                            VersionLabel=version_label,
                            DeleteSourceBundle=True)
    return result['ResponseMetadata']['RequestId']


def delete_application_and_envs(app_name):
    LOG.debug('Inside delete_application_and_envs')
    result = _make_api_call('delete_application',
                            ApplicationName=app_name,
                            TerminateEnvByForce=True)
    return result['ResponseMetadata']['RequestId']


def describe_application(app_name):
    LOG.debug('Inside describe_application api wrapper')
    result = _make_api_call('describe_applications',
                            ApplicationNames=[app_name])
    apps = result['Applications']
    if len(apps) != 1:
        raise NotFoundError('Application "' + app_name + '" not found.')
    return apps[0]


def is_cname_available(cname):
    LOG.debug('Inside is_cname_available api wrapper')
    result = _make_api_call('check_dns_availability',
                            CNAMEPrefix=cname)
    return result['Available']


def swap_environment_cnames(source_env, dest_env):
    LOG.debug('Inside swap_environment_cnames api wrapper')
    result = _make_api_call('swap_environment_cnames',
                            SourceEnvironmentName=source_env,
                            DestinationEnvironmentName=dest_env)
    return result['ResponseMetadata']['RequestId']


def describe_applications():
    LOG.debug('Inside describe_applications api wrapper')
    result = _make_api_call('describe_applications')
    return result['Applications']


def application_exist(app_name):
    try:
        describe_application(app_name)
    except NotFoundError:
        return False
    return True


def describe_configuration_settings(app_name, env_name):
    LOG.debug('Inside describe_configuration_settings api wrapper')
    result = _make_api_call('describe_configuration_settings',
                            ApplicationName=app_name,
                            EnvironmentName=env_name)
    return result['ConfigurationSettings'][0]


def get_application_names():
    applications = get_all_applications()

    return [application.name for application in applications]


def get_option_setting_from_environment(app_name, env_name, namespace, option):
    env = describe_configuration_settings(app_name, env_name)
    try:
        option_settings = env['OptionSettings']
        return get_option_setting(option_settings, namespace, option)
    except KeyError:
        return None


def get_option_setting(option_settings, namespace, option):
    for setting in option_settings:
        if setting['Namespace'] == namespace and \
                                setting['OptionName'] == option:
            try:
                return setting['Value']
            except KeyError:
                return None

    return None


def create_option_setting(namespace, option, value):
    return {
        'Namespace': namespace,
        'OptionName': option,
        'Value': value
    }


def get_specific_configuration(env_config, namespace, option):
    return get_option_setting(env_config['OptionSettings'], namespace, option)


def get_specific_configuration_for_env(app_name, env_name, namespace, option):
    env_config = describe_configuration_settings(app_name, env_name)
    return get_specific_configuration(env_config, namespace, option)


def get_available_solution_stacks(fail_on_empty_response=True):
    LOG.debug('Inside get_available_solution_stacks api wrapper')
    result = _make_api_call('list_available_solution_stacks')
    stack_strings = result['SolutionStacks']

    LOG.debug('Solution Stack result size = ' + str(len(stack_strings)))

    if fail_on_empty_response and len(stack_strings) == 0:
        raise NotFoundError(strings['sstacks.notfound'])

    solution_stacks = [SolutionStack(s) for s in stack_strings]

    try:
        return sorted(solution_stacks)
    except Exception:
        return solution_stacks


def get_application_versions(app_name, version_labels=None, max_records=None, next_token=None):
    LOG.debug('Inside get_application_versions api wrapper')
    kwargs = {}
    if version_labels:
        kwargs['VersionLabels'] = version_labels
    if max_records:
        kwargs['MaxRecords'] = max_records
    if next_token:
        # To avoid throttling we sleep for 100ms before requesting the next page
        time.sleep(0.1)
        kwargs['NextToken'] = next_token
    result = _make_api_call('describe_application_versions',
                            ApplicationName=app_name,
                            **kwargs)
    return result


def application_version_exists(app_name, version_label):
    app_versions = get_application_versions(app_name, version_labels=[version_label])['ApplicationVersions']

    if len(app_versions) > 0:
        return app_versions[0]


def get_all_applications():
    LOG.debug('Inside get_all_applications api wrapper')
    result = _make_api_call('describe_applications')
    app_list = []
    for app in result['Applications']:
        try:
            description = app['Description']
        except KeyError:
            description = None

        try:
            versions = app['Versions']
        except KeyError:
            versions = None
        app_list.append(
            Application(
                name=app['ApplicationName'],
                date_created=app['DateCreated'],
                date_updated=app['DateUpdated'],
                description=description,
                versions=versions,
                templates=app['ConfigurationTemplates'],
            )
        )

    return app_list


def get_raw_app_environments(app_name, include_deleted=False, deleted_back_to=None):
    LOG.debug('Inside get_app_environments api wrapper')

    kwargs = {}
    if include_deleted and deleted_back_to is not None:
        kwargs['IncludedDeletedBackTo'] = deleted_back_to

    result = _make_api_call('describe_environments',
                            ApplicationName=app_name,
                            IncludeDeleted=include_deleted,
                            **kwargs)
    return result['Environments']


def get_app_environments(app_name, include_deleted=False, deleted_back_to=None):
    LOG.debug('Inside get_app_environments api wrapper')

    kwargs = {}
    if include_deleted and deleted_back_to is not None:
        kwargs['IncludedDeletedBackTo'] = deleted_back_to

    result = _make_api_call('describe_environments',
                            ApplicationName=app_name,
                            IncludeDeleted=include_deleted,
                            **kwargs)

    return Environment.json_to_environment_objects_array(result['Environments'])


def get_all_environment_names():
    environments = get_all_environments()

    return [environment.name for environment in environments]


def get_all_environments():
    LOG.debug('Inside get_all_environments api wrapper')
    result = _make_api_call('describe_environments',
                            IncludeDeleted=False)

    return Environment.json_to_environment_objects_array(result['Environments'])


def get_environment(
        app_name=None,
        env_name=None,
        env_id=None,
        include_deleted=False,
        deleted_back_to=None,
        want_solution_stack=False
):
    LOG.debug('Inside get_environment api wrapper')

    kwargs = {}
    if app_name is not None:
        kwargs['ApplicationName'] = app_name
    if env_name is not None:
        kwargs['EnvironmentNames'] = [env_name]
    if env_id is not None:
        kwargs['EnvironmentIds'] = [env_id]
    if include_deleted and deleted_back_to is not None:
        kwargs['IncludedDeletedBackTo'] = deleted_back_to

    result = _make_api_call('describe_environments',
                            IncludeDeleted=include_deleted,
                            **kwargs)

    envs = result['Environments']
    if len(envs) < 1:
        env_str = env_id if env_name is None else env_name
        raise NotFoundError('Environment "' + env_str + '" not Found.')
    else:
        return Environment.json_to_environment_object(envs[0], want_solution_stack)


def get_environment_names(app_name):
    environments = get_app_environments(app_name)
    return [environment.name for environment in environments]


def get_app_version_labels(app_name):
    app_versions = get_application_versions(app_name)['ApplicationVersions']

    return [app_version['VersionLabel'] for app_version in app_versions]


def get_environments(env_names=None):
    LOG.debug('Inside get_environments api wrapper')
    result = _make_api_call('describe_environments',
                            EnvironmentNames=env_names or [],
                            IncludeDeleted=False)

    environments = result['Environments']
    if not environments and env_names:
        raise NotFoundError(
            'Could not find any environments from the list: {}'.format(
                ', '.join(env_names)
            )
        )
    return Environment.json_to_environment_objects_array(environments)


def get_environment_settings(app_name, env_name):
    LOG.debug('Inside get_environment_settings api wrapper')
    result = _make_api_call('describe_configuration_settings',
                            ApplicationName=app_name,
                            EnvironmentName=env_name)

    return Environment.json_to_environment_object(result['ConfigurationSettings'][0])


def get_environment_resources(env_name):
    LOG.debug('Inside get_environment_resources api wrapper')
    result = _make_api_call('describe_environment_resources',
                            EnvironmentName=env_name)
    return result


def get_new_events(app_name, env_name, request_id,
                   last_event_time=None, version_label=None, platform_arn=None):
    LOG.debug('Inside get_new_events api wrapper')

    if last_event_time is not None:
        time = last_event_time
        new_time = time + datetime.timedelta(0, 0, 1000)
    else:
        new_time = None
    kwargs = {}
    if app_name:
        kwargs['ApplicationName'] = app_name
    if version_label:
        kwargs['VersionLabel'] = version_label
    if env_name:
        kwargs['EnvironmentName'] = env_name
    if request_id:
        kwargs['RequestId'] = request_id
    if new_time:
        kwargs['StartTime'] = str(new_time)
    if platform_arn:
        kwargs['PlatformArn'] = platform_arn

    result = _make_api_call('describe_events',
                            **kwargs)

    return Event.json_to_event_objects(result['Events'])


def get_storage_location():
    LOG.debug('Inside get_storage_location api wrapper')
    response = _make_api_call('create_storage_location')
    return response['S3Bucket']


def update_environment(env_name, options, remove=None,
                       template=None, template_body=None,
                       solution_stack_name=None,
                       platform_arn=None):
    LOG.debug('Inside update_environment api wrapper')
    if remove is None:
        remove = []
    kwargs = {
        'EnvironmentName': env_name,

    }
    if options:
        kwargs['OptionSettings'] = options
    if remove:
        kwargs['OptionsToRemove'] = remove
    if template:
        kwargs['TemplateName'] = template
    if template_body:
        kwargs['TemplateSpecification'] = \
            {'TemplateSource':
                {'SourceContents': template_body}}
    if solution_stack_name:
        kwargs['SolutionStackName'] = solution_stack_name
    if platform_arn:
        kwargs['PlatformArn'] = platform_arn

    try:
        response = _make_api_call('update_environment',
                                  **kwargs)
    except aws.InvalidParameterValueError as e:
        if e.message == responses['env.invalidstate'].replace('{env-name}',
                                                              env_name):
            raise InvalidStateError(e)
        else:
            raise
    return response['ResponseMetadata']['RequestId']


def abort_environment_update(env_name):
    LOG.debug('Inside abort_environment_update')
    result = _make_api_call('abort_environment_update',
                            EnvironmentName=env_name)
    return result['ResponseMetadata']['RequestId']


def update_application_resource_lifecycle(app_name, resource_config):
    LOG.debug('Inside update_application_resource_lifecycle api wrapper')

    response = _make_api_call('update_application_resource_lifecycle',
                              ApplicationName=app_name,
                              ResourceLifecycleConfig=resource_config)

    return response


def update_env_application_version(env_name,
                                   version_label,
                                   group_name):
    LOG.debug('Inside update_env_application_version api wrapper')
    if group_name:
        response = _make_api_call('update_environment',
                                  EnvironmentName=env_name,
                                  VersionLabel=version_label,
                                  GroupName=group_name)
    else:
        response = _make_api_call('update_environment',
                                  EnvironmentName=env_name,
                                  VersionLabel=version_label)
    return response['ResponseMetadata']['RequestId']


def request_environment_info(env_name, info_type):
    result = _make_api_call('request_environment_info',
                            EnvironmentName=env_name,
                            InfoType=info_type)
    return result


def retrieve_environment_info(env_name, info_type):
    result = _make_api_call('retrieve_environment_info',
                            EnvironmentName=env_name,
                            InfoType=info_type)
    return result


def terminate_environment(env_name, force_terminate=False):
    result = _make_api_call('terminate_environment',
                            EnvironmentName=env_name,
                            ForceTerminate=force_terminate)
    return result['ResponseMetadata']['RequestId']


def create_configuration_template(app_name, env_name, template_name,
                                  description, tags):
    kwargs = {
        'TemplateName': template_name,
        'ApplicationName': app_name,
        'Description': description,
        'TemplateSpecification':
            {'TemplateSource':
                {'EnvironmentName': env_name}},
        'Tags': tags
    }
    try:
        result = _make_api_call('create_configuration_template', **kwargs)
    except InvalidParameterValueError as e:
        if e.message == responses['cfg.nameexists'].replace('{name}',
                                                            template_name):
            raise AlreadyExistsError(e.message)
        else:
            raise

    return result


def delete_configuration_template(app_name, template_name):
    _make_api_call('delete_configuration_template',
                   ApplicationName=app_name,
                   TemplateName=template_name)


def validate_template(app_name, template_name, platform=None):
    kwargs = {}
    if platform:
        if PlatformVersion.is_valid_arn(platform):
            kwargs['TemplateSpecification'] = {
                'TemplateSource': {
                    'PlatformArn': platform
                }
            }
        else:
            kwargs['TemplateSpecification'] = {
                'TemplateSource': {
                    'SolutionStackName': platform
                }
            }

    result = _make_api_call('validate_configuration_settings',
                            ApplicationName=app_name,
                            TemplateName=template_name,
                            **kwargs)
    return result


def describe_template(app_name, template_name):
    LOG.debug('Inside describe_template api wrapper')
    result = _make_api_call('describe_configuration_settings',
                            ApplicationName=app_name,
                            TemplateName=template_name)
    return result['ConfigurationSettings'][0]


def get_environment_health(env_name, attributes=None):
    if attributes is None:
        attributes = [
            "HealthStatus",
            "Status",
            "Color",
            "Causes",
            "ApplicationMetrics",
            "InstancesHealth",
            "RefreshedAt",
        ]
    result = _make_api_call('describe_environment_health',
                            EnvironmentName=env_name,
                            AttributeNames=attributes)
    return result


def get_environment_tier_definition():
    return get_environment(app_name=None, env_name=None).tier


def get_instance_health(env_name, next_token=None, attributes=None):
    if attributes is None:
        attributes = [
            "HealthStatus",
            "Color",
            "Causes",
            "ApplicationMetrics",
            "RefreshedAt",
            "LaunchedAt",
            "System",
            "Deployment",
            "AvailabilityZone",
            "InstanceType",
        ]
    kwargs = {}
    if next_token:
        time.sleep(0.1)  # To avoid throttling we sleep for 100ms before requesting the next page
        kwargs['NextToken'] = next_token
    result = _make_api_call('describe_instances_health',
                            EnvironmentName=env_name,
                            AttributeNames=attributes,
                            **kwargs)
    return result


def compose_environments(application_name, version_labels_list, group_name=None):
    kwargs = {}
    if group_name is not None:
        kwargs['GroupName'] = group_name
    result = _make_api_call('compose_environments',
                            ApplicationName=application_name,
                            VersionLabels=version_labels_list,
                            **kwargs)
    request_id = result['ResponseMetadata']['RequestId']

    return request_id


def rebuild_environment(env_id=None, env_name=None):
    kwargs = {}
    if env_name is not None:
        kwargs['EnvironmentName'] = env_name
    if env_id is not None:
        kwargs['EnvironmentId'] = env_id

    result = _make_api_call('rebuild_environment',
                            **kwargs)

    request_id = result['ResponseMetadata']['RequestId']
    return request_id


def get_environment_arn(env_name):
    return get_environments([env_name])[0].environment_arn


def list_tags_for_resource(resource_arn):
    response = _make_api_call(
        'list_tags_for_resource',
        ResourceArn=resource_arn
    )

    return sorted(response['ResourceTags'], key=lambda tag: tag['Key'])


def update_tags_for_resource(resource_arn, tags_to_add, tags_to_remove):
    response = _make_api_call(
        'update_tags_for_resource',
        ResourceArn=resource_arn,
        TagsToAdd=tags_to_add,
        TagsToRemove=tags_to_remove
    )

    return response['ResponseMetadata']['RequestId']
