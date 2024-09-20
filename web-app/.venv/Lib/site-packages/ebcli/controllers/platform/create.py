# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
from ebcli.core import fileoperations
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.core.fileoperations import write_config_setting
from ebcli.objects.exceptions import NotInitializedError
from ebcli.operations.platform_version_ops import create_platform_version
from ebcli.operations.tagops import tagops
from ebcli.resources.strings import strings, flag_text
from ebcli.resources.statics import iam_attributes
from ebcli.operations import commonops


class GenericPlatformCreateController(AbstractBaseController):
    class Meta:
        is_platform_workspace_only_command = True
        requires_directory_initialization = True
        description = strings['platformcreateversion.info']
        arguments = [
            (
                ['version'],
                dict(
                    action='store',
                    nargs='?',
                    default=None,
                    help=flag_text['platformcreateversion.version']
                )
            ),
            (
                ['-M',
                 '--major-increment'],
                dict(
                    action='store_true',
                    help=flag_text['platformcreateversion.major']
                )
            ),
            (
                ['-m',
                 '--minor-increment'],
                dict(
                    action='store_true',
                    help=flag_text['platformcreateversion.minor']
                )
            ),
            (
                ['-p',
                 '--patch-increment'],
                dict(
                    action='store_true',
                    help=flag_text['platformcreateversion.patch']
                )
            ),
            (
                ['-i',
                 '--instance-type'],
                dict(
                    help=flag_text['create.itype']
                )
            ),
            (
                ['-ip',
                 '--instance_profile'],
                dict(
                    action='store',
                    help=flag_text['platformcreate.instanceprofile']
                )
            ),
            (
                ['--vpc.id'],
                dict(
                    dest='vpc_id',
                    help=flag_text['platformcreateversion.vpc.id']
                )
            ),
            (
                ['--vpc.subnets'],
                dict(
                    dest='vpc_subnets',
                    help=flag_text['platformcreateversion.vpc.subnets']
                )
            ),
            (
                ['--vpc.publicip'],
                dict(
                    action='store_true',
                    dest='vpc_publicip',
                    help=flag_text['platformcreateversion.vpc.publicip']
                )
            ),
            (
                ['--timeout'],
                dict(
                    type=int,
                    help=flag_text['general.timeout']
                )
            ),
            (
                ['--tags'],
                dict(
                    help=flag_text['create.tags'],
                )
            ),
        ]
        epilog = strings['platformcreateversion.epilog']

        @classmethod
        def clone(cls):
            return type('Meta', cls.__bases__, dict(cls.__dict__))

    def do_command(self):
        self.get_instance_profile()
        tags = self.app.pargs.tags
        if tags:
            tags = tagops.get_and_validate_tags(tags)

        create_platform_version(
            self.app.pargs.version,
            self.app.pargs.major_increment,
            self.app.pargs.minor_increment,
            self.app.pargs.patch_increment,
            self.app.pargs.instance_type,
            {
                'id': self.app.pargs.vpc_id,
                'subnets': self.app.pargs.vpc_subnets,
                'publicip': self.app.pargs.vpc_publicip
            },
            timeout=self.app.pargs.timeout,
            tags=tags,
        )

    def get_instance_profile(self):
        profile_name = self.app.pargs.instance_profile

        if profile_name is None:
            try:
                profile_name = fileoperations.get_instance_profile()
            except NotInitializedError:
                pass

        if profile_name is None\
                or profile_name == iam_attributes.DEFAULT_PLATFORM_BUILDER_ROLE:
            profile_name = commonops.create_instance_profile(
                iam_attributes.DEFAULT_PLATFORM_BUILDER_ROLE,
                iam_attributes.DEFAULT_CUSTOM_PLATFORM_BUILDER_POLICIES
            )

        write_config_setting('global', 'instance_profile', profile_name)


class PlatformCreateController(GenericPlatformCreateController):
    Meta = GenericPlatformCreateController.Meta.clone()
    Meta.label = 'platform create'
    Meta.aliases = ['create']
    Meta.aliases_only = True
    Meta.stacked_on = 'platform'
    Meta.stacked_type = 'nested'
    Meta.usage = 'eb platform create <version> [options...]'


class EBPCreateController(GenericPlatformCreateController):
    Meta = GenericPlatformCreateController.Meta.clone()
    Meta.label = 'create'
    Meta.usage = 'ebp create <version> [options...]'
