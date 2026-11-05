#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Bruce Ashfield
#
# SPDX-License-Identifier: MIT
#
# Give a runtime bundle a cgroupsPath, unless it already has one.
#
#   oci-bundle-cgroups-path.py <config.json> <cgroupsPath>
#
# If the bundle has its own cgroupsPath, leave it and print it.

import json
import sys

path, cgroup = sys.argv[1:3]

with open(path) as f:
    config = json.load(f)

linux = config.setdefault('linux', {})
if 'cgroupsPath' in linux:
    print(linux['cgroupsPath'])
    sys.exit(0)

linux['cgroupsPath'] = cgroup
with open(path, 'w') as f:
    json.dump(config, f, indent=2)
