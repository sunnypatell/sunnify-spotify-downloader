# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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


class CFNStack(object):
    def __init__(
            self,
            stack_id=None,
            stack_name=None,
            change_set_id=None,
            description=None,
            creation_time=None,
            deletion_time=None,
            last_updated_time=None,
            stack_status=None,
            stack_status_reason=None,
            enable_termination_protection=None,
    ):
        self.stack_id = stack_id
        self.stack_name = stack_name
        self.change_set_id = change_set_id
        self.description = description
        self.creation_time = creation_time
        self.deletion_time = deletion_time
        self.last_updated_time = last_updated_time
        self.stack_status = stack_status
        self.stack_status_reason = stack_status_reason
        self.enable_termination_protection = enable_termination_protection

    def __str__(self):
        return self.stack_name

    @classmethod
    def json_to_stack_object(cls, cfn_stack_json):
        return CFNStack(
            stack_id=cfn_stack_json.get('StackId'),
            stack_name=cfn_stack_json.get('StackName'),
            change_set_id=cfn_stack_json.get('ChangeSetId'),
            description=cfn_stack_json.get('Sescription'),
            creation_time=cfn_stack_json.get('CreationTime'),
            deletion_time=cfn_stack_json.get('DeletionTime'),
            last_updated_time=cfn_stack_json.get('LastUpdatedTime'),
            stack_status=cfn_stack_json.get('StackStatus'),
            stack_status_reason=cfn_stack_json.get('StackStatusReason'),
            enable_termination_protection=cfn_stack_json.get(
                'EnableTerminationProtection'
            )
        )
