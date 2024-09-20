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
import re


class PackerRegExpressions(object):
    LOG_MESSAGE_REGEX = re.compile(r'.* -- (.+)$')
    LOG_MESSAGE_SEVERITY_REGEX = re.compile(r'.*(INFO|ERROR|WARN) -- .*')
    OTHER_FORMAT_REGEX = re.compile(r'[^:]+: (.+)')
    PACKER_UI_MESSAGE_FORMAT_REGEX = re.compile(r'Packer:.*ui,.*,(.*)')
    PACKER_OTHER_MESSAGE_DATA_REGEX = re.compile(r'Packer: \d+,([^,]*),.*')
    PACKER_OTHER_MESSAGE_TARGET_REGEX = re.compile(r'Packer: \d+,[^,]*,(.+)')


class PlatformRegExpressions(object):
    VALID_PLATFORM_NAME_FORMAT = re.compile(r'^([^:/]+)$')
    VALID_PLATFORM_SHORT_FORMAT = re.compile(r'^([^:/]+)/(\d+\.\d+\.\d+)$')
    VALID_PLATFORM_VERSION_FORMAT = re.compile(r'^\d+\.\d+\.\d+$')
