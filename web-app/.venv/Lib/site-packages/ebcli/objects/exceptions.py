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

import sys


class EBCLIException(Exception):
    """ Base exception for all EB-CLI exceptions """

    ''' Python 3 removes the .message property
        This causes some weird unicode issues.
        A message for a python 2 exception could be in unicode.
        Using str(e) and comparing results is problematic with unicode in
        python 2. However using the .message works just fine. So we add the
        .message back into 3 to solve compatibility problems'''
    if sys.version_info[0] >= 3:
        @property
        def message(self):
            return str(self)


class NotFoundError(EBCLIException):
    pass


class CommandError(EBCLIException):
    """ Error occurred executing some non eb cli command """
    def __init__(self, message=None, output=None, code=None):
        super(CommandError, self).__init__(message)
        self.output = output
        self.code = code


class GitRemoteNotSetupError(EBCLIException):
    pass


class ServiceError(EBCLIException):
    """  Error occurred calling the api    """
    def __init__(self, message=None, code=None):
        self.code = code
        super(ServiceError, self).__init__(message)


class CredentialsError(EBCLIException):
    """  Error occurred with credentials   """
    pass


class NotAuthorizedError(EBCLIException):
    pass


class NotAuthorizedInRegionError(EBCLIException):
    pass


class InvalidPlatformVersionError(EBCLIException):
    """
    The provided version does not match '\d+\.\d+\.\d+'
    """
    pass


class PlatformWorkspaceEmptyError(EBCLIException):
    """
    The customer attempted to create a Platform version but the workspace is empty.
    """
    pass


class PlatformWorkspaceNotSupportedError(EBCLIException):
    """
    The EB directory has been initialized as a Platform workspace. This command does
    not support Platform workspaces.
    """
    pass


class ApplicationWorkspaceNotSupportedError(EBCLIException):
    """
    The EB directory has been initialized as an Application workspace. This command does
    not support Application workspaces.
    """
    pass


class AlreadyInitializedAsPlatformWorkspaceError(EBCLIException):
    """
    The EB directory has already been initialized as a Platform workspace, and the
    customer is now trying to reinitialize it as an Application workspace.
    """
    pass


class AlreadyInitializedAsApplicationWorkspaceError(EBCLIException):
    """
    The EB directory has already been initialized as a Application workspace, and the
    customer is now trying to reinitialize it as an Platform workspace.
    """
    pass


class NotInitializedError(EBCLIException):
    """  The eb directory can not be found.  """
    pass


class NoSourceControlError(EBCLIException):
    """  Error occured because a source control system
    can not be found in the current directory
     """
    pass


class NoEnvironmentForBranchError(EBCLIException):
    """ No provided environment for the given Branch   """
    pass


class NoRegionError(EBCLIException):
    """  No region provided or found   """
    pass


class ConnectionError(OSError):
    """ Region provided cannot be resolved    """
    pass


class TimeoutError(EBCLIException):
    """ Operation timed out   """
    pass


class InvalidStateError(EBCLIException):
    """ Environment is in an updating state    """
    pass


class AlreadyExistsError(EBCLIException):
    """ The object already exists and can not be created  """
    pass


class InvalidSyntaxError(EBCLIException):
    """ The file syntax is invalid  """
    pass


class InvalidOptionsError(EBCLIException):
    """ Options given through command line are invalid  """
    pass


class NoKeypairError(EBCLIException):
    """ Instance/environment has no associated keypair    """
    pass


class NotSupportedError(EBCLIException):
    """  Operation not supported   """
    pass


class InvalidProfileError(EBCLIException):
    """ Given profile is invalid  """
    pass


class ValidationError(EBCLIException):
    pass


class FileTooLargeError(EBCLIException):
    pass


class UploadError(EBCLIException):
    """ An error occured while uploading app version
    """


class WorkerQueueNotFound(EBCLIException):
    """ A worker queue could not be found for a worker environment """


class DockerVersionError(Exception):
    pass


class RetiredPlatformBranchError(EBCLIException):
    pass


class EndOfTestError(EOFError):
    """
    Class defines exception to raise in tests to allow exiting from the infinite `while` loop.
    Must not be raised in source code.
    """
    pass
