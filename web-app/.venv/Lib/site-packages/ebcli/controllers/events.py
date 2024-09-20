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

from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.resources.strings import strings, flag_text
from ebcli.operations import eventsops


class EventsController(AbstractBaseController):
    class Meta:
        label = 'events'
        description = strings['events.info']
        arguments = AbstractBaseController.Meta.arguments + [
            (['-f', '--follow'], dict(
                action='store_true', help=flag_text['events.follow']))
        ]
        usage = AbstractBaseController.Meta.usage.replace('{cmd}', label)

    def do_command(self):
        app_name = self.get_app_name()
        env_name = self.get_env_name()
        follow = self.app.pargs.follow

        eventsops.print_events(app_name, env_name, follow)
