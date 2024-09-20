# Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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


class BuildConfiguration:
    def __init__(self, image=None, service_role=None, compute_type=None,
                 timeout=None):
        self.image = image
        self.service_role = service_role
        self.compute_type = compute_type
        self.timeout = timeout

    def __str__(self):
        return ['Image: {0}'.format(self.image), 'ServiceRole: {0}'.format(self.service_role),
                'ComputeType: {0}'.format(self.compute_type), 'Timeout: {0}'.format(self.timeout)]
