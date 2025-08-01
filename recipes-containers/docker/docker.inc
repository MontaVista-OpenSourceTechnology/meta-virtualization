DEPENDS = " \
    btrfs-tools \
    sqlite3 \
    libtool-native \
    libtool \
    "

DEPENDS:append:class-target = " lvm2"
RDEPENDS:${PN} = "util-linux util-linux-unshare iptables \
                  ${@bb.utils.contains('DISTRO_FEATURES', 'aufs', 'aufs-util', '', d)} \
                  ${@bb.utils.contains('DISTRO_FEATURES', 'systemd', '', 'cgroup-lite', d)} \
                  bridge-utils \
                  ca-certificates \
                 "
RDEPENDS:${PN} += "virtual-containerd ${VIRTUAL-RUNTIME_container_runtime}"

RRECOMMENDS:${PN} = "kernel-module-dm-thin-pool \
                     kernel-module-nf-conntrack \
                     kernel-module-nf-conntrack-netlink \
                     kernel-module-nf-nat \
                     kernel-module-nfnetlink \
                     kernel-module-overlay \
                     kernel-module-veth \
                     kernel-module-x-tables \
                     kernel-module-xt-addrtype \
                     kernel-module-xt-conntrack \
                     kernel-module-xt-masquerade \
                    "

PROVIDES += "virtual/docker"

# we want all the docker variant recpes to be installable via "docker"
PACKAGE_NAME = "docker"
RPROVIDES:${PN} += "docker"
RPROVIDES:${PN}-dbg += "docker-dbg"
RPROVIDES:${PN}-dev += "docker-dev"
RPROVIDES:${PN}-contrip += "docker-dev"

inherit pkgconfig
PACKAGECONFIG ??= "docker-init seccomp"
PACKAGECONFIG[seccomp] = "seccomp,,libseccomp"
PACKAGECONFIG[docker-init] = ",,,docker-init"
PACKAGECONFIG[transient-config] = "transient-config"

GO_IMPORT = "import"

inherit systemd update-rc.d
inherit go
inherit goarch
inherit pkgconfig

REQUIRED_DISTRO_FEATURES ?= "seccomp ipv6"
inherit features_check

do_configure[noexec] = "1"

# Export for possible use in Makefiles, default value comes from go.bbclass
export GO_LINKSHARED

DOCKER_PKG = "github.com/docker/docker"
# in order to exclude devicemapper and btrfs - https://github.com/docker/docker/issues/14056
BUILD_TAGS ?= "exclude_graphdriver_btrfs exclude_graphdriver_devicemapper"

do_compile() {
	# Set GOPATH. See 'PACKAGERS.md'. Don't rely on
	# docker to download its dependencies but rather
	# use dependencies packaged independently.
	cd ${S}/src/import
	rm -rf .gopath
	mkdir -p .gopath/src/"$(dirname "${DOCKER_PKG}")"
	ln -sf ../../../.. .gopath/src/"${DOCKER_PKG}"
	
	mkdir -p .gopath/src/github.com/docker
	ln -sf ${S}/cli .gopath/src/github.com/docker/cli

	export GOPATH="${S}/src/import/.gopath:${S}/src/import/vendor"
	export GOROOT="${STAGING_DIR_NATIVE}/${nonarch_libdir}/${HOST_SYS}/go"

	# Pass the needed cflags/ldflags so that cgo
	# can find the needed headers files and libraries
	export GOARCH=${TARGET_GOARCH}
	export CGO_ENABLED="1"
	export CGO_CFLAGS="${CFLAGS} --sysroot=${STAGING_DIR_TARGET}"
	export CGO_LDFLAGS="${LDFLAGS} --sysroot=${STAGING_DIR_TARGET}"
	export DOCKER_BUILDTAGS='${BUILD_TAGS} ${PACKAGECONFIG_CONFARGS}'
	export GO111MODULE=off

	export DISABLE_WARN_OUTSIDE_CONTAINER=1

	cd ${S}/src/import/

	# this is the unsupported built structure
	# that doesn't rely on an existing docker
	# to build this:
	VERSION="${DOCKER_VERSION}" DOCKER_GITCOMMIT="${DOCKER_COMMIT}" ./hack/make.sh dynbinary

        # build the cli
	cd ${S}/src/import/.gopath/src/github.com/docker/cli
	export CFLAGS=""
	export LDFLAGS=""
	export DOCKER_VERSION=${DOCKER_VERSION}
	VERSION="${DOCKER_VERSION}" DOCKER_GITCOMMIT="${DOCKER_COMMIT}" make dynbinary
}

do_install() {
	mkdir -p ${D}/${bindir}
	cp ${S}/cli/build/docker ${D}/${bindir}/docker
	cp ${S}/src/import/bundles/dynbinary-daemon/dockerd ${D}/${bindir}/dockerd
	cp ${S}/src/import/bundles/dynbinary-daemon/docker-proxy ${D}/${bindir}/docker-proxy

	if ${@bb.utils.contains('DISTRO_FEATURES','systemd','true','false',d)}; then
		install -d ${D}${systemd_unitdir}/system
		install -m 644 ${S}/src/import/contrib/init/systemd/docker.* ${D}/${systemd_unitdir}/system
		# replaces one copied from above with one that uses the local registry for a mirror
		install -m 644 ${S}/src/import/contrib/init/systemd/docker.service ${D}/${systemd_unitdir}/system
		rm -f ${D}/${systemd_unitdir}/system/docker.service.rpm
	else
		install -d ${D}${sysconfdir}/init.d
		install -m 0755 ${UNPACKDIR}/docker.init ${D}${sysconfdir}/init.d/docker.init
	fi
	# TLS key that docker creates at run-time if not found is what resides here
	if ${@bb.utils.contains('PACKAGECONFIG','transient-config','true','false',d)}; then
		install -d ${D}${sysconfdir}
		ln -s ..${localstatedir}/run/docker ${D}${sysconfdir}/docker
	else
		install -d ${D}${sysconfdir}/docker
	fi

	mkdir -p ${D}${datadir}/docker/
	install -m 0755 ${S}/src/import/contrib/check-config.sh ${D}${datadir}/docker/
}


SYSTEMD_PACKAGES = "${@bb.utils.contains('DISTRO_FEATURES','systemd','${PN}','',d)}"
SYSTEMD_SERVICE:${PN} = "${@bb.utils.contains('DISTRO_FEATURES','systemd','docker.service docker.socket','',d)}"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

# inverted logic warning. We ony want the sysvinit init to be installed if systemd
# is NOT in the distro features
INITSCRIPT_PACKAGES += "${@bb.utils.contains('DISTRO_FEATURES','systemd','', '${PN}',d)}"
INITSCRIPT_NAME:${PN} = "${@bb.utils.contains('DISTRO_FEATURES','systemd','', 'docker.init',d)}"
INITSCRIPT_PARAMS:${PN} = "defaults"

inherit useradd
USERADD_PACKAGES = "${PN}"
GROUPADD_PARAM:${PN} = "-r docker"

COMPATIBLE_HOST = "^(?!(qemu)?mips).*"

INSANE_SKIP:${PN} += "ldflags textrel"

FILES:${PN} += "${systemd_unitdir}/system/* ${sysconfdir}/docker"

PACKAGES =+ "${PN}-contrib"
FILES:${PN}-contrib += "${datadir}/docker/check-config.sh"
RDEPENDS:${PN}-contrib += "bash"

# By the docker-packaging repository and https://docs.docker.com/engine/install/centos/#installation-methods
# docker is packaged by most distros with a split between the engine and the CLI.
#
# We do the same here, by introducing the -cli package
#
# But to keep existing use cases working, we also create a RDEPENDS between the main
# docker package (the engine) and the cli, so existing "docker" package installs will
# continue to work the same way. To have separate and non-redepending packages created
# set the DOCKER_UNIFIED_PACKAGE variable to False
#
PACKAGES =+ "${PN}-cli"
FILES:${PN}-cli += "${bindir}/docker"

# set to "False" if packages should be generated for the cli and engine, and
# NOT rdepend to get a classic one-package install
DOCKER_UNIFIED_PACKAGE ?= "True"
RDEPENDS:${PN} += "${@bb.utils.contains("DOCKER_UNIFIED_PACKAGE", "True", "${PN}-cli", "", d)}"
