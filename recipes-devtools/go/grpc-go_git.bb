DESCRIPTION = "The Go language implementation of gRPC. HTTP/2 based RPC"
HOMEPAGE = "https://github.com/grpc/grpc-go"
SECTION = "devel/go"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${PKG_NAME}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

SRCNAME = "grpc-go"

PKG_NAME = "google.golang.org/grpc"
SRC_URI = "git://github.com/grpc/${SRCNAME}.git;destsuffix=${BB_GIT_DEFAULT_DESTSUFFIX}/src/${PKG_NAME};branch=v1.59.x;protocol=https"

SRCREV = "7765221f4bf6104973db7946d56936cf838cad46"
PV = "1.59.0+git"

# NO-OP the do compile rule because this recipe is source only.
do_compile() {
}

do_install() {
	install -d ${D}${prefix}/local/go/src/${PKG_NAME}
	for j in $(cd ${S} && find src/${PKG_NAME} -name "*.go"); do
	    if [ ! -d ${D}${prefix}/local/go/$(dirname $j) ]; then
	        mkdir -p ${D}${prefix}/local/go/$(dirname $j)
	    fi
	    cp $j ${D}${prefix}/local/go/$j
	done
	cp -r ${S}/src/${PKG_NAME}/LICENSE ${D}${prefix}/local/go/src/${PKG_NAME}/
}

SYSROOT_PREPROCESS_FUNCS += "go_grpc_sysroot_preprocess"

go_grpc_sysroot_preprocess () {
    install -d ${SYSROOT_DESTDIR}${prefix}/local/go/src/${PKG_NAME}
    cp -r ${D}${prefix}/local/go/src/${PKG_NAME} ${SYSROOT_DESTDIR}${prefix}/local/go/src/$(dirname ${PKG_NAME})
}

FILES:${PN} += " \
    ${prefix}/local/go/src/${PKG_NAME}/* \
"

# some CVEs are reported with "cpe:2.3:a:grpc:grpc:*:*:*:*:*:go:*:*"
# it's better to have false positives than false negatives
CVE_PRODUCT += "grpc"
# CVE-2024-7246 is an HTTP/2 HPACK poisoning issue in gRPC C-core
# (C/C++ implementation, meta-openembedded).
# grpc-go (Go implementation in meta-virtualization) does not
# contain the affected HPACK code path.
CVE_STATUS[CVE-2024-7246] = "not-applicable-config: CVE is for grpc (C-core), not grpc-go."
