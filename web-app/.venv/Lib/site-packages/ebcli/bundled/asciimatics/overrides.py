# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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

# Copyright 2016 Peter Brittain
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import threading
import sys

from ebcli.bundled.asciimatics.screen import Screen

if not sys.platform.startswith('win32'):
    import curses


logger = logging.getLogger(__name__)
original_refresh_method = Screen.refresh


class ScreenPatch(object):
    """
    Class acts as a proxy for asciimatics.screen.Screen to help override methods defined within it
    for the fastest rendering experience possible
    """
    class refresh_lock(object):
        _LOCK = threading.Lock()

        def __enter__(self):
            self._LOCK.acquire()

        def __exit__(self, a, b, c):
            self._LOCK.release()

    def refresh(self):
        with ScreenPatch.refresh_lock():
            original_refresh_method(self)


def apply():
    if not sys.platform.startswith('win32'):
        def noop(_):
            pass
        curses.mousemask = noop

    Screen.refresh = ScreenPatch.refresh
