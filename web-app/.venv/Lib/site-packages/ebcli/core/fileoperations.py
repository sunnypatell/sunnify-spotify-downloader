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

import codecs
import glob
import json
import os
import shutil
import stat
import sys
import warnings
import yaml
import zipfile

from cement.utils.misc import minimal_logger
from ebcli.objects.buildconfiguration import BuildConfiguration
from pathspec import PathSpec
from six import StringIO
from yaml import safe_load, safe_dump
from yaml.parser import ParserError
from yaml.scanner import ScannerError
from json import load, JSONDecodeError
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

from ebcli.core import io
from ebcli.resources.strings import prompts, strings
from ebcli.objects.exceptions import (
    NotInitializedError,
    InvalidSyntaxError,
    NotFoundError
)
from ebcli.core.ebglobals import Constants

LOG = minimal_logger(__name__)


def get_aws_home():
    sep = os.path.sep
    p = '~' + sep + '.aws' + sep
    return os.path.expanduser(p)


def get_ssh_folder():
    sep = os.path.sep
    p = '~' + sep + '.ssh' + sep
    p = os.path.expanduser(p)
    if not os.path.exists(p):
        os.makedirs(p)
    return p


beanstalk_directory = '.elasticbeanstalk' + os.path.sep
buildspec_name = "buildspec.yml"
buildspec_config_header = 'eb_codebuild_settings'
global_config_file = beanstalk_directory + 'config.global.yml'
local_config_file = beanstalk_directory + 'config.yml'
aws_config_folder = get_aws_home()
aws_config_location = aws_config_folder + 'config'
aws_credentials_location = aws_config_folder + 'credentials'
aws_access_key = 'aws_access_key_id'
aws_secret_key = 'aws_secret_access_key'
region_key = 'region'
default_section = 'default'
ebcli_section = 'profile eb-cli'
app_version_folder = beanstalk_directory + 'app_versions'
logs_folder = beanstalk_directory + 'logs' + os.path.sep
env_yaml = 'env.yaml'

_marker = object()


class ProjectRoot(object):
    @classmethod
    def traverse(cls):
        cwd = os.getcwd()
        if not os.path.isdir(beanstalk_directory):
            LOG.debug('beanstalk directory not found in ' + cwd +
                      '  -Going up a level')
            os.chdir(os.path.pardir)

            if cwd == os.getcwd():
                LOG.debug('Still at the same directory ' + cwd)
                raise NotInitializedError('EB is not yet initialized')

            ProjectRoot.traverse()
        else:
            LOG.debug('Project root found at: ' + cwd)


def _get_option(config, section, key, default):
    try:
        return config.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return default


def is_git_directory_present():
    return os.path.isdir('.git')

def clean_up():
    cwd = os.getcwd()
    try:
        ProjectRoot.traverse()
        if os.path.isdir(beanstalk_directory):
            shutil.rmtree(beanstalk_directory, ignore_errors=True)
    finally:
        os.chdir(cwd)


def _set_not_none(config, section, option, value):
    if value:
        config.set(section, option, value)


def get_war_file_location():
    cwd = os.getcwd()
    try:
        ProjectRoot.traverse()
        lst = glob.glob('{}'.format(os.path.join('build', 'libs', '*.war')))
        try:
            return os.path.join(os.getcwd(), lst[0])
        except IndexError:
            raise NotFoundError('Can not find .war artifact in build' +
                                os.path.sep + 'libs' + os.path.sep)
    finally:
        os.chdir(cwd)


def config_file_present():
    return os.path.isfile(local_config_file)


def project_file_path(filename):
    return os.path.join(get_project_root(), filename)


def project_file_exists(filename):
    return file_exists(project_file_path(filename))


def save_to_aws_config(access_key, secret_key):
    config = configparser.ConfigParser()
    if not os.path.isdir(aws_config_folder):
        os.makedirs(aws_config_folder)

    config.read(aws_config_location)

    if ebcli_section not in config.sections():
        config.add_section(ebcli_section)

    _set_not_none(config, ebcli_section, aws_access_key, access_key)
    _set_not_none(config, ebcli_section, aws_secret_key, secret_key)

    with open(aws_config_location, 'w') as f:
        config.write(f)

    set_user_only_permissions(aws_config_location)


def set_user_only_permissions(location):
    """
    Sets permissions so that only a user can read/write (chmod 400).
    Can be a folder or a file.
    :param location: Full location of either a folder or a location
    """
    if os.path.isdir(location):

        for root, dirs, files in os.walk(location):
            for d in dirs:
                pass
                _set_user_only_permissions_file(os.path.join(root, d), ex=True)
            for f in files:
                _set_user_only_permissions_file(os.path.join(root, f))

    else:
        _set_user_only_permissions_file(location)


def _set_user_only_permissions_file(location, ex=False):
    """
    :param ex: Boolean: add executable permission
    """
    permission = stat.S_IRUSR | stat.S_IWUSR
    if ex:
        permission |= stat.S_IXUSR
    os.chmod(location, permission)


def set_all_unrestricted_permissions(location):
    """
    Set permissions so that user, group, and others all have read,
    write and execute permissions (chmod 777).
    :param location: Full location of either a folder or a location
    """
    os.chmod(location, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)


def remove_execute_access_from_group_and_other_users(location):
    os.chmod(location, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)


def get_current_directory_name():
    dirname, filename = os.path.split(os.getcwd())

    from ebcli.lib.utils import decode_bytes
    filename = decode_bytes(filename)

    return filename


def get_platform_version(default=_marker):
    try:
        return get_global_value('platform_version')
    except NotInitializedError:
        return None


def get_instance_profile(default=None):
    try:
        return get_global_value('instance_profile', default)
    except NotInitializedError:
        return default


def get_application_name(default=_marker):
    return get_global_value('application_name')


def get_platform_name(default=_marker):
    return get_global_value('platform_name')


def get_workspace_type(default=_marker):
    try:
        return get_global_value('workspace_type', default)
    except NotInitializedError:
        if default == _marker:
            raise NotInitializedError
        return default


def get_global_value(key, default=_marker):
    result = get_config_setting('global', key)
    if result is not None:
        return result

    LOG.debug('Directory found, but no config or app name exists')
    if default is _marker:
        raise NotInitializedError
    return default


def touch_config_folder(dir_path=None):
    if not os.path.isdir(os.path.join(dir_path, beanstalk_directory)
                         if dir_path
                         else beanstalk_directory):
        os.makedirs(os.path.join(dir_path, beanstalk_directory)
                    if dir_path
                    else beanstalk_directory)


def create_config_file(
        app_name,
        region,
        solution_stack,
        workspace_type=Constants.WorkSpaceTypes.APPLICATION,
        platform_name=None,
        platform_version=None,
        instance_profile=None,
        dir_path=None,
        repository=None,
        branch=None):
    """
        We want to make sure we do not override the file if it already exists,
         but we do want to fill in all missing pieces
    :param app_name: name of the application
    :return: VOID: no return value
    """
    LOG.debug('Creating config file at ' + os.getcwd())

    if not os.path.isdir(os.path.join(dir_path, beanstalk_directory)
                         if dir_path
                         else beanstalk_directory):
        os.makedirs(os.path.join(dir_path, beanstalk_directory)
                    if dir_path
                    else beanstalk_directory)

    write_config_setting('global', 'application_name', app_name, dir_path=dir_path)
    write_config_setting('global', 'default_region', region, dir_path=dir_path)
    write_config_setting('global', 'default_platform', solution_stack, dir_path=dir_path)
    write_config_setting('global', 'workspace_type', workspace_type, dir_path=dir_path)
    write_config_setting('global', 'platform_name', platform_name, dir_path=dir_path)
    write_config_setting('global', 'platform_version', platform_version, dir_path=dir_path)
    write_config_setting('global', 'instance_profile', instance_profile, dir_path=dir_path)
    from ebcli.operations import gitops
    gitops.set_repo_default_for_current_environment(repository)
    gitops.set_branch_default_for_current_environment(branch)


def get_project_root():
    cwd = os.getcwd()
    try:
        ProjectRoot.traverse()
        return os.getcwd()
    finally:
        os.chdir(cwd)


def inside_ebcli_project():
    try:
        return not not get_project_root()
    except NotInitializedError:
        return False


def get_zip_location(file_name):
    cwd = os.getcwd()
    try:
        ProjectRoot.traverse()
        if not os.path.isdir(app_version_folder):
            os.makedirs(app_version_folder)

        return os.path.abspath(app_version_folder) + os.path.sep + file_name

    finally:
        os.chdir(cwd)


def get_logs_location(folder_name):
    cwd = os.getcwd()
    try:
        ProjectRoot.traverse()
        if not os.path.isdir(logs_folder):
            os.makedirs(logs_folder)

        return os.path.abspath(os.path.join(logs_folder, folder_name))

    finally:
        os.chdir(cwd)


def program_is_installed(program):
    return False if os_which(program) is None else True


def os_which(program):
    path = os.getenv('PATH')
    for p in path.split(os.path.pathsep):
        p = os.path.join(p, program)
        if sys.platform.startswith('win'):
            p += '.exe'
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p


def delete_file(location):
    if os.path.exists(location):
        os.remove(location)


def delete_directory(location):
    if os.path.isdir(location):
        shutil.rmtree(location, ignore_errors=True)


def delete_app_versions():
    cwd = os.getcwd()
    try:
        ProjectRoot.traverse()
        delete_directory(app_version_folder)
    finally:
        os.chdir(cwd)


def zip_append_archive(target_file, source_file):
    zip_source = zipfile.ZipFile(source_file, 'r', allowZip64=True)
    zip_target = zipfile.ZipFile(target_file, 'a', allowZip64=True)
    with warnings.catch_warnings():
        # Ignore UserWarning raised by zip module for zipping modules.
        warnings.simplefilter('ignore', category=UserWarning)
        for filename in zip_source.namelist():
            zf = zip_source.read(filename)
            zip_target.writestr(filename, zf)
    zip_target.close()
    zip_source.close()


def zip_up_folder(directory, location, ignore_list=None):
    cwd = os.getcwd()
    try:
        os.chdir(directory)
        io.log_info('Zipping up folder at location: ' + str(os.getcwd()))
        zipf = zipfile.ZipFile(location, 'w', zipfile.ZIP_DEFLATED, allowZip64=True)
        _zipdir('./', zipf, ignore_list=ignore_list)
        zipf.close()
        LOG.debug('File size: ' + str(os.path.getsize(location)))
    finally:
        os.chdir(cwd)


def zip_up_project(location, ignore_list=None):
    cwd = os.getcwd()

    try:
        ProjectRoot.traverse()

        zip_up_folder('./', location, ignore_list=ignore_list)

    finally:
        os.chdir(cwd)

def _zipdir(path, zipf, ignore_list=None):
    if ignore_list is None:
        ignore_list = {'.gitignore'}
    ignore_list = {'./' + i for i in ignore_list}
    zipped_roots = []
    for root, dirs, files in os.walk(path):
        if '.elasticbeanstalk' in root:
            io.log_info('  -skipping: {}'.format(root))
            continue
        for f in files:
            cur_file = os.path.join(root, f)

            if (
                cur_file.endswith('~')
                or cur_file in ignore_list
                or not _validate_file_for_archive(cur_file)
            ):
                # Ignore editor backup files (like file.txt~)
                # Ignore anything in the .ebignore file
                # Ignore files that cannot be archived
                io.log_info('  -skipping: {}'.format(cur_file))
            else:
                if root not in zipped_roots:
                    # Windows requires us to index the folders.
                    io.log_info(' +adding: {}/'.format(root))
                    zipf.write(root)
                    zipped_roots.append(root)
                io.log_info('  +adding: {}'.format(cur_file))
                if os.path.islink(cur_file):
                    zipInfo = zipfile.ZipInfo()
                    zipInfo.filename = os.path.join(root, f)

                    if sys.version_info > (3,):
                        zipInfo.external_attr = 2716663808
                    else:
                        zipInfo.external_attr = long(2716663808)
                    zipf.writestr(zipInfo, os.readlink(cur_file))
                else:
                    zipf.write(cur_file)


def unzip_folder(file_location, directory):
    if not os.path.isdir(directory):
        os.makedirs(directory)

    zip = zipfile.ZipFile(file_location, 'r', allowZip64=True)
    for cur_file in zip.namelist():
        if not cur_file.endswith('/'):
            root, name = os.path.split(cur_file)
            path = os.path.normpath(os.path.join(directory, root))
            if not os.path.isdir(path):
                os.makedirs(path)
            open(os.path.join(path, name), 'wb').write(zip.read(cur_file))


def delete_app_file(app_name):
    cwd = os.getcwd()
    file_name = beanstalk_directory + app_name

    try:
        ProjectRoot.traverse()
        for file_ext in ['.app.yml']:
            path = file_name + file_ext
            delete_file(path)
    finally:
        os.chdir(cwd)


def delete_env_file(env_name):
    cwd = os.getcwd()
    file_name = beanstalk_directory + env_name

    try:
        ProjectRoot.traverse()
        for file_ext in ['.ebe.yml', '.env.yml']:
            path = file_name + file_ext
            delete_file(path)
    finally:
        os.chdir(cwd)


def get_editor():
    editor = get_config_setting('global', 'editor')
    if not editor:
        editor = os.getenv('EDITOR')
    if not editor:
        platform = sys.platform
        windows = platform.startswith('win')
        if windows:
            editor = 'notepad.exe'
        else:
            editor = 'nano'

    return editor


def save_app_file(app):
    cwd = os.getcwd()
    env_name = app['ApplicationName']
    file_name = env_name + '.app.yml'

    file_name = beanstalk_directory + file_name
    try:
        ProjectRoot.traverse()

        file_name = os.path.abspath(file_name)

        with codecs.open(file_name, 'w', encoding='utf8') as f:
            f.write(safe_dump(app, default_flow_style=False,
                              line_break=os.linesep))

    finally:
        os.chdir(cwd)

    return file_name


def save_env_file(env):
    cwd = os.getcwd()
    env_name = env['EnvironmentName']
    file_name = env_name + '.env.yml'

    file_name = beanstalk_directory + file_name
    try:
        ProjectRoot.traverse()

        file_name = os.path.abspath(file_name)

        with codecs.open(file_name, 'w', encoding='utf8') as f:
            f.write(safe_dump(env, default_flow_style=False,
                              line_break=os.linesep))

    finally:
        os.chdir(cwd)

    return file_name


def get_environment_from_file(env_name, path=None):
    cwd = os.getcwd()
    file_name = beanstalk_directory + env_name

    try:
        if not path:
            ProjectRoot.traverse()
            file_ext = '.env.yml'
            path = file_name + file_ext
        if os.path.exists(path):
            with codecs.open(path, 'r', encoding='utf8') as f:
                try:
                    return safe_load(f)
                except (ScannerError, ParserError):
                    f.seek(0)
                    try:
                        return load(f)
                    except JSONDecodeError:
                        raise InvalidSyntaxError('The environment configuration contains invalid syntax. Make sure your input '
                                             'matches one of the supported formats: JSON, YAML.')
        else:
            raise NotFoundError('The file you specified in this configuration path cannot be found: '+path)


    finally:
        os.chdir(cwd)


def get_application_from_file(app_name):
    cwd = os.getcwd()
    file_name = beanstalk_directory + app_name

    try:
        ProjectRoot.traverse()
        file_ext = '.app.yml'
        path = file_name + file_ext
        if os.path.exists(path):
            with codecs.open(path, 'r', encoding='utf8') as f:
                return safe_load(f)
    except (ScannerError, ParserError):
        raise InvalidSyntaxError('The application file contains '
                                 'invalid syntax.')

    finally:
        os.chdir(cwd)


def update_platform_version(version):
    if version:
        write_config_setting('global', 'platform_version', version)


def update_platform_name(platform_name):
    if platform_name:
        write_config_setting('global', 'platform_name', platform_name)


def write_keyname(keyname):
    write_config_setting('global', 'default_ec2_keyname', keyname)


def get_keyname():
    return get_config_setting('global', 'default_ec2_keyname', None)


def write_config_setting(section, key_name, value, dir_path=None, file=local_config_file):
    cwd = os.getcwd()
    if dir_path:
        os.chdir(dir_path)
    try:
        ProjectRoot.traverse()

        config = _get_yaml_dict(file)
        if not config:
            config = {}
        # Value will be a dict when we are passing in branch config settings
        if type(value) is dict:
            for key in value.keys():
                config.setdefault(section, {}).setdefault(key_name, {})[key] = value[key]
        else:
            if config.get(section) is None:
                config[section] = {}
            config.setdefault(section, {})[key_name] = value

        with codecs.open(file, 'w', encoding='utf8') as f:
            f.write(safe_dump(config, default_flow_style=False,
                              line_break=os.linesep))

    finally:
        os.chdir(cwd)


def get_config_setting(section, key_name, default=_marker):
    cwd = os.getcwd()

    try:
        ProjectRoot.traverse()

        config_global = _get_yaml_dict(global_config_file)
        config_local = _get_yaml_dict(local_config_file)

        # Grab value, local gets priority
        try:
            value = config_global[section][key_name]
        except KeyError:
            value = None

        try:
            if config_local:
                value = config_local[section][key_name]
        except KeyError:
            pass

        if value is None and default != _marker:
            return default
    except NotInitializedError:
        if default == _marker:
            raise
        else:
            return default
    finally:
        os.chdir(cwd)
    return value


def get_json_dict(fullpath):
    """
    Read json file at fullpath and deserialize as dict.
    :param fullpath: str: path to the json file
    :return: dict
    """

    return json.loads(read_from_text_file(fullpath))


def write_json_dict(json_data, fullpath):
    def date_handler(obj):
        return obj.isoformat() if hasattr(obj, 'isoformat') else obj

    data = json.dumps(json_data, sort_keys=True, indent=4,
                      default=date_handler)
    write_to_text_file(data, fullpath)


def _get_yaml_dict(filename):
    try:
        with codecs.open(filename, 'r', encoding='utf8') as f:
            return safe_load(f)
    except IOError:
        return {}


def file_exists(full_path):
    return os.path.isfile(full_path)


def eb_file_exists(location):
    cwd = os.getcwd()
    try:
        ProjectRoot.traverse()
        path = beanstalk_directory + location
        return os.path.isfile(path)
    finally:
        os.chdir(cwd)


def build_spec_exists():
    cwd = os.getcwd()
    try:
        ProjectRoot.traverse()
        return os.path.isfile(buildspec_name)
    finally:
        os.chdir(cwd)


def get_build_configuration():
    service_role_key = 'CodeBuildServiceRole'
    image_key = 'Image'
    compute_key = 'ComputeType'
    timeout_key = 'Timeout'

    cwd = os.getcwd()

    try:
        ProjectRoot.traverse()

        build_spec = _get_yaml_dict(buildspec_name)

        if build_spec is None or buildspec_config_header not in build_spec.keys():
            LOG.debug("Buildspec Keys: {0}".format(build_spec.keys()))
            io.log_warning(strings['codebuild.noheader'].replace('{header}', buildspec_config_header))
            return None

        beanstalk_build_configs = build_spec[buildspec_config_header]

        if beanstalk_build_configs is None:
            LOG.debug("No values for EB header in buildspec file")
            return BuildConfiguration()

        LOG.debug("EB Config Keys: {0}".format(beanstalk_build_configs.keys()))

        build_configuration = BuildConfiguration(
            compute_type=beanstalk_build_configs.get(compute_key),
            image=beanstalk_build_configs.get(image_key),
            service_role=beanstalk_build_configs.get(service_role_key),
            timeout=beanstalk_build_configs.get(timeout_key)
        )
    finally:
        os.chdir(cwd)

    return build_configuration


def write_buildspec_config_header(key_name, value):
    write_config_setting(
        buildspec_config_header,
        key_name,
        value,
        file=buildspec_name
    )


def directory_empty(location):
    return not os.listdir(location)


def get_ebignore_list():
    location = get_ebignore_location()

    if not os.path.isfile(location):
        return None

    with codecs.open(location, 'r', encoding='utf-8') as f:
        spec = PathSpec.from_lines('gitwildmatch', f)

    matches = [f for f in spec.match_tree_entries(get_project_root())]
    ignore_list = {match.path for match in matches}
    ignore_list.add('.ebignore')

    return ignore_list


def make_eb_dir(location):
    cwd = os.getcwd()
    try:
        ProjectRoot.traverse()
        path = beanstalk_directory + location
        if not os.path.isdir(path):
            os.makedirs(path)
    finally:
        os.chdir(cwd)


def write_to_eb_data_file(location, data):
    cwd = os.getcwd()
    try:
        ProjectRoot.traverse()
        path = beanstalk_directory + location
        write_to_data_file(path, data)
    finally:
        os.chdir(cwd)


def write_to_data_file(location, data):
    with codecs.open(location, 'wb', encoding=None) as f:
        f.write(data)


def read_from_data_file(location):
    with codecs.open(location, 'rb', encoding=None) as f:
        return f.read()


def read_from_text_file(location):
    with codecs.open(location, 'rt', encoding=None) as f:
        return f.read()


def write_to_text_file(data, location):
    with codecs.open(location, 'wt', encoding=None) as f:
        f.write(data)


def append_to_text_file(location, data):
    with codecs.open(location, 'at', encoding=None) as f:
        f.write(data)


def readlines_from_text_file(location):
    with codecs.open(location, 'rt', encoding=None) as f:
        return f.readlines()


def get_project_file_full_location(location):
    cwd = os.getcwd()
    try:
        ProjectRoot.traverse()
        full_path = os.path.abspath(location)
        return full_path
    finally:
        os.chdir(cwd)


def get_ebignore_location():
    return get_project_file_full_location('.ebignore')


def get_eb_file_full_location(location):
    return get_project_file_full_location(beanstalk_directory + location)


def get_home():
    return os.path.expanduser('~')


def get_filename_without_extension(file_location):
    filename = os.path.basename(file_location)
    extension = 'fake'
    while extension != '':
        filename, extension = os.path.splitext(filename)
    return filename


def env_yaml_exists():
    return os.path.isfile(os.path.join(os.getcwd(), env_yaml))


def get_env_name_from_env_yaml():
    with open(os.path.join(os.getcwd(), env_yaml), 'r') as f:
        data = yaml.safe_load(f)
        try:
            env_name = data['EnvironmentName']
            return env_name
        except KeyError:
            return None


def get_platform_from_env_yaml():
    with open(os.path.join(os.getcwd(), env_yaml), 'r') as f:
        data = yaml.safe_load(f)
        try:
            env_name = data['SolutionStack']
            return env_name
        except KeyError:
            return None


def open_file_for_editing(file_location):
    file_location = '"{0}"'.format(file_location)
    editor = get_editor()
    try:
        os.system(editor + ' ' + file_location)
    except OSError:
        io.log_error(
            prompts['fileopen.error1'].replace(
                '{editor}',
                editor
            )
        )


def _validate_file_for_archive(file_location):
    file_mode = os.stat(file_location).st_mode
    return not stat.S_ISSOCK(file_mode)
