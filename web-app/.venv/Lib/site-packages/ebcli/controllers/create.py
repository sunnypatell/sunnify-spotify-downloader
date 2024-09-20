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
import os
import time

from ebcli.core import io, fileoperations, hooks
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.lib import elasticbeanstalk, utils, iam
from ebcli.objects.exceptions import (
    AlreadyExistsError,
    InvalidOptionsError,
    RetiredPlatformBranchError,
    NotFoundError,
)
from ebcli.objects.platform import PlatformVersion, PlatformBranch
from ebcli.objects.solutionstack import SolutionStack
from ebcli.objects.requests import CreateEnvironmentRequest
from ebcli.objects.tier import Tier
from ebcli.operations import (
    commonops,
    composeops,
    createops,
    envvarops,
    platformops,
    platform_branch_ops,
    saved_configs,
    solution_stack_ops,
    shared_lb_ops,
    spotops,
    statusops,
)
from ebcli.operations.tagops import tagops
from ebcli.resources.strings import strings, prompts, flag_text, alerts
from ebcli.resources.statics import elb_names, platform_branch_lifecycle_states


class CreateController(AbstractBaseController):
    class Meta:
        label = 'create'
        usage = AbstractBaseController.Meta.usage.replace('{cmd}', label)
        description = strings['create.info']
        epilog = strings['create.epilog']
        arguments = [
            (['environment_name'], dict(
                action='store', nargs='?', default=None,
                help=flag_text['create.name'])),
            (['-m', '--modules'], dict(nargs='*', help=flag_text['create.modules'])),
            (['-g', '--env-group-suffix'], dict(help=flag_text['create.group'])),
            (['-c', '--cname'], dict(help=flag_text['create.cname'])),
            (['-t', '--tier'], dict(help=flag_text['create.tier'])),
            (['-i', '--instance_type'], dict(
                help=flag_text['create.itype'])),
            (['-p', '--platform'], dict(help=flag_text['create.platform'])),
            (['-s', '--single'], dict(
                action='store_true', help=flag_text['create.single'])),
            (['--sample'], dict(
                action='store_true', help=flag_text['create.sample'])),
            (['-d', '--branch_default'], dict(
                action='store_true', help=flag_text['create.default'])),
            (['-ip', '--instance_profile'], dict(
                help=flag_text['create.iprofile'])),
            (['-sr', '--service-role'], dict(
                help=flag_text['create.servicerole'])),
            (['--version'], dict(help=flag_text['create.version'])),
            (['-k', '--keyname'], dict(help=flag_text['create.keyname'])),
            (['--scale'], dict(type=int, help=flag_text['create.scale'])),
            (['-nh', '--nohang'], dict(
                action='store_true', help=flag_text['create.nohang'])),
            (['--timeout'], dict(type=int, help=flag_text['general.timeout'])),
            (['--tags'], dict(help=flag_text['create.tags'])),
            (['--envvars'], dict(help=flag_text['create.envvars'])),
            (['--cfg'], dict(help=flag_text['create.config'])),
            (['--source'], dict(help=flag_text['create.source'])),
            (['--elb-type'], dict(help=flag_text['create.elb_type'])),
            (['-ls', '--shared-lb'], dict(help=flag_text['create.shared_lb'])),
            (['-lp', '--shared-lb-port'], dict(help=flag_text['create.shared_lb_port'])),
            (['-es', '--enable-spot'], dict(action='store_true', help=flag_text['create.enable_spot'])),
            (['-sm', '--spot-max-price'], dict(help=flag_text['create.maxprice'])),
            (['-it', '--instance-types'], dict(help=flag_text['create.instance_types'])),
            (['-sb', '--on-demand-base-capacity'], dict(help=flag_text['create.on_demand_capacity'])),
            (['-sp', '--on-demand-above-base-capacity'], dict(help=flag_text['create.on_demand_above_base_percent'])),
            (['-im', '--min-instances'], dict(help=flag_text['create.min_instances'])),
            (['-ix', '--max-instances'], dict(help=flag_text['create.max_instances'])),
            (['-db', '--database'], dict(
                action="store_true", help=flag_text['create.database'])),

            # Hidden RDS commands
            (
                ['-db.user', '--database.username'],
                dict(
                    dest='db_user',
                    help=argparse.SUPPRESS
                )
            ),
            (['-db.pass', '--database.password'],
                dict(dest='db_pass', help=argparse.SUPPRESS)),
            (['-db.i', '--database.instance'],
                dict(dest='db_instance', help=argparse.SUPPRESS)),
            (['-db.version', '--database.version'],
                dict(dest='db_version', help=argparse.SUPPRESS)),
            (['-db.size', '--database.size'],
                dict(type=int, dest='db_size', help=argparse.SUPPRESS)),
            (['-db.engine', '--database.engine'],
                dict(dest='db_engine', help=argparse.SUPPRESS)),
            (['--vpc'], dict(action='store_true',
                             help=flag_text['create.vpc'])),
            (['--vpc.id'], dict(dest='vpc_id', help=argparse.SUPPRESS)),
            (['--vpc.ec2subnets'], dict(
                dest='vpc_ec2subnets', help=argparse.SUPPRESS)),
            (['--vpc.elbsubnets'], dict(
                dest='vpc_elbsubnets', help=argparse.SUPPRESS)),
            (['--vpc.elbpublic'], dict(
                action='store_true', dest='vpc_elbpublic',
                help=argparse.SUPPRESS)),
            (['--vpc.publicip'], dict(
                action='store_true', dest='vpc_publicip',
                help=argparse.SUPPRESS)),
            (['--vpc.securitygroups'], dict(
                dest='vpc_securitygroups', help=argparse.SUPPRESS)),
            (['--vpc.dbsubnets'], dict(
                dest='vpc_dbsubnets', help=argparse.SUPPRESS)),
            (['-pr', '--process'], dict(
                action='store_true', help=flag_text['create.process'])),
        ]

    def do_command(self):
        env_name = self.app.pargs.environment_name
        modules = self.app.pargs.modules
        if modules and len(modules) > 0:
            self.compose_multiple_apps()
            return
        group = self.app.pargs.env_group_suffix
        cname = self.app.pargs.cname
        tier = self.app.pargs.tier
        itype = self.app.pargs.instance_type
        platform = self.app.pargs.platform
        single = self.app.pargs.single
        iprofile = self.app.pargs.instance_profile
        service_role = self.app.pargs.service_role
        label = self.app.pargs.version
        branch_default = self.app.pargs.branch_default
        key_name = self.app.pargs.keyname
        sample = self.app.pargs.sample
        nohang = self.app.pargs.nohang
        tags = self.app.pargs.tags
        envvars = self.app.pargs.envvars
        scale = self.app.pargs.scale
        timeout = self.app.pargs.timeout
        cfg = self.app.pargs.cfg
        elb_type = self.app.pargs.elb_type
        shared_lb = self.app.pargs.shared_lb
        shared_lb_port = self.app.pargs.shared_lb_port
        source = self.app.pargs.source
        process = self.app.pargs.process
        enable_spot = self.app.pargs.enable_spot
        spot_max_price = self.app.pargs.spot_max_price
        instance_types = self.app.pargs.instance_types
        on_demand_base_capacity = self.app.pargs.on_demand_base_capacity
        on_demand_above_base_capacity = self.app.pargs.on_demand_above_base_capacity
        max_instances = self.app.pargs.max_instances
        min_instances = self.app.pargs.min_instances

        interactive = False if env_name else True

        provided_env_name = env_name

        if sample and label:
            raise InvalidOptionsError(strings['create.sampleandlabel'])

        if single and scale:
            raise InvalidOptionsError(strings['create.singleandsize'])

        if (max_instances or min_instances) and scale:
            raise InvalidOptionsError(strings['create.scaleandminmax'])

        if (max_instances or min_instances) and single:
            raise InvalidOptionsError(strings['create.singleandminmax'])

        if single and elb_type:
            raise InvalidOptionsError(strings['create.single_and_elb_type'])

        if single and shared_lb:
            raise InvalidOptionsError(alerts['create.can_not_use_options_together'].format("--single", "--shared-lb"))

        if (shared_lb or shared_lb_port) and elb_type != 'application':
            raise InvalidOptionsError(alerts['sharedlb.wrong_elb_type'])

        if shared_lb_port and not shared_lb:
            raise InvalidOptionsError(alerts['sharedlb.missing_shared_lb'])

        if cname and tier and Tier.looks_like_worker_tier(tier):
            raise InvalidOptionsError(strings['worker.cname'])

        if cname and not elasticbeanstalk.is_cname_available(cname):
            raise AlreadyExistsError(
                strings['cname.unavailable'].replace('{cname}', cname)
            )

        if tier and Tier.looks_like_worker_tier(tier):
            if self.app.pargs.vpc_elbpublic or self.app.pargs.vpc_elbsubnets or self.app.pargs.vpc_publicip:
                raise InvalidOptionsError(strings['create.worker_and_incompatible_vpc_arguments'])

        if (not tier or Tier.looks_like_webserver_tier(tier)) and single:
            if self.app.pargs.vpc_elbpublic or self.app.pargs.vpc_elbsubnets:
                raise InvalidOptionsError(strings['create.single_and_elbpublic_or_elb_subnet'])

        if (spot_max_price or on_demand_base_capacity or on_demand_above_base_capacity) and not enable_spot:
            raise InvalidOptionsError(strings['create.missing_enable_spot'])

        if instance_types == "":
            raise InvalidOptionsError(strings['spot.instance_types_validation'])

        if itype and instance_types:
            raise InvalidOptionsError(strings['create.itype_and_instances'])
        
        if service_role and not iam.role_exists(service_role):
            raise InvalidOptionsError(f"The specified service role '{service_role}' does not exist. Please use a role that exists or create a new role .")

        platform = _determine_platform(platform, iprofile)

        app_name = self.get_app_name()
        tags = tagops.get_and_validate_tags(tags)
        envvars = get_and_validate_envars(envvars)
        process_app_version = fileoperations.env_yaml_exists() or process
        template_name = get_template_name(app_name, cfg)
        tier = get_environment_tier(tier)
        env_name = provided_env_name or get_environment_name(app_name, group)
        cname = cname or get_environment_cname(env_name, provided_env_name, tier)
        key_name = key_name or commonops.get_default_keyname()
        vpc = self.form_vpc_object(tier, single)
        elb_type = elb_type or get_elb_type_from_customer(interactive, single, tier)
        shared_lb = get_shared_load_balancer(interactive, elb_type, platform, shared_lb, vpc)
        shared_lb_port = shared_lb_port or shared_lb_ops.get_shared_lb_port_from_customer(interactive, shared_lb)
        enable_spot = enable_spot or spotops.get_spot_request_from_customer(interactive)
        instance_types = instance_types or spotops.get_spot_instance_types_from_customer(interactive, enable_spot)
        database = self.form_database_object()

        if not timeout and database:
            timeout = 15

        env_request = CreateEnvironmentRequest(
            app_name=app_name,
            env_name=env_name,
            group_name=group,
            cname=cname,
            template_name=template_name,
            platform=platform,
            tier=tier,
            instance_type=itype,
            version_label=label,
            instance_profile=iprofile,
            service_role=service_role,
            single_instance=single,
            key_name=key_name,
            sample_application=sample,
            tags=tags,
            scale=scale,
            database=database,
            vpc=vpc,
            elb_type=elb_type,
            shared_lb = shared_lb,
            shared_lb_port = shared_lb_port,
            enable_spot=enable_spot,
            instance_types=instance_types,
            spot_max_price=spot_max_price,
            on_demand_base_capacity=on_demand_base_capacity,
            on_demand_above_base_capacity=on_demand_above_base_capacity,
            min_instances=min_instances,
            max_instances=max_instances)

        env_request.option_settings += envvars

        createops.make_new_env(env_request,
                               branch_default=branch_default,
                               process_app_version=process_app_version,
                               nohang=nohang,
                               interactive=interactive,
                               timeout=timeout,
                               source=source)

    def form_database_object(self):
        create_db = self.app.pargs.database
        username = self.app.pargs.db_user
        password = self.app.pargs.db_pass
        engine = self.app.pargs.db_engine
        size = self.app.pargs.db_size
        instance = self.app.pargs.db_instance
        version = self.app.pargs.db_version

        if create_db or username or password or engine or size \
                or instance or version:
            db_object = dict()
            if not username:
                io.echo()
                username = io.get_input(prompts['rds.username'],
                                        default='ebroot')
            if not password:
                password = io.get_pass(prompts['rds.password'])
            db_object['username'] = username
            db_object['password'] = password
            db_object['engine'] = engine
            db_object['size'] = str(size) if size else None
            db_object['instance'] = instance
            db_object['version'] = version
            return db_object
        else:
            return {}

    def form_vpc_object(self, tier, single):
        vpc = self.app.pargs.vpc
        vpc_id = self.app.pargs.vpc_id
        ec2subnets = self.app.pargs.vpc_ec2subnets
        elbsubnets = self.app.pargs.vpc_elbsubnets
        elbpublic = self.app.pargs.vpc_elbpublic
        publicip = self.app.pargs.vpc_publicip
        securitygroups = self.app.pargs.vpc_securitygroups
        dbsubnets = self.app.pargs.vpc_dbsubnets
        database = self.app.pargs.database

        if vpc:
            io.echo()
            vpc_id = vpc_id or io.get_input(prompts['vpc.id'])

            if not tier or tier.is_webserver():
                publicip = publicip or io.get_boolean_response(text=prompts['vpc.publicip'])
            ec2subnets = ec2subnets or io.get_input(prompts['vpc.ec2subnets'])

            if (not tier or tier.is_webserver()) and not single:
                elbsubnets = elbsubnets or io.get_input(prompts['vpc.elbsubnets'])
                elbpublic = elbpublic or io.get_boolean_response(text=prompts['vpc.elbpublic'])

            securitygroups = securitygroups or io.get_input(prompts['vpc.securitygroups'])
            if database:
                dbsubnets = dbsubnets or io.get_input(prompts['vpc.dbsubnets'])

        if vpc_id or vpc:
            vpc_object = dict()
            vpc_object['id'] = vpc_id
            vpc_object['ec2subnets'] = ec2subnets

            if (not tier or tier.is_webserver()) and not single:
                vpc_object['elbsubnets'] = elbsubnets
                vpc_object['elbscheme'] = 'public' if elbpublic else 'internal'
            else:
                vpc_object['elbsubnets'] = None
                vpc_object['elbscheme'] = None

            if not tier or tier.is_webserver():
                vpc_object['publicip'] = 'true' if publicip else 'false'
            else:
                vpc_object['publicip'] = None
            vpc_object['securitygroups'] = securitygroups
            vpc_object['dbsubnets'] = dbsubnets
            return vpc_object

        else:
            return {}

    def compose_multiple_apps(self):
        module_names = self.app.pargs.modules
        group = self.app.pargs.env_group_suffix or 'dev'
        nohang = self.app.pargs.nohang
        timeout = self.app.pargs.timeout

        root_dir = os.getcwd()

        version_labels = []
        grouped_env_names = []
        app_name = None
        for module in module_names:
            if not os.path.isdir(os.path.join(root_dir, module)):
                io.log_warning(strings['create.appdoesntexist'].replace('{app_name}',
                                                                        module))
                continue

            os.chdir(os.path.join(root_dir, module))

            if not fileoperations.env_yaml_exists():
                io.log_warning(strings['compose.noenvyaml'].replace('{module}',
                                                                    module))
                continue

            io.echo('--- Creating application version for module: {0} ---'.format(module))

            hooks.set_region(None)
            hooks.set_ssl(None)
            hooks.set_profile(None)

            commonops.set_group_suffix_for_current_branch(group)

            if not app_name:
                app_name = self.get_app_name()
            process_app_version = fileoperations.env_yaml_exists()
            version_label = commonops.create_app_version(app_name, process=process_app_version)

            version_labels.append(version_label)

            environment_name = fileoperations.get_env_name_from_env_yaml()
            if environment_name is not None:
                commonops.set_environment_for_current_branch(environment_name.
                                                             replace('+', '-{0}'.
                                                                     format(group)))

                grouped_env_names.append(environment_name.replace('+', '-{0}'.
                                                                  format(group)))

            os.chdir(root_dir)

        if len(version_labels) > 0:
            composeops.compose(app_name, version_labels, grouped_env_names, group,
                               nohang, timeout)
        else:
            io.log_warning(strings['compose.novalidmodules'])


def get_environment_cname(env_name, provided_env_name, tier):
    """
    Returns the CNAME for the environment that will be created. Suggests to customer a name based
    of the environment name, which the customer is free to disregard.

    :param env_name: Name of the environment determined by `create.get_environment_name`
    :param provided_env_name: True/False depending on whether or not the customer passed an environment name
    through the command line
    :return: Unique CNAME for the environment which will be created by `eb create`
    """
    if tier and tier.is_worker():
        return

    if not provided_env_name:
        return get_cname_from_customer(env_name)


def get_environment_name(app_name, group):
    """
    Returns:
        - environment name is present in the env.yaml file if one exists, or
        - prompts customer interactively to enter an environment name

    If using env.yaml to create an environment with, `group` must be passed through
    the `-g/--env-group-suffix/` argument.

    :param app_name: name of the application associated with the present working
    directory
    :param group: name of the group associated with
    :return: Unique name of the environment which will be created by `eb create`
    """
    env_name = None
    if fileoperations.env_yaml_exists():
        env_name = fileoperations.get_env_name_from_env_yaml()
        if env_name:
            if env_name.endswith('+') and not group:
                raise InvalidOptionsError(strings['create.missinggroupsuffix'])
            elif not env_name.endswith('+') and group:
                raise InvalidOptionsError(strings['create.missing_plus_sign_in_group_name'])
            else:
                env_name = env_name[:-1] + '-' + group

    return env_name or io.prompt_for_environment_name(get_unique_environment_name(app_name))


def get_environment_tier(tier):
    """
    Set the 'tier' for the environment from the raw value received for the `--tier`
    argument.

    If a configuration template corresponding to `template_name` is also resolved,
    and the tier corresponding to the configuration template is a 'worker' tier,
    any previously set value for 'tier' is replaced with the value from the saved
    config.
    :return: A Tier object representing the environment's tier type
    """
    if tier:
        tier = Tier.from_raw_string(tier)

    return tier


def get_unique_cname(env_name):
    """
    Derive a unique CNAME for a new environment based on the environment name
    :param env_name: name of the environment
    directory
    :return: A unique CNAME for a new environment
    """
    cname = env_name
    tried_cnames = []
    while not elasticbeanstalk.is_cname_available(cname):
        tried_cnames.append(cname)
        _sleep(0.5)
        cname = utils.get_unique_name(cname, tried_cnames)
    return cname


def get_unique_environment_name(app_name):
    """
    Derive a unique name for a new environment based on the application name
    to suggest to the customer
    :param app_name: name of the application associated with the present working
    directory
    :return: A unique name for a new environment
    """
    default_name = app_name + '-dev'
    current_environments = elasticbeanstalk.get_all_environment_names()

    return utils.get_unique_name(default_name, current_environments)


def get_cname_from_customer(env_name):
    """
    Prompt customer to specify the CNAME for the environment.

    Selection defaults to the Environment's name when provided with blank input.
    :param env_name: name of the environment whose CNAME to configure
    :return: CNAME chosen for the environment
    """
    cname = get_unique_cname(env_name)
    while True:
        cname = io.prompt_for_cname(default=cname)
        if cname and not elasticbeanstalk.is_cname_available(cname):
            io.echo('That cname is not available. Please choose another.')
        else:
            break
    return cname


def get_elb_type_from_customer(interactive, single, tier):
    """
    Prompt customer to specify the ELB type if operating in the interactive mode and
    on a load-balanced environment.

    Selection defaults to 'application' when provided with blank input.
    :param interactive: True/False depending on whether operating in the interactive mode or not
    :param single: False/True depending on whether environment is load balanced or not
    :param region: AWS region in which in load balancer will be created
    :param tier: the tier type of the environment
    :return: selected ELB type which is one among ['application', 'classic', 'network']
    """
    if single or (tier and not tier.is_webserver()):
        return
    elif not interactive:
        return elb_names.APPLICATION_VERSION

    io.echo()
    io.echo('Select a load balancer type')
    result = utils.prompt_for_item_in_list(
        [elb_names.CLASSIC_VERSION, elb_names.APPLICATION_VERSION, elb_names.NETWORK_VERSION],
        default=2
    )
    elb_type = result

    return elb_type


def get_shared_load_balancer(interactive, elb_type, platform, shared_lb=None, vpc=None):
    if shared_lb:
        shared_lb = shared_lb_ops.validate_shared_lb_for_non_interactive(shared_lb)
    else:
        shared_lb = shared_lb_ops.get_shared_lb_from_customer(interactive, elb_type, platform, vpc)

    return shared_lb


def get_and_validate_envars(environment_variables_input):
    """
    Returns a list of environment variables as option settings from the raw environment variables
    string input provided by the customer
    :param environment_variables_input: a string of the form "KEY_1=VALUE_1,...,KYE_N=VALUE_N"
    :return: the list of option settings derived from the key-value pairs in `environment_variables_input`
    """
    environment_variables = envvarops.sanitize_environment_variables_from_customer_input(
        environment_variables_input
    )
    environment_variable_option_settings, options_to_remove = envvarops.create_environment_variables_list(
        environment_variables
    )

    return environment_variable_option_settings


def get_template_name(app_name, cfg):
    """
    Returns the name of the saved configuration template:
    - specified by the customer stored in S3
    - identified as 'default' present locally

    For more information, please refer to saved_configs.resolve_config_name
    :param app_name: name of the application associated with this directory
    :param cfg: saved config name specified by the customer
    :return: normalized
    """
    if not cfg:
        if not saved_configs.resolve_config_location('default'):
            return
        else:
            cfg = 'default'

    return saved_configs.resolve_config_name(app_name, cfg)


def _determine_platform(platform_string=None, iprofile=None):
    platform = None

    if not platform_string:
        platform_string = platformops.get_configured_default_platform()

    if platform_string:
        platform = platformops.get_platform_for_platform_string(
            platform_string)
    else:
        platform = platformops.prompt_for_platform()

    if isinstance(platform, SolutionStack):
        if platform.language_name == 'Multi-container Docker' and not iprofile:
            io.log_warning(prompts['ecs.permissions'])
    if isinstance(platform, PlatformVersion):
        platform.hydrate(elasticbeanstalk.describe_platform_version)
        if platform.platform_branch_lifecycle_state == platform_branch_lifecycle_states.RETIRED:
            raise RetiredPlatformBranchError(alerts['platformbranch.retired'])
        statusops.alert_platform_status(platform)
        if 'Multi-container Docker' in platform.platform_name and not iprofile:
            io.log_warning(prompts['ecs.permissions'])

    return platform


def _sleep(seconds):
    time.sleep(seconds)
