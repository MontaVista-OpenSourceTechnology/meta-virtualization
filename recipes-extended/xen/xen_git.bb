SRCREV ?= "ae992e68d3ed7a177adea8b9afa4ec88c27254f0"

XEN_REL ?= "4.21-dev"
XEN_BRANCH ?= "master"

SRC_URI = " \
    git://xenbits.xen.org/xen.git;branch=${XEN_BRANCH} \
    file://0001-menuconfig-mconf-cfg-Allow-specification-of-ncurses-location.patch \
    "

LIC_FILES_CHKSUM ?= "file://COPYING;md5=d1a1e216f80b6d8da95fec897d0dbec9"

PV = "${XEN_REL}+git"

DEFAULT_PREFERENCE ??= "-1"

require xen.inc
require xen-hypervisor.inc
