include meta-virt-container.inc

# Only the OCI runtime, runc, with no container engine in front of it. It
# runs OCI runtime bundles, from recipes with OCI_IMAGE_OUTPUT_MODE = "bundle",
# which BUNDLED_CONTAINERS installs to /var/lib/oci-bundles and can start
# with a systemd service. No container networking is installed: by default
# a bundle has its own network namespace with only loopback, and
# OCI_RUNTIME_NAMESPACES without "network" gives it the host's network.
VIRTUAL-RUNTIME_container_engine ??= ""
VIRTUAL-RUNTIME_container_runtime ??= "virtual-runc"
VIRTUAL-RUNTIME_container_networking ??= ""
VIRTUAL-RUNTIME_container_dns ??= ""
VIRTUAL-RUNTIME_container_orchestration ??= ""
