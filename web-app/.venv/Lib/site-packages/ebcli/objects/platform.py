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
import re

from ebcli.lib import utils
from ebcli.objects.exceptions import EBCLIException
from ebcli.resources.statics import (
    platform_branch_lifecycle_states,
    platform_version_lifecycle_states
)


class PlatformVersion(object):

    API_KEYS = [
        'CustomAmiList',
        'DateCreated',
        'DateUpdated',
        'Description',
        'Maintainer',
        'OperatingSystemName',
        'OperatingSystemVersion',
        'PlatformArn',
        'PlatformBranchLifecycleState',
        'PlatformBranchName',
        'PlatformCategory',
        'PlatformLifecycleState',
        'PlatformName',
        'PlatformOwner',
        'PlatformStatus',
        'PlatformVersion',
        'SolutionStackName',
        'SupportedAddonList',
        'SupportedTierList',
    ]

    ARN_PATTERN = re.compile(
        r'^arn:[^:]+:elasticbeanstalk:[^:]+:([^:]*):platform/([^/]+)/(\d+\.\d+\.\d+)$'
    )

    class UnableToParseArnException(EBCLIException):
        pass

    @classmethod
    def arn_to_platform(cls, arn):
        match = PlatformVersion.ARN_PATTERN.search(arn)

        if not match:
            raise PlatformVersion.UnableToParseArnException("Unable to parse arn '{}'".format(arn))

        account_id, platform_name, platform_version = match.group(1, 2, 3)

        return account_id, platform_name, platform_version

    @classmethod
    def from_platform_version_description(cls, platform_version_description):
        platform_version_description = utils.pick(
            platform_version_description, PlatformVersion.API_KEYS)
        platform_version_args = utils.convert_dict_from_camel_to_snake(
            platform_version_description)

        return PlatformVersion(**platform_version_args)

    @classmethod
    def from_platform_version_summary(cls, platform_version_summary):
        """
        Semantic wrapper around PlatformVersion.from_platform_version_description
        """
        return PlatformVersion.from_platform_version_description(
            platform_version_summary)

    @classmethod
    def get_platform_name(cls, arn):
        _, platform_name, _ = PlatformVersion.arn_to_platform(arn)

        return platform_name

    @classmethod
    def get_platform_version(cls, arn):
        _, _, platform_version = PlatformVersion.arn_to_platform(arn)

        return platform_version

    @classmethod
    def get_region_from_platform_arn(cls, arn):
        if cls.is_eb_managed_platform_arn(arn):
            split_string = arn.split(':')
            return split_string[3]

    @classmethod
    def is_custom_platform_arn(cls, arn):
        if PlatformVersion.is_valid_arn(arn):
            return PlatformVersion(arn).account_id

    @classmethod
    def is_eb_managed_platform_arn(cls, arn):
        if PlatformVersion.is_valid_arn(arn):
            return not PlatformVersion(arn).account_id

    @classmethod
    def is_valid_arn(cls, arn):
        if not isinstance(arn, str) and not isinstance(arn, bytes):
            return False

        return PlatformVersion.ARN_PATTERN.search(arn)

    @classmethod
    def match_with_complete_arn(
            cls,
            platforms,
            input_platform_name
    ):
        for platform in platforms:
            if platform == input_platform_name:
                return PlatformVersion(platform)

    @classmethod
    def match_with_platform_name(
            cls,
            custom_platforms,
            input_platform_name
    ):
        for custom_platform in custom_platforms:
            if PlatformVersion.get_platform_name(custom_platform) == input_platform_name:
                return PlatformVersion(custom_platform)

    def __init__(
        self,
        platform_arn,  # Positioned first for backwards compatability
        custom_ami_list=None,
        date_created=None,
        date_updated=None,
        description=None,
        maintainer=None,
        operating_system_name=None,
        operating_system_version=None,
        platform_branch_lifecycle_state=None,
        platform_branch_name=None,
        platform_category=None,
        platform_lifecycle_state=None,
        platform_name=None,
        platform_owner=None,
        platform_status=None,
        platform_version=None,
        solution_stack_name=None,
        supported_addon_list=None,
        supported_tier_list=None,
    ):
        self.custom_ami_list = custom_ami_list
        self.date_created = date_created
        self.date_updated = date_updated
        self.maintainer = maintainer
        self.operating_system_name = operating_system_name
        self.operating_system_version = operating_system_version
        self.platform_arn = platform_arn
        self.platform_branch_lifecycle_state = platform_branch_lifecycle_state
        self.platform_branch_name = platform_branch_name
        self.platform_category = platform_category
        self.platform_lifecycle_state = platform_lifecycle_state
        self.platform_name = platform_name
        self.platform_owner = platform_owner
        self.platform_status = platform_status
        self.platform_version = platform_version
        self.solution_stack_name = solution_stack_name
        self.supported_addon_list = supported_addon_list
        self.supported_tier_list = supported_tier_list

        self.__hydrate_ran = False

        # Legacy attributes
        account_id, arn_platform_name, arn_platform_version = PlatformVersion.arn_to_platform(self.platform_arn)
        self.account_id = account_id
        self.arn = self.platform_arn
        self.name = self.platform_arn
        self.version = self.platform_arn
        self.platform_version = self.platform_version or arn_platform_version
        self.platform_shorthand = self.platform_name or arn_platform_name

    def __str__(self):
        return self.platform_arn

    def __eq__(self, other):
        if not isinstance(other, PlatformVersion):
            return False

        return self.platform_arn == other.platform_arn

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if not isinstance(other, PlatformVersion):
            raise TypeError(
                "'<' not supported between instances of {} {}".format(
                    type(self).__name__, type(other).__name__)
            )
        if self.platform_owner != other.platform_owner:
            raise ValueError("'<' not suported between PlatformVersions with different owners")
        if self.platform_name != other.platform_name:
            raise ValueError("'<' not suported between PlatformVersions with different platform names")

        return utils.parse_version(self.version) < utils.parse_version(other.version)

    @property
    def has_healthd_group_version_2_support(self):
        if PlatformVersion.is_custom_platform_arn(self.platform_arn):
            return False

        return utils.parse_version(self.platform_version) \
            >= utils.parse_version('2.0.10')

    @property
    def has_healthd_support(self):
        return utils.parse_version(self.platform_version) \
               >= utils.parse_version('2.0.0')

    @property
    def is_recommended(self):
        return self.platform_lifecycle_state == platform_version_lifecycle_states.RECOMMENDED

    @property
    def sortable_version(self):
        return utils.parse_version(self.platform_version)

    def hydrate(self, describe_platform_version):
        """
        Given a function the takes a platform version arn as input and returns
        a platform version description, will populate the class instance
        properties with the values from the platform version description.

        Will only run once.
        """
        if not self._is_hydrated():
            platform_version_description = describe_platform_version(
                self.platform_arn)

            platform_version_description = utils.pick(
                platform_version_description, PlatformVersion.API_KEYS)

            for key in platform_version_description:
                attr = utils.camel_to_snake(key)
                setattr(self, attr, platform_version_description[key])

            self.__hydrate_ran = True

        return self

    def _is_hydrated(self):
        if not self.__hydrate_ran:
            attrs = list(map(utils.camel_to_snake, PlatformVersion.API_KEYS))

            for attr in attrs:
                if not getattr(self, attr):
                    return False

        return True


class PlatformBranch(object):

    API_KEYS = [
        'BranchName',
        'LifecycleState',
        'PlatformName',
        'SupportedTierList',
    ]

    LIFECYCLE_SORT_VALUES = {
        platform_branch_lifecycle_states.SUPPORTED: 0,
        platform_branch_lifecycle_states.BETA: 1,
        platform_branch_lifecycle_states.DEPRECATED: 2,
        platform_branch_lifecycle_states.RETIRED: 3,
        'DEFAULT': 4,
    }

    @classmethod
    def from_platform_branch_summary(cls, platform_branch_summary):
        platform_branch_summary = utils.pick(
            platform_branch_summary, PlatformBranch.API_KEYS)
        platform_branch_args = utils.convert_dict_from_camel_to_snake(
            platform_branch_summary)

        return PlatformBranch(**platform_branch_args)

    def __init__(
        self,
        branch_name,
        lifecycle_state=None,
        platform_name=None,
        supported_tier_list=None,
    ):
        self.branch_name = branch_name
        self.lifecycle_state = lifecycle_state
        self.platform_name = platform_name
        self.supported_tier_list = supported_tier_list

        self.__hydrate_ran = False

    def __eq__(self, other):
        if not isinstance(other, PlatformBranch):
            return False

        self_comp_value = (self.platform_name, self.branch_name, self.lifecycle_state)
        other_comp_value = (other.platform_name, other.branch_name, other.lifecycle_state)
        return self_comp_value == other_comp_value

    def __lt__(self, other):
        if not isinstance(other, PlatformBranch):
            raise TypeError(
                "'<' not supported between instances of %s %s" %
                (type(self).__name__, type(other).__name__)
            )

        lifecycle_sort_values = PlatformBranch.LIFECYCLE_SORT_VALUES
        default_lifecycle_sort_value = lifecycle_sort_values['DEFAULT']

        self_comp_value = (
            self.platform_name,
            lifecycle_sort_values.get(self.lifecycle_state, default_lifecycle_sort_value),
            self.branch_name)
        other_comp_value = (
            other.platform_name,
            lifecycle_sort_values.get(other.lifecycle_state, default_lifecycle_sort_value),
            other.branch_name)
        return self_comp_value < other_comp_value

    @property
    def is_beta(self):
        return self.lifecycle_state == platform_branch_lifecycle_states.BETA

    @property
    def is_deprecated(self):
        return self.lifecycle_state == platform_branch_lifecycle_states.DEPRECATED

    @property
    def is_retired(self):
        return self.lifecycle_state == platform_branch_lifecycle_states.RETIRED

    @property
    def is_supported(self):
        return self.lifecycle_state == platform_branch_lifecycle_states.SUPPORTED

    def hydrate(self, get_platform_branch_by_name):
        """
        Given a function the takes a platform branch name as input and
        returns a platform branch summary, will populate the class
        instance properties with the values from the
        platform branch summary.

        Will only run once.
        """
        if not self._is_hydrated():
            platform_branch_summary = get_platform_branch_by_name(
                self.branch_name)

            platform_branch_summary = utils.pick(
                platform_branch_summary, PlatformBranch.API_KEYS)

            for key in platform_branch_summary:
                attr = utils.camel_to_snake(key)
                setattr(self, attr, platform_branch_summary[key])

            self.__hydrate_ran = True

        return self

    def _is_hydrated(self):
        if not self.__hydrate_ran:
            attrs = list(map(utils.camel_to_snake, PlatformBranch.API_KEYS))

            for attr in attrs:
                if not getattr(self, attr):
                    return False

        return True
