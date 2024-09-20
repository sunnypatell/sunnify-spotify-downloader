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

import sys

from ebcli.core import fileoperations
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.lib import aws
from ebcli.objects.exceptions import NotInitializedError
from ebcli.operations import commonops, platformops, initializeops
from ebcli.resources.strings import strings, flag_text, prompts
from ebcli.core.ebglobals import Constants
from ebcli.operations import commonops, sshops

KEYPAIR_NAMESPACE = 'aws:autoscaling:launchconfiguration'
KEYPAIR_OPTION = 'EC2KeyName'


class GenericPlatformInitController(AbstractBaseController):
    class Meta:
        is_platform_workspace_only_command = False
        requires_directory_initialization = False
        arguments = [
            (['platform_name'], dict(help=flag_text['platforminit.name'], nargs='?', default=[])),
            (['-i', '--interactive'], dict(action='store_true', help=flag_text['init.interactive'])),
            (['-k', '--keyname'], dict(help=flag_text['init.keyname']))
        ]
        epilog = strings['platforminit.epilog']

        @classmethod
        def clone(cls):
            return type('Meta', cls.__bases__, dict(cls.__dict__))

    def do_command(self):
        commonops.raise_if_inside_application_workspace()

        fileoperations.touch_config_folder()

        self.interactive = self.app.pargs.interactive or not self.app.pargs.platform_name
        self.region = self.app.pargs.region

        if self.interactive or not self.app.pargs.platform_name:
            self.region = commonops.get_region(self.app.pargs.region, self.interactive)
        else:
            self.region = commonops.get_region_from_inputs(self.app.pargs.region)

        aws.set_region(self.region)

        self.region = commonops.set_up_credentials(self.app.pargs.profile, self.region, self.interactive)
        self.platform_name, version = get_platform_name_and_version(self.app.pargs.platform_name)
        self.keyname = self.app.pargs.keyname

        if not self.keyname and self.interactive:
            self.keyname = get_keyname()

        initializeops.setup(
            'Custom Platform Builder',
            self.region,
            None,
            workspace_type=Constants.WorkSpaceTypes.PLATFORM,
            platform_name=self.platform_name,
            platform_version=version)

        fileoperations.write_keyname(self.keyname)

        if version is None:
            platformops.set_workspace_to_latest()


class PlatformInitController(GenericPlatformInitController):
    Meta = GenericPlatformInitController.Meta.clone()
    Meta.arguments = GenericPlatformInitController.Meta.arguments
    Meta.label = 'platform init'
    Meta.aliases = ['init']
    Meta.aliases_only = True
    Meta.stacked_on = 'platform'
    Meta.stacked_type = 'nested'
    Meta.description = strings['platforminit.info']
    Meta.usage = 'eb platform init <platform name> [options...]'


class EBPInitController(GenericPlatformInitController):
    Meta = GenericPlatformInitController.Meta.clone()
    Meta.arguments = GenericPlatformInitController.Meta.arguments
    Meta.label = 'init'
    Meta.description = strings['platforminit.info']
    Meta.usage = 'ebp init <platform name> [options...]'


def get_keyname():
    return commonops.get_default_keyname() or sshops.prompt_for_ec2_keyname(
        message=prompts['platforminit.ssh']
    )


def get_platform_name_and_version(platform_name):
    version = None

    if not platform_name:
        try:
            platform_name = fileoperations.get_platform_name(default=None)
            version = fileoperations.get_platform_version()
        except NotInitializedError:
            platform_name, version = platformops.get_platform_name_and_version_interactive()

    if sys.version_info[0] < 3 and isinstance(platform_name, unicode):
        try:
            platform_name.encode('utf8')
            platform_name = platform_name.encode('utf8')
        except UnicodeDecodeError:
            pass

    return platform_name, version
