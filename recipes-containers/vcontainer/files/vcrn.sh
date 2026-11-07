#!/bin/bash
# SPDX-FileCopyrightText: Copyright (C) 2026 Bruce Ashfield
#
# SPDX-License-Identifier: GPL-2.0-only
#
# vcrn: run an OCI runtime bundle with crun, in a QEMU guest of the target
# architecture.
#
# The guest is the one vpdmn uses, so vcrn shares vpdmn's blobs, configuration,
# state and memory resident daemon. Podman itself takes no part in the run.

# Set runtime-specific parameters before sourcing common code
VCONTAINER_RUNTIME_NAME="vcrn"
VCONTAINER_RUNTIME_CMD="podman"
VCONTAINER_RUNTIME_PREFIX="VPDMN"
VCONTAINER_IMPORT_TARGET="containers-storage:"
VCONTAINER_BUNDLE_RUNTIME="crun"
VCONTAINER_STATE_FILE="podman-state.img"
VCONTAINER_OTHER_PREFIX="VDKR"
VCONTAINER_VERSION="1.0.0"

export VPDMN_STATE_DIR="${VPDMN_STATE_DIR:-$HOME/.vpdmn}"
export VPDMN_CONFIG_DIR="${VPDMN_CONFIG_DIR:-$HOME/.config/vpdmn}"

SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
if [ ! -f "${SCRIPT_DIR}/vcontainer-common.sh" ]; then
    echo "Error: vcontainer-common.sh not found" >&2
    exit 1
fi
export VCONTAINER_LIBDIR="${SCRIPT_DIR}"
source "${SCRIPT_DIR}/vcontainer-common.sh" "$@"
