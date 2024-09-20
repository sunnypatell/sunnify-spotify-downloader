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
import copy

from ebcli.objects.solutionstack import SolutionStack
from ebcli.objects.platform import PlatformVersion
from ebcli.resources.strings import strings
from ebcli.resources.statics import elb_names, namespaces, option_names


class OptionSetting(object):
    def __init__(self, namespace, option_name, value):
        self.namespace = namespace
        self.option_name = option_name
        self.value = value

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    def __hash__(self):
        """
        __hash__ method for `OptionSetting` to enable comparison of sets of `OptionSetting`s objects.
        :return: a hash of the `tuple` of the `OptionSetting` attributes
        """
        return hash((self.namespace, self.option_name, self.value))

    @classmethod
    def option_settings_from_json(cls, json_array):
        option_settings = set()
        for option_setting in json_array:
            option_settings.add(
                OptionSetting(
                    namespace=option_setting['Namespace'],
                    option_name=option_setting['OptionName'],
                    value=option_setting['Value'],
                )
            )

        return option_settings


class CreateEnvironmentRequest(object):

    def __init__(self, app_name=None, env_name=None, cname=None, platform=None,
                 tier=None, instance_type=None, version_label=None,
                 instance_profile=None, service_role=None,
                 single_instance=False, key_name=None,
                 sample_application=False, tags=None, scale=None,
                 database=None, vpc=None, template_name=None, group_name=None,
                 elb_type=None, shared_lb=None, shared_lb_port=None, enable_spot=None, instance_types=None,
                 spot_max_price=None, on_demand_base_capacity=None,
                 on_demand_above_base_capacity=None, min_instances=None,
                 max_instances=None):
        self.app_name = app_name
        self.cname = cname
        self.env_name = env_name
        self.instance_profile = instance_profile
        self.instance_type = instance_type
        self.key_name = key_name
        self.platform = platform
        self.sample_application = sample_application
        self.service_role = service_role
        self.single_instance = single_instance
        self.template_name = template_name
        self.tier = tier
        self.version_label = version_label
        self.group_name = group_name
        if tags is None:
            self.tags = []
        else:
            self.tags = list(tags)
        if database is None:
            self.database = {}
        else:
            self.database = dict(database)
        if vpc is None:
            self.vpc = {}
        else:
            self.vpc = dict(vpc)

        self.elb_type = elb_type
        self.shared_lb = shared_lb
        self.shared_lb_port = shared_lb_port
        self.scale = None
        self.option_settings = []
        self.compiled = False
        self.description = strings['env.description']
        self.enable_spot = enable_spot
        self.instance_types = instance_types
        self.spot_max_price = spot_max_price
        self.on_demand_base_capacity = on_demand_base_capacity
        self.on_demand_above_base_capacity = on_demand_above_base_capacity
        self.min_instances = min_instances
        self.max_instances = max_instances

        if not self.app_name:
            raise TypeError(self.__class__.__name__ + ' requires key-word argument app_name')
        if not self.env_name:
            raise TypeError(self.__class__.__name__ + ' requires key-word argument env_name')

        if scale:
            if not isinstance(scale, int):
                raise TypeError('key-word argument scale must be of type int')
            else:
                self.scale = str(scale)

    def __eq__(self, other):
        self_dict = copy.deepcopy(self.__dict__)
        other_dict = copy.deepcopy(other.__dict__)

        self_dict['option_settings'] = OptionSetting.option_settings_from_json(
            self_dict.get('option_settings', [])
        )
        other_dict['option_settings'] = OptionSetting.option_settings_from_json(
            other_dict.get('option_settings', [])
        )

        return self_dict == other_dict

    def __ne__(self, other):
        return not self == other

    def add_option_setting(self, namespace, option_name, value, resource=None):
        setting = {'Namespace': namespace,
                   'OptionName': option_name,
                   'Value': value}
        if resource:
            setting['ResourceName'] = resource

        self.option_settings.append(setting)

    def convert_to_kwargs(self):
        self.compile_option_settings()
        return self.get_standard_kwargs()

    def compile_option_settings(self):
        if not self.compiled:
            self.add_client_defaults()
            self.compile_database_options()
            self.compile_vpc_options()
            self.compile_spot_options()
            self.compile_common_options()
            self.compile_shared_lb_options()
            self.compiled = True

    def get_standard_kwargs(self):
        kwargs = {
            'ApplicationName': self.app_name,
            'EnvironmentName': self.env_name,
            'OptionSettings': self.option_settings,
            }
        if self.platform:
            if isinstance(self.platform, SolutionStack):
                kwargs['SolutionStackName'] = self.platform.name
            elif isinstance(self.platform, PlatformVersion):
                kwargs['PlatformArn'] = self.platform.name
        if self.description:
            kwargs['Description'] = self.description
        if self.cname:
            kwargs['CNAMEPrefix'] = self.cname
        if self.template_name:
            kwargs['TemplateName'] = self.template_name
        if self.version_label:
            kwargs['VersionLabel'] = self.version_label
        if self.tags:
            kwargs['Tags'] = self.tags
        if self.tier:
            kwargs['Tier'] = self.tier.to_dict()

        if self.scale:
            self.add_option_setting(
                namespaces.AUTOSCALING,
                option_names.MAX_SIZE,
                self.scale)
            self.add_option_setting(
                namespaces.AUTOSCALING,
                option_names.MIN_SIZE,
                self.scale)

        return kwargs

    def compile_common_options(self):
        if self.instance_profile:
            self.add_option_setting(
                namespaces.LAUNCH_CONFIGURATION,
                option_names.IAM_INSTANCE_PROFILE,
                self.instance_profile)
        if self.service_role:
            self.add_option_setting(
                namespaces.ENVIRONMENT,
                option_names.SERVICE_ROLE,
                self.service_role
            )
        if self.instance_type:
            self.add_option_setting(
                namespaces.LAUNCH_CONFIGURATION,
                option_names.INSTANCE_TYPE,
                self.instance_type)
        if self.instance_types:
            self.add_option_setting(
                namespaces.SPOT,
                option_names.INSTANCE_TYPES,
                self.instance_types)
        if self.single_instance:
            self.add_option_setting(
                namespaces.ENVIRONMENT,
                option_names.ENVIRONMENT_TYPE,
                'SingleInstance')
        if self.key_name:
            self.add_option_setting(
                namespaces.LAUNCH_CONFIGURATION,
                option_names.EC2_KEY_NAME,
                self.key_name)
        if self.scale:
            self.add_option_setting(
                namespaces.AUTOSCALING,
                option_names.MAX_SIZE,
                self.scale)
            self.add_option_setting(
                namespaces.AUTOSCALING,
                option_names.MIN_SIZE,
                self.scale)
        if self.min_instances:
            self.add_option_setting(
                namespaces.AUTOSCALING,
                option_names.MIN_SIZE,
                self.min_instances)
        if self.max_instances:
            self.add_option_setting(
                namespaces.AUTOSCALING,
                option_names.MAX_SIZE,
                self.max_instances)
        if self.elb_type:
            self.add_option_setting(
                namespaces.ENVIRONMENT,
                option_names.LOAD_BALANCER_TYPE,
                self.elb_type)

    def add_client_defaults(self):
        if self.template_name:
            return

        if self.platform and self.platform.has_healthd_support:
            self.add_option_setting(
                namespaces.HEALTH_SYSTEM,
                option_names.SYSTEM_TYPE,
                'enhanced')

        self.add_option_setting(
            namespaces.COMMAND,
            option_names.BATCH_SIZE,
            '30')
        self.add_option_setting(
            namespaces.COMMAND,
            option_names.BATCH_SIZE_TYPE,
            'Percentage')
        if not self.tier or self.tier.name.lower() == 'webserver':
            self.add_option_setting(
                namespaces.ELB_POLICIES,
                option_names.CONNECTION_DRAINING,
                'true')
            self.add_option_setting(
                namespaces.LOAD_BALANCER,
                option_names.CROSS_ZONE,
                'true')
            if not self.single_instance:
                self.add_option_setting(
                    namespaces.ROLLING_UPDATES,
                    option_names.ROLLING_UPDATE_ENABLED,
                    'true')
                self.add_option_setting(
                    namespaces.ROLLING_UPDATES,
                    option_names.ROLLING_UPDATE_TYPE,
                    'Health')

    def compile_database_options(self):
        if not self.database:
            return

        namespace = namespaces.RDS
        self.add_option_setting(namespace, option_names.DB_PASSWORD,
                                self.database['password'])
        self.add_option_setting(namespace, option_names.DB_USER,
                                self.database['username'])
        if self.database['instance']:
            self.add_option_setting(namespace, option_names.DB_INSTANCE,
                                    self.database['instance'])
        if self.database['size']:
            self.add_option_setting(namespace, option_names.DB_STORAGE_SIZE,
                                    self.database['size'])
        if self.database['engine']:
            self.add_option_setting(namespace, option_names.DB_ENGINE,
                                    self.database['engine'])
        if self.database['version']:
            self.add_option_setting(namespace, option_names.DB_ENGINE_VERSION,
                                    self.database['version'])
        self.add_option_setting(namespace, option_names.DB_DELETION_POLICY,
                                'Snapshot')

    def compile_vpc_options(self):
        if not self.vpc:
            return

        namespace = namespaces.VPC
        self.add_option_setting(namespace, option_names.VPC_ID,
                                self.vpc['id'])
        if self.vpc['publicip']:
            self.add_option_setting(
                namespace,
                option_names.PUBLIC_IP,
                self.vpc['publicip']
            )
        if self.vpc['elbscheme']:
            self.add_option_setting(namespace, option_names.ELB_SCHEME,
                                    self.vpc['elbscheme'])
        if self.vpc['elbsubnets']:
            self.add_option_setting(namespace, option_names.ELB_SUBNETS,
                                    self.vpc['elbsubnets'])
        if self.vpc['ec2subnets']:
            self.add_option_setting(namespace, option_names.SUBNETS,
                                    self.vpc['ec2subnets'])
        if self.vpc['securitygroups']:
            self.add_option_setting(namespaces.LAUNCH_CONFIGURATION,
                                    option_names.SECURITY_GROUPS,
                                    self.vpc['securitygroups'])
        if self.vpc['dbsubnets']:
            self.add_option_setting(namespace, option_names.DB_SUBNETS,
                                    self.vpc['dbsubnets'])

    def compile_spot_options(self):
        if not self.enable_spot:
            return

        namespace = namespaces.SPOT
        self.add_option_setting(namespace, option_names.ENABLE_SPOT, 'true')


        if self.on_demand_base_capacity:
            self.add_option_setting(namespace, option_names.ON_DEMAND_BASE_CAPACITY, self.on_demand_base_capacity)

        if self.on_demand_above_base_capacity:
            self.add_option_setting(namespace, option_names.ON_DEMAND_PERCENTAGE_ABOVE_BASE_CAPACITY, self.on_demand_above_base_capacity)

        if self.spot_max_price:
            self.add_option_setting(namespace, option_names.SPOT_MAX_PRICE, self.spot_max_price)

        if self.on_demand_base_capacity:
            self.add_option_setting(namespace, option_names.ON_DEMAND_BASE_CAPACITY, self.on_demand_base_capacity)

        if self.on_demand_above_base_capacity:
            self.add_option_setting(
                namespace,
                option_names.ON_DEMAND_PERCENTAGE_ABOVE_BASE_CAPACITY,
                self.on_demand_above_base_capacity)

    def compile_shared_lb_options(self):
        if self.elb_type != elb_names.APPLICATION_VERSION or self.shared_lb==None:
            return

        if self.shared_lb:
            self.add_option_setting(
                namespaces.ENVIRONMENT,
                option_names.LOAD_BALANCER_IS_SHARED,
                'true'
            )
            self.add_option_setting(
                namespaces.LOAD_BALANCER_V2,
                option_names.SHARED_LOAD_BALANCER,
                self.shared_lb)

        if self.shared_lb_port and self.shared_lb:
            namespace = namespaces.LISTENER.format(self.shared_lb_port)
            self.add_option_setting(
                namespace,
                option_names.LISTENER_RULE,
                'default'
            )


class CloneEnvironmentRequest(CreateEnvironmentRequest):
    def __init__(self, app_name=None, env_name=None, original_name=None,
                 cname=None, platform=None, scale=None, tags=None):
        if not original_name:
            raise TypeError(self.__class__.__name__ + ' requires key-word argument clone_name')
        self.original_name = original_name
        super(CloneEnvironmentRequest, self).__init__(
            app_name=app_name, env_name=env_name, cname=cname,
            platform=platform, scale=scale, tags=tags
        )
        self.description = strings['env.clonedescription']. \
            replace('{env-name}', self.env_name)

    def compile_option_settings(self):
        if not self.compiled:
            self.compile_common_options()
            self.compiled = True
