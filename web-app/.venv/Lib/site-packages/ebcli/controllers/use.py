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
from cement.utils.misc import minimal_logger

from ebcli.lib import utils
from ebcli.objects.exceptions import InvalidOptionsError, NotFoundError
from ebcli.objects.sourcecontrol import SourceControl
from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.resources.strings import strings, flag_text
from ebcli.operations import useops, gitops

LOG = minimal_logger(__name__)


class UseController(AbstractBaseController):
    class Meta:
        label = 'use'
        description = strings['use.info']
        arguments = [
            (
                ['environment_name'],
                dict(action='store', nargs=1, help=flag_text['use.env'])
            ),
            (
                ['--source'],
                dict(help=flag_text['deploy.source'])
            ),
        ]
        usage = 'eb use [environment_name] [options ...]'

    def do_command(self):
        source = self.app.pargs.source
        env_name = self.app.pargs.environment_name[0]

        useops.switch_default_environment(env_name)

        if source:
            self.__attempt_to_checkout_branch_specified_in_source_input(source)
        else:
            self.__attempt_to_change_branch_to_environment_default()

    @staticmethod
    def __attempt_to_change_branch_to_environment_default():
        source_control = SourceControl.get_source_control()
        default_branch = gitops.get_branch_default_for_current_environment()
        if default_branch:
            source_control.checkout_branch(default_branch)

    @staticmethod
    def __attempt_to_checkout_branch_specified_in_source_input(source):
        source_location, repo, branch = utils.parse_source(source)
        if not branch or not repo:
            raise InvalidOptionsError(strings['codecommit.bad_source'])

        source_control = SourceControl.get_source_control()
        source_control.is_setup()

        repo = repo or gitops.get_default_repository()

        useops.switch_default_repo_and_branch(repo, branch)
        successfully_checked_out_branch = source_control.checkout_branch(branch)

        if not successfully_checked_out_branch:
            raise NotFoundError("Could not checkout branch {0}.".format(branch))
