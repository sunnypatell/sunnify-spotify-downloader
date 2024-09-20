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
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.operations.platformops import show_platform_events
from ebcli.resources.strings import strings, flag_text


class GenericPlatformEventsController(AbstractBaseController):
    class Meta:
        is_platform_workspace_only_command = True
        requires_directory_initialization = True
        description = strings['platformevents.info']
        arguments = [
            (
                ['version'],
                dict(
                    action='store',
                    nargs='?',
                    default=None,
                    help=flag_text['platformevents.version']
                )
            ),
            (
                ['-f', '--follow'],
                dict(
                    action='store_true',
                    help=flag_text['events.follow']
                )
            )
        ]

        @classmethod
        def clone(cls):
            return type('Meta', cls.__bases__, dict(cls.__dict__))

    @classmethod
    def add_to_handler(cls, handler):
        handler.register(cls)

    def do_command(self):
        version = self.app.pargs.version
        follow = self.app.pargs.follow

        show_platform_events(follow, version)


class PlatformEventsController(GenericPlatformEventsController):
    Meta = GenericPlatformEventsController.Meta.clone()
    Meta.label = 'platform events'
    Meta.aliases = ['events']
    Meta.aliases_only = True
    Meta.stacked_on = 'platform'
    Meta.stacked_type = 'nested'
    Meta.usage = 'eb platform events <version> [options...]'


class EBPEventsController(GenericPlatformEventsController):
    Meta = GenericPlatformEventsController.Meta.clone()
    Meta.label = 'events'
    Meta.usage = 'ebp events <version> [options...]'
