DESCRIPTION = "OCI systemd hook enables users to run systemd in docker and OCI"
SECTION = "console/utils"
LICENSE = "GPLv3"
LIC_FILES_CHKSUM = "file://LICENSE;md5=d32239bcb673463ab874e80d47fae504"
PRIORITY = "optional"

DEPENDS = "yajl util-linux"

SRCREV = "05e692346ca73e022754332a7da641230dae2ffe"
SRC_URI = "git://github.com/projectatomic/oci-systemd-hook;branch=master;protocol=https \
           file://0001-selinux-drop-selinux-support.patch \
           file://0001-configure-drop-selinux-support.patch \
           file://0001-Add-additional-cgroup-mounts-from-root-NS-automatica.patch \
"

PV = "0.2.0+git${SRCPV}"
S = "${WORKDIR}/git"

inherit autotools pkgconfig

PACKAGECONFIG ??= ""
PACKAGECONFIG[selinux] = ",,libselinux"

EXTRA_OECONF += "--libexecdir=${libexecdir}/oci/hooks.d"

# nothing to compile, we do it all in the install task
do_compile[noexec] = "1"

do_install() {
    # Avoid building docs, and other artifacts by surgically calling the
    # semi-internal target of "install-exec-am"
    oe_runmake 'DESTDIR=${D}' install-exec-am
}

FILES_${PN} += "${libexecdir}/oci/hooks.d/"

