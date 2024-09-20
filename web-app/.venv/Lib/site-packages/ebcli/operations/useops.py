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
from ebcli.objects.exceptions import ServiceError, NotFoundError
from ebcli.lib import elasticbeanstalk, codecommit
from ebcli.operations import commonops, gitops


def switch_default_environment(env_name):
    __verify_environment_exists(env_name)

    commonops.set_environment_for_current_branch(env_name)


def switch_default_repo_and_branch(repo_name, branch_name):
    __verify_codecommit_branch_and_repository_exist(repo_name, branch_name)

    gitops.set_repo_default_for_current_environment(repo_name)
    gitops.set_branch_default_for_current_environment(branch_name)


def __verify_environment_exists(env_name):
    elasticbeanstalk.get_environment(env_name=env_name)


def __verify_codecommit_branch_and_repository_exist(repo_name, branch_name):
    try:
        codecommit.get_branch(repo_name, branch_name)
    except ServiceError:
        raise NotFoundError("CodeCommit branch not found: {}".format(branch_name))
