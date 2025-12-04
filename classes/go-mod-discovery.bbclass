#
# Copyright OpenEmbedded Contributors
#
# SPDX-License-Identifier: MIT
#

# go-mod-discovery.bbclass
#
# Provides a do_discover_modules task for Go projects that downloads complete
# module metadata from proxy.golang.org for use with the bootstrap strategy.
#
# USAGE:
#   1. Add to recipe: inherit go-mod-discovery
#   2. Set required variables (see CONFIGURATION below)
#   3. Run discovery: bitbake <recipe> -c discover_modules
#      (This automatically: downloads modules, extracts metadata, regenerates recipe)
#   4. Build normally: bitbake <recipe>
#
# CONFIGURATION:
#
# Required (must be set by recipe):
#
#   GO_MOD_DISCOVERY_BUILD_TARGET - Build target for go build
#                                   Example: "./cmd/server" or "./..."
#
# Optional (have sensible defaults):
#
#   GO_MOD_DISCOVERY_SRCDIR     - Directory containing go.mod
#                                 Default: "${S}/src/import" (standard Go recipe layout)
#
#   GO_MOD_DISCOVERY_BUILD_TAGS - Build tags for go build
#                                 Default: "${TAGS}" (uses recipe's TAGS variable if set)
#                                 Example: "netcgo osusergo static_build"
#
#   GO_MOD_DISCOVERY_LDFLAGS    - Linker flags for go build
#                                 Default: "-w -s"
#                                 Example: "-X main.version=${PV} -w -s"
#
#   GO_MOD_DISCOVERY_GOPATH     - GOPATH for discovery build
#                                 Default: "${S}/src/import/.gopath:${S}/src/import/vendor"
#
#   GO_MOD_DISCOVERY_OUTPUT     - Output binary path
#                                 Default: "${WORKDIR}/discovery-build-output"
#
#   GO_MOD_DISCOVERY_DIR        - Persistent cache location
#                                 Default: "${TOPDIR}/go-mod-discovery/${PN}/${PV}"
#
#   GO_MOD_DISCOVERY_MODULES_JSON - Output path for extracted module metadata
#                                   Default: "${GO_MOD_DISCOVERY_DIR}/modules.json"
#
#   GO_MOD_DISCOVERY_SKIP_EXTRACT - Set to "1" to skip automatic extraction
#                                   Default: "0" (extraction runs automatically)
#
#   GO_MOD_DISCOVERY_SKIP_GENERATE - Set to "1" to skip automatic recipe generation
#                                    Default: "0" (generation runs automatically)
#
#   GO_MOD_DISCOVERY_GIT_REPO     - Git repository URL for recipe generation
#                                   Example: "https://github.com/rancher/k3s.git"
#                                   Required for automatic generation
#
#   GO_MOD_DISCOVERY_GIT_REF      - Git ref (commit/tag) for recipe generation
#                                   Default: "${SRCREV}" (uses recipe's SRCREV)
#
#   GO_MOD_DISCOVERY_RECIPEDIR    - Output directory for generated .inc files
#                                   Default: "${FILE_DIRNAME}" (recipe's directory)
#
# MINIMAL EXAMPLE (manual generation - no GIT_REPO set):
#
#   TAGS = "netcgo osusergo"
#   GO_MOD_DISCOVERY_BUILD_TARGET = "./cmd/myapp"
#   inherit go-mod-discovery
#   # Run: bitbake myapp -c discover_modules
#   # Then manually: oe-go-mod-fetcher.py --discovered-modules ... --git-repo ...
#
# FULL AUTOMATIC EXAMPLE (all-in-one discovery + generation):
#
#   TAGS = "netcgo osusergo"
#   GO_MOD_DISCOVERY_BUILD_TARGET = "./cmd/myapp"
#   GO_MOD_DISCOVERY_GIT_REPO = "https://github.com/example/myapp.git"
#   inherit go-mod-discovery
#   # Run: bitbake myapp -c discover_modules
#   # Recipe files are automatically regenerated!
#
# See: meta-virtualization/scripts/BOOTSTRAP-STRATEGY.md (Approach B)
#
# This task is NOT part of the normal build - it must be explicitly invoked
# via bitbake <recipe> -c discover_modules
#
# PERSISTENT CACHE: The discovery cache is stored in ${TOPDIR}/go-mod-discovery/${PN}/${PV}/
# instead of ${WORKDIR}. This ensures the cache survives `bitbake <recipe> -c cleanall`
# since TOPDIR is the build directory root (e.g., /path/to/build/).
# To clean the discovery cache, run: rm -rf ${TOPDIR}/go-mod-discovery/${PN}/${PV}/

# Required variable (must be set by recipe)
GO_MOD_DISCOVERY_BUILD_TARGET ?= ""

# Optional variables with sensible defaults for standard Go recipe layout
GO_MOD_DISCOVERY_SRCDIR ?= "${S}/src/import"
GO_MOD_DISCOVERY_BUILD_TAGS ?= "${TAGS}"
GO_MOD_DISCOVERY_LDFLAGS ?= "-w -s"
GO_MOD_DISCOVERY_GOPATH ?= "${S}/src/import/.gopath:${S}/src/import/vendor"
GO_MOD_DISCOVERY_OUTPUT ?= "${WORKDIR}/discovery-build-output"

# Persistent discovery cache location - survives cleanall
GO_MOD_DISCOVERY_DIR ?= "${TOPDIR}/go-mod-discovery/${PN}/${PV}"

# Output JSON file for discovered modules (used by oe-go-mod-fetcher.py --discovered-modules)
GO_MOD_DISCOVERY_MODULES_JSON ?= "${GO_MOD_DISCOVERY_DIR}/modules.json"

# Set to "1" to skip automatic extraction (only download modules, don't extract metadata)
GO_MOD_DISCOVERY_SKIP_EXTRACT ?= "0"

# Set to "1" to skip automatic recipe regeneration (only discover and extract)
GO_MOD_DISCOVERY_SKIP_GENERATE ?= "0"

# Git repository URL for recipe generation (required if SKIP_GENERATE != "1")
# Example: "https://github.com/rancher/k3s.git"
GO_MOD_DISCOVERY_GIT_REPO ?= ""

# Git ref (commit/tag) for recipe generation - defaults to recipe's SRCREV
GO_MOD_DISCOVERY_GIT_REF ?= "${SRCREV}"

# Recipe directory for generated .inc files - defaults to recipe's directory
GO_MOD_DISCOVERY_RECIPEDIR ?= "${FILE_DIRNAME}"

# Empty default for TAGS if not set by recipe (avoids undefined variable errors)
TAGS ?= ""

# Shell task that mirrors do_compile but with network access and discovery GOMODCACHE
do_discover_modules() {
    # Validate required variable
    if [ -z "${GO_MOD_DISCOVERY_BUILD_TARGET}" ]; then
        bbfatal "GO_MOD_DISCOVERY_BUILD_TARGET must be set (e.g., './cmd/server' or './...')"
    fi

    # Validate source directory exists and contains go.mod
    if [ ! -d "${GO_MOD_DISCOVERY_SRCDIR}" ]; then
        bbfatal "GO_MOD_DISCOVERY_SRCDIR does not exist: ${GO_MOD_DISCOVERY_SRCDIR}
Hint: Set GO_MOD_DISCOVERY_SRCDIR in your recipe if go.mod is not in \${S}/src/import"
    fi
    if [ ! -f "${GO_MOD_DISCOVERY_SRCDIR}/go.mod" ]; then
        bbfatal "go.mod not found in GO_MOD_DISCOVERY_SRCDIR: ${GO_MOD_DISCOVERY_SRCDIR}
Hint: Set GO_MOD_DISCOVERY_SRCDIR to the directory containing go.mod"
    fi

    # Use PERSISTENT cache location outside WORKDIR to survive cleanall
    # This is stored in ${TOPDIR}/go-mod-discovery/${PN}/${PV}/ so it persists
    DISCOVERY_CACHE="${GO_MOD_DISCOVERY_DIR}/cache"

    # Create required directories first
    mkdir -p "${DISCOVERY_CACHE}"
    mkdir -p "${WORKDIR}/go-tmp"
    mkdir -p "$(dirname "${GO_MOD_DISCOVERY_OUTPUT}")"

    # Use discovery-cache instead of the normal GOMODCACHE
    export GOMODCACHE="${DISCOVERY_CACHE}"

    # Enable network access to proxy.golang.org
    export GOPROXY="https://proxy.golang.org,direct"
    export GOSUMDB="sum.golang.org"

    # Standard Go environment - use recipe-provided GOPATH or default
    export GOPATH="${GO_MOD_DISCOVERY_GOPATH}:${STAGING_DIR_TARGET}/${prefix}/local/go"
    export CGO_ENABLED="1"
    export GOTOOLCHAIN="local"

    # Use system temp directory for Go's work files
    export GOTMPDIR="${WORKDIR}/go-tmp"

    # Disable excessive debug output from BitBake environment
    unset GODEBUG

    # Build tags from recipe configuration
    TAGS="${GO_MOD_DISCOVERY_BUILD_TAGS}"

    # Change to source directory
    cd "${GO_MOD_DISCOVERY_SRCDIR}"

    echo "======================================================================"
    echo "MODULE DISCOVERY: ${PN} ${PV}"
    echo "======================================================================"
    echo "GOMODCACHE:    ${GOMODCACHE}"
    echo "GOPROXY:       ${GOPROXY}"
    echo "Source dir:    ${GO_MOD_DISCOVERY_SRCDIR}"
    echo "Build target:  ${GO_MOD_DISCOVERY_BUILD_TARGET}"
    echo "Build tags:    ${TAGS:-<none>}"
    echo "LDFLAGS:       ${GO_MOD_DISCOVERY_LDFLAGS}"
    echo ""

    # Use native go binary (not cross-compiler)
    GO_NATIVE="${STAGING_DIR_NATIVE}${bindir_native}/go"

    # NOTE: Do NOT run go mod tidy during discovery - it can upgrade versions in go.mod
    # without adding checksums to go.sum, causing version mismatches.
    # The source's go.mod/go.sum should already be correct for the commit.
    # echo "Running: go mod tidy"
    # ${GO_NATIVE} mod tidy
    # ${GO_NATIVE} mod download  # If tidy is re-enabled, this ensures go.sum gets all checksums

    echo ""
    echo "Running: go build (to discover all modules)..."

    # Build to discover ALL modules that would be used at compile time
    # This is better than 'go mod download' because it handles build tags correctly
    BUILD_CMD="${GO_NATIVE} build -v -trimpath"
    if [ -n "${TAGS}" ]; then
        BUILD_CMD="${BUILD_CMD} -tags \"${TAGS}\""
    fi
    BUILD_CMD="${BUILD_CMD} -ldflags \"${GO_MOD_DISCOVERY_LDFLAGS}\""
    BUILD_CMD="${BUILD_CMD} -o \"${GO_MOD_DISCOVERY_OUTPUT}\" ${GO_MOD_DISCOVERY_BUILD_TARGET}"

    echo "Executing: ${BUILD_CMD}"
    eval ${BUILD_CMD}

    echo ""
    echo "Fetching ALL modules referenced in go.sum..."
    # go build downloads .zip files but not always .info files
    # We need .info files for VCS metadata (Origin.URL, Origin.Hash)
    # Extract unique module@version pairs from go.sum and download each
    # go.sum format: "module version/go.mod hash" or "module version hash"
    #
    # IMPORTANT: We must download ALL versions, including /go.mod-only entries!
    # When GOPROXY=off during compile, Go may need these for dependency resolution.
    # Strip the /go.mod suffix to get the base version, then download it.
    awk '{gsub(/\/go\.mod$/, "", $2); print $1 "@" $2}' go.sum | sort -u | while read modver; do
        ${GO_NATIVE} mod download "$modver" 2>/dev/null || true
    done

    # Download ALL modules in the complete dependency graph.
    # The go.sum loop above only gets direct dependencies. Replace directives
    # can introduce transitive deps that aren't in go.sum but are needed at
    # compile time when GOPROXY=off. `go mod download all` resolves and
    # downloads the entire module graph, including transitive dependencies.
    echo ""
    echo "Downloading complete module graph (including transitive deps)..."
    ${GO_NATIVE} mod download all 2>&1 || echo "Warning: some modules may have failed to download"

    # Additionally scan for any modules that go build downloaded but don't have .info
    # This ensures we capture everything that was fetched dynamically
    echo ""
    echo "Ensuring .info files for all cached modules..."
    find "${GOMODCACHE}/cache/download" -name "*.zip" 2>/dev/null | while read zipfile; do
        # Extract module@version from path like: .../module/@v/version.zip
        version=$(basename "$zipfile" .zip)
        moddir=$(dirname "$zipfile")
        infofile="${moddir}/${version}.info"
        if [ ! -f "$infofile" ]; then
            # Reconstruct module path from directory structure
            # cache/download/github.com/foo/bar/@v/v1.0.0.zip -> github.com/foo/bar@v1.0.0
            modpath=$(echo "$moddir" | sed "s|${GOMODCACHE}/cache/download/||" | sed 's|/@v$||')
            echo "  Fetching .info for: ${modpath}@${version}"
            ${GO_NATIVE} mod download "${modpath}@${version}" 2>/dev/null || true
        fi
    done

    # Download transitive deps of REPLACED modules.
    # Replace directives can point to older versions whose deps aren't in the MVS
    # graph. At compile time with GOPROXY=off, Go validates the replaced version's
    # go.mod. We parse replace directives and download each replacement version,
    # which fetches all its transitive dependencies.
    echo ""
    echo "Downloading dependencies of replaced modules..."

    # Extract replace directives: "old_module => new_module new_version"
    awk '/^replace \($/,/^\)$/ {if ($0 !~ /^replace|^\)/) print}' go.mod | \
    grep "=>" | while read line; do
        # Parse: github.com/foo/bar => github.com/baz/qux v1.2.3
        new_module=$(echo "$line" | awk '{print $(NF-1)}')
        new_version=$(echo "$line" | awk '{print $NF}')

        if [ -n "$new_module" ] && [ -n "$new_version" ] && [ "$new_version" != "=>" ]; then
            echo "  Replace target: ${new_module}@${new_version}"
            # Download this specific version - Go will fetch all its dependencies
            ${GO_NATIVE} mod download "${new_module}@${new_version}" 2>/dev/null || true
        fi
    done

    # Count modules discovered
    MODULE_COUNT=$(find "${GOMODCACHE}/cache/download" -name "*.info" 2>/dev/null | wc -l)

    echo ""
    echo "======================================================================"
    echo "DISCOVERY COMPLETE"
    echo "======================================================================"
    echo "Modules discovered: ${MODULE_COUNT}"
    echo "Cache location:     ${GOMODCACHE}"

    # Extract module metadata automatically (unless skipped)
    if [ "${GO_MOD_DISCOVERY_SKIP_EXTRACT}" != "1" ]; then
        echo ""
        echo "Extracting module metadata..."

        # Find the extraction script relative to this class file
        EXTRACT_SCRIPT="${COREBASE}/../meta-virtualization/scripts/extract-discovered-modules.py"
        if [ ! -f "${EXTRACT_SCRIPT}" ]; then
            # Try alternate location
            EXTRACT_SCRIPT="$(dirname "${COREBASE}")/meta-virtualization/scripts/extract-discovered-modules.py"
        fi
        if [ ! -f "${EXTRACT_SCRIPT}" ]; then
            # Last resort - search in layer path
            for layer in ${BBLAYERS}; do
                if [ -f "${layer}/scripts/extract-discovered-modules.py" ]; then
                    EXTRACT_SCRIPT="${layer}/scripts/extract-discovered-modules.py"
                    break
                fi
            done
        fi

        if [ -f "${EXTRACT_SCRIPT}" ]; then
            python3 "${EXTRACT_SCRIPT}" \
                --gomodcache "${GOMODCACHE}" \
                --output "${GO_MOD_DISCOVERY_MODULES_JSON}"
            EXTRACT_RC=$?
            if [ $EXTRACT_RC -eq 0 ]; then
                echo ""
                echo "✓ Module metadata extracted to: ${GO_MOD_DISCOVERY_MODULES_JSON}"
            else
                bbwarn "Module extraction failed (exit code $EXTRACT_RC)"
                bbwarn "You can run manually: python3 ${EXTRACT_SCRIPT} --gomodcache ${GOMODCACHE} --output ${GO_MOD_DISCOVERY_MODULES_JSON}"
                EXTRACT_RC=1  # Mark as failed for generation check
            fi
        else
            bbwarn "Could not find extract-discovered-modules.py script"
            bbwarn "Run manually: extract-discovered-modules.py --gomodcache ${GOMODCACHE} --output ${GO_MOD_DISCOVERY_MODULES_JSON}"
            EXTRACT_RC=1  # Mark as failed for generation check
        fi
    else
        echo ""
        echo "Skipping automatic extraction (GO_MOD_DISCOVERY_SKIP_EXTRACT=1)"
        EXTRACT_RC=1  # Skip generation too if extraction skipped
    fi

    # Step 3: Generate recipe .inc files (unless skipped or extraction failed)
    if [ "${GO_MOD_DISCOVERY_SKIP_GENERATE}" != "1" ] && [ "${EXTRACT_RC:-0}" = "0" ]; then
        # Validate required git repo
        if [ -z "${GO_MOD_DISCOVERY_GIT_REPO}" ]; then
            bbwarn "GO_MOD_DISCOVERY_GIT_REPO not set - skipping recipe generation"
            bbwarn "Set GO_MOD_DISCOVERY_GIT_REPO in your recipe to enable automatic generation"
            echo ""
            echo "NEXT STEP: Regenerate recipe manually:"
            echo ""
            echo "   ./meta-virtualization/scripts/oe-go-mod-fetcher.py \\"
            echo "     --discovered-modules ${GO_MOD_DISCOVERY_MODULES_JSON} \\"
            echo "     --git-repo <your-git-repo-url> \\"
            echo "     --git-ref ${GO_MOD_DISCOVERY_GIT_REF} \\"
            echo "     --recipedir ${GO_MOD_DISCOVERY_RECIPEDIR}"
        else
            echo ""
            echo "Generating recipe .inc files..."

            # Find the fetcher script (same search as extraction script)
            FETCHER_SCRIPT="${COREBASE}/../meta-virtualization/scripts/oe-go-mod-fetcher.py"
            if [ ! -f "${FETCHER_SCRIPT}" ]; then
                FETCHER_SCRIPT="$(dirname "${COREBASE}")/meta-virtualization/scripts/oe-go-mod-fetcher.py"
            fi
            if [ ! -f "${FETCHER_SCRIPT}" ]; then
                for layer in ${BBLAYERS}; do
                    if [ -f "${layer}/scripts/oe-go-mod-fetcher.py" ]; then
                        FETCHER_SCRIPT="${layer}/scripts/oe-go-mod-fetcher.py"
                        break
                    fi
                done
            fi

            if [ -f "${FETCHER_SCRIPT}" ]; then
                python3 "${FETCHER_SCRIPT}" \
                    --discovered-modules "${GO_MOD_DISCOVERY_MODULES_JSON}" \
                    --git-repo "${GO_MOD_DISCOVERY_GIT_REPO}" \
                    --git-ref "${GO_MOD_DISCOVERY_GIT_REF}" \
                    --recipedir "${GO_MOD_DISCOVERY_RECIPEDIR}"
                GENERATE_RC=$?
                if [ $GENERATE_RC -eq 0 ]; then
                    echo ""
                    echo "✓ Recipe files regenerated in: ${GO_MOD_DISCOVERY_RECIPEDIR}"
                else
                    bbwarn "Recipe generation failed (exit code $GENERATE_RC)"
                    bbwarn "Check the output above for errors"
                fi
            else
                bbwarn "Could not find oe-go-mod-fetcher.py script"
                bbwarn "Run manually: oe-go-mod-fetcher.py --discovered-modules ${GO_MOD_DISCOVERY_MODULES_JSON} --git-repo ${GO_MOD_DISCOVERY_GIT_REPO} --git-ref ${GO_MOD_DISCOVERY_GIT_REF} --recipedir ${GO_MOD_DISCOVERY_RECIPEDIR}"
            fi
        fi
    elif [ "${GO_MOD_DISCOVERY_SKIP_GENERATE}" = "1" ]; then
        echo ""
        echo "Skipping automatic generation (GO_MOD_DISCOVERY_SKIP_GENERATE=1)"
        echo ""
        echo "NEXT STEP: Regenerate recipe manually:"
        echo ""
        echo "   ./meta-virtualization/scripts/oe-go-mod-fetcher.py \\"
        echo "     --discovered-modules ${GO_MOD_DISCOVERY_MODULES_JSON} \\"
        echo "     --git-repo <your-git-repo-url> \\"
        echo "     --git-ref <your-git-ref> \\"
        echo "     --recipedir ${GO_MOD_DISCOVERY_RECIPEDIR}"
    fi

    echo ""
    echo "NOTE: Cache is stored OUTSIDE WORKDIR in a persistent location."
    echo "      This cache survives 'bitbake ${PN} -c cleanall'!"
    echo "      To clean: rm -rf ${GO_MOD_DISCOVERY_DIR}"
    echo ""
    echo "======================================================================"
}

# Make this task manually runnable (not part of default build)
# Run after unpack and patch so source is available
addtask discover_modules after do_patch

# Task dependencies - need source unpacked and full toolchain available
# Depend on do_prepare_recipe_sysroot to get cross-compiler for CGO
do_discover_modules[depends] = "${PN}:do_prepare_recipe_sysroot"

# Enable network access for this task ONLY
do_discover_modules[network] = "1"

# Don't create stamp file - allow running multiple times
do_discover_modules[nostamp] = "1"

# Track all configuration variables for proper task hashing
do_discover_modules[vardeps] += "GO_MOD_DISCOVERY_DIR GO_MOD_DISCOVERY_SRCDIR \
    GO_MOD_DISCOVERY_BUILD_TARGET GO_MOD_DISCOVERY_BUILD_TAGS \
    GO_MOD_DISCOVERY_LDFLAGS GO_MOD_DISCOVERY_GOPATH GO_MOD_DISCOVERY_OUTPUT \
    GO_MOD_DISCOVERY_MODULES_JSON GO_MOD_DISCOVERY_SKIP_EXTRACT \
    GO_MOD_DISCOVERY_SKIP_GENERATE GO_MOD_DISCOVERY_GIT_REPO \
    GO_MOD_DISCOVERY_GIT_REF GO_MOD_DISCOVERY_RECIPEDIR"

# Task to clean the persistent discovery cache
# Usage: bitbake <recipe> -c clean_discovery
do_clean_discovery() {
    if [ -d "${GO_MOD_DISCOVERY_DIR}" ]; then
        echo "Removing discovery cache: ${GO_MOD_DISCOVERY_DIR}"
        rm -rf "${GO_MOD_DISCOVERY_DIR}"
        echo "Discovery cache removed."
    else
        echo "Discovery cache not found: ${GO_MOD_DISCOVERY_DIR}"
    fi
}

addtask clean_discovery
do_clean_discovery[nostamp] = "1"
do_clean_discovery[vardeps] += "GO_MOD_DISCOVERY_DIR"
