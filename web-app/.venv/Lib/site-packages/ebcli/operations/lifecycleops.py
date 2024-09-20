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
from cement.utils.misc import minimal_logger

from ebcli.lib import elasticbeanstalk, aws
from ebcli.core import fileoperations, io
from ebcli.objects.lifecycleconfiguration import LifecycleConfiguration
from ebcli.objects.exceptions import InvalidSyntaxError
from ebcli.resources.strings import strings

LOG = minimal_logger(__name__)
SPACER = ' ' * 2
NO_ITEM_TOKEN = '-'


def print_lifecycle_policy(app_name):
    application = elasticbeanstalk.describe_application(app_name)
    region = aws.get_region_name()

    io.echo('Application details for:', app_name)
    io.echo('{0}Region:'.format(SPACER), region)
    io.echo('{0}Description:'.format(SPACER), getattr(application, 'Description', NO_ITEM_TOKEN))
    io.echo('{0}Date Created:'.format(SPACER), application['DateCreated'].strftime("%Y/%m/%d %H:%M %Z"))
    io.echo('{0}Date Updated:'.format(SPACER), application['DateUpdated'].strftime("%Y/%m/%d %H:%M %Z"))
    io.echo('{0}Application Versions:'.format(SPACER), getattr(application, 'Versions', NO_ITEM_TOKEN))
    io.echo('{0}Resource Lifecycle Config(s):'.format(SPACER))
    resource_configs = application['ResourceLifecycleConfig']
    recursive_print_api_dict(resource_configs)


def recursive_print_api_dict(config, spaced=2):
    for entry in config:
        entry_value = config[u'{0}'.format(entry)]
        if isinstance(entry_value, dict):
            io.echo('{0}{1}:'.format(SPACER * spaced, entry))
            recursive_print_api_dict(entry_value, spaced + 1)
        else:
            io.echo('{0}{1}: {2}'.format(SPACER * spaced, entry, entry_value))


def interactive_update_lifcycle_policy(app_name):
    api_model = elasticbeanstalk.describe_application(app_name)

    lifecycle_config = LifecycleConfiguration(api_model)
    usr_model = lifecycle_config.convert_api_to_usr_model()

    file_location = fileoperations.save_app_file(usr_model)
    fileoperations.open_file_for_editing(file_location)

    try:
        usr_model = fileoperations.get_application_from_file(app_name)
        config_changes = lifecycle_config.collect_changes(usr_model)
        fileoperations.delete_app_file(app_name)
    except InvalidSyntaxError:
        io.log_error(strings['lifecycle.invalidsyntax'])
        fileoperations.delete_app_file(app_name)
        return

    if not config_changes:
        io.log_warning(strings['lifecycle.updatenochanges'])
        return

    elasticbeanstalk.update_application_resource_lifecycle(app_name, config_changes)
    io.echo(strings['lifecycle.success'])
