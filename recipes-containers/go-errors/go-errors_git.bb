DESCRIPTION = "Simple error handling primitives"
HOMEPAGE = "https://github.com/pkg/errors"
SECTION = "devel/go"
LICENSE = "BSD-2-Clause"
LIC_FILES_CHKSUM = "file://src/${PKG_NAME}/LICENSE;md5=6fe682a02df52c6653f33bd0f7126b5a"

SRCNAME = "errors"

PKG_NAME = "github.com/pkg/${SRCNAME}"
SRC_URI = "git://${PKG_NAME};destsuffix=${BB_GIT_DEFAULT_DESTSUFFIX}/src/${PKG_NAME};branch=master;protocol=https"

SRCREV = "5dd12d0cfe7f152f80558d591504ce685299311e"
PV = "v0.8.1+git"

# NO-OP the do compile rule because this recipe is source only.
do_compile() {
}

inherit meta-virt-depreciated-warning

do_install() {
	install -d ${D}${prefix}/local/go/src/${PKG_NAME}
	for j in $(cd ${S} && find src/${PKG_NAME} -name "*.go" -not -path "*/.tool/*"); do
	    if [ ! -d ${D}${prefix}/local/go/$(dirname $j) ]; then
	        mkdir -p ${D}${prefix}/local/go/$(dirname $j)
	    fi
	    cp $j ${D}${prefix}/local/go/$j
	done
	cp -r ${S}/src/${PKG_NAME}/LICENSE ${D}${prefix}/local/go/src/${PKG_NAME}/
}

SYSROOT_PREPROCESS_FUNCS += "go_errors_file_sysroot_preprocess"

go_errors_file_sysroot_preprocess () {
    install -d ${SYSROOT_DESTDIR}${prefix}/local/go/src/${PKG_NAME}
    cp -r ${D}${prefix}/local/go/src/${PKG_NAME} ${SYSROOT_DESTDIR}${prefix}/local/go/src/$(dirname ${PKG_NAME})
}

FILES:${PN} += "${prefix}/local/go/src/${PKG_NAME}/*"

CLEANBROKEN = "1"
