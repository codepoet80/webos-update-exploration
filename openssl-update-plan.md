# OpenSSL Update Package Plan

## Current State

**Installed Version:** OpenSSL 0.9.8k (December 2011)

**Files:**
```
/usr/bin/openssl              # CLI tool (449KB)
/usr/lib/libssl.so.0.9.8      # SSL library (298KB)
/usr/lib/libssl.so            # symlink -> libssl.so.0.9.8
/usr/lib/libcrypto.so.0.9.8   # Crypto library (1.5MB)
/usr/lib/libcrypto.so         # symlink -> libcrypto.so.0.9.8
/usr/lib/ssl/openssl.cnf      # Configuration
/etc/ssl/openssl.cnf          # Configuration (duplicate)
```

**Architecture:** ARMv7 (EABI5), GNU/Linux 2.6.14

**Critical Dependencies (will break if ABI changes):**
- `luna-sysmgr` - Main UI system
- `browserserver` - Web browser engine
- `luna-webkit` - WebKit browser
- `curl` / `libcurl` - HTTP client
- `nodejs` - Node.js runtime
- `keymanager` - Key/credential storage
- `hostapd` - WiFi AP daemon
- `gnutls` - GNU TLS (uses libcrypto)
- 15+ other system packages

## The Challenge

OpenSSL 0.9.8k is **severely outdated** with numerous CVEs. However, the entire webOS system links against `libssl.so.0.9.8` and `libcrypto.so.0.9.8`. Replacing these requires:

1. **ABI Compatibility** - New libraries must work with existing binaries
2. **SONAME Preservation** - Must provide `.so.0.9.8` files or symlinks
3. **Cross-compilation** - Must build for ARMv7

## Recommended Approach

### Option A: OpenSSL 1.0.2u (Recommended)

**Why 1.0.2u:**
- Last LTS release of the 1.0.x branch (EOL Dec 2019, but still buildable)
- Maintains backward compatibility with 0.9.8 API
- Adds TLS 1.1/1.2 support
- Includes critical security fixes
- Can be built with `0.9.8` SONAME for drop-in replacement

**Risks:** Moderate - API mostly compatible, some edge cases may break

### Option B: OpenSSL 1.1.1w

**Why 1.1.1:**
- Long-term support until Sep 2023
- TLS 1.3 support
- Better security

**Risks:** High - ABI changed significantly, would require shipping both old and new libraries, apps would still use old version

### Option C: LibreSSL

**Why LibreSSL:**
- Drop-in replacement for OpenSSL
- Better security defaults
- Active maintenance

**Risks:** Moderate - Some API differences, may need testing

---

## Implementation Plan (Option A - OpenSSL 1.0.2u)

### Phase 1: Setup Cross-Compilation Environment

```bash
# Need ARM cross-compiler toolchain
# Options:
# 1. Linaro GCC toolchain (arm-linux-gnueabi)
# 2. Buildroot with ARMv7 target
# 3. crosstool-NG

# Example with Linaro toolchain:
export CROSS_COMPILE=arm-linux-gnueabi-
export CC=${CROSS_COMPILE}gcc
export AR=${CROSS_COMPILE}ar
export RANLIB=${CROSS_COMPILE}ranlib
```

### Phase 2: Build OpenSSL 1.0.2u

```bash
# Download source
wget https://www.openssl.org/source/openssl-1.0.2u.tar.gz
tar xzf openssl-1.0.2u.tar.gz
cd openssl-1.0.2u

# Configure for ARMv7
./Configure linux-armv4 \
    --prefix=/usr \
    --openssldir=/usr/lib/ssl \
    shared \
    no-asm \
    -march=armv7-a \
    -mfloat-abi=softfp

# Build
make CC="${CROSS_COMPILE}gcc" AR="${CROSS_COMPILE}ar r" RANLIB="${CROSS_COMPILE}ranlib"

# The built libraries will be:
# libssl.so.1.0.0
# libcrypto.so.1.0.0
```

### Phase 3: Create Compatibility Layer

Since existing apps expect `libssl.so.0.9.8`, we have two options:

**Option 3a: Rebuild with custom SONAME (Preferred)**
```bash
# Modify Makefile to use 0.9.8 SONAME
sed -i 's/SHLIB_MAJOR=1/SHLIB_MAJOR=0/' Makefile
sed -i 's/SHLIB_MINOR=0.0/SHLIB_MINOR=9.8/' Makefile
make clean && make
```

**Option 3b: Symlink approach**
```bash
# After install, create compatibility symlinks
ln -sf libssl.so.1.0.0 libssl.so.0.9.8
ln -sf libcrypto.so.1.0.0 libcrypto.so.0.9.8
```

### Phase 4: Package Structure

```
openssl-update/
├── CONTROL/
│   ├── control
│   ├── preinst        # Backup original files
│   ├── postinst       # Set up symlinks, verify
│   └── prerm          # Restore original if needed
│
└── data/
    └── usr/
        ├── bin/
        │   └── openssl
        ├── lib/
        │   ├── libssl.so.0.9.8      # New library with old SONAME
        │   ├── libssl.so -> libssl.so.0.9.8
        │   ├── libcrypto.so.0.9.8
        │   └── libcrypto.so -> libcrypto.so.0.9.8
        └── lib/ssl/
            └── openssl.cnf
```

### Phase 5: Package Scripts

**CONTROL/control:**
```
Package: openssl-update
Version: 1.0.2u-1
Section: security
Priority: required
Architecture: armv7
Maintainer: webOS Update Project
Description: OpenSSL security update (0.9.8k -> 1.0.2u)
 Replaces vulnerable OpenSSL 0.9.8k with 1.0.2u.
 Provides TLS 1.1/1.2 support and critical security fixes.
Conflicts: openssl
Replaces: openssl, libssl, libcrypto
```

**CONTROL/preinst:**
```bash
#!/bin/sh
# Backup original OpenSSL files
BACKUP_DIR="/var/lib/openssl-backup"
mkdir -p "$BACKUP_DIR"

cp -a /usr/lib/libssl.so* "$BACKUP_DIR/"
cp -a /usr/lib/libcrypto.so* "$BACKUP_DIR/"
cp -a /usr/bin/openssl "$BACKUP_DIR/"
cp -a /usr/lib/ssl/openssl.cnf "$BACKUP_DIR/" 2>/dev/null || true

echo "Original OpenSSL backed up to $BACKUP_DIR"
exit 0
```

**CONTROL/postinst:**
```bash
#!/bin/sh
# Verify installation
if ! /usr/bin/openssl version; then
    echo "ERROR: OpenSSL verification failed!"
    exit 1
fi

# Update library cache if ldconfig exists
ldconfig 2>/dev/null || true

# Log success
echo "OpenSSL updated successfully"
/usr/bin/openssl version > /media/internal/openssl-update.log
date >> /media/internal/openssl-update.log

exit 0
```

**CONTROL/prerm:**
```bash
#!/bin/sh
# Restore original files if backup exists
BACKUP_DIR="/var/lib/openssl-backup"

if [ -d "$BACKUP_DIR" ]; then
    echo "Restoring original OpenSSL..."
    cp -a "$BACKUP_DIR"/libssl.so* /usr/lib/
    cp -a "$BACKUP_DIR"/libcrypto.so* /usr/lib/
    cp -a "$BACKUP_DIR"/openssl /usr/bin/
    ldconfig 2>/dev/null || true
fi

exit 0
```

---

## Build Script

Create `build-openssl-update.sh`:

```bash
#!/bin/bash
set -e

OPENSSL_VERSION="1.0.2u"
CROSS_COMPILE="${CROSS_COMPILE:-arm-linux-gnueabi-}"
BUILD_DIR="$(pwd)/build"
OUTPUT_DIR="$(pwd)/output"

# Check for cross-compiler
if ! command -v ${CROSS_COMPILE}gcc &> /dev/null; then
    echo "ERROR: Cross-compiler not found: ${CROSS_COMPILE}gcc"
    echo "Install with: apt install gcc-arm-linux-gnueabi"
    exit 1
fi

# Download OpenSSL
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

if [ ! -f "openssl-${OPENSSL_VERSION}.tar.gz" ]; then
    wget "https://www.openssl.org/source/openssl-${OPENSSL_VERSION}.tar.gz"
fi

tar xzf "openssl-${OPENSSL_VERSION}.tar.gz"
cd "openssl-${OPENSSL_VERSION}"

# Configure
./Configure linux-armv4 \
    --prefix=/usr \
    --openssldir=/usr/lib/ssl \
    shared \
    no-asm \
    -march=armv7-a

# Patch SONAME for 0.9.8 compatibility
sed -i 's/SHLIB_MAJOR=1/SHLIB_MAJOR=0/' Makefile
sed -i 's/SHLIB_MINOR=0.0/SHLIB_MINOR=9.8/' Makefile

# Build
make CC="${CROSS_COMPILE}gcc" \
     AR="${CROSS_COMPILE}ar r" \
     RANLIB="${CROSS_COMPILE}ranlib" \
     -j$(nproc)

# Create package structure
PKG_DIR="$OUTPUT_DIR/openssl-update"
mkdir -p "$PKG_DIR"/{CONTROL,data/usr/bin,data/usr/lib,data/usr/lib/ssl}

# Copy built files
cp apps/openssl "$PKG_DIR/data/usr/bin/"
cp libssl.so.0.9.8 "$PKG_DIR/data/usr/lib/"
cp libcrypto.so.0.9.8 "$PKG_DIR/data/usr/lib/"
cd "$PKG_DIR/data/usr/lib"
ln -sf libssl.so.0.9.8 libssl.so
ln -sf libcrypto.so.0.9.8 libcrypto.so
cd -
cp apps/openssl.cnf "$PKG_DIR/data/usr/lib/ssl/"

# Strip binaries
${CROSS_COMPILE}strip "$PKG_DIR/data/usr/bin/openssl"
${CROSS_COMPILE}strip "$PKG_DIR/data/usr/lib/"*.so.*

echo "Build complete! Package files in: $PKG_DIR"
echo "Run create-ipk.sh to create the final IPK"
```

---

## Testing Plan

### Before Deployment (on build machine)
1. Verify ARM binary: `file output/openssl-update/data/usr/bin/openssl`
2. Check library dependencies: `readelf -d output/openssl-update/data/usr/lib/libssl.so.0.9.8`
3. Verify SONAME: `objdump -p output/openssl-update/data/usr/lib/libssl.so.0.9.8 | grep SONAME`

### On Device (staged testing)
1. Copy files to `/tmp` first, test manually
2. Verify `LD_PRELOAD=/tmp/libssl.so.0.9.8 /tmp/openssl version`
3. Test HTTPS: `LD_PRELOAD=/tmp/libssl.so.0.9.8 curl https://example.com`
4. If working, deploy via IPK

### Post-Install Verification
1. Check version: `openssl version` should show `1.0.2u`
2. Test TLS 1.2: `openssl s_client -connect google.com:443 -tls1_2`
3. Verify browser still works
4. Check `/media/internal/openssl-update.log`

---

## Rollback Plan

If the update causes issues:

```bash
# On device via SSH/novacom:
mount -o remount,rw /

# Restore from backup
cp -a /var/lib/openssl-backup/libssl.so* /usr/lib/
cp -a /var/lib/openssl-backup/libcrypto.so* /usr/lib/
cp -a /var/lib/openssl-backup/openssl /usr/bin/
ldconfig

mount -o remount,ro /
reboot
```

---

## Security Improvements

Updating from 0.9.8k to 1.0.2u addresses:

- **CVE-2014-0160** (Heartbleed) - Fixed in 1.0.1g
- **CVE-2014-0224** (CCS Injection) - Fixed in 1.0.1h
- **POODLE, BEAST, CRIME** attacks - Mitigations added
- **TLS 1.2 support** - Required by most modern servers
- **ECDHE support** - Better forward secrecy
- **SHA-256 certificates** - Required for modern sites
- 100+ other CVE fixes

---

## Alternative: Prebuilt Binaries

If cross-compilation is difficult, check:

1. **webOS Ports** - May have prebuilt packages
2. **Preware feeds** - Community packages for webOS
3. **OpenEmbedded/Yocto** - ARMv7 builds available

---

## Next Steps

1. [ ] Set up ARM cross-compilation toolchain
2. [ ] Build OpenSSL 1.0.2u with 0.9.8 SONAME
3. [ ] Test on device in `/tmp` before system install
4. [ ] Create IPK package with backup/restore scripts
5. [ ] Test full update via webos-update-server
6. [ ] Document any compatibility issues found
