HOMEPAGE = "https://podman.io/"
SUMMARY =  "A daemonless container engine"
DESCRIPTION = "Podman is a daemonless container engine for developing, \
    managing, and running OCI Containers on your Linux System. Containers can \
    either be run as root or in rootless mode. Simply put: \
    `alias docker=podman`. \
    "

inherit features_check
REQUIRED_DISTRO_FEATURES ?= "seccomp ipv6"

DEPENDS = " \
    gpgme \
    libseccomp \
    ${@bb.utils.filter('DISTRO_FEATURES', 'systemd', d)} \
    gettext-native \
"

SRCREV = "227df90eb7c021097c9ba5f8000c83648a598028"
SRC_URI = " \
    git://github.com/containers/libpod.git;branch=v5.4;protocol=https;destsuffix=${GO_SRCURI_DESTSUFFIX} \
    ${@bb.utils.contains('PACKAGECONFIG', 'rootless', 'file://50-podman-rootless.conf', '', d)} \
    file://run-ptest \
    file://CVE-2025-6032.patch;patchdir=src/import \
    file://CVE-2025-9566.patch;patchdir=src/import \
"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/import/LICENSE;md5=3d9b931fa23ab1cacd0087f9e2ee12c0"

GO_IMPORT = "import"

S = "${WORKDIR}/git"

PV = "v5.4.1"

CVE_STATUS[CVE-2022-2989] = "fixed-version: fixed since v4.3.0"
CVE_STATUS[CVE-2023-0778] = "fixed-version: fixed since v4.5.0"

PACKAGES =+ "${PN}-contrib"

PODMAN_PKG = "github.com/containers/libpod"

BUILDTAGS_EXTRA ?= "${@bb.utils.contains('VIRTUAL-RUNTIME_container_networking','cni','cni','',d)}"
BUILDTAGS ?= "seccomp varlink \
${@bb.utils.contains('DISTRO_FEATURES', 'systemd', 'systemd', '', d)} \
exclude_graphdriver_btrfs exclude_graphdriver_devicemapper ${BUILDTAGS_EXTRA}"

# overide LDFLAGS to allow podman to build without: "flag provided but not # defined: -Wl,-O1
export LDFLAGS = ""

# https://github.com/llvm/llvm-project/issues/53999
TOOLCHAIN = "gcc"

# podmans Makefile expects BUILDFLAGS to be set but go.bbclass defines them in GOBUILDFLAGS
export BUILDFLAGS = "${GOBUILDFLAGS}"

inherit go goarch
inherit container-host
inherit systemd pkgconfig ptest

do_configure[noexec] = "1"

EXTRA_OEMAKE = " \
     PREFIX=${prefix} BINDIR=${bindir} LIBEXECDIR=${libexecdir} \
     ETCDIR=${sysconfdir} TMPFILESDIR=${nonarch_libdir}/tmpfiles.d \
     SYSTEMDDIR=${systemd_unitdir}/system USERSYSTEMDDIR=${systemd_user_unitdir} \
"

# remove 'docker' from the features if you don't want podman to
# build and install the docker wrapper. If docker is enabled in the
# variable, the podman package will rconfict with docker.
PODMAN_FEATURES ?= "docker"

PACKAGECONFIG ?= ""
PACKAGECONFIG[rootless] = ",,,fuse-overlayfs slirp4netns,,"

do_compile() {
	cd ${S}/src
	rm -rf .gopath
	mkdir -p .gopath/src/"$(dirname "${PODMAN_PKG}")"
	ln -sf ../../../../import/ .gopath/src/"${PODMAN_PKG}"

	ln -sf "../../../import/vendor/github.com/varlink/" ".gopath/src/github.com/varlink"

	export GOARCH="${BUILD_GOARCH}"
	export GOPATH="${S}/src/.gopath"
	export GOROOT="${STAGING_DIR_NATIVE}/${nonarch_libdir}/${HOST_SYS}/go"

	cd ${S}/src/.gopath/src/"${PODMAN_PKG}"

	# Pass the needed cflags/ldflags so that cgo
	# can find the needed headers files and libraries
	export GOARCH=${TARGET_GOARCH}
	export CGO_ENABLED="1"
	export CGO_CFLAGS="${CFLAGS} --sysroot=${STAGING_DIR_TARGET}"
	export CGO_LDFLAGS="${LDFLAGS} --sysroot=${STAGING_DIR_TARGET}"

	# podman now builds go-md2man and requires the host/build details
	export NATIVE_GOOS=${BUILD_GOOS}
	export NATIVE_GOARCH=${BUILD_GOARCH}

	oe_runmake NATIVE_GOOS=${BUILD_GOOS} NATIVE_GOARCH=${BUILD_GOARCH} BUILDTAGS="${BUILDTAGS}"
}

do_install() {
	cd ${S}/src/.gopath/src/"${PODMAN_PKG}"

	export GOARCH="${BUILD_GOARCH}"
	export GOPATH="${S}/src/.gopath"
	export GOROOT="${STAGING_DIR_NATIVE}/${nonarch_libdir}/${HOST_SYS}/go"

	oe_runmake install DESTDIR="${D}"
	if ${@bb.utils.contains('PODMAN_FEATURES', 'docker', 'true', 'false', d)}; then
		oe_runmake install.docker DESTDIR="${D}"
	fi

	# Silence docker emulation warnings.
	mkdir -p ${D}/etc/containers
	touch ${D}/etc/containers/nodocker

	if ${@bb.utils.contains('PACKAGECONFIG', 'rootless', 'true', 'false', d)}; then
		install -d "${D}${sysconfdir}/sysctl.d"
		install -m 0644 "${UNPACKDIR}/50-podman-rootless.conf" "${D}${sysconfdir}/sysctl.d"
		install -d "${D}${sysconfdir}/containers"
		cat <<-EOF >> "${D}${sysconfdir}/containers/containers.conf"
		[NETWORK]
		default_rootless_network_cmd="slirp4netns"
		EOF
	fi
}

do_install_ptest () {
	cp ${S}/src/import/Makefile ${D}${PTEST_PATH}
	install -d ${D}${PTEST_PATH}/test
	cp -r ${S}/src/import/test/system ${D}${PTEST_PATH}/test

	# Some compatibility links for the Makefile assumptions.
	install -d ${D}${PTEST_PATH}/bin
	ln -s ${bindir}/podman ${D}${PTEST_PATH}/bin/podman
	ln -s ${bindir}/podman-remote ${D}${PTEST_PATH}/bin/podman-remote
}

FILES:${PN} += " \
    ${systemd_unitdir}/system/* \
    ${nonarch_libdir}/systemd/* \
    ${systemd_user_unitdir}/* \
    ${nonarch_libdir}/tmpfiles.d/* \
    ${datadir}/user-tmpfiles.d/* \
    ${sysconfdir}/cni \
"

SYSTEMD_SERVICE:${PN} = "podman.service podman.socket"

# The other option for this is "busybox", since meta-virt ensures
# that busybox is configured with nsenter
VIRTUAL-RUNTIME_base-utils-nsenter ?= "util-linux-nsenter"

COMPATIBLE_HOST = "^(?!mips).*"

RDEPENDS:${PN} += "\
	catatonit conmon ${VIRTUAL-RUNTIME_container_runtime} iptables libdevmapper \
	${VIRTUAL-RUNTIME_container_dns} ${VIRTUAL-RUNTIME_container_networking} ${VIRTUAL-RUNTIME_base-utils-nsenter} \
"
RRECOMMENDS:${PN} += "slirp4netns \
                      kernel-module-xt-masquerade \
                      kernel-module-xt-comment \
                      kernel-module-xt-mark \
                      kernel-module-xt-addrtype \
                      kernel-module-xt-conntrack \
                      kernel-module-xt-tcpudp \
                      "
RCONFLICTS:${PN} = "${@bb.utils.contains('PACKAGECONFIG', 'docker', 'docker', '', d)}"

RDEPENDS:${PN}-ptest += " \
	bash \
	bats \
	buildah \
	coreutils \
	file \
	gnupg \
	jq \
	make \
	skopeo \
	tar \
"
