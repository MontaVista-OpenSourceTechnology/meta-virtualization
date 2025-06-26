# master status March 2025
SRCREV ?= "de0254b90922a8644bb2c4c1593786d45c80ea22"

XEN_REL ?= "4.21-dev"
XEN_BRANCH ?= "master"

SRC_URI = " \
    git://xenbits.xen.org/xen.git;branch=${XEN_BRANCH} \
    file://0001-python-pygrub-pass-DISTUTILS-xen-4.20.patch \
    "

LIC_FILES_CHKSUM ?= "file://COPYING;md5=d1a1e216f80b6d8da95fec897d0dbec9"

PV = "${XEN_REL}+git"

DEFAULT_PREFERENCE ??= "-1"

require xen.inc
require xen-tools.inc
