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
from cement.utils.misc import minimal_logger

from ebcli.operations import commonops
from ebcli.core import io, fileoperations
from ebcli.lib import elasticbeanstalk, aws
from ebcli.operations import gitops, buildspecops

LOG = minimal_logger(__name__)


def deploy(app_name, env_name, version, label, message, group_name=None,
           process_app_versions=False, staged=False, timeout=5, source=None):
    region_name = aws.get_region_name()

    build_config = None
    if fileoperations.build_spec_exists() and version is None:
        build_config = fileoperations.get_build_configuration()
        LOG.debug("Retrieved build configuration from buildspec: {0}".format(build_config.__str__()))

    io.log_info('Deploying code to ' + env_name + " in region " + region_name)

    if version:
        app_version_label = version
    elif source is not None:
        app_version_label = commonops.create_app_version_from_source(
            app_name,
            source,
            process=process_app_versions,
            label=label,
            message=message,
            build_config=build_config
        )
        io.echo("Starting environment deployment via specified source")
        process_app_versions = True
    elif gitops.git_management_enabled() and not staged:
        app_version_label = commonops.create_codecommit_app_version(
            app_name, process=process_app_versions, label=label, message=message, build_config=build_config)
        io.echo("Starting environment deployment via CodeCommit")
        process_app_versions = True
    else:
        app_version_label = commonops.create_app_version(
            app_name,
            process=process_app_versions,
            label=label,
            message=message,
            staged=staged,
            build_config=build_config
        )

    if build_config is not None:
        buildspecops.stream_build_configuration_app_version_creation(
            app_name, app_version_label, build_config)
    elif process_app_versions is True:
        success = commonops.wait_for_processed_app_versions(
            app_name,
            [app_version_label],
            timeout=timeout or 5
        )
        if not success:
            return

    request_id = elasticbeanstalk.update_env_application_version(
        env_name, app_version_label, group_name)

    commonops.wait_for_success_events(request_id,
                                      timeout_in_minutes=timeout,
                                      can_abort=True,
                                      env_name=env_name)
