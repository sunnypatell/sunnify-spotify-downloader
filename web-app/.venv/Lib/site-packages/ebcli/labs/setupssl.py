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
import subprocess

from cement.utils.misc import minimal_logger

from ebcli.core.abstractcontroller import AbstractBaseController
from ebcli.resources.strings import strings
from ebcli.core import io, fileoperations
from ebcli.lib import elasticbeanstalk, iam, utils
from ebcli.objects.exceptions import NotFoundError, InvalidOptionsError, \
    CommandError, NotSupportedError
from ebcli.operations import commonops
from ebcli.resources.statics import namespaces, option_names

LOG = minimal_logger(__name__)


class SetupSSLController(AbstractBaseController):
    class Meta:
        label = 'setup-ssl'
        stacked_on = 'labs'
        stacked_type = 'nested'
        description = strings['setup-ssl.info']
        usage = 'eb labs setup-ssl <environment_name> [options...]'
        arguments = AbstractBaseController.Meta.arguments + [
            (['--cert-file'], dict(action='store', help='certificate file')),
            (['--private-key'], dict(action='store', help='private key file')),
            (['--cert-chain'], dict(action='store',
                                    help='certificate chain file')),
            (['--name'], dict(action='store',
                              help='certificate name '
                                   'DEFAULT={environment-name}'))
        ]
        epliog = 'All files must be in X.509 PEM format.'

    def do_command(self):
        app_name = self.get_app_name()
        env_name = self.get_env_name(cmd_example='eb labs setup-ssl')
        certfile = self.app.pargs.cert_file
        privatekey = self.app.pargs.private_key
        certchain = self.app.pargs.cert_chain
        cert_name = self.app.pargs.name

        if certfile or privatekey or certfile:
            if not (certfile and privatekey):
                raise InvalidOptionsError(
                    'When providing your own certificate the --cert-file '
                    'and --private-key options are both required.')
            _validate_files_exists(certfile, privatekey, certchain)

        if not cert_name:
            cert_name = env_name

        if _is_single_instance(app_name, env_name):
            raise NotSupportedError('This command is currently not supported '
                                    'for single instance environments. \n'
                                    'For more information please see '
                                    'http://docs.aws.amazon.com/elasticbeanstalk/'
                                    'latest/dg/SSL.SingleInstance.html')

        if not certfile:
            privatekey, certfile = generate_self_signed_cert(cert_name)

        certfile = fileoperations.read_from_text_file(certfile)
        privatekey = fileoperations.read_from_text_file(privatekey)
        if certchain:
            certchain = fileoperations.read_from_text_file(certchain)

        result = iam.upload_server_certificate(cert_name + '.crt', certfile,
                                               privatekey, chain=certchain)
        arn = result['Arn']

        option_settings = [
            elasticbeanstalk.create_option_setting(
                namespaces.LOAD_BALANCER,
                option_names.LOAD_BALANCER_HTTP_PORT,
                'OFF'
            ),
            elasticbeanstalk.create_option_setting(
                namespaces.LOAD_BALANCER,
                option_names.LOAD_BALANCER_HTTPS_PORT,
                '443'
            ),
            elasticbeanstalk.create_option_setting(
                namespaces.LOAD_BALANCER,
                option_names.SSL_CERT_ID,
                arn
            ),
        ]
        commonops.update_environment(env_name, changes=option_settings,
                                     nohang=False)


def generate_self_signed_cert(cert_name):
    home = fileoperations.get_home()
    cert_dir = os.path.join(home, '.ssl')
    privatekey_filename = cert_name + '-privatekey.pem'
    privatekey_dir = os.path.join(cert_dir, privatekey_filename)
    sign_request_filename = cert_name + '-csr.pem'
    sign_request_dir = os.path.join(cert_dir, sign_request_filename)
    server_cert_filename = cert_name + '.crt'
    server_cert_dir = os.path.join(cert_dir, server_cert_filename)

    if not os.path.isdir(cert_dir):
        os.mkdir(cert_dir)

    io.log_warning('Generating a self-signed certificate. '
                   'To provide an already created certificate, '
                   'use the command options.'
                   '\nSee "eb labs setup-ssl --help" for more info.')

    if not fileoperations.program_is_installed('openssl'):
        raise CommandError('This command requires openssl to be '
                           'installed on the PATH')

    if not os.path.isfile(privatekey_dir):
        utils.exec_cmd_quiet(['openssl', 'genrsa', '-out', privatekey_dir])

    if not os.path.isfile(sign_request_dir):
        io.echo()
        subprocess.check_call(['openssl', 'req', '-new',
                               '-key', privatekey_dir,
                               '-out', sign_request_dir])
        io.echo()

    if not os.path.isfile(server_cert_dir):
        utils.exec_cmd_quiet(['openssl', 'x509', '-req', '-days', '365',
                              '-in', sign_request_dir,
                              '-signkey', privatekey_dir,
                              '-out', server_cert_dir])

    return privatekey_dir, server_cert_dir


def _validate_files_exists(*files):
    for f in files:
        if f is None:
            continue
        if not fileoperations.file_exists(f):
            raise NotFoundError('Cannot find file {}'.format(f))


def _is_single_instance(app_name, env_name):
    env = elasticbeanstalk.describe_configuration_settings(app_name, env_name)
    option_settings = env['OptionSettings']
    env_type = elasticbeanstalk.get_option_setting(
        option_settings,
        namespaces.ENVIRONMENT,
        option_names.ENVIRONMENT_TYPE)

    if env_type == 'SingleInstance':
        return True
