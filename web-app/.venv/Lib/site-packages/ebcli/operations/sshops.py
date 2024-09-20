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

import subprocess
import os

from cement.utils.misc import minimal_logger

from ebcli.lib import ec2, utils
from ebcli.objects.exceptions import NoKeypairError, NotFoundError, CommandError, InvalidOptionsError
from ebcli.resources.strings import strings, prompts
from ebcli.core import io, fileoperations
from ebcli.operations import commonops


LOG = minimal_logger(__name__)


def prepare_for_ssh(env_name, instance, keep_open, force, setup, number,
                    keyname=None, no_keypair_error_message=None,
                    custom_ssh=None, command=None, timeout=None):
    if setup:
        setup_ssh(env_name, keyname, timeout=timeout)
        return

    if instance and number:
        raise InvalidOptionsError(strings['ssh.instanceandnumber'])

    if not instance:
        instances = commonops.get_instance_ids(env_name)
        if number is not None:
            if number > len(instances) or number < 1:
                raise InvalidOptionsError(
                    'Invalid index number (' + str(number) +
                    ') for environment with ' + str(len(instances)) +
                    ' instances')
            else:
                instance = instances[number - 1]

        elif len(instances) == 1:
            instance = instances[0]
        elif len(instances) == 0:
            raise InvalidOptionsError(strings['ssh.noinstance'])
        else:
            io.echo()
            io.echo('Select an instance to ssh into')
            instance = utils.prompt_for_item_in_list(instances)

    try:
        ssh_into_instance(
            instance,
            keep_open=keep_open,
            force_open=force,
            custom_ssh=custom_ssh,
            command=command
        )
    except NoKeypairError:
        if not no_keypair_error_message:
            no_keypair_error_message = prompts['ssh.nokey']
        io.log_error(no_keypair_error_message)


def setup_ssh(env_name, keyname, timeout=None):
    io.log_warning(prompts['ssh.setupwarn'].replace('{env-name}',
                                                    env_name))

    keyname = prompt_for_ec2_keyname(env_name=env_name, keyname=keyname)

    if keyname:
        options = [
            {'Namespace': 'aws:autoscaling:launchconfiguration',
             'OptionName': 'EC2KeyName',
             'Value': keyname}
        ]
        commonops.update_environment(env_name, options, False, timeout=timeout or 5)


def ssh_into_instance(instance_id, keep_open=False, force_open=False, custom_ssh=None, command=None):
    instance = ec2.describe_instance(instance_id)
    try:
        keypair_name = instance['KeyName']
    except KeyError:
        raise NoKeypairError()
    try:
        ip = instance['PublicIpAddress']
    except KeyError:
        if 'PrivateIpAddress' in instance:
            ip = instance['PrivateIpAddress']
        else:
            raise NotFoundError(strings['ssh.noip'])
    security_groups = instance['SecurityGroups']

    user = 'ec2-user'

    ssh_group = None
    has_restriction = False
    rule_existed_before = False
    group_id = None
    for group in security_groups:
        group_id = group['GroupId']
        group = ec2.describe_security_group(group_id)
        for permission in group.get('IpPermissions', []):
            if permission.get('ToPort', None) == 22:
                ssh_group = group_id
                for rng in permission.get('IpRanges', []):
                    ip_restriction = rng.get('CidrIp', None)
                    if ip_restriction is not None:
                        if ip_restriction != '0.0.0.0/0':
                            has_restriction = True
                        elif ip_restriction == '0.0.0.0/0':
                            rule_existed_before = True

    if has_restriction and not force_open:
        io.log_warning(strings['ssh.notopening'])
    elif group_id and not rule_existed_before:
        io.echo(strings['ssh.openingport'])
        ec2.authorize_ssh(ssh_group or group_id)
        io.echo(strings['ssh.portopen'])

    try:
        if custom_ssh:
            custom_ssh = custom_ssh.split()
        else:
            ident_file = _get_ssh_file(keypair_name)
            custom_ssh = ['ssh', '-i', ident_file, '-o', 'IdentitiesOnly yes']

        custom_ssh.extend([user + '@' + ip])

        if command:
            custom_ssh.extend(command.split())

        io.echo('INFO: Running ' + ' '.join(custom_ssh))
        returncode = subprocess.call(custom_ssh)
        if returncode != 0:
            LOG.debug(custom_ssh[0] + ' returned exitcode: ' + str(returncode))
            raise CommandError('An error occurred while running: ' + custom_ssh[0] + '.')
    except OSError:
        CommandError(strings['ssh.notpresent'])
    finally:
        if keep_open:
            pass
        elif (not has_restriction or force_open) and group_id and not rule_existed_before:
            ec2.revoke_ssh(ssh_group or group_id)
            io.echo(strings['ssh.closeport'])


def _get_ssh_file(keypair_name):
    key_file = fileoperations.get_ssh_folder() + keypair_name
    if not os.path.exists(key_file):
        if os.path.exists(key_file + '.pem'):
            key_file += '.pem'
        else:
            raise NotFoundError(strings['ssh.filenotfound'].replace(
                '{key-name}', keypair_name))

    return key_file


def prompt_for_ec2_keyname(env_name=None, message=None, keyname=None):
    if message is None:
        message = prompts['ssh.setup']

    if env_name:
        io.validate_action(prompts['terminate.validate'], env_name)
    else:
        io.echo(message)
        ssh = io.get_boolean_response()
        if not ssh:
            return None

    keys = [k['KeyName'] for k in ec2.get_key_pairs()]
    default_option = len(keys)

    if keyname:
        for index, key in enumerate(keys):
            if key == keyname:
                default_option = index + 1

    if len(keys) < 1:
        keyname = _generate_and_upload_keypair(keys)

    else:
        new_key_option = '[ Create new KeyPair ]'
        keys.append(new_key_option)
        io.echo()
        io.echo(prompts['keypair.prompt'])
        keyname = utils.prompt_for_item_in_list(keys, default=default_option)

        if keyname == new_key_option:
            keyname = _generate_and_upload_keypair(keys)

    return keyname


def _generate_and_upload_keypair(keys):
    io.echo()
    io.echo(prompts['keypair.nameprompt'])
    unique = utils.get_unique_name('aws-eb', keys)
    keyname = io.prompt('Default is ' + unique, default=unique)
    file_name = fileoperations.get_ssh_folder() + keyname

    try:
        exitcode = subprocess.call(
            ['ssh-keygen', '-f', file_name, '-C', keyname]
        )
    except OSError:
        raise CommandError(strings['ssh.notpresent'])

    if exitcode == 0 or exitcode == 1:
        commonops.upload_keypair_if_needed(keyname)
        return keyname
    else:
        LOG.debug('ssh-keygen returned exitcode: ' + str(exitcode) +
                  ' with filename: ' + file_name)
        raise CommandError('An error occurred while running ssh-keygen.')
