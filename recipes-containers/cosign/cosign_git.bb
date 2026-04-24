SUMMARY = "Container signing, verification and storage in an OCI registry"
HOMEPAGE = "https://github.com/sigstore/cosign"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/COPYRIGHT.txt;md5=3830a9ca4f9dc30be01bfa2e4042dd46 \
                    file://src/${GO_IMPORT}/LICENSE;md5=86d3f3a95c324c9479bd8986968f4327 \
                    "

GO_IMPORT = "github.com/sigstore/cosign"
GO_INSTALL = "${GO_IMPORT}/v3/cmd/cosign"
SRC_URI = "git://${GO_IMPORT};protocol=https;nobranch=1;destsuffix=${GO_SRCURI_DESTSUFFIX}"
PV = "3.0.6+git"
SRCREV = "f1ad3ee952313be5d74a49d67ba0aa8d0d5e351f"

require ${BPN}-licenses.inc
require ${BPN}-go-mods.inc

inherit go-mod go-mod-update-modules

BBCLASSEXTEND = "native nativesdk"
