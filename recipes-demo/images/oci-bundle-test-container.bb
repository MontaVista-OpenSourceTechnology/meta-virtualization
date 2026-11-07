SUMMARY = "OCI runtime bundle test container"
DESCRIPTION = "A container for testing OCI runtime bundles. It reports what \
it was started with, for tests/test_oci_bundle.py to compare with the settings \
below, and exits with a known code."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COREBASE}/meta/COPYING.MIT;md5=3da9cfbcb788c80a0384361b4de20420"

require recipes-extended/images/container-base.bb

# Adds a layer after the image is built, with directories that belong to a
# non-root user, which the bundle must have too. The process stays root.
inherit container-nonroot-user
NONROOT_OWNED_DIRS = "/var/lib/bundle-test"
OCI_IMAGE_RUNTIME_UID = ""

OCI_IMAGE_OUTPUT_MODE = "image bundle"

OCI_IMAGE_ENTRYPOINT = "/usr/bin/bundle-check"
OCI_IMAGE_CMD = "from-cmd"
OCI_IMAGE_ENV_VARS = "BUNDLE_TEST=from-env"
OCI_IMAGE_WORKINGDIR = "/tmp"

OCI_RUNTIME_HOSTNAME = "bundle-test"
OCI_RUNTIME_CAPABILITIES = "CAP_KILL"
OCI_RUNTIME_RLIMITS = "RLIMIT_NOFILE:64:64"
OCI_RUNTIME_READONLY_ROOTFS = "1"
OCI_RUNTIME_MOUNTS += "/mnt/bundle-test:tmpfs:tmpfs:size=1m"
OCI_RUNTIME_DEVICES = "/dev/net/tun:c:10:200:0660:0:5"

oci_bundle_test_script() {
    install -d ${IMAGE_ROOTFS}/usr/bin
    cat > ${IMAGE_ROOTFS}/usr/bin/bundle-check <<'EOF_CHECK'
#!/bin/sh
echo "args=$1"
echo "env=$BUNDLE_TEST"
echo "cwd=$(pwd)"
echo "uid=$(id -u)"
echo "host=$(hostname)"
echo "capeff=$(grep CapEff /proc/self/status | cut -f2)"
echo "nofile=$(ulimit -n)"
echo "uidmap=$(tr -s ' ' < /proc/self/uid_map)"
touch /bundle-test 2>/dev/null && echo "rootfs=writable" || echo "rootfs=readonly"
grep -q ' /mnt/bundle-test ' /proc/self/mounts && echo "mount=yes" || echo "mount=no"
[ -c /dev/net/tun ] && echo "device=yes" || echo "device=no"
[ -c /dev/null ] && echo "devnull=yes" || echo "devnull=no"
exit 7
EOF_CHECK
    chmod 0755 ${IMAGE_ROOTFS}/usr/bin/bundle-check
}
ROOTFS_POSTPROCESS_COMMAND += "oci_bundle_test_script"
