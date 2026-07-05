#!/bin/sh
# webOS OTA device fingerprint
# -----------------------------
# Decides whether a device may receive this OTA, and if so which baseline it is.
# Fully READ-ONLY: inspects files, sizes/hashes, and the ipkg databases only;
# never writes to the system.
#
# Two uses:
#   1. Standalone:  sh fingerprint.sh            (human-readable report)
#                   sh fingerprint.sh --oneline  (single machine line)
#   2. From an update's postinst: source it, call fp_detect, then fp_log so the
#      update records what it matched (and what else it saw) before touching anything:
#          . /path/to/fingerprint.sh
#          fp_detect
#          fp_log /media/internal/ota-update.log
#
# VERDICT PRECEDENCE (first match wins):
#   1. model != Nova-HP-Topaz            -> UNSUPPORTED  (wrong product; NEVER push)
#   2. custom kernel installed           -> HAZARD       (unsafe system state; do not push)
#   3. LunaSysMgr is an unrecognized build -> UNKNOWN     (can't trust L axis; do not push)
#   4. L/T/Q matches a baseline          -> A / B / C / D / E
#   5. anything else                     -> UNKNOWN       (Topaz, undefined combo; do not push)
#
# GATE 1 -- DEVICE MODEL (hard precondition):
#   This OTA targets the full-size Wi-Fi HP TouchPad ("Topaz", BUILDNAME
#   "Nova-HP-Topaz", webOS 3.0.5) ONLY. BUILDNAME is HP-assigned per product and
#   survives the version-string experiment (that only touches PRODUCT_VERSION_STRING
#   and BUILDNUMBER). Known other products, all excluded:
#     - Nova-ATT-Topaz  = AT&T 4G TouchPad  (different hardware + older 3.0.0 base image)
#     - Nova-Dubonnet   = TouchPad Go / Opal (never-released prototype)
#   Excluding by model also stops a stock non-Topaz device from false-matching D.
#
# GATE 2 -- CUSTOM KERNEL (hard hazard):
#   Our OTA drives make-update-uimage and rewrites /boot/uImage; post-update restores
#   /boot/uImage to the STOCK uImage-2.6.35-palm-tenderloin. A device running a
#   community kernel (org.webosinternals.kernels.<device>.<name> -- UberKernel/Warthog
#   class -- or a non-stock /boot/uImage target) would have that silently reverted/
#   broken. So a custom kernel is a do-not-push HAZARD even on a supported Topaz.
#   (Policy choice: change HAZARD->warn below if kernel-modders should be allowed in.)
#
# The three baseline axes (evaluated only after Gates 1 and 2 pass):
#   L = LunaCE launcher    -> /usr/bin/LunaSysMgr md5 matches a known Topaz build.
#                             stock -> L=0; LunaCE (either variant) -> L=1;
#                             unrecognized hash -> UNKNOWN (do NOT assume stock).
#   T = Community TLS 1.3  -> private modern stack at /usr/lib/ssl11. Does NOT change
#                             `openssl version` / system libssl.so.0.9.8 (stay 0.9.8k).
#   Q = nizovn Qt5/QupZilla-> com.nizovn.qupzilla PDK app.
#     L T Q -> A=111 B=010 C=101 D=000 E=110 F=011 G=001 H=100  (all 8 defined)
#     F (011) = stock launcher + community TLS + QupZilla: the common "modernized
#     but skipped the opt-in LunaCE launcher swap" config. Ready (T=1); nothing
#     auto-pushed (already has TLS+browser); LunaCE remains an opt-in offer.
#     G (001) = stock launcher + QupZilla but NO community TLS (QupZilla ships its own
#     crypto, so a browser-only user lands here). H (100) = LunaCE launcher only.
#     Both are T=0 -> not OTA-ready yet (can't reach the HTTPS server); action
#     INSTALL_TLS. Once TLS is added they roll into a ready baseline (G->F, H->E).
#
# EVIDENCE (logged, never gates):
#   - Optware OpenSSL (mobi.optware.openssl): vestigial /opt-only 0.9.8 build. Owns no
#     /usr files, not in the linker path, no ipkg Conflicts -> harmless to our OTA.
#   - AUSMT patches (org.webosinternals.patches.*): logged so a file-level conflict with
#     a shipped package can be spotted; not a gate on its own.

# --- paths ---
FP_LUNA=/usr/bin/LunaSysMgr
FP_SSL11=/usr/lib/ssl11
FP_APPS=/media/cryptofs/apps/usr/palm/applications
FP_BUILDINFO=/etc/palm-build-info
FP_IPKG_DBS="/var/lib/ipkg/status /media/cryptofs/apps/usr/lib/ipkg/status"

# --- model gate ---
FP_MODEL_REQUIRED=Nova-HP-Topaz

# --- reference LunaSysMgr hashes (Topaz 3.0.5 builds; see ~/Projects/LunaCE-All/bin) ---
FP_MD5_STOCK=ac55840a2826f03a04268aa92aed920f        # Topaz stock (5,206,309 B)
FP_MD5_CE_RELEASE=aaf9b3bb4bd9596e7fe9332f466c9851   # LunaCE, build number SHOWN (4,661,821 B)
FP_MD5_CE_CUSTOM=660a5418b70174e6c3cdba769c4186ae    # LunaCE, build number HIDDEN (4,661,821 B)

_fp_size() { wc -c < "$1" 2>/dev/null | tr -d ' '; }
_fp_md5()  { md5sum "$1" 2>/dev/null | cut -d' ' -f1; }
_fp_pkg_installed() {  # $1 = exact package name; searches both ipkg dbs
    for _db in $FP_IPKG_DBS; do
        grep -q "^Package: $1\$" "$_db" 2>/dev/null && return 0
    done
    return 1
}

# fp_detect: sets FP_MODEL FP_MODEL_DESC FP_KERNEL FP_OPTWARE_SSL FP_PATCHES
#            FP_L FP_T FP_Q FP_BASELINE FP_REASON. Returns 0 always.
fp_detect() {
    FP_REASON=""; FP_L=""; FP_T=""; FP_Q=""; FP_LUNA_VARIANT=""

    # ---- model ----------------------------------------------------------
    FP_MODEL=$(grep '^BUILDNAME=' "$FP_BUILDINFO" 2>/dev/null | cut -d= -f2)
    [ -z "$FP_MODEL" ] && FP_MODEL="(unknown)"
    case "$FP_MODEL" in
        Nova-HP-Topaz)  FP_MODEL_DESC="Wi-Fi TouchPad (supported)" ;;
        Nova-ATT-Topaz) FP_MODEL_DESC="AT&T 4G TouchPad (different base image)" ;;
        Nova-Dubonnet)  FP_MODEL_DESC="TouchPad Go / Opal (unreleased prototype)" ;;
        *)              FP_MODEL_DESC="unrecognized non-Topaz model" ;;
    esac

    # ---- safety evidence (model-independent; gather even when unsupported) ----
    # Custom community kernels register under org.webosinternals.kernels.<device>.<name>
    # (NOT "kernel"/"kernel-module-*", which are the STOCK webOS kernel packages, nor
    # "org.webosinternals.kernel"). Also treat a non-stock /boot/uImage target as custom.
    # Verified on real hardware: UberKernel registers as
    # org.webosinternals.kernels.uber-kernel-touchpad, which the namespace prefix
    # matches. Warthog/other variants share the org.webosinternals.kernels.* prefix.
    FP_KERNEL="stock"
    for _db in $FP_IPKG_DBS; do
        _wik=$(grep -h '^Package: org.webosinternals.kernels\.' "$_db" 2>/dev/null | head -1 | sed 's/^Package: //')
        [ -n "$_wik" ] && { FP_KERNEL="CUSTOM ($_wik)"; break; }
    done
    if [ "$FP_KERNEL" = stock ]; then
        _utgt=$(readlink /boot/uImage 2>/dev/null)
        case "$_utgt" in
            ""|uImage-2.6.35-palm-tenderloin) ;;              # stock (or unreadable -> don't false-positive)
            *) FP_KERNEL="CUSTOM (/boot/uImage -> $_utgt)" ;;  # boots a non-stock image
        esac
    fi
    if [ -d "$FP_APPS/mobi.optware.openssl" ] || _fp_pkg_installed mobi.optware.openssl; then
        FP_OPTWARE_SSL="present (vestigial /opt-only 0.9.8; harmless to OTA)"
    else
        FP_OPTWARE_SSL="none"
    fi
    FP_PATCHES=$(grep -h '^Package: org.webosinternals.patches.' $FP_IPKG_DBS 2>/dev/null \
                 | sed 's/^Package: //' | tr '\n' ' ')
    [ -z "$FP_PATCHES" ] && FP_PATCHES="none"

    # ---- GATE 1: model --------------------------------------------------
    if [ "$FP_MODEL" != "$FP_MODEL_REQUIRED" ]; then
        FP_BASELINE=UNSUPPORTED
        FP_REASON="model '$FP_MODEL' ($FP_MODEL_DESC) is not $FP_MODEL_REQUIRED -- Topaz-only OTA; NEVER push"
        return 0
    fi

    # ---- GATE 2: custom kernel -----------------------------------------
    if [ "$FP_KERNEL" != "stock" ]; then
        FP_BASELINE=HAZARD
        FP_REASON="custom kernel present ($FP_KERNEL) -- OTA rewrites /boot/uImage and post-update reverts to the stock kernel, which would clobber it; do not push"
        return 0
    fi

    # ---- Axis L (hash-based; unrecognized -> not trusted) --------------
    FP_LUNA_SIZE=$(_fp_size "$FP_LUNA")
    FP_LUNA_MD5=$(_fp_md5 "$FP_LUNA")
    FP_L_KNOWN=1
    case "$FP_LUNA_MD5" in
        "$FP_MD5_STOCK")      FP_L=0; FP_LUNA_VARIANT="stock" ;;
        "$FP_MD5_CE_CUSTOM")  FP_L=1; FP_LUNA_VARIANT="LunaCE (build# hidden)" ;;
        "$FP_MD5_CE_RELEASE") FP_L=1; FP_LUNA_VARIANT="LunaCE (build# shown)" ;;
        *) FP_L=0; FP_L_KNOWN=0
           FP_LUNA_VARIANT="UNRECOGNIZED launcher ($FP_LUNA_SIZE B, md5 $FP_LUNA_MD5)" ;;
    esac

    # ---- Axis T / Q -----------------------------------------------------
    { [ -d "$FP_SSL11" ] && [ -f "$FP_SSL11/libssl.so.1.1" ]; } && FP_T=1 || FP_T=0
    [ -d "$FP_APPS/com.nizovn.qupzilla" ] && FP_Q=1 || FP_Q=0

    # ---- classify -------------------------------------------------------
    if [ "$FP_L_KNOWN" = 0 ]; then
        FP_BASELINE=UNKNOWN
        FP_REASON="Topaz, but LunaSysMgr is an unrecognized build -- cannot trust the L axis; do not push"
        return 0
    fi
    case "$FP_L$FP_T$FP_Q" in
        111) FP_BASELINE=A ;;
        010) FP_BASELINE=B ;;
        101) FP_BASELINE=C ;;
        000) FP_BASELINE=D ;;
        110) FP_BASELINE=E ;;
        011) FP_BASELINE=F ;;   # stock launcher + community TLS + QupZilla (no LunaCE)
        001) FP_BASELINE=G ;;   # stock launcher + QupZilla, no TLS (needs TLS first)
        100) FP_BASELINE=H ;;   # LunaCE launcher only, no TLS/browser (needs TLS first)
        *)   FP_BASELINE=UNKNOWN
             FP_REASON="Topaz, but L$FP_L T$FP_T Q$FP_Q is not a defined baseline -- deploy policy TBD; do not push" ;;
    esac
    return 0
}

# fp_oneline: one machine-parseable line.
fp_oneline() {
    fp_detect
    echo "baseline=$FP_BASELINE model=$FP_MODEL L=${FP_L:-.} T=${FP_T:-.} Q=${FP_Q:-.} kernel=$FP_KERNEL optware_ssl=$FP_OPTWARE_SSL patches=[$FP_PATCHES]"
}

# fp_report: human-readable, with the evidence behind each decision.
fp_report() {
    fp_detect
    echo "===== webOS OTA device fingerprint ====="
    echo "build-info : $(head -1 "$FP_BUILDINFO" 2>/dev/null) / build $(grep '^BUILDNUMBER=' "$FP_BUILDINFO" 2>/dev/null | cut -d= -f2)"
    echo "model      : $FP_MODEL   ($FP_MODEL_DESC)"
    echo "kernel     : $FP_KERNEL"
    echo "optware ssl: $FP_OPTWARE_SSL"
    echo "patches    : $FP_PATCHES"
    if [ "$FP_BASELINE" = "UNSUPPORTED" ] || [ "$FP_BASELINE" = "HAZARD" ]; then
        echo
        echo "  => VERDICT: $FP_BASELINE  (do not push)"
        echo "     $FP_REASON"
        echo "========================================"
        return 0
    fi
    echo
    echo "  L LunaCE launcher : $FP_L   ($FP_LUNA_VARIANT)"
    echo "  T Community TLS1.3 : $FP_T   ($([ "$FP_T" = 1 ] && echo "/usr/lib/ssl11 present" || echo "/usr/lib/ssl11 absent"))"
    echo "  Q nizovn Qt5/QupZilla : $FP_Q   ($([ "$FP_Q" = 1 ] && echo "com.nizovn.qupzilla installed" || echo "not installed"))"
    echo
    echo "  => MATCHED BASELINE: $FP_BASELINE"
    [ -n "$FP_REASON" ] && echo "     $FP_REASON"
    echo "========================================"
}

# fp_json: machine-readable status for the "Get Ready for OTA" app.
# Adds an `action` code (what the user must do) and a `ready` boolean on top of
# the raw fingerprint. action: UNSUPPORTED | REMOVE_KERNEL | REVIEW | INSTALL_TLS | READY.
# "ready" for the OTA == supported Topaz + stock kernel + modern TLS present (T==1).
fp_json() {
    fp_detect
    case "$FP_BASELINE" in
        UNSUPPORTED) _act=UNSUPPORTED;   _ready=false ;;
        HAZARD)      _act=REMOVE_KERNEL; _ready=false ;;
        UNKNOWN)     _act=REVIEW;        _ready=false ;;
        *) if [ "$FP_T" = 1 ]; then _act=READY; _ready=true; else _act=INSTALL_TLS; _ready=false; fi ;;
    esac
    _pj=""
    for _p in $FP_PATCHES; do
        [ "$_p" = none ] && continue
        [ -n "$_pj" ] && _pj="$_pj,"
        _pj="$_pj\"$_p\""
    done
    printf '{'
    printf '"verdict":"%s",' "$FP_BASELINE"
    printf '"action":"%s",' "$_act"
    printf '"ready":%s,' "$_ready"
    printf '"model":"%s",' "$FP_MODEL"
    printf '"model_desc":"%s",' "$FP_MODEL_DESC"
    printf '"L":"%s","T":"%s","Q":"%s",' "${FP_L:-}" "${FP_T:-}" "${FP_Q:-}"
    printf '"kernel":"%s",' "$FP_KERNEL"
    printf '"optware_ssl":"%s",' "$FP_OPTWARE_SSL"
    printf '"patches":[%s],' "$_pj"
    printf '"reason":"%s"' "$FP_REASON"
    printf '}\n'
}

# fp_log FILE: append a timestamped oneline result (for use in postinst).
fp_log() {
    _f="${1:-/media/internal/ota-update.log}"
    fp_detect
    echo "$(date 2>/dev/null) fingerprint: baseline=$FP_BASELINE model=$FP_MODEL L=${FP_L:-.} T=${FP_T:-.} Q=${FP_Q:-.} kernel=$FP_KERNEL optware_ssl=$FP_OPTWARE_SSL patches=[$FP_PATCHES]${FP_REASON:+ -- $FP_REASON}" >> "$_f" 2>/dev/null
}

case "$1" in
    --oneline) fp_oneline ;;
    --json)    fp_json ;;
    --log)     fp_log "$2"; cat "${2:-/media/internal/ota-update.log}" 2>/dev/null | tail -1 ;;
    *)         fp_report ;;
esac
