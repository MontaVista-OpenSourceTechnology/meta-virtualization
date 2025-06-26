SUMMARY = "Native Linux KVM tool"
DESCRIPTION = "kvmtool is a lightweight tool for hosting KVM guests."

LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=fcb02dc552a041dee27e4b85c7396067"

DEPENDS = "dtc libaio zlib"
do_configure[depends] += "virtual/kernel:do_shared_workdir"

inherit kernel-arch

SRC_URI = "git://git.kernel.org/pub/scm/linux/kernel/git/will/kvmtool.git;branch=master \
           file://external-crosscompiler.patch \
           file://0001-kvmtool-9p-fixed-compilation-error.patch \
           file://0002-kvmtool-add-EXTRA_CFLAGS-variable.patch \
           file://0003-kvmtool-Werror-disabled.patch \
           "

SRCREV = "e48563f5c4a48fe6a6bc2a98a9a7c84a10f043be"
PV = "5.10.0+git"

EXTRA_OEMAKE = 'V=1 EXTRA_CFLAGS="-I${STAGING_KERNEL_BUILDDIR}/include/generated -I${STAGING_KERNEL_BUILDDIR}/arch/${ARCH}/include/generated"'

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${S}/lkvm ${D}${bindir}/
}
