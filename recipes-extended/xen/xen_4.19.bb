# tag: RELEASE-4.19.0
SRCREV = "3f22c5d1317a2c3eea143dd3962c5863dfe3967a"

XEN_REL ?= "4.19.0"
XEN_BRANCH ?= "stable-4.19"

SRC_URI = " \
    git://xenbits.xen.org/xen.git;branch=${XEN_BRANCH} \
    file://0001-menuconfig-mconf-cfg-Allow-specification-of-ncurses-location.patch \
    "

LIC_FILES_CHKSUM ?= "file://COPYING;md5=d1a1e216f80b6d8da95fec897d0dbec9"

PV = "${XEN_REL}+stable"

DEFAULT_PREFERENCE ??= "-1"

require xen.inc
require xen-hypervisor.inc
