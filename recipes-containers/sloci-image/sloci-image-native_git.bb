SUMMARY = "A simple CLI tool for packing rootfs into a single-layer OCI image"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://git/LICENSE;md5=948cd8e59069fad992b0469af9ad7966"
SRC_URI = "git://github.com/jirutka/sloci-image.git;branch=master;protocol=https"

DEPENDS = ""

SRCREV = "4015e49763e5a738026a5bbfcf32b38b5a4fa650"
PV = "v0.1.0+git${SRCPV}"

inherit native

S = "${WORKDIR}"

do_compile() { 
	:
}

do_install() {
	cd ${S}/git
        make PREFIX="${exec_prefix}" DESTDIR=${D} install
}
