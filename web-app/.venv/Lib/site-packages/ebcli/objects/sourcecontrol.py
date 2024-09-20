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

import datetime
import fileinput
import os
import re
import subprocess
import sys

from cement.utils.misc import minimal_logger
from cement.utils.shell import exec_cmd

from ebcli.lib import utils
from ebcli.core import fileoperations, io
from ebcli.objects.exceptions import (
    CommandError,
    NotInitializedError,
    NoSourceControlError
)
from ebcli.resources.strings import git_ignore, strings

LOG = minimal_logger(__name__)


class SourceControl(object):
    name = 'base'

    def __init__(self):
        self.name = ''

    def get_name(self):
        return None

    def get_current_branch(self):
        pass

    def do_zip(self, location, staged=False):
        pass

    def set_up_ignore_file(self):
        pass

    def get_version_label(self):
        pass

    def untracked_changes_exist(self):
        pass

    @staticmethod
    def get_source_control():
        try:
            git_installed = fileoperations.get_config_setting('global', 'sc')
        except NotInitializedError:
            git_installed = False

        if not git_installed:
            if Git().is_setup():
                return Git()
            else:
                return NoSC()

        return Git()


class NoSC(SourceControl):
    """
        No source control installed
    """
    DEFAULT_MESSAGE = 'EB-CLI deploy'

    def get_name(self):
        return None

    def get_version_label(self):
        suffix = datetime.datetime.now().strftime("%y%m%d_%H%M%S%f")
        return 'app-' + suffix

    def get_current_branch(self):
        return 'default'

    def do_zip(self, location, staged=False):
        io.log_info('Creating zip using systems zip')
        fileoperations.zip_up_project(location)

    def get_message(self):
        return NoSC.DEFAULT_MESSAGE

    def is_setup(self):
        pass

    def set_up_ignore_file(self):
        Git().set_up_ignore_file()

    def clean_up_ignore_file(self):
        pass

    def untracked_changes_exist(self):
        return False


class Git(SourceControl):
    """
    The user has git installed
    """
    codecommit_remote_name = 'codecommit-origin'

    def get_name(self):
        return 'git'

    def _handle_exitcode(self, exitcode, stderr):
        if exitcode == 0:
            return
        if exitcode == 127:
            # 127 = git not installed
            raise NoSourceControlError
        if exitcode == 128:
            # 128 = No HEAD
            if "HEAD" in stderr:
                LOG.debug(
                    'An error occurred while handling git command.\nError code: '
                    + str(exitcode)
                    + ' Error: '
                    + stderr
                )
                raise CommandError(
                    'git could not find the HEAD; '
                    'most likely because there are no commits present'
                )

        raise CommandError('An error occurred while handling git command.'
                           '\nError code: ' + str(exitcode) + ' Error: ' +
                           stderr)

    def get_version_label(self):
        io.log_info('Getting version label from git with git-describe')
        stdout, stderr, exitcode = \
            self._run_cmd(['git', 'describe', '--always', '--abbrev=4'])

        version_label = 'app-{}-{:%y%m%d_%H%M%S%f}'.format(stdout, datetime.datetime.now())
        return version_label.replace('.', '_')

    def untracked_changes_exist(self):
        try:
            result = subprocess.check_output(['git', 'diff', '--numstat'])

            if isinstance(result, bytes):
                result = result.decode()

            LOG.debug('Result of `git diff --numstat`: ' + result)
        except subprocess.CalledProcessError as e:
            LOG.debug('`git diff --numstat` resulted in an error: ' + str(e))

    def get_current_repository(self):
        current_branch = self.get_current_branch()
        get_remote_name_command = ['git', 'config', '--get', 'branch.{0}.remote'.format(current_branch)]
        LOG.debug(
            'Getting current repository name based on the current branch name:'
            '{0}'.format(' '.join(get_remote_name_command))
        )

        stdout, stderr, exitcode = self._run_cmd(
            get_remote_name_command,
            handle_exitcode=False
        )

        current_remote = stdout
        if exitcode != 0:
            LOG.debug("No remote found for the current working directory.")
            current_remote = None

        LOG.debug('Found remote: {}'.format(current_remote))
        return current_remote

    def get_current_branch(self):
        revparse_command = ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
        LOG.debug('Getting current branch name by performing `{0}`'.format(' '.join(revparse_command)))

        stdout, stderr, exitcode = self._run_cmd(revparse_command, handle_exitcode=False)

        if stdout.strip() == 'HEAD':
            io.log_warning('Git is in a detached head state. Using branch "default".')
            return 'default'
        else:
            self._handle_exitcode(exitcode, stderr)

        LOG.debug(stdout)

        return stdout

    def get_current_commit(self):
        latest_commit_command = ['git', 'rev-parse', '--verify', 'HEAD']
        LOG.debug('Getting current commit by performing `{0}`'.format(' '.join(latest_commit_command)))

        stdout, stderr, exitcode = self._run_cmd(
            latest_commit_command,
            handle_exitcode=False
        )
        if exitcode != 0:
            LOG.debug('No current commit found')
            return
        else:
            self._handle_exitcode(exitcode, stderr)

        LOG.debug(stdout)
        return stdout

    def do_zip_submodule(self, main_location, sub_location, staged=False, submodule_dir=None):
        if staged:
            commit_id, stderr, exitcode = self._run_cmd(['git', 'write-tree'])

        else:
            commit_id = 'HEAD'

        io.log_info('creating zip using git submodule archive {0}'.format(commit_id))

        # individually zip submodules if there are any
        stdout, stderr, exitcode = self._run_cmd(['git', 'archive', '-v', '--format=zip',
                                                  '--prefix', os.path.join(submodule_dir, ''),
                                                  '-o', sub_location, commit_id])
        io.log_info('git archive output: {0}'.format(stderr))

        fileoperations.zip_append_archive(main_location, sub_location)
        fileoperations.delete_file(sub_location)

    def do_zip(self, location, staged=False):
        cwd = os.getcwd()
        try:
            fileoperations.ProjectRoot.traverse()

            if staged:
                commit_id, stderr, exitcode = self._run_cmd(['git', 'write-tree'])
            else:
                commit_id = 'HEAD'

            io.log_info('creating zip using git archive {0}'.format(commit_id))
            stdout, stderr, exitcode = self._run_cmd(
                ['git', 'archive', '-v', '--format=zip',
                 '-o', location, commit_id])
            io.log_info('git archive output: {0}'.format(stderr))

            project_root = os.getcwd()

            must_zip_submodules = fileoperations.get_config_setting('global', 'include_git_submodules')

            if must_zip_submodules:
                stdout, stderr, exitcode = self._run_cmd(['git', 'submodule', 'foreach', '--recursive'])

                for index, line in enumerate(stdout.splitlines()):
                    submodule_dir = line.split(' ')[1].strip('\'')
                    os.chdir(os.path.join(project_root, submodule_dir))
                    self.do_zip_submodule(
                        location,
                        "{0}_{1}".format(
                            location,
                            str(index)
                        ),
                        staged=staged,
                        submodule_dir=submodule_dir
                    )

        finally:
            os.chdir(cwd)

    def get_message(self):
        stdout, stderr, exitcode = self._run_cmd(
            ['git', 'log', '--oneline', '-1'])
        return stdout.split(' ', 1)[1]

    def is_setup(self):
        if fileoperations.is_git_directory_present():
            if not fileoperations.program_is_installed('git'):
                raise CommandError(strings['sc.gitnotinstalled'])
            else:
                return True
        return False

    def set_up_ignore_file(self):
        if not os.path.exists('.gitignore'):
            open('.gitignore', 'w')
        else:
            with open('.gitignore', 'r') as f:
                for line in f:
                    if line.strip() == git_ignore[0]:
                        return

        with open('.gitignore', 'a') as f:
            f.write('\n')
            for line in git_ignore:
                f.write('{}\n'.format(line))

    def clean_up_ignore_file(self):
        cwd = os.getcwd()
        try:
            fileoperations.ProjectRoot.traverse()

            in_section = False
            for line in fileinput.input('.gitignore', inplace=True):
                if line.startswith(git_ignore[0]):
                    in_section = True
                if not line.strip():
                    in_section = False

                if not in_section:
                    print(line, end='')

        finally:
            os.chdir(cwd)

    def push_codecommit_code(self):
        io.log_info('Pushing local code to codecommit with git-push')

        stdout, stderr, exitcode = self._run_cmd(
            [
                'git', 'push',
                self.get_current_repository(),
                self.get_current_branch()
            ]
        )

        if exitcode != 0:
            io.log_warning('Git is not able to push code: {0}'.format(exitcode))
            io.log_warning(stderr)
        else:
            LOG.debug('git push result: {0}'.format(stdout))
            self._handle_exitcode(exitcode, stderr)

    def setup_codecommit_remote_repo(self, remote_url):
        self.verify_url_is_a_codecommit_url(remote_url)
        remote_add_command = ['git', 'remote', 'add', self.codecommit_remote_name, remote_url]
        LOG.debug('Adding remote: {0}'.format(' '.join(remote_add_command)))

        stdout, stderr, exitcode = self._run_cmd(remote_add_command, handle_exitcode=False)

        if exitcode != 0:
            if exitcode == 128:
                remote_set_url_command = [
                    'git', 'remote', 'set-url',
                    self.codecommit_remote_name,
                    remote_url
                ]
                LOG.debug(
                    'Remote already exists, performing: {0}'.format(
                        ' '.join(remote_set_url_command)
                    )
                )
                self._run_cmd(remote_set_url_command)

                remote_set_url_with_push_command = [
                    'git',
                    'remote',
                    'set-url',
                    '--push',
                    self.codecommit_remote_name,
                    remote_url
                ]
                LOG.debug(
                    '                {0}'.format(
                        ' '.join(remote_set_url_with_push_command)
                    )
                )
                self._run_cmd(remote_set_url_with_push_command)
            else:
                LOG.debug("Error setting up git config for CodeCommit: {0}".format(stderr))
                return
        else:
            remote_set_url_with_add_push_command = [
                'git', 'remote', 'set-url',
                '--add',
                '--push',
                self.codecommit_remote_name,
                remote_url
            ]
            LOG.debug(
                'Setting remote URL and pushing to it: {0}'.format(
                    ' '.join(remote_set_url_with_add_push_command)
                )
            )
            self._run_cmd(remote_set_url_with_add_push_command)
            self._handle_exitcode(exitcode, stderr)

        LOG.debug('git remote result: ' + stdout)

    def setup_new_codecommit_branch(self, branch_name):
        LOG.debug("Setting up CodeCommit branch")

        self.fetch_remote_branches(self.codecommit_remote_name)

        self.checkout_branch(branch_name, create_branch=True)

        stdout, stderr, exitcode = self._run_cmd(
            ['git', 'push', '-u', self.codecommit_remote_name, branch_name],
            handle_exitcode=False
        )

        if exitcode == 1:
            io.log_warning('Git is not able to push code: {0}'.format(exitcode))
            io.log_warning(stderr)

        if stderr:
            LOG.debug('git push error: ' + stderr)

        LOG.debug('git push result: ' + stdout)

        self.fetch_remote_branches(self.codecommit_remote_name)

        stdout, stderr, exitcode = self._run_cmd(
            [
                'git',
                'branch',
                '--set-upstream-to',
                '{0}/{1}'.format(self.codecommit_remote_name, branch_name)
            ],
            handle_exitcode=False
        )

        if stderr:
            LOG.debug('git branch --set-upstream-to error: ' + stderr)

        LOG.debug('git branch result: ' + stdout)

    def setup_existing_codecommit_branch(self, branch_name):
        self.fetch_remote_branches(self.codecommit_remote_name)

        self.checkout_branch(branch_name, create_branch=True)

        stdout, stderr, exitcode = self._run_cmd(
            [
                'git', 'branch', '--set-upstream-to', "{0}/{1}".format(
                    self.codecommit_remote_name,
                    branch_name
                )
            ],
            handle_exitcode=False
        )

        if exitcode != 0:
            LOG.debug('git branch --set-upstream-to error: ' + stderr)
            return False

        LOG.debug('git branch result: ' + stdout)

        return True

    def checkout_branch(self, branch_name, create_branch=False):
        stdout, stderr, exitcode = self._run_cmd(['git', 'checkout', branch_name], handle_exitcode=False)

        if exitcode != 0:
            LOG.debug('Git is not able to checkout code: {0}'.format(exitcode))
            LOG.debug(stderr)
            if exitcode == 1:
                if create_branch:
                    LOG.debug(
                        "Could not checkout branch '{0}', creating the branch "
                        "locally with current HEAD".format(branch_name)
                    )
                    self._run_cmd(['git', 'checkout', '-b', branch_name])
                else:
                    return False
        return True

    def get_list_of_staged_files(self):
        stdout, stderr, exitcode = self._run_cmd(['git', 'diff', '--name-only', '--cached'])
        LOG.debug('git diff result: {0}'.format(stdout))
        return stdout

    def create_initial_commit(self):
        with open('README', 'w') as readme:
            readme.write('')
        self._run_cmd(['git', 'add', 'README'])
        stdout, stderr, exitcode = self._run_cmd(
            ['git', 'commit', '--allow-empty', '-m', 'EB CLI initial commit'],
            handle_exitcode=False
        )

        if exitcode != 0:
            LOG.debug('git was not able to initialize an empty commit: {0}'.format(stderr))

        LOG.debug('git commit result: {0}'.format(stdout))
        return stdout

    def fetch_remote_branches(self, remote_name):
        fetch_command = [
            'git',
            'fetch',
            remote_name
        ]
        LOG.debug('Fetching remote branches using remote name: {0}'.format(' '.join(fetch_command)))

        stdout, stderr, exitcode = self._run_cmd(fetch_command, handle_exitcode=False)

        if exitcode != 0:
            LOG.debug('git fetch error: ' + stderr)
            return False

        LOG.debug('git fetch result: {0}'.format(stdout))
        return True

    def setup_codecommit_cred_config(self):
        LOG.debug('Setup git config settings for code commit credentials')
        self._run_cmd(
            ['git', 'config', '--local', '--replace-all', 'credential.UseHttpPath', 'true'])

        self._run_cmd(
            ['git', 'config', '--local', '--replace-all', 'credential.helper', credential_helper_command()])

    def _run_cmd(self, cmd, handle_exitcode=True):
        stdout, stderr, exitcode = exec_cmd(cmd)

        stdout = utils.decode_bytes(stdout).strip()
        stderr = utils.decode_bytes(stderr).strip()

        if handle_exitcode:
            self._handle_exitcode(exitcode, stderr)
        return stdout, stderr, exitcode

    def verify_url_is_a_codecommit_url(self, remote_url):
        codecommit_url_regex = re.compile(r'.*git-codecommit\..*\.amazonaws.com.*')

        if not codecommit_url_regex.search(remote_url):
            # Prevent communications with non-CodeCommit repositories because of unknown security implications
            # Integration with non-CodeCommit repositories is not something Beanstalk presently supports
            raise NoSourceControlError('Could not connect to repository located at {}'.format(remote_url))


def credential_helper_command():
    return '!aws codecommit credential-helper $@'
