#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Bruce Ashfield
#
# SPDX-License-Identifier: MIT
#
# Tar up config.json and rootfs/ from a bundle unpacked with umoci --rootless.
#
#   oci-bundle-archive.py <bundle directory> <output tarball>
#
# An unprivileged unpack can't chown, so every file on disk belongs to the build
# user and umoci records non-root ownership in the user.rootlesscontainers xattr.
# Run it with pseudo disabled (PSEUDO_DISABLED=1), as pseudo hides that xattr.

import os
import stat
import sys
import tarfile

UNSET = 0xffffffff

def owner(path):
    uid = gid = 0
    try:
        data = os.getxattr(path, 'user.rootlesscontainers', follow_symlinks=False)
    except OSError:
        return uid, gid
    # protobuf message: field 1 is the uid, field 2 is the gid, both varints
    i = 0
    while i < len(data):
        field = data[i] >> 3
        i += 1
        value = shift = 0
        while True:
            byte = data[i]
            i += 1
            value |= (byte & 0x7f) << shift
            shift += 7
            if not byte & 0x80:
                break
        if value != UNSET:
            if field == 1:
                uid = value
            elif field == 2:
                gid = value
    return uid, gid

bundle, output = sys.argv[1:3]

with tarfile.open(output, 'w', format=tarfile.PAX_FORMAT) as tar:
    def add(path, arcname):
        info = tar.gettarinfo(path, arcname=arcname)
        info.uid, info.gid = owner(path)
        info.uname = info.gname = ''
        # Modes such as 0000 are valid in an image but stop us reading the tree.
        # Directories stay accessible so the unpacked bundle can be removed.
        if info.isreg():
            os.chmod(path, info.mode | stat.S_IRUSR)
            with open(path, 'rb') as f:
                tar.addfile(info, f)
            os.chmod(path, info.mode)
        else:
            if info.isdir():
                os.chmod(path, info.mode | stat.S_IRWXU)
            tar.addfile(info)

    add(os.path.join(bundle, 'config.json'), 'config.json')
    rootfs = os.path.join(bundle, 'rootfs')
    add(rootfs, 'rootfs')
    for dirpath, dirnames, filenames in os.walk(rootfs):
        dirnames.sort()
        for name in sorted(dirnames + filenames):
            path = os.path.join(dirpath, name)
            add(path, os.path.join('rootfs', os.path.relpath(path, rootfs)))
