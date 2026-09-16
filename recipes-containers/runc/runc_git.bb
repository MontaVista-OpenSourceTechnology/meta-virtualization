include runc.inc

SRCREV = "a60612054a79ced633593ded0fb29ec47d7e93fa"
SRC_URI = " \
    git://github.com/opencontainers/runc;branch=release-1.5;protocol=https;destsuffix=${GO_SRCURI_DESTSUFFIX} \
    file://0001-Makefile-respect-GOBUILDFLAGS-for-runc-and-remove-re.patch \
    "
RUNC_VERSION = "1.5.1"

# for compatibility with existing RDEPENDS that have existed since
# runc-docker and runc-opencontainers were separate
RPROVIDES:${PN} += "runc-docker"
RPROVIDES:${PN} += "runc-opencontainers"

CVE_PRODUCT = "linuxfoundation:runc"

LDFLAGS += "${@bb.utils.contains('DISTRO_FEATURES', 'ld-is-gold', ' -fuse-ld=bfd', '', d)}"
