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

import sys

from cement.ext.ext_logging import LoggingLogHandler
from cement.utils.misc import minimal_logger

from ebcli import __version__
from ebcli.core import fileoperations
from ebcli.lib import aws
from ebcli.operations import commonops


LOG = minimal_logger(__name__)


def pre_run_hook(app):
    if app.pargs.verbose:
        LoggingLogHandler.set_level(app.log, 'INFO')

    LOG.debug('-- EBCLI Version: {}'.format(__version__))
    LOG.debug('-- Python Version: {}'.format(sys.version))

    set_profile(app.pargs.profile)
    set_region(app.pargs.region)

    set_endpoint(app.pargs.endpoint_url)
    set_ssl(app.pargs.no_verify_ssl)
    set_debugboto(app.pargs.debugboto)


def set_profile(profile):
    if profile:
        aws.set_profile_override(profile)
    else:
        profile = commonops.get_default_profile()
        if profile:
            aws.set_profile(profile)


def set_ssl(noverify):
    if not noverify:
        noverify = fileoperations.get_config_setting(
            'global', 'no-verify-ssl', default=False)
    if noverify:
        aws.no_verify_ssl()


def set_region(region_name):
    if not region_name:
        region_name = commonops.get_default_region()

    aws.set_region(region_name)


def set_endpoint(endpoint_url):
    if endpoint_url:
        aws.set_endpoint_url(endpoint_url)


def set_debugboto(debugboto):
    if debugboto:
        aws.set_debug()
