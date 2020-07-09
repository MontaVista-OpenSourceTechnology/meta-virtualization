SRCREV ?= "b66ce5058ec9ce84418cedd39b2bf07b7c5a1f65"

XEN_REL ?= "4.13"
XEN_BRANCH ?= "stable-${XEN_REL}"

SRC_URI = " \
    git://xenbits.xen.org/xen.git;branch=${XEN_BRANCH} \
    file://0001-python-pygrub-pass-DISTUTILS-xen.4.12.patch \
    "

LIC_FILES_CHKSUM ?= "file://COPYING;md5=4295d895d4b5ce9d070263d52f030e49"

PV = "${XEN_REL}+git${SRCPV}"

S = "${WORKDIR}/git"

require xen.inc
require xen-tools.inc
