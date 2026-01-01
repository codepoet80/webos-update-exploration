#!/bin/bash
# Build OTA update packages for webOS
# Creates properly formatted IPK files

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/ota-build"
OUTPUT_DIR="$SCRIPT_DIR"

# Build an IPK package from a directory
build_ipk() {
    local name="$1"
    local src_dir="$BUILD_DIR/$name"
    local work_dir="$BUILD_DIR/${name}_work"

    echo "Building $name..."

    # Clean work directory
    rm -rf "$work_dir"
    mkdir -p "$work_dir"

    # Create debian-binary
    echo "2.0" > "$work_dir/debian-binary"

    # Create control.tar.gz with ./ prefix and root ownership
    if [ -d "$src_dir/CONTROL" ]; then
        # Build list of control files with ./ prefix
        local ctrl_files=""
        for item in "$src_dir/CONTROL"/*; do
            ctrl_files="$ctrl_files ./$(basename "$item")"
        done
        (cd "$src_dir/CONTROL" && tar --uid=0 --gid=0 -czf "$work_dir/control.tar.gz" $ctrl_files)
    else
        echo "No CONTROL directory for $name"
        return 1
    fi

    # Create data.tar.gz (everything except CONTROL)
    # Use ./ prefix for paths and root ownership (required by webOS)
    local data_files=""
    for item in "$src_dir"/*; do
        if [ "$(basename "$item")" != "CONTROL" ]; then
            data_files="$data_files ./$(basename "$item")"
        fi
    done

    if [ -n "$data_files" ]; then
        (cd "$src_dir" && tar --uid=0 --gid=0 -czf "$work_dir/data.tar.gz" $data_files)
    else
        # Create empty data.tar.gz with root ownership
        (cd "$src_dir" && tar --uid=0 --gid=0 -czf "$work_dir/data.tar.gz" --files-from /dev/null)
    fi

    # Get version from control file
    local version=$(grep "^Version:" "$src_dir/CONTROL/control" | cut -d' ' -f2)
    local pkg_name=$(grep "^Package:" "$src_dir/CONTROL/control" | cut -d' ' -f2)
    local arch=$(grep "^Architecture:" "$src_dir/CONTROL/control" | cut -d' ' -f2)

    local ipk_name="${pkg_name}_${version}_${arch}.ipk"

    # Create IPK (ar archive)
    (cd "$work_dir" && ar -cr "$OUTPUT_DIR/$ipk_name" debian-binary control.tar.gz data.tar.gz)

    echo "Created: $OUTPUT_DIR/$ipk_name"

    # Calculate MD5
    local md5=$(md5sum "$OUTPUT_DIR/$ipk_name" | cut -d' ' -f1)
    local size=$(stat -f%z "$OUTPUT_DIR/$ipk_name" 2>/dev/null || stat -c%s "$OUTPUT_DIR/$ipk_name" 2>/dev/null)

    echo "  Size: $size bytes"
    echo "  MD5:  $md5"

    # Clean up
    rm -rf "$work_dir"

    # Return info for manifest
    echo "$pkg_name|$version|$ipk_name|$size|$md5"
}

echo "=== Building OTA Update Packages ==="
echo ""

# Build updatefsinfo package
info1=$(build_ipk "updatefsinfo")
echo ""

# Build test app package
info2=$(build_ipk "testapp")
echo ""

echo "=== Build Complete ==="
echo ""
echo "Package info for manifest:"
echo "$info1"
echo "$info2"
