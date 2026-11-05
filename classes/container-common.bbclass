# SPDX-FileCopyrightText: Copyright (C) 2025 Bruce Ashfield
#
# SPDX-License-Identifier: MIT
#
# container-common.bbclass
# ===========================================================================
# Shared functions for container bundling and cross-installation
# ===========================================================================
#
# This class provides common helper functions used by both:
#   - container-bundle.bbclass
#   - container-cross-install.bbclass
#
# These functions map target architecture to multiconfig names, machine names,
# and blob directory names used by vdkr/vpdmn.

# Determine multiconfig name for blob building based on target architecture
# Returns the multiconfig name (e.g., 'vruntime-aarch64' or 'vruntime-x86-64')
def get_vruntime_multiconfig(d):
    arch = d.getVar('TARGET_ARCH')
    if arch == 'aarch64':
        return 'vruntime-aarch64'
    elif arch in ['x86_64', 'i686', 'i586']:
        return 'vruntime-x86-64'
    else:
        return None

# Get the MACHINE name used in the multiconfig (for deploy path)
# Returns the machine name (e.g., 'qemuarm64' or 'qemux86-64')
def get_vruntime_machine(d):
    arch = d.getVar('TARGET_ARCH')
    if arch == 'aarch64':
        return 'qemuarm64'
    elif arch in ['x86_64', 'i686', 'i586']:
        return 'qemux86-64'
    else:
        return None

# Map TARGET_ARCH to blob directory name (aarch64, x86_64)
# The blob directories contain pre-built kernel and initramfs for vdkr/vpdmn
def get_blob_arch(d):
    """Map Yocto TARGET_ARCH to blob directory name"""
    arch = d.getVar('TARGET_ARCH')
    blob_map = {
        'aarch64': 'aarch64',
        'arm': 'aarch64',  # Use aarch64 blobs for 32-bit ARM too
        'x86_64': 'x86_64',
        'i686': 'x86_64',
        'i586': 'x86_64',
    }
    return blob_map.get(arch, 'aarch64')

# The runtimes that run OCI runtime bundles rather than importing an OCI image
OCI_BUNDLE_RUNTIMES ?= "crun runc"
OCI_BUNDLE_RUNTIMES_PATTERN = "${@'|'.join(d.getVar('OCI_BUNDLE_RUNTIMES').split())}"

# Whether a runtime is one of OCI_BUNDLE_RUNTIMES
# Args: runtime
is_bundle_runtime() {
    case "$1" in
        ${OCI_BUNDLE_RUNTIMES_PATTERN})
            return 0
            ;;
    esac
    return 1
}
