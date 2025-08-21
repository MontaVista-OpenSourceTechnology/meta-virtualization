include runc.inc

SRCREV = "81693c22ec27c3ee3aa890433e81cb0104ee8ff8"
SRC_URI = " \
    git://github.com/opencontainers/runc;branch=release-1.3;protocol=https;destsuffix=${GO_SRCURI_DESTSUFFIX} \
    file://0001-Makefile-respect-GOBUILDFLAGS-for-runc-and-remove-re.patch \
    "
RUNC_VERSION = "1.3.0"

# for compatibility with existing RDEPENDS that have existed since
# runc-docker and runc-opencontainers were separate
RPROVIDES:${PN} += "runc-docker"
RPROVIDES:${PN} += "runc-opencontainers"

CVE_PRODUCT = "runc"

LDFLAGS += "${@bb.utils.contains('DISTRO_FEATURES', 'ld-is-gold', ' -fuse-ld=bfd', '', d)}"
