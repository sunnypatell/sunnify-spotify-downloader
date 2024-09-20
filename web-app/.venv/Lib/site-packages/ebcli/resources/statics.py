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


class logs_operations_constants(object):

    class LOG_SOURCES(object):
        ALL_LOG_SOURCES = 'all'
        ENVIRONMENT_HEALTH_LOG_SOURCE = 'environment-health'
        INSTANCE_LOG_SOURCE = 'instance'

    class INFORMATION_FORMAT(object):
        BUNDLE = 'bundle'
        TAIL = 'tail'


class iam_documents(object):
    EC2_ASSUME_ROLE_PERMISSION = '{"Version": "2008-10-17","Statement": [{"Action":' \
                                 ' "sts:AssumeRole","Principal": {"Service": ' \
                                 '"ec2.amazonaws.com"},"Effect": "Allow","Sid": ""}]}'
    EC2_ASSUME_ROLE_PERMISSION_CN = '{"Version": "2008-10-17","Statement": [{"Action":' \
                                 ' "sts:AssumeRole","Principal": {"Service": ' \
                                 '"ec2.amazonaws.com.cn"},"Effect": "Allow","Sid": ""}]}'


class iam_attributes(object):
    DEFAULT_ROLE_NAME = 'aws-elasticbeanstalk-ec2-role'
    DEFAULT_PLATFORM_BUILDER_ROLE = 'aws-elasticbeanstalk-custom-platform-ec2-role'
    DEFAULT_ROLE_POLICIES = [
        'arn:aws:iam::aws:policy/AWSElasticBeanstalkWebTier',
        'arn:aws:iam::aws:policy/AWSElasticBeanstalkMulticontainerDocker',
        'arn:aws:iam::aws:policy/AWSElasticBeanstalkWorkerTier'
    ]
    DEFAULT_CUSTOM_PLATFORM_BUILDER_POLICIES = [
        'arn:aws:iam::aws:policy/AWSElasticBeanstalkWebTier',
        'arn:aws:iam::aws:policy/AWSElasticBeanstalkCustomPlatformforEC2Role',
    ]


class namespaces(object):
    AUTOSCALING = 'aws:autoscaling:asg'
    COMMAND = 'aws:elasticbeanstalk:command'
    RDS = 'aws:rds:dbinstance'
    ENVIRONMENT = 'aws:elasticbeanstalk:environment'
    HEALTH_CHECK = 'aws:elb:healthcheck'
    HEALTH_SYSTEM = 'aws:elasticbeanstalk:healthreporting:system'
    LAUNCH_CONFIGURATION = 'aws:autoscaling:launchconfiguration'
    LOAD_BALANCER = 'aws:elb:loadbalancer'
    ELB_POLICIES = 'aws:elb:policies'
    ROLLING_UPDATES = 'aws:autoscaling:updatepolicy:rollingupdate'
    VPC = 'aws:ec2:vpc'
    SPOT = 'aws:ec2:instances'
    CLOUDWATCH_LOGS = 'aws:elasticbeanstalk:cloudwatch:logs'
    CLOUDWATCH_ENVIRONMENT_HEALTH_LOGS = 'aws:elasticbeanstalk:cloudwatch:logs:health'
    LOAD_BALANCER_V2 = 'aws:elbv2:loadbalancer'
    LISTENER = 'aws:elbv2:listener:{}'


class option_names(object):
    BATCH_SIZE = 'BatchSize'
    BATCH_SIZE_TYPE = 'BatchSizeType'
    CONNECTION_DRAINING = 'ConnectionDrainingEnabled'
    CROSS_ZONE = 'CrossZone'
    DB_DELETION_POLICY = 'DBDeletionPolicy'
    DB_ENGINE = 'DBEngine'
    DB_ENGINE_VERSION = 'DBEngineVersion'
    DB_INSTANCE = 'DBInstanceClass'
    DB_PASSWORD = 'DBPassword'
    DB_STORAGE_SIZE = 'DBAllocatedStorage'
    DB_SUBNETS = 'DBSubnets'
    DB_USER = 'DBUser'
    EC2_KEY_NAME = 'EC2KeyName'
    ELB_SCHEME = 'ELBScheme'
    ELB_SUBNETS = 'ELBSubnets'
    ENVIRONMENT_TYPE = 'EnvironmentType'
    IAM_INSTANCE_PROFILE = 'IamInstanceProfile'
    INSTANCE_TYPE = 'InstanceType'
    INTERVAL = 'Interval'
    LOAD_BALANCER_HTTP_PORT = 'LoadBalancerHTTPPort'
    LOAD_BALANCER_HTTPS_PORT = 'LoadBalancerHTTPSPort'
    LOAD_BALANCER_TYPE = 'LoadBalancerType'
    MAX_SIZE = 'MaxSize'
    MIN_SIZE = 'MinSize'
    PUBLIC_IP = 'AssociatePublicIpAddress'
    ROLLING_UPDATE_ENABLED = 'RollingUpdateEnabled'
    ROLLING_UPDATE_TYPE = 'RollingUpdateType'
    SECURITY_GROUPS = 'SecurityGroups'
    SERVICE_ROLE = 'ServiceRole'
    SUBNETS = 'Subnets'
    SSL_CERT_ID = 'SSLCertificateId'
    SYSTEM_TYPE = 'SystemType'
    VPC_ID = 'VPCId'
    STREAM_LOGS = 'StreamLogs'
    CLOUDWATCH_ENVIRONMENT_HEALTH_LOGS_ENABLED = 'HealthStreamingEnabled'
    DELETE_ON_TERMINATE = 'DeleteOnTerminate'
    RETENTION_DAYS = 'RetentionInDays'
    ENABLE_SPOT = 'EnableSpot'
    ON_DEMAND_BASE_CAPACITY = 'SpotFleetOnDemandBase'
    ON_DEMAND_PERCENTAGE_ABOVE_BASE_CAPACITY = 'SpotFleetOnDemandAboveBasePercentage'
    SPOT_MAX_PRICE = 'SpotMaxPrice'
    INSTANCE_TYPES = 'InstanceTypes'
    LOAD_BALANCER_IS_SHARED = 'LoadBalancerIsShared'
    SHARED_LOAD_BALANCER = 'SharedLoadBalancer'
    LISTENER_RULE = 'Rules'


class option_values(object):
    SYSTEM_TYPE__ENHANCED = 'enhanced'


class elb_names(object):
    HEALTHY_STATE = 'healthy'
    UNHEALTHY_STATE = 'unhealthy'
    V2_RESOURCE_TYPE = 'AWS::ElasticLoadBalancingV2::TargetGroup'
    DEFAULT_PROCESS_LOGICAL_ID = 'AWSEBV2LoadBalancerTargetGroup'
    CLASSIC_VERSION = 'classic'
    APPLICATION_VERSION = 'application'
    NETWORK_VERSION = 'network'


class ec2_instance_statuses(object):
    IN_SERVICE = 'InService'


class platform_branch_lifecycle_states(object):
    BETA = 'Beta'
    SUPPORTED = 'Supported'
    DEPRECATED = 'Deprecated'
    RETIRED = 'Retired'


class platform_version_lifecycle_states(object):
    RECOMMENDED = 'Recommended'
