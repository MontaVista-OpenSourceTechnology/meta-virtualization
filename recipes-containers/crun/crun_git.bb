DESCRIPTION = "A fast and low-memory footprint OCI Container Runtime fully written in C."
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=b234ee4d69f5fce4486a80fdaf4a4263"
PRIORITY = "optional"

SRCREV_crun = "ca8e5c74c13dbd5b1125d0357a9081d283a50971"
SRCREV_libocispec = "68397329bc51a66c56938fc4111fac751d6fd3b0"
SRCREV_ispec = "64294bd7a2bf2537e1a6a34d687caae70300b0c4"
SRCREV_rspec = "82cca47c22f5e87880421381fe1f8e0ef541ab64"
SRCREV_yajl = "f344d21280c3e4094919fd318bc5ce75da91fc06"

SRCREV_FORMAT = "crun_rspec"
SRC_URI = "git://github.com/containers/crun.git;branch=main;name=crun;protocol=https \
           git://github.com/containers/libocispec.git;branch=main;name=libocispec;destsuffix=${BB_GIT_DEFAULT_DESTSUFFIX}/libocispec;protocol=https \
           git://github.com/opencontainers/runtime-spec.git;branch=main;name=rspec;destsuffix=${BB_GIT_DEFAULT_DESTSUFFIX}/libocispec/runtime-spec;protocol=https \
           git://github.com/opencontainers/image-spec.git;branch=main;name=ispec;destsuffix=${BB_GIT_DEFAULT_DESTSUFFIX}/libocispec/image-spec;protocol=https \
           git://github.com/containers/yajl.git;branch=main;name=yajl;destsuffix=${BB_GIT_DEFAULT_DESTSUFFIX}/libocispec/yajl;protocol=https \
          "

PV = "v1.23.1+git${SRCREV_crun}"

inherit autotools-brokensep pkgconfig

# if this is true, we'll symlink crun to runc for easier integration
# with container stacks
CRUN_AS_RUNC ?= "true"

PACKAGECONFIG ??= " \
    caps external-yajl man \
    ${@bb.utils.contains('DISTRO_FEATURES', 'seccomp', 'seccomp', '', d)} \
    ${@bb.utils.contains('DISTRO_FEATURES', 'systemd', 'systemd', '', d)} \
"

PACKAGECONFIG[caps] = "--enable-caps,--disable-caps,libcap"
PACKAGECONFIG[external-yajl] = "--disable-embedded-yajl,--enable-embedded-yajl,yajl"
# whether to regenerate manpages that are already present in the repo
PACKAGECONFIG[man] = ",,go-md2man-native"
PACKAGECONFIG[seccomp] = "--enable-seccomp,--disable-seccomp,libseccomp"
PACKAGECONFIG[systemd] = "--enable-systemd,--disable-systemd,systemd"

DEPENDS = "m4-native"
DEPENDS:append:libc-musl = " argp-standalone"

do_configure:prepend () {
    # extracted from autogen.sh in crun source. This avoids
    # git submodule fetching.
    mkdir -p m4
    autoreconf -fi
}

do_install() {
    oe_runmake 'DESTDIR=${D}' install
    if [ -n "${CRUN_AS_RUNC}" ]; then
        ln -sr "${D}/${bindir}/crun" "${D}${bindir}/runc"
    fi
}
