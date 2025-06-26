SUMMARY = "Virtual Machine Viewer"
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=59530bdf33659b29e73d4adb9f9f6552"

# for ovirt support librest-0.7 and libgovirt would be needed
DEPENDS = " \
	desktop-file-utils-native \
	glib-2.0 \
	gtk+3 \
	libxml2 \
"

SRC_URI = "git://gitlab.com/virt-viewer/virt-viewer.git;protocol=https;branch=master"

SRCREV = "107f60c168c405cf1782b686a65bf4af16ec8c9d"
PV = "11.0+git"

REQUIRED_DISTRO_FEATURES = "opengl"

PACKAGECONFIG ?= "libvirt spice vte"

PACKAGECONFIG[libvirt] = "-Dlibvirt=enabled,-Dlibvirt=disabled,libvirt libvirt-glib"
PACKAGECONFIG[spice] = "-Dspice=enabled,-Dspice=disabled,spice-gtk spice-protocol"
PACKAGECONFIG[vnc] = "-Dvnc=enabled,-Dvnc=disabled,gtk-vnc"
PACKAGECONFIG[vte] = "-Dvte=enabled,-Dvte=disabled,vte"

inherit meson pkgconfig gtk-icon-cache mime mime-xdg gobject-introspection features_check

FILES:${PN} += "${datadir}"
GIR_MESON_OPTION = ''

do_compile:append() {
    # glib-mkenums is embedding full paths into this file. There's no
    # option to it to use a sysroot style variable. So to avoid QA
    # errors, we sed WORKDIR out and make its includes relative
    sed -i "s,${WORKDIR}/build/,," src/virt-viewer-enums.c
}
