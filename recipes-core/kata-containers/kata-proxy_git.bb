DESCRIPTION = " Kata Containers stdio proxy component"
HOMEPAGE = "https://github.com/kata-containers/proxy"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/github.com/kata-containers/proxy/LICENSE;md5=86d3f3a95c324c9479bd8986968f4327"

GO_IMPORT = "github.com/kata-containers/proxy"
SRCREV = "1148847739f9a9f47b92e34e4f309dc109d4dba9"
SRC_URI = "git://${GO_IMPORT}.git;branch=master \
          "

RDEPENDS_${PN}-dev_append = "bash"

S = "${WORKDIR}/git"

inherit go

do_compile() {
	# Pass the needed cflags/ldflags so that cgo
	# can find the needed headers files and libraries
	export GOARCH=${TARGET_GOARCH}
	export CGO_ENABLED="1"
	export CGO_CFLAGS="${CFLAGS} --sysroot=${STAGING_DIR_TARGET}"
	export CGO_LDFLAGS="${LDFLAGS} --sysroot=${STAGING_DIR_TARGET}"

	cd ${S}/src/${GO_IMPORT}
	oe_runmake kata-proxy
}

do_install() {
	mkdir -p ${D}/${libexecdir}/kata-containers
	cp ${WORKDIR}/git/src/${GO_IMPORT}/kata-proxy ${D}/${libexecdir}/kata-containers
}

deltask compile_ptest_base
