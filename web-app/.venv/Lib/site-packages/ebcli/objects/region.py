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


def get_all_regions():
    return [
        Region('us-east-1', 'US East (N. Virginia)'),
        Region('us-west-1', 'US West (N. California)'),
        Region('us-west-2', 'US West (Oregon)'),
        Region('eu-west-1', 'EU (Ireland)'),
        Region('eu-central-1', 'EU (Frankfurt)'),
        Region('ap-south-1', 'Asia Pacific (Mumbai)'),
        Region('ap-southeast-1', 'Asia Pacific (Singapore)'),
        Region('ap-southeast-2', 'Asia Pacific (Sydney)'),
        Region('ap-northeast-1', 'Asia Pacific (Tokyo)'),
        Region('ap-northeast-2', 'Asia Pacific (Seoul)'),
        Region('sa-east-1', 'South America (Sao Paulo)'),
        Region('cn-north-1', 'China (Beijing)'),
        Region('cn-northwest-1', 'China (Ningxia)'),
        Region('us-east-2', 'US East (Ohio)'),
        Region('ca-central-1', 'Canada (Central)'),
        Region('eu-west-2', 'EU (London)'),
        Region('eu-west-3', 'EU (Paris)'),
        Region('eu-north-1', 'EU (Stockholm)'),
        Region('eu-south-1', 'EU (Milano)'),
        Region('ap-east-1', 'Asia Pacific (Hong Kong)'),
        Region('me-south-1', 'Middle East (Bahrain)'),
        Region('af-south-1', 'Africa (Cape Town)'),
        Region('ap-southeast-3', 'Asia Pacific (Jakarta)'),
        Region('ap-northeast-3', 'Asia Pacific (Osaka)'),
    ]


class Region():
    def __init__(self, name, description):
        self.name = name
        self.description = description

    def __str__(self):
        return self.name + ' : ' + self.description
