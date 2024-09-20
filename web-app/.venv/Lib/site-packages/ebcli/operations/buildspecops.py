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

import time

from datetime import datetime, timedelta
from cement.utils.misc import minimal_logger
from ebcli.core import io
from ebcli.lib import elasticbeanstalk, codebuild
from ebcli.objects.exceptions import ServiceError, ValidationError

from ebcli.resources.strings import strings

LOG = minimal_logger(__name__)


def stream_build_configuration_app_version_creation(app_name, app_version_label, build_spec):
    # Get the CloudWatch logs link
    successfully_generated = wait_for_app_version_attribute(
        app_name,
        [app_version_label],
        timeout=1
    )
    app_version_response = elasticbeanstalk.get_application_versions(
        app_name,
        version_labels=[app_version_label]
    )['ApplicationVersions']

    build_response = codebuild.batch_get_builds([app_version_response[0]['BuildArn']]) \
        if successfully_generated else None

    codebuild_timeout = build_spec.timeout or 60
    if build_response is not None and 'logs' in build_response['builds'][0]:
        log_link_text = strings['codebuild.buildlogs'].replace(
            '{logs_link}',
            build_response['builds'][0]['logs']['deepLink']
        )
        io.echo(log_link_text)
        io.echo(
            "NOTE: The CodeBuild timeout is set to {0} minutes, so this "
            "operation may take upto '{0}' minutes to complete.".format(codebuild_timeout)
        )
    else:
        io.log_warning("Could not retrieve CloudWatch link for CodeBuild logs")

    try:
        # Need to lazy-import `ebcli.lib.commonops` because `pytest` is unable to load it
        # at module load-time using Python 2.7 and Python 3.4
        from ebcli.operations import commonops
        timeout_error_message = ' '.join([
            'The CodeBuild build timed out after {} minute(s).'.format(codebuild_timeout),
            "To increase the time limit, use the 'Timeout' option in the 'buildspec.yml' file."
        ])
        commonops.wait_for_success_events(
            app_name=app_name,
            can_abort=False,
            request_id=None,
            timeout_error_message=timeout_error_message,
            timeout_in_minutes=codebuild_timeout,
            version_label=app_version_label
        )

    except ServiceError as exception:
        LOG.debug("Caught service error while creating application version '{0}' "
                  "deleting the created application version as it is useless now.".format(app_version_label))
        elasticbeanstalk.delete_application_version(app_name, app_version_label)
        raise exception


def validate_build_config(build_config):
    if build_config.service_role is not None:
        from ebcli.lib.iam import get_roles
        role = build_config.service_role
        validated_role = None
        existing_roles = get_roles()
        for existing_role in existing_roles:
            if role == existing_role['Arn'] or role == existing_role['RoleName']:
                validated_role = existing_role['Arn']
                break

        if validated_role is None:
            LOG.debug("Role '{0}' not found in retrieved list of roles".format(role))
            raise ValidationError("Role '{0}' does not exist.".format(role))
        build_config.service_role = validated_role
    else:
        io.log_warning(
            "To learn more about creating a service role for CodeBuild, see Docs:"
            " https://docs-aws.amazon.com/codebuild/latest/userguide/"
            "setting-up.html#setting-up-service-role"
        )
        raise ValidationError("No service role specified in buildspec; this is a required argument.")
    if build_config.image is None:
        raise ValidationError("No image specified in buildspec; this is a required argument.")


def wait_for_app_version_attribute(app_name, version_labels, timeout=5):
    io.echo('--- Waiting for Application Versions to populate attributes ---')
    versions_to_check = list(version_labels)
    found = dict.fromkeys(version_labels)
    failed = dict.fromkeys(version_labels)
    start_time = datetime.utcnow()
    timediff = timedelta(minutes=timeout)
    while versions_to_check:
        if _timeout_reached(start_time, timediff):
            io.log_error(
                strings['appversion.attribute.failed'].replace(
                    '{app_version}',
                    ', '.join(version_labels)
                )
            )
            return False
        io.LOG.debug('Retrieving app versions.')
        app_versions = elasticbeanstalk.get_application_versions(
            app_name,
            versions_to_check
        )['ApplicationVersions']
        for version in app_versions:
            if version.get('BuildArn'):
                found[version['VersionLabel']] = True
                io.echo(strings['appversion.attribute.success'].format(app_version=version['VersionLabel']))
                versions_to_check.remove(version['VersionLabel'])
            elif version.get('Status') == 'FAILED':
                failed[version['VersionLabel']] = True
                io.log_error(
                    strings['appversion.attribute.failed'].format(
                        app_version=version['VersionLabel']
                    )
                )
                versions_to_check.remove(version['VersionLabel'])

        if all(found.values()):
            return True

        _sleep()

    return not any(failed.values())


def _sleep():
    time.sleep(4)


def _timeout_reached(start_time, timediff):
    return datetime.utcnow() - start_time >= timediff
