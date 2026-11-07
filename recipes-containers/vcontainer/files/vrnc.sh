#!/bin/bash
# SPDX-FileCopyrightText: Copyright (C) 2026 Bruce Ashfield
#
# SPDX-License-Identifier: GPL-2.0-only
#
# vrnc: run an OCI runtime bundle with runc, in a QEMU guest of the target
# architecture.
#
# The guest is the one vdkr uses, so vrnc shares vdkr's blobs, configuration,
# state and memory resident daemon. Docker itself takes no part in the run.

# Set runtime-specific parameters before sourcing common code
VCONTAINER_RUNTIME_NAME="vrnc"
VCONTAINER_RUNTIME_CMD="docker"
VCONTAINER_RUNTIME_PREFIX="VDKR"
VCONTAINER_IMPORT_TARGET="docker-daemon:"
VCONTAINER_BUNDLE_RUNTIME="runc"
VCONTAINER_STATE_FILE="docker-state.img"
VCONTAINER_OTHER_PREFIX="VPDMN"
VCONTAINER_VERSION="1.0.0"

export VDKR_STATE_DIR="${VDKR_STATE_DIR:-$HOME/.vdkr}"
export VDKR_CONFIG_DIR="${VDKR_CONFIG_DIR:-$HOME/.config/vdkr}"

SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
if [ ! -f "${SCRIPT_DIR}/vcontainer-common.sh" ]; then
    echo "Error: vcontainer-common.sh not found" >&2
    exit 1
fi
export VCONTAINER_LIBDIR="${SCRIPT_DIR}"
source "${SCRIPT_DIR}/vcontainer-common.sh" "$@"
