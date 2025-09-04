HOMEPAGE = "https://github.com/cri-o/cri-o"
SUMMARY = "Open Container Initiative-based implementation of Kubernetes Container Runtime Interface"
DESCRIPTION = "cri-o is meant to provide an integration path between OCI conformant \
runtimes and the kubelet. Specifically, it implements the Kubelet Container Runtime \
Interface (CRI) using OCI conformant runtimes. The scope of cri-o is tied to the scope of the CRI. \
. \
At a high level, we expect the scope of cri-o to be restricted to the following functionalities: \
. \
 - Support multiple image formats including the existing Docker image format \
 - Support for multiple means to download images including trust & image verification \
 - Container image management (managing image layers, overlay filesystems, etc) \
 - Container process lifecycle management \
 - Monitoring and logging required to satisfy the CRI \
 - Resource isolation as required by the CRI \
 "

SRCREV_cri-o = "259e23fd4353e67b59b33a0457202210f40322ec"
SRC_URI = "\
	git://github.com/cri-o/cri-o.git;branch=release-1.34;name=cri-o;protocol=https;destsuffix=${GO_SRCURI_DESTSUFFIX} \
        file://crio.conf \
        file://run-ptest \
	"

# Apache-2.0 for docker
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/import/LICENSE;md5=e3fc50a88d0a364313df4b21ef20c29e"

GO_IMPORT = "import"

PV = "1.33.0+git${SRCREV_cri-o}"

inherit features_check ptest
REQUIRED_DISTRO_FEATURES ?= "seccomp"

DEPENDS = " \
    glib-2.0 \
    btrfs-tools \
    gpgme \
    ostree \
    libdevmapper \
    libseccomp \
    "
RDEPENDS:${PN} = " \
    cni \
    libdevmapper \
    "

PACKAGECONFIG ?= "${@bb.utils.filter('DISTRO_FEATURES', 'selinux', d)}"
PACKAGECONFIG[selinux] = ",,libselinux"

PACKAGES =+ "${PN}-config"

RDEPENDS:${PN} += " ${VIRTUAL-RUNTIME_container_runtime}"
RDEPENDS:${PN} += " e2fsprogs-mke2fs conmon util-linux iptables conntrack-tools"

inherit systemd
inherit go
inherit goarch
inherit pkgconfig
inherit container-host

EXTRA_OEMAKE = "BUILDTAGS='' DEBUG=1 STRIP=true"
# avoid textrel QA issue
EXTRA_OEMAKE += "GO_BUILD='${GO} build -trimpath -buildmode=pie'"
EXTRA_OEMAKE += "GO_TEST='${GO} test -trimpath -buildmode=pie'"

do_compile() {
	set +e

	cd ${S}/src/import

	oe_runmake local-cross
	oe_runmake binaries
}

do_compile_ptest() {
    set +e

    cd ${S}/src/import

    oe_runmake test-binaries
}
SYSTEMD_PACKAGES = "${@bb.utils.contains('DISTRO_FEATURES','systemd','${PN}','',d)}"
SYSTEMD_SERVICE:${PN} = "${@bb.utils.contains('DISTRO_FEATURES','systemd','crio.service','',d)}"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

do_install() {
    set +e
    localbindir="/usr/local/bin"

    install -d ${D}${localbindir}
    install -d ${D}/${libexecdir}/crio
    install -d ${D}/${sysconfdir}/crio
    install -d ${D}${systemd_unitdir}/system/
    install -d ${D}/usr/share/containers/oci/hooks.d

    install ${UNPACKDIR}/crio.conf ${D}/${sysconfdir}/crio/crio.conf

    # sample config files, they'll go in the ${PN}-config below
    install -d ${D}/${sysconfdir}/crio/config/
    install -m 755 -D ${S}/src/import/test/testdata/* ${D}/${sysconfdir}/crio/config/

    install ${S}/src/import/bin/crio.cross.linux* ${D}/${localbindir}/crio
    install ${S}/src/import/bin/crio-status ${D}/${localbindir}/
    install ${S}/src/import/bin/pinns ${D}/${localbindir}/

    install -m 0644 ${S}/src/import/contrib/systemd/crio.service  ${D}${systemd_unitdir}/system/
    install -m 0644 ${S}/src/import/contrib/systemd/crio-shutdown.service  ${D}${systemd_unitdir}/system/
    install -m 0644 ${S}/src/import/contrib/systemd/crio-wipe.service  ${D}${systemd_unitdir}/system/

    install -d ${D}${localstatedir}/lib/crio
}

do_install_ptest() {
    install -d ${D}${PTEST_PATH}/test
    install -d ${D}${PTEST_PATH}/bin
    cp -rf ${S}/src/import/test ${D}${PTEST_PATH}
    cp -rf ${S}/src/import/bin ${D}${PTEST_PATH}
    # CRI-O testing changed the default container runtime from runc to crun in version 1.31+.
    # To maintain compatibility with older tests expecting runc, and to allow for other custom runtimes,
    # this section explicitly sets CONTAINER_DEFAULT_RUNTIME in the run-ptest script.
    # The value is determined by the VIRTUAL-RUNTIME_container_runtime variable.
    if [ "${VIRTUAL-RUNTIME_container_runtime}" = "virtual-runc" ]; then
        sed -i '/^.\/test\/test_runner/iexport CONTAINER_DEFAULT_RUNTIME=runc' ${D}${PTEST_PATH}/run-ptest
    else
        sed -i '/^.\/test\/test_runner/iexport CONTAINER_DEFAULT_RUNTIME=${VIRTUAL-RUNTIME_container_runtime}' ${D}${PTEST_PATH}/run-ptest
    fi

}

FILES:${PN}-config = "${sysconfdir}/crio/config/*"
FILES:${PN} += "${systemd_unitdir}/system/*"
FILES:${PN} += "/usr/local/bin/*"
FILES:${PN} += "/usr/share/containers/oci/hooks.d"

INSANE_SKIP:${PN}-ptest += "ldflags"

RDEPENDS:${PN}-ptest += " \
    bash \
    bats \
    cni \
    crictl \
    coreutils \
    dbus-daemon-proxy \
    iproute2 \
    util-linux-unshare \
    jq \
    slirp4netns \
    parallel \
    podman \
"

COMPATIBLE_HOST = "^(?!(qemu)?mips).*"
