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
"""

Asciimatics is a package to help people create full-screen text UIs (from interactive forms to
ASCII animations) on any platform.  It is licensed under the Apache Software Foundation License 2.0.
"""
__author__ = 'Peter Brittain'

try:
    from .version import version
except ImportError:
    # Someone is running straight from the GIT repo - dummy out the version
    version = "0.0.0"

__version__ = version
