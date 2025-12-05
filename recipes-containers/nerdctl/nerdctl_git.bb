HOMEPAGE = "https://github.com/containerd/nerdctl"
SUMMARY =  "Docker-compatible CLI for containerd"
DESCRIPTION = "nerdctl: Docker-compatible CLI for containerd \
    "

DEPENDS = " \
    go-md2man \
    rsync-native \
    ${@bb.utils.filter('DISTRO_FEATURES', 'systemd', d)} \
"

SRCREV_FORMAT = "nerdcli"
SRCREV_nerdcli = "497c7cf74d09bf1ddf2678382360ca61e6faebac"

SRC_URI = "git://github.com/containerd/nerdctl.git;name=nerdcli;branch=main;protocol=https;destsuffix=${GO_SRCURI_DESTSUFFIX}"

include go-mod-git.inc
include go-mod-cache.inc

# patches
SRC_URI += " \
            file://0001-Makefile-allow-external-specification-of-build-setti.patch \
           "

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/import/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

GO_IMPORT = "import"

PV = "v2.0.3"

NERDCTL_PKG = "github.com/containerd/nerdctl"

# go-mod-discovery configuration
GO_MOD_DISCOVERY_BUILD_TARGET = "./cmd/nerdctl"
GO_MOD_DISCOVERY_GIT_REPO = "https://github.com/containerd/nerdctl.git"
GO_MOD_DISCOVERY_GIT_REF = "${SRCREV_nerdcli}"

inherit go goarch
inherit systemd pkgconfig
inherit go-mod-discovery

do_configure[noexec] = "1"

EXTRA_OEMAKE = " \
     PREFIX=${prefix} BINDIR=${bindir} LIBEXECDIR=${libexecdir} \
     ETCDIR=${sysconfdir} TMPFILESDIR=${nonarch_libdir}/tmpfiles.d \
     SYSTEMDDIR=${systemd_unitdir}/system USERSYSTEMDDIR=${systemd_unitdir}/user \
"

PACKAGECONFIG ?= ""

do_compile() {
        export GOPATH="${S}/src/import/.gopath:${S}/src/import/vendor:${STAGING_DIR_TARGET}/${prefix}/local/go"
        export GOMODCACHE="${S}/pkg/mod"
        export CGO_ENABLED="1"
        export GOSUMDB="off"
        export GOTOOLCHAIN="local"
        export GOPROXY="off"

        cd ${S}/src/import

        # Pass the needed cflags/ldflags so that cgo
        # can find the needed headers files and libraries
        export GOARCH=${TARGET_GOARCH}
        export CGO_CFLAGS="${CFLAGS} --sysroot=${STAGING_DIR_TARGET}"
        export CGO_LDFLAGS="${LDFLAGS} --sysroot=${STAGING_DIR_TARGET}"

        # -trimpath removes build paths from the binary (required for reproducible builds)
        oe_runmake GO=${GO} BUILDTAGS="${BUILDTAGS}" GO_BUILD_FLAGS="-trimpath" binaries
}

do_install() {
        install -d "${D}${BIN_PREFIX}${base_bindir}"
        install -m 755 "${S}/src/import/_output/nerdctl" "${D}${BIN_PREFIX}${base_bindir}"
}

INHIBIT_PACKAGE_STRIP = "1"
INSANE_SKIP:${PN} += "ldflags already-stripped"

