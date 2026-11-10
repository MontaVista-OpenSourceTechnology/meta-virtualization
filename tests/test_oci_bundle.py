# SPDX-FileCopyrightText: Copyright (C) 2026 Bruce Ashfield
#
# SPDX-License-Identifier: MIT
"""
Tests for OCI runtime bundles: OCI_IMAGE_OUTPUT_MODE, the OCI_RUNTIME_* variables,
crun and runc entries in BUNDLED_CONTAINERS, and vrnc and vcrn.

Most of the classes run the class code directly and need no build:
    pytest tests/test_oci_bundle.py -v -m "not slow"

The slow classes build oci-bundle-test-container, and run it in a guest with the
vcontainer SDK:
    pytest tests/test_oci_bundle.py -v --vdkr-dir /tmp/vcontainer

To run a bundle that is already built instead of building one:
    pytest tests/test_oci_bundle.py -v --vdkr-dir /tmp/vcontainer \\
        --oci-bundle tmp/deploy/images/qemux86-64/oci-bundle-test-container-latest-oci-bundle.tar
"""

import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest

from test_multilayer_oci import (  # noqa: F401
    build_dir, deploy_dir, machine, meta_virt_dir, poky_dir, run_bitbake,
)

TEST_RECIPE = "oci-bundle-test-container"
ROOTLESS_XATTR = "user.rootlesscontainers"


def class_function(path, name, **scope):
    """A python def from a class, to call without bitbake."""
    lines = path.read_text().split("\n")
    start = lines.index(next(line for line in lines if line.startswith(f"def {name}(")))
    body = [lines[start]]
    for line in lines[start + 1:]:
        if line and not line.startswith(" "):
            break
        body.append(line)
    scope = {"os": os, **scope}
    exec("\n".join(body), scope)
    return scope[name]


@pytest.fixture(scope="module")
def runtime_config(poky_dir, meta_virt_dir):
    """oci_runtime_config() from the class, with its defaults in a real datastore."""
    sys.path.insert(0, str(poky_dir / "bitbake" / "lib"))
    bb = pytest.importorskip("bb")
    import bb.data
    import bb.utils

    path = meta_virt_dir / "classes" / "image-oci.bbclass"
    defaults = {
        m.group(1): m.group(2).replace("\\\n", " ")
        for m in re.finditer(r'^(OCI_RUNTIME_\w+) \?= "((?:[^"\\]|\\\n)*)"', path.read_text(), re.M)
    }
    oci_runtime_config = class_function(path, "oci_runtime_config", bb=bb)

    def generate(**overrides):
        d = bb.data.init()
        d.setVar("IMAGE_BASENAME", "testapp")
        for name, value in {**defaults, **overrides}.items():
            d.setVar(name, value)
        # config.json is written from it, so it has to be plain JSON
        return json.loads(json.dumps(oci_runtime_config(d)))

    return generate


class TestRuntimeConfig:
    """OCI_RUNTIME_* to JSON."""

    def test_defaults_are_for_a_root_runtime(self, runtime_config):
        config = runtime_config()
        linux = config["linux"]
        assert [n["type"] for n in linux["namespaces"]] == \
            ["cgroup", "pid", "network", "ipc", "uts", "mount"]
        assert "uidMappings" not in linux
        assert "devices" not in linux
        assert linux["resources"]["devices"] == [{"allow": False, "access": "rwm"}]
        assert config["process"]["terminal"] is False
        assert config["process"]["noNewPrivileges"] is True
        assert config["hostname"] == "testapp"
        assert config["readonlyRootfs"] is False

    def test_a_value_replaces_the_default(self, runtime_config):
        config = runtime_config(OCI_RUNTIME_NAMESPACES="pid mount")
        assert [n["type"] for n in config["linux"]["namespaces"]] == ["pid", "mount"]

    def test_empty_means_nothing(self, runtime_config):
        config = runtime_config(
            OCI_RUNTIME_MOUNTS="", OCI_RUNTIME_RLIMITS="", OCI_RUNTIME_MASKED_PATHS="")
        assert config["mounts"] == []
        assert config["process"]["rlimits"] == []
        assert config["linux"]["maskedPaths"] == []

    def test_capability_sets(self, runtime_config):
        config = runtime_config(
            OCI_RUNTIME_CAPABILITIES="CAP_KILL",
            OCI_RUNTIME_CAPABILITIES_AMBIENT="")
        capabilities = config["process"]["capabilities"]
        assert capabilities["ambient"] == []
        for name in ("bounding", "effective", "inheritable", "permitted"):
            assert capabilities[name] == ["CAP_KILL"]

    def test_mount_with_a_placeholder(self, runtime_config):
        config = runtime_config(
            OCI_RUNTIME_MOUNTS="/proc:proc:proc /data:bind:@INSTANCE_DIR@/data:rbind,ro")
        assert config["mounts"] == [
            {"destination": "/proc", "type": "proc", "source": "proc"},
            {"destination": "/data", "type": "bind", "source": "@INSTANCE_DIR@/data",
             "options": ["rbind", "ro"]},
        ]

    def test_join_a_namespace(self, runtime_config):
        config = runtime_config(OCI_RUNTIME_NAMESPACES="pid network=/run/netns/x")
        assert config["linux"]["namespaces"] == [
            {"type": "pid"}, {"type": "network", "path": "/run/netns/x"}]

    def test_hostname_needs_a_private_uts_namespace(self, runtime_config):
        assert "hostname" not in runtime_config(OCI_RUNTIME_NAMESPACES="pid mount")
        assert "hostname" not in runtime_config(OCI_RUNTIME_NAMESPACES="pid mount uts=/run/uts/x")

    def test_devices_get_an_allow_rule(self, runtime_config):
        config = runtime_config(
            OCI_RUNTIME_DEVICES="/dev/net/tun:c:10:200:0660:0:5 /dev/loop0:b:7:0")
        assert config["linux"]["devices"] == [
            {"path": "/dev/net/tun", "type": "c", "major": 10, "minor": 200,
             "fileMode": 0o660, "uid": 0, "gid": 5},
            {"path": "/dev/loop0", "type": "b", "major": 7, "minor": 0},
        ]
        assert config["linux"]["resources"]["devices"] == [
            {"allow": False, "access": "rwm"},
            {"allow": True, "type": "c", "major": 10, "minor": 200, "access": "rwm"},
            {"allow": True, "type": "b", "major": 7, "minor": 0, "access": "rwm"},
        ]

    def test_user_namespace(self, runtime_config):
        config = runtime_config(
            OCI_RUNTIME_NAMESPACES="pid mount user",
            OCI_RUNTIME_UID_MAPPINGS="0:1000:1",
            OCI_RUNTIME_GID_MAPPINGS="0:1000:1",
            OCI_RUNTIME_DEVICES="/dev/fuse:c:10:229")
        linux = config["linux"]
        assert linux["uidMappings"] == [{"containerID": 0, "hostID": 1000, "size": 1}]
        assert linux["gidMappings"] == [{"containerID": 0, "hostID": 1000, "size": 1}]
        assert "resources" not in linux, "an unprivileged runtime can't manage device rules"
        assert len(linux["devices"]) == 1

    def test_mappings_turn_on_the_user_namespace(self, runtime_config):
        config = runtime_config(
            OCI_RUNTIME_NAMESPACES="pid mount",
            OCI_RUNTIME_UID_MAPPINGS="0:100000:65536",
            OCI_RUNTIME_GID_MAPPINGS="0:100000:65536")
        assert config["linux"]["namespaces"] == [
            {"type": "pid"}, {"type": "mount"}, {"type": "user"}]
        assert "resources" not in config["linux"]

    @pytest.mark.parametrize("overrides", [
        {"OCI_RUNTIME_MOUNTS": "/proc:proc"},
        {"OCI_RUNTIME_RLIMITS": "RLIMIT_NOFILE:many:1"},
        {"OCI_RUNTIME_UID_MAPPINGS": "0:1000:1"},
        {"OCI_RUNTIME_NAMESPACES": "pid user=/proc/1/ns/user",
         "OCI_RUNTIME_UID_MAPPINGS": "0:1000:1", "OCI_RUNTIME_GID_MAPPINGS": "0:1000:1"},
        {"OCI_RUNTIME_NAMESPACES": "pid user"},
        {"OCI_RUNTIME_DEVICES": "/dev/x:c:1"},
        {"OCI_RUNTIME_DEVICES": "/dev/x:z:1:2"},
        {"OCI_RUNTIME_DEVICES": "/dev/x:c:1:2:999"},
        {"OCI_RUNTIME_DEVICES": "/dev/x:c:1:2:0666:0"},
    ], ids=["mount", "rlimit", "uid-mapping-no-gid", "mapping-joined-namespace",
            "namespace-no-mapping",
            "device-short", "device-type", "device-mode", "device-uid-no-gid"])
    def test_a_bad_value_is_an_error(self, runtime_config, overrides):
        with pytest.raises(Exception) as error:
            runtime_config(**overrides)
        assert type(error.value).__name__ == "BBHandledException"


def rootless_owner(uid=None, gid=None):
    """The protobuf umoci stores in user.rootlesscontainers."""
    def varint(value):
        out = bytearray()
        while True:
            byte = value & 0x7f
            value >>= 7
            if value:
                out.append(byte | 0x80)
            else:
                out.append(byte)
                return bytes(out)
    data = b""
    if uid is not None:
        data += b"\x08" + varint(uid)
    if gid is not None:
        data += b"\x10" + varint(gid)
    return data


class TestBundleArchive:
    """oci-bundle-archive.py and oci_configure_bundle against a rootless unpack."""

    @pytest.fixture
    def bundle(self, tmp_path):
        """A bundle as umoci unpack --rootless leaves it."""
        bundle = tmp_path / "bundle"
        rootfs = bundle / "rootfs"
        (rootfs / "home" / "app").mkdir(parents=True)
        (rootfs / "bin").mkdir()
        (bundle / "config.json").write_text(json.dumps({
            "ociVersion": "1.3.0",
            "process": {"terminal": True, "args": ["/bin/app", "arg"], "cwd": "/home/app",
                        "env": ["A=b"], "user": {"uid": 1001, "gid": 0}},
            "root": {"path": "rootfs"},
            "hostname": "umoci-default",
            "mounts": [{"destination": "/sys", "type": "bind", "source": "/sys"}],
            "linux": {"uidMappings": [{"containerID": 0, "hostID": 1000, "size": 1}],
                      "gidMappings": [{"containerID": 0, "hostID": 1000, "size": 1}],
                      "namespaces": [{"type": "user"}]},
        }))
        (bundle / "umoci.json").write_text("{}")
        (rootfs / "home" / "app" / "f").write_text("f")
        try:
            os.setxattr(rootfs / "home" / "app", ROOTLESS_XATTR, rootless_owner(1001, 1001))
        except OSError:
            pytest.skip("no user xattrs on the test filesystem")
        os.setxattr(rootfs / "home" / "app" / "f", ROOTLESS_XATTR, rootless_owner(1001, 1002))
        (rootfs / "bin" / "su").write_text("su")
        (rootfs / "bin" / "su").chmod(0o4755)
        os.link(rootfs / "bin" / "su", rootfs / "bin" / "su2")
        (rootfs / "bin" / "uidonly").write_text("x")
        os.setxattr(rootfs / "bin" / "uidonly", ROOTLESS_XATTR, rootless_owner(uid=5))
        os.symlink("/etc/passwd", rootfs / "abslink")
        os.mkfifo(rootfs / "fifo")
        return bundle

    def archive(self, meta_virt_dir, runtime_config, bundle, tmp_path):
        output = tmp_path / "out.tar"
        script = meta_virt_dir / "scripts" / "oci-bundle-archive.py"
        subprocess.run([sys.executable, script, bundle, output], check=True)
        return tarfile.open(output)

    def test_layout(self, meta_virt_dir, runtime_config, bundle, tmp_path):
        names = self.archive(meta_virt_dir, runtime_config, bundle, tmp_path).getnames()
        assert "config.json" in names
        assert "rootfs" in names
        assert "rootfs/home/app/f" in names
        assert "umoci.json" not in names

    def test_owners_come_from_the_xattr(self, meta_virt_dir, runtime_config, bundle, tmp_path):
        tar = self.archive(meta_virt_dir, runtime_config, bundle, tmp_path)
        owner = lambda name: (tar.getmember(name).uid, tar.getmember(name).gid)
        assert owner("rootfs/home/app") == (1001, 1001)
        assert owner("rootfs/home/app/f") == (1001, 1002)
        assert owner("rootfs/bin/uidonly") == (5, 0)
        assert owner("rootfs/bin/su") == (0, 0), "no xattr means root, not the build user"
        assert tar.getmember("rootfs/bin/su").uname == ""

    def test_file_types_and_modes(self, meta_virt_dir, runtime_config, bundle, tmp_path):
        tar = self.archive(meta_virt_dir, runtime_config, bundle, tmp_path)
        assert tar.getmember("rootfs/bin/su").mode == 0o4755
        assert tar.getmember("rootfs/bin/su2").islnk()
        assert tar.getmember("rootfs/abslink").linkname == "/etc/passwd"
        assert tar.getmember("rootfs/fifo").isfifo()

    def test_unreadable_modes(self, meta_virt_dir, runtime_config, bundle, tmp_path):
        rootfs = bundle / "rootfs"
        (rootfs / "shadow").write_text("secret")
        (rootfs / "shadow").chmod(0)
        (rootfs / "locked").mkdir()
        (rootfs / "locked" / "inside").write_text("x")
        (rootfs / "locked").chmod(0)
        tar = self.archive(meta_virt_dir, runtime_config, bundle, tmp_path)
        assert tar.getmember("rootfs/shadow").mode == 0
        assert tar.extractfile("rootfs/shadow").read() == b"secret"
        assert tar.getmember("rootfs/locked").mode == 0
        assert tar.extractfile("rootfs/locked/inside").read() == b"x"
        assert stat.S_IMODE((rootfs / "shadow").stat().st_mode) == 0
        assert (rootfs / "locked").stat().st_mode & stat.S_IRWXU == stat.S_IRWXU, \
            "the unpacked bundle has to stay removable"

    def test_configure_replaces_the_rootless_config(self, meta_virt_dir, runtime_config, bundle):
        config = bundle / "config.json"
        configure = class_function(meta_virt_dir / "classes" / "image-oci-umoci.inc",
                                   "oci_configure_bundle")
        configure(config, runtime_config())
        result = json.loads(config.read_text())
        assert stat.S_IMODE(config.stat().st_mode) == 0o644
        assert "uidMappings" not in result["linux"]
        assert "user" not in [n["type"] for n in result["linux"]["namespaces"]]
        assert result["process"]["terminal"] is False
        assert result["hostname"] == "testapp"
        assert "/sys" in [m["destination"] for m in result["mounts"]]
        assert result["mounts"][0]["destination"] == "/proc"
        # what the image settings decide is left alone
        assert result["process"]["args"] == ["/bin/app", "arg"]
        assert result["process"]["env"] == ["A=b"]
        assert result["process"]["cwd"] == "/home/app"
        assert result["process"]["user"] == {"uid": 1001, "gid": 0}


class CrossInstall:
    """Runs the real merge_installed_bundles and bundle_containers under pseudo,
    as do_rootfs does."""

    def __init__(self, meta_virt_dir, pseudo, root):
        self.pseudo = pseudo
        self.root = root
        self.rootfs = root / "rootfs"
        self.deploy = root / "deploy"
        for path in (self.rootfs / "usr" / "bin", self.deploy, root / "pseudo",
                     root / "work", root / "vdkr", root / "vpdmn"):
            path.mkdir(parents=True)
        (self.rootfs / "usr" / "bin" / "crun").touch()
        self.vrunner = root / "vrunner"
        self.vrunner.write_text("#!/bin/sh\nexit 0\n")
        self.vrunner.chmod(0o755)
        source = (meta_virt_dir / "classes" / "container-cross-install.bbclass").read_text()
        self.function = source[source.index("\nmerge_installed_bundles() {"):source.index("# First merge any bundles")]
        common = (meta_virt_dir / "classes" / "container-common.bbclass").read_text()
        self.function = common[common.index("is_bundle_runtime() {"):] + self.function
        self.template = meta_virt_dir / "files" / "oci-bundle.service.in"
        self.cgroups_path = meta_virt_dir / "scripts" / "oci-bundle-cgroups-path.py"

    def pseudo_env(self):
        env = dict(os.environ)
        env.update(PSEUDO_PREFIX=str(self.pseudo), PSEUDO_LOCALSTATEDIR=str(self.root / "pseudo"),
                   PSEUDO_PASSWD="/", PSEUDO_NOSYMLINKEXP="1")
        return env

    def shell(self, script):
        return subprocess.run([str(self.pseudo / "bin" / "pseudo"), "dash", "-c", script],
                              env=self.pseudo_env(), capture_output=True, text=True)

    def run(self, bundled="", service_map="", function="bundle_containers"):
        values = {
            "BUNDLED_CONTAINERS": bundled, "DEPLOY_DIR_IMAGE": str(self.deploy),
            "IMAGE_ROOTFS": str(self.rootfs), "OCI_BUNDLE_INSTALL_DIR": "/var/lib/oci-bundles",
            "VRUNNER_PATH": str(self.vrunner), "QEMU_ARCH": "x86_64", "BLOB_ARCH": "x86_64",
            "CONTAINER_DEFAULT_RUNTIME": "docker", "CONTAINER_SERVICE_FILE_MAP": service_map,
            "WORKDIR": str(self.root / "work"), "MACHINE": "qemux86-64", "bindir": "/usr/bin",
            "VDKR_BLOB_DIR": str(self.root / "vdkr"), "VPDMN_BLOB_DIR": str(self.root / "vpdmn"),
            "CONTAINER_IMPORT_TIMEOUT_BASE": "1", "CONTAINER_IMPORT_TIMEOUT_PER": "1",
            "STAGING_BINDIR_NATIVE": "/nonexistent", "datadir": "/usr/share",
            "OCI_BUNDLE_RUNTIMES": "crun runc", "OCI_BUNDLE_RUNTIMES_PATTERN": "crun|runc",
            "OCI_BUNDLE_SERVICE_TEMPLATE": str(self.template),
            "OCI_BUNDLE_CGROUPS_PATH_SCRIPT": str(self.cgroups_path),
        }
        source = re.sub(r"\$\{([A-Za-z_]+)\}",
                        lambda m: values.get(m.group(1), m.group(0)), self.function)
        return self.shell('bbnote() { :; }\nbbwarn() { echo "WARNING: $*"; }\n'
                          'bbfatal() { echo "FATAL: $*"; exit 1; }\n'
                          + source + f"\n{function}\n")

    def add_bundle(self, name, config=b"{}"):
        path = self.root / f"{name}.tar"
        self.write_bundle(path, config)
        os.symlink(path, self.deploy / f"{name}-latest-oci-bundle.tar")

    def add_package(self, name, runtime, policy="", config=b"{}", service=None):
        """What a container-bundle package installs for crun or runc."""
        bundles = self.rootfs / "usr/share/container-bundles"
        (bundles / runtime / "bundles").mkdir(parents=True, exist_ok=True)
        self.write_bundle(bundles / runtime / "bundles" / f"{name}.tar", config)
        entry = f"{name}:{runtime}:{policy}" if policy else f"{name}:{runtime}"
        with open(bundles / "pkg.meta", "a") as meta:
            meta.write(entry + "\n")
        if service is not None:
            (bundles / runtime / "services").mkdir(exist_ok=True)
            (bundles / runtime / "services" / f"{name}.service").write_text(service)

    @staticmethod
    def write_bundle(path, config):
        with tarfile.open(path, "w", format=tarfile.PAX_FORMAT) as tar:
            def add(member, data=None, mode=0o644, uid=0, gid=0):
                info = tarfile.TarInfo(member)
                info.mode, info.uid, info.gid = mode, uid, gid
                if data is None:
                    info.type = tarfile.DIRTYPE
                else:
                    info.size = len(data)
                tar.addfile(info, io.BytesIO(data or b""))
            add("config.json", config)
            add("rootfs", None, 0o755)
            add("rootfs/app", None, 0o750, 1001, 1001)
            add("rootfs/app/f", b"f", 0o644, 1001, 1002)
            add("rootfs/su", b"su", 0o4755)

    def add_image(self, name):
        (self.deploy / f"{name}-latest-oci").mkdir()


@pytest.fixture
def cross_install(meta_virt_dir, build_dir, tmp_path):
    pseudo = build_dir / "tmp" / "sysroots-components" / "x86_64" / "pseudo-native" / "usr"
    if not (pseudo / "bin" / "pseudo").exists():
        pytest.skip(f"pseudo-native not found in {pseudo}")
    return CrossInstall(meta_virt_dir, pseudo, tmp_path)


class TestCrossInstallBundle:
    """crun and runc entries in BUNDLED_CONTAINERS."""

    SERVICE = "lib/systemd/system/container-app.service"

    def test_extracted_with_owners_and_modes(self, cross_install):
        cross_install.add_bundle("app")
        result = cross_install.run("app:crun")
        assert result.returncode == 0, result.stdout + result.stderr
        bundle = cross_install.rootfs / "var" / "lib" / "oci-bundles" / "app"
        assert (bundle / "config.json").exists()
        listing = cross_install.shell(f'stat -c "%a %u %g %n" {bundle}/rootfs/app {bundle}/rootfs/app/f {bundle}/rootfs/su')
        lines = [" ".join(line.split()[:3]) for line in listing.stdout.splitlines()]
        assert lines == ["750 1001 1001", "644 1001 1002", "4755 0 0"], listing.stdout + listing.stderr

    def test_no_service_without_autostart(self, cross_install):
        cross_install.add_bundle("app")
        assert cross_install.run("app:crun").returncode == 0
        assert not (cross_install.rootfs / self.SERVICE).exists()

    @pytest.mark.parametrize("runtime", ["crun", "runc"])
    def test_autostart_service(self, cross_install, runtime):
        cross_install.add_bundle("app")
        result = cross_install.run(f"app:{runtime}:autostart")
        assert result.returncode == 0, result.stdout + result.stderr
        service = (cross_install.rootfs / self.SERVICE).read_text()
        assert "Restart=always" in service
        assert f"ExecStart=/usr/bin/{runtime} run --bundle /var/lib/oci-bundles/app app" in service
        assert f"ExecStartPre=-/usr/bin/{runtime} delete --force app" in service
        wants = cross_install.rootfs / "etc/systemd/system/multi-user.target.wants/container-app.service"
        assert os.readlink(wants) == "/lib/systemd/system/container-app.service"

    def test_autostart_puts_the_container_below_the_service(self, cross_install):
        cross_install.add_bundle("app", b'{"linux": {"namespaces": []}}')
        result = cross_install.run("app:crun:autostart")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Delegate=yes" in (cross_install.rootfs / self.SERVICE).read_text()
        config = json.loads((cross_install.rootfs / "var/lib/oci-bundles/app/config.json").read_text())
        assert config["linux"] == {"namespaces": [],
                                   "cgroupsPath": "/system.slice/container-app.service/container"}

    def test_a_cgroups_path_of_its_own_is_kept(self, cross_install):
        cross_install.add_bundle("app", b'{"linux": {"cgroupsPath": "/mine"}}')
        result = cross_install.run("app:crun:autostart")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "sets its own cgroupsPath, /mine" in result.stdout
        config = json.loads((cross_install.rootfs / "var/lib/oci-bundles/app/config.json").read_text())
        assert config["linux"]["cgroupsPath"] == "/mine"

    def test_no_cgroups_path_without_autostart(self, cross_install):
        cross_install.add_bundle("app")
        assert cross_install.run("app:crun").returncode == 0
        assert (cross_install.rootfs / "var/lib/oci-bundles/app/config.json").read_text() == "{}"

    def test_a_template_of_its_own(self, cross_install, tmp_path):
        cross_install.add_bundle("app")
        cross_install.template = tmp_path / "oci-bundle.service.in"
        cross_install.template.write_text(
            "[Service]\nExecStart=@RUNTIME@ run --bundle @BUNDLE_DIR@ @CONTAINER_NAME@\n"
            "Restart=@RESTART_POLICY@\nEnvironment=FROM=layer\n")
        result = cross_install.run("app:crun:on-failure")
        assert result.returncode == 0, result.stdout + result.stderr
        assert (cross_install.rootfs / self.SERVICE).read_text() == (
            "[Service]\nExecStart=/usr/bin/crun run --bundle /var/lib/oci-bundles/app app\n"
            "Restart=on-failure\nEnvironment=FROM=layer\n")

    def test_custom_service_file(self, cross_install, tmp_path):
        cross_install.add_bundle("app")
        custom = tmp_path / "custom.service"
        custom.write_text("[Service]\nExecStart=/custom\n")
        result = cross_install.run("app:crun:autostart", f"app={custom}")
        assert result.returncode == 0, result.stdout + result.stderr
        assert (cross_install.rootfs / self.SERVICE).read_text() == custom.read_text()

    def test_missing_runtime_warns(self, cross_install):
        cross_install.add_bundle("app")
        result = cross_install.run("app:runc")
        assert result.returncode == 0
        assert "WARNING: app uses runc" in result.stdout

    def test_image_with_a_bundle_runtime_is_an_error(self, cross_install):
        cross_install.add_image("app")
        result = cross_install.run("app:crun")
        assert result.returncode != 0
        assert "FATAL: 'app' is an OCI image" in result.stdout

    def test_bundle_with_an_image_runtime_is_an_error(self, cross_install):
        cross_install.add_bundle("app")
        result = cross_install.run("app:docker")
        assert result.returncode != 0
        assert "FATAL: 'app' is a runtime bundle" in result.stdout

    def test_missing_bundle_is_an_error(self, cross_install):
        result = cross_install.run("app:crun")
        assert result.returncode != 0
        assert "FATAL: Runtime bundle not found for 'app'" in result.stdout

    def test_both_outputs_serve_both_runtimes(self, cross_install):
        cross_install.add_bundle("app")
        cross_install.add_image("app")
        result = cross_install.run("app:docker app:crun")
        assert result.returncode == 0, result.stdout + result.stderr
        assert (cross_install.rootfs / "var/lib/oci-bundles/app/config.json").exists()


class TestInstalledBundlePackage:
    """crun and runc bundles from container-bundle packages in IMAGE_INSTALL."""

    SERVICE = "lib/systemd/system/container-app.service"

    def merge(self, cross_install):
        return cross_install.run(function="merge_installed_bundles")

    def test_extracted_with_owners_and_modes(self, cross_install):
        cross_install.add_package("app", "crun")
        result = self.merge(cross_install)
        assert result.returncode == 0, result.stdout + result.stderr
        bundle = cross_install.rootfs / "var" / "lib" / "oci-bundles" / "app"
        assert (bundle / "config.json").exists()
        listing = cross_install.shell(f'stat -c "%a %u %g %n" {bundle}/rootfs/app {bundle}/rootfs/app/f {bundle}/rootfs/su')
        lines = [" ".join(line.split()[:3]) for line in listing.stdout.splitlines()]
        assert lines == ["750 1001 1001", "644 1001 1002", "4755 0 0"], listing.stdout + listing.stderr
        assert not (cross_install.rootfs / "usr/share/container-bundles").exists()
        assert not (cross_install.rootfs / self.SERVICE).exists()

    @pytest.mark.parametrize("runtime", ["crun", "runc"])
    def test_autostart_service(self, cross_install, runtime):
        (cross_install.rootfs / "usr/bin/runc").touch()
        cross_install.add_package("app", runtime, "autostart")
        result = self.merge(cross_install)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "WARNING" not in result.stdout
        service = (cross_install.rootfs / self.SERVICE).read_text()
        assert "Restart=always" in service
        assert "Delegate=yes" in service
        assert f"ExecStart=/usr/bin/{runtime} run --bundle /var/lib/oci-bundles/app app" in service
        wants = cross_install.rootfs / "etc/systemd/system/multi-user.target.wants/container-app.service"
        assert os.readlink(wants) == "/lib/systemd/system/container-app.service"
        config = json.loads((cross_install.rootfs / "var/lib/oci-bundles/app/config.json").read_text())
        assert config["linux"]["cgroupsPath"] == "/system.slice/container-app.service/container"

    def test_custom_service_file(self, cross_install):
        custom = "[Service]\nExecStart=/custom\n"
        cross_install.add_package("app", "crun", "autostart", service=custom)
        result = self.merge(cross_install)
        assert result.returncode == 0, result.stdout + result.stderr
        assert (cross_install.rootfs / self.SERVICE).read_text() == custom

    def test_missing_runtime_warns(self, cross_install):
        cross_install.add_package("app", "runc")
        result = self.merge(cross_install)
        assert result.returncode == 0
        assert "WARNING: app uses runc" in result.stdout


class TestRestartPolicy:
    """systemd has no Restart=unless-stopped, and ignores the line if it sees one."""

    def test_docker_service(self, cross_install):
        cross_install.add_image("app")
        result = cross_install.run("app:docker:autostart")
        assert result.returncode == 0, result.stdout + result.stderr
        service = cross_install.rootfs / "lib/systemd/system/container-app.service"
        assert "Restart=always" in service.read_text()

    def test_podman_quadlet(self, cross_install):
        cross_install.add_image("app")
        result = cross_install.run("app:podman:autostart")
        assert result.returncode == 0, result.stdout + result.stderr
        quadlet = cross_install.rootfs / "etc/containers/systemd/container-app.container"
        assert "Restart=always" in quadlet.read_text()

    @pytest.mark.parametrize("policy", ["on-failure", "always", "no"])
    def test_systemd_policies_are_unchanged(self, cross_install, policy):
        cross_install.add_image("app")
        assert cross_install.run(f"app:docker:{policy}").returncode == 0
        service = cross_install.rootfs / "lib/systemd/system/container-app.service"
        assert f"Restart={policy}\n" in service.read_text()

    @pytest.mark.parametrize("function", [
        "generate_docker_service_from_bundle", "generate_podman_service_from_bundle"])
    def test_installed_bundle_packages(self, meta_virt_dir, function):
        source = (meta_virt_dir / "classes" / "container-cross-install.bbclass").read_text()
        body = source[source.index(f"{function}() {{"):]
        body = body[:body.index("\n}\n")]
        assert 'restart_policy="always"' in body


@pytest.fixture(scope="module")
def bundle_tar(request, build_dir, machine):
    """The test recipe's bundle, built unless --oci-bundle gives one."""
    given = request.config.getoption("--oci-bundle")
    if given:
        return Path(given)
    result = run_bitbake(build_dir, TEST_RECIPE, timeout=3600)
    if result.returncode != 0:
        pytest.fail(f"Build failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")
    return build_dir / "tmp" / "deploy" / "images" / machine / f"{TEST_RECIPE}-latest-oci-bundle.tar"


@pytest.mark.slow
class TestBundleBuild:
    """What bitbake deploys for oci-bundle-test-container."""

    def test_both_outputs_are_deployed(self, request, bundle_tar):
        if request.config.getoption("--oci-bundle"):
            pytest.skip("--oci-bundle given, nothing was built")
        assert bundle_tar.exists()
        image = bundle_tar.parent / f"{TEST_RECIPE}-latest-oci"
        assert (image / "index.json").exists(), "OCI_IMAGE_OUTPUT_MODE has image too"

    def test_bundle_contents(self, bundle_tar):
        with tarfile.open(bundle_tar) as tar:
            names = tar.getnames()
            config = json.load(tar.extractfile("config.json"))
        assert "rootfs/usr/bin/bundle-check" in names
        assert not [n for n in names if n.startswith(("blobs/", "umoci.json", "sha256_"))]
        assert config["process"]["args"] == ["/usr/bin/bundle-check", "from-cmd"]
        assert "BUNDLE_TEST=from-env" in config["process"]["env"]
        assert config["process"]["cwd"] == "/tmp"
        assert config["process"]["user"]["uid"] == 0
        assert config["process"]["capabilities"]["effective"] == ["CAP_KILL"]
        assert config["hostname"] == "bundle-test"
        assert config["root"] == {"path": "rootfs", "readonly": True}
        assert "uidMappings" not in config["linux"]
        assert "/mnt/bundle-test" in [m["destination"] for m in config["mounts"]]
        assert config["linux"]["devices"][0]["path"] == "/dev/net/tun"

    def test_recipe_files_are_owned_by_root(self, bundle_tar):
        with tarfile.open(bundle_tar) as tar:
            member = tar.getmember("rootfs/usr/bin/bundle-check")
        assert (member.uid, member.gid) == (0, 0), "the build user must not leak into the bundle"

    @pytest.mark.parametrize("path", ["rootfs/home/nonroot", "rootfs/var/lib/bundle-test"])
    def test_a_layer_added_later_keeps_its_owners(self, bundle_tar, path):
        """container-nonroot-user adds its layer after the image is built."""
        with tarfile.open(bundle_tar) as tar:
            member = tar.getmember(path)
        assert (member.uid, member.gid) == (65532, 65532)

    @pytest.mark.parametrize("assignment, message", [
        ('OCI_IMAGE_OUTPUT_MODE:pn-container-base = "bogus"', "must be 'image', 'bundle' or both"),
        ('OCI_IMAGE_OUTPUT_MODE:pn-container-base = "bundle"\n'
         'OCI_IMAGE_BACKEND:pn-container-base = "sloci-image"', "not supported by the 'sloci-image' backend"),
        ('OCI_IMAGE_OUTPUT_MODE:pn-container-base = "bundle"\n'
         'OCI_RUNTIME_MOUNTS:pn-container-base = "/proc:proc"', "bad entry"),
    ], ids=["bad-mode", "sloci", "bad-runtime-variable"])
    def test_parse_errors(self, build_dir, tmp_path, assignment, message):
        conf = tmp_path / "bundle-test.conf"
        conf.write_text(assignment + "\n")
        result = run_bitbake(build_dir, "container-base", extra_args=["-e", "-R", str(conf)], timeout=600)
        assert result.returncode != 0
        assert message in result.stdout + result.stderr


GUEST_SETTINGS = {
    "args": "from-cmd",
    "env": "from-env",
    "cwd": "/tmp",
    "uid": "0",
    "host": "bundle-test",
    "capeff": "0000000000000020",
    "nofile": "64",
    "rootfs": "readonly",
    "mount": "yes",
    "device": "yes",
    "devnull": "yes",
}


def assert_reports_its_settings(output):
    found = dict(line.strip().split("=", 1) for line in output.splitlines()
                 if "=" in line and line.split("=")[0].strip() in {*GUEST_SETTINGS, "uidmap"})
    for name, value in GUEST_SETTINGS.items():
        assert found.get(name) == value, f"{name}: {output}"
    assert found["uidmap"].split() == ["0", "0", "4294967295"], "no user namespace"


# Each bundle tool, with the tool whose guest and fixtures it shares
BUNDLE_TOOLS = {"vrnc": ("vdkr", "memres_session"), "vcrn": ("vpdmn", "vpdmn_memres_session")}


def bundle_tool(request, tool, daemon=False):
    """A runner for tool, with the state of the tool it shares a guest with."""
    base_name, memres_name = BUNDLE_TOOLS[tool]
    base = request.getfixturevalue(memres_name if daemon else base_name)
    binary = base.binary.parent / f"{tool}-{base.arch}"
    if not binary.exists():
        pytest.fail(f"{binary} not found, rebuild the SDK with tests/build-vcontainer-sdk.sh")
    return type(base)(binary, base.env, base.arch, base.state_dir)


def sleeping_bundle(bundle_tar, path):
    """A copy of bundle_tar, whose container says so and runs until it is killed."""
    with tarfile.open(bundle_tar) as source, tarfile.open(path, "w") as copy:
        for member in source:
            content = source.extractfile(member) if member.isfile() else None
            if member.name in ("config.json", "./config.json"):
                config = json.load(content)
                config["process"]["args"] = ["/bin/sh", "-c", "echo started; exec sleep 1000"]
                data = json.dumps(config, indent=2).encode()
                member.size = len(data)
                content = io.BytesIO(data)
            copy.addfile(member, content)
    return path


@pytest.mark.slow
@pytest.mark.parametrize("tool", BUNDLE_TOOLS)
class TestBundleTools:
    """vrnc and vcrn run the test recipe's bundle in a guest."""

    TIMEOUT = 300

    def test_without_a_daemon(self, request, tool, bundle_tar):
        runner = bundle_tool(request, tool)
        runner.run("vmemres", "stop", check=False, timeout=60)
        result = runner.run("--no-daemon", "run", "-b", str(bundle_tar), "t1", timeout=self.TIMEOUT, check=False)
        assert result.returncode == 7, result.stdout
        assert_reports_its_settings(result.stdout)

    @pytest.mark.memres
    def test_with_the_daemon(self, request, tool, bundle_tar):
        result = bundle_tool(request, tool, daemon=True).run("run", "--bundle", str(bundle_tar), "t2",
                                                             timeout=self.TIMEOUT, check=False)
        assert result.returncode == 7, result.stdout
        assert_reports_its_settings(result.stdout)

    @pytest.mark.memres
    def test_a_directory_bundle(self, request, tool, bundle_tar, tmp_path):
        subprocess.run(["tar", "-xf", str(bundle_tar), "-C", str(tmp_path)], check=True)
        result = bundle_tool(request, tool, daemon=True).run("run", "-b", str(tmp_path), "t3",
                                                             timeout=self.TIMEOUT, check=False)
        assert result.returncode == 7, result.stdout
        assert_reports_its_settings(result.stdout)


@pytest.mark.slow
@pytest.mark.memres
@pytest.mark.parametrize("tool", BUNDLE_TOOLS)
class TestBundleToolLifecycle:
    """The runtime's commands reach a container that outlasts each of them."""

    def test_detached(self, request, tool, bundle_tar, tmp_path):
        runner = bundle_tool(request, tool, daemon=True)
        bundle = str(sleeping_bundle(bundle_tar, tmp_path / "sleep.tar"))
        assert runner.run("run", "-d", "-b", bundle, "web", check=False).returncode == 0
        try:
            state = runner.run("state", "web", check=False)
            assert json.loads(state.stdout)["status"] == "running", state.stdout
            assert "web" in runner.run("list", check=False).stdout

            # Arguments arrive as they were given, and the exit code comes back
            result = runner.run("exec", "web", "/bin/sh", "-c", 'echo "a  b"; exit 3', check=False)
            assert result.returncode == 3
            assert "a  b" in result.stdout

            result = runner.run("run", "-d", "-b", bundle, "web", check=False)
            assert result.returncode == 1
            assert "already exists" in result.stdout + result.stderr
            assert runner.run("exec", "web", "true", check=False).returncode == 0, "the bundle was replaced"

            assert runner.run("kill", "web", "KILL", check=False).returncode == 0
        finally:
            assert runner.run("delete", "--force", "web", check=False).returncode == 0
        assert "web" not in runner.run("list", check=False).stdout

    def test_create_and_start(self, request, tool, bundle_tar, tmp_path):
        runner = bundle_tool(request, tool, daemon=True)
        bundle = str(sleeping_bundle(bundle_tar, tmp_path / "sleep.tar"))
        assert runner.run("create", "-b", bundle, "c1", check=False).returncode == 0
        try:
            assert json.loads(runner.run("state", "c1", check=False).stdout)["status"] == "created"
            assert runner.run("start", "c1", check=False).returncode == 0
            assert json.loads(runner.run("state", "c1", check=False).stdout)["status"] == "running"
        finally:
            assert runner.run("delete", "--force", "c1", check=False).returncode == 0

    def test_vlogs(self, request, tool, bundle_tar, tmp_path):
        runner = bundle_tool(request, tool, daemon=True)
        bundle = str(sleeping_bundle(bundle_tar, tmp_path / "sleep.tar"))
        assert runner.run("run", "-d", "-b", bundle, "l1", check=False).returncode == 0
        try:
            for _ in range(10):
                result = runner.run("vlogs", "l1", check=False)
                assert result.returncode == 0, result.stdout
                if "started" in result.stdout:
                    break
                time.sleep(1)
            assert "started" in result.stdout
        finally:
            assert runner.run("delete", "--force", "l1", check=False).returncode == 0
        assert runner.run("vlogs", "l1", check=False).returncode == 1, "the log outlived its container"

    def test_keep(self, request, tool, bundle_tar):
        runner = bundle_tool(request, tool, daemon=True)
        result = runner.run("run", "--keep", "-b", str(bundle_tar), "k1", check=False, timeout=300)
        assert result.returncode == 7, result.stdout
        assert "k1" in runner.run("list", check=False).stdout
        assert runner.run("delete", "k1", check=False).returncode == 0
        assert "k1" not in runner.run("list", check=False).stdout

    def test_no_daemon_with_a_running_daemon(self, request, tool, bundle_tar):
        result = bundle_tool(request, tool, daemon=True).run("--no-daemon", "run", "-b", str(bundle_tar), "n1", check=False)
        assert result.returncode == 1
        assert "can't share the state" in result.stdout + result.stderr

    def test_failure_is_reported(self, request, tool):
        result = bundle_tool(request, tool, daemon=True).run("kill", "nosuch", check=False)
        assert result.returncode != 0
        assert result.stdout + result.stderr


@pytest.mark.parametrize("tool", BUNDLE_TOOLS)
class TestBundleToolErrors:
    """Bad input is refused before booting a guest."""

    def refused(self, request, tool, *args):
        result = bundle_tool(request, tool).run(*args, check=False, timeout=30)
        assert result.returncode == 1
        return result.stdout + result.stderr

    @pytest.mark.parametrize("args", [("run",), ("run", "a", "b")], ids=["no-id", "two-ids"])
    def test_needs_one_id(self, request, tool, args):
        assert "exactly one <container-id>" in self.refused(request, tool, *args)

    @pytest.mark.parametrize("args", [("run",), ("vlogs",)], ids=["run", "vlogs"])
    def test_bad_id(self, request, tool, args):
        assert "Invalid container id" in self.refused(request, tool, *args, "../x")

    @pytest.mark.parametrize("command", ["logs", "memres", "vrun"])
    def test_other_commands_are_unknown(self, request, tool, command):
        assert "Unknown command" in self.refused(request, tool, command, "x")

    def test_not_found(self, request, tool, tmp_path):
        assert "Not found" in self.refused(request, tool, "run", "-b", str(tmp_path / "nope.tar"), "x")

    def test_not_a_bundle(self, request, tool, tmp_path):
        path = tmp_path / "x.tar"
        path.write_bytes(b"not a tar file")
        assert "Not a runtime bundle" in self.refused(request, tool, "run", "-b", str(path), "x")

    def test_directory_without_a_config(self, request, tool, tmp_path):
        assert "Not a runtime bundle" in self.refused(request, tool, "run", "-b", str(tmp_path), "x")

    def test_wrong_architecture(self, request, tool, tmp_path):
        path = tmp_path / "x.tar"
        config = tmp_path / "config.json"
        other = "riscv64"
        config.write_text(json.dumps({"annotations": {"org.opencontainers.image.architecture": other}}))
        with tarfile.open(path, "w") as tar:
            tar.add(config, arcname="config.json")
        assert f"Bundle is for {other}" in self.refused(request, tool, "run", "-b", str(path), "x")

    def test_engine_commands_are_refused(self, request, tool):
        assert "Unknown command: images" in self.refused(request, tool, "images")

    @pytest.mark.parametrize("args", [
        ("create", "x"), ("run", "-d", "x"), ("run", "--keep", "x"), ("list",), ("kill", "x"),
    ], ids=["create", "detach", "keep", "list", "kill"])
    def test_state_needs_the_daemon(self, request, tool, args):
        assert "needs the daemon" in self.refused(request, tool, "--no-daemon", *args)

    @pytest.mark.parametrize("args", [
        ("run", "--pid-file", "/p", "x"), ("create", "--console-socket=/s", "x"), ("exec", "--process", "/p", "x"),
        ("update", "--resources", "/r", "x"), ("--log", "/l", "list"),
    ], ids=["pid-file", "console-socket", "process", "resources", "log"])
    def test_guest_paths_are_refused(self, request, tool, args):
        assert "names a path in the guest" in self.refused(request, tool, *args)

    @pytest.mark.parametrize("command", ["spec", "checkpoint", "restore"])
    def test_unsupported_commands(self, request, tool, command):
        assert f"{command} is not supported" in self.refused(request, tool, command)

    def test_events_without_stats(self, request, tool):
        assert "--stats" in self.refused(request, tool, "events", "x")

    def test_options_after_the_command_are_not_ours(self, request, tool):
        """--version after the command is the runtime's, and isn't answered here."""
        assert "exactly one <container-id>" in self.refused(request, tool, "run", "--version")
