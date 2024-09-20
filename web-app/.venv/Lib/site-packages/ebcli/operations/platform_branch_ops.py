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
from ebcli.lib import elasticbeanstalk
from ebcli.objects.platform import PlatformBranch, PlatformVersion

_non_retired_platform_branches_cache = None


def collect_families_from_branches(branches):
    return list(set([branch['PlatformName'] for branch in branches]))


def is_platform_branch_name(platform_string):
    return bool(
        # a platform branch name cannot be an arn
        not PlatformVersion.is_valid_arn(platform_string)
        # request the platform branch from the api to determine if it exists
        and get_platform_branch_by_name(platform_string)
    )


def get_platform_branch_by_name(branch_name):
    branch_name_filter = {
        'Attribute': 'BranchName',
        'Operator': '=',
        'Values': [branch_name],
    }

    results = elasticbeanstalk.list_platform_branches(
        filters=[branch_name_filter])

    if len(results) == 0:
        return None
    elif len(results) > 1:
        return _resolve_conflicting_platform_branches(results)

    return results[0]


def list_nonretired_platform_branches():
    """
    Provides a list of all platform branches that are not retired.
    This includes deprecated and beta platform branches.
    Return value is cached preventing redundant http requests on
    subsequent calls.
    """
    global _non_retired_platform_branches_cache
    if not _non_retired_platform_branches_cache:
        noretired_filter = {
            'Attribute': 'LifecycleState',
            'Operator': '!=',
            'Values': ['Retired']
        }
        _non_retired_platform_branches_cache = elasticbeanstalk.list_platform_branches(
            filters=[noretired_filter])

    return _non_retired_platform_branches_cache


def _resolve_conflicting_platform_branches(branches):
    """
    Accepts a list of PlatformBranchSummary objects and
    and returns one PlatformBranchSummary object based on
    LifecycleState precedence.
    Supported < Beta < Deprecated < Retired
    """
    if not branches:
        return None

    branches = list(sorted(
        branches,
        key=lambda x: PlatformBranch.LIFECYCLE_SORT_VALUES.get(
            x['LifecycleState'],
            PlatformBranch.LIFECYCLE_SORT_VALUES['DEFAULT'],
        )
    ))

    return branches[0]
