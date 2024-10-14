#-----------------------------------------------------------------------------
# Copyright (c) 2023, PyInstaller Development Team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#
# SPDX-License-Identifier: Apache-2.0
#-----------------------------------------------------------------------------

# `tensorflow` versions prior to 2.3.0 attempt to use `site.USER_SITE` in path/string manipulation functions.
# As frozen application runs with disabled `site`, the value of this variable is `None`, and causes path/string
# manipulation functions to raise an error. As a work-around, we set `site.USER_SITE` to an empty string, which is
# also what the fake `site` module available in PyInstaller prior to v5.5 did.
import site

if site.USER_SITE is None:
    site.USER_SITE = ''
