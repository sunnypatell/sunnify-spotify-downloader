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

import os

from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.resources.strings import strings
from ebcli.core import io, fileoperations
from ebcli.containers import dockerrun
from ebcli.objects.exceptions import NotFoundError, NotSupportedError

DOCKERRUN_FILENAME = 'Dockerrun.aws.json'


class ConvertDockerrunController(AbstractBaseController):
    class Meta:
        label = 'convert-dockerrun'
        stacked_on = 'labs'
        stacked_type = 'nested'
        description = strings['convert-dockkerrun.info']
        usage = 'eb labs convert-dockerrun [options...]'

    def do_command(self):
        dockerrun_location = os.path.join(os.getcwd(), DOCKERRUN_FILENAME)
        v1_json = dockerrun.get_dockerrun(dockerrun_location)
        if not v1_json:
            raise NotFoundError('Dockerrun.aws.json file not found in current directory.')
        if v1_json['AWSEBDockerrunVersion'] == 2:
            raise NotSupportedError('Dockerrun file already at version 2')

        fileoperations.write_json_dict(v1_json, dockerrun_location + '_backup')
        io.echo('Version 1 file saved as Dockerrun.aws.json_backup.')

        v2_json = get_dockerrun_v2(v1_json)
        fileoperations.write_json_dict(v2_json, dockerrun_location)
        io.echo('Dockerrun.aws.json successfully converted to Version 2.')

        io.echo()
        io.echo('To change your default platform, type "eb platform select".')


def get_dockerrun_v2(v1_json):
    v2_json = {
        'AWSEBDockerrunVersion': 2,
        'containerDefinitions': [
            {
                'name': 'myapp',
                'essential': True,
                'memory': 512,
                'portMappings': [
                    {
                        'hostPort': 80,
                    }
                ]
            }
        ]
    }
    try:
        v2_json['containerDefinitions'][0]['image'] = v1_json['Image']['Name']
    except KeyError:
        raise NotFoundError('The "image" field is required for v2 conversion.')
    try:
        v2_json['containerDefinitions'][0]['containerPort'] = \
            int(v1_json['Ports'][0]['ContainerPort'])
    except (KeyError, IndexError):
        raise NotFoundError('The "port" field is required for v2 conversion.')

    if 'Authentication' in v1_json:
        v2_json['authentication'] = {
            'bucket': v1_json['Authentication']['Bucket'],
            'key': v1_json['Authentication']['Key']
        }

    for i, volume in enumerate(v1_json.get('Volumes', [])):
        if 'volumes' not in v2_json:
            v2_json['volumes'] = []

        v2_json['volumes'].append(
            {
                'name': "volume#{i}".format(i=i),
                'host': {
                    'sourcePath': volume['HostDirectory']
                }
            }
        )

        if 'mountPoints' not in v2_json['containerDefinitions'][0]:
            v2_json['containerDefinitions'][0]['mountPoints'] = []

        v2_json['containerDefinitions'][0]['mountPoints'].append(
            {
                'sourceVolume': "volume#{i}".format(i=i),
                'containerPath': volume['ContainerDirectory']
            })

    if v1_json['Logging']:
        if 'mountPoints' not in v2_json['containerDefinitions'][0]:
            v2_json['containerDefinitions'][0]['mountPoints'] = []
        v2_json['containerDefinitions'][0]['mountPoints'].append(
            {
                'sourceVolume': 'awseb-logs-myapp',
                'containerPath': v1_json['Logging']
            })

    return v2_json
