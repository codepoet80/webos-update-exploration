# Update Baselines

Device A - Luna Community Edition (build number shown), QupZilla with the nizovn QT5 SDK, Community OpenSSL TLS1.3 patches
Device B - Stock Luna, Community OpenSSL TLS1.3 patches
Device C - Luna Community Edition, QupZilla with the nizovn QT5 SDK, Stock OpenSSL
Device D - Fully Stock
Device E - Luna Community Edition modded to hide build number, Community OpenSSL TLS1.3 patches

# Additional defined baselines (no dedicated reference device)

A–E above each have a physical reference device. F–H complete the full 8-combination
L/T/Q matrix so every real-world config classifies to a defined baseline instead of
falling to UNKNOWN/REVIEW. F was found in the field during the 1.1.11 beta (testers
achunt + moustacheboy); G and H are the remaining two combinations, added for coverage.

Device F - Stock Luna, QupZilla with the nizovn QT5 SDK, Community OpenSSL TLS1.3 patches
Device G - Stock Luna, QupZilla with the nizovn QT5 SDK, Stock OpenSSL
Device H - Luna Community Edition, no QupZilla, Stock OpenSSL

# L/T/Q axes and OTA readiness

Each baseline is a triple of independent axes (see device-scripts/fingerprint.sh):
L = LunaCE launcher · T = Community TLS 1.3 stack (/usr/lib/ssl11) · Q = nizovn QupZilla.

    base  L T Q   config                                        OTA-ready?
    A     1 1 1   LunaCE + TLS + QupZilla                        yes
    B     0 1 0   Stock Luna + TLS                               yes
    C     1 0 1   LunaCE + QupZilla, no TLS                      no  -> INSTALL_TLS
    D     0 0 0   Fully stock                                    no  -> INSTALL_TLS
    E     1 1 0   LunaCE (build# hidden) + TLS                   yes
    F     0 1 1   Stock Luna + TLS + QupZilla                    yes
    G     0 0 1   Stock Luna + QupZilla, no TLS                  no  -> INSTALL_TLS (-> F once TLS added)
    H     1 0 0   LunaCE only, no TLS/browser                    no  -> INSTALL_TLS (-> E once TLS added)

Readiness keys ONLY on T (modern TLS): a device is offered the OTA only when T=1,
because reaching the HTTPS update server requires it. T=0 baselines (C, D, G, H) are
never offered the OTA — they get action INSTALL_TLS until the TLS stack is installed.

# Sources

Luna Community Edition: https://github.com/webOS-ports/LunaCE
    - Luna Community Edition installer with mod: ~/Projects/LunaCE-All
Community OpenSSL TLS 1.3 patches: ~/Projects/OpenSSL-legacyWebOS
QupZilla with nizovn QT5 SDK: ~/Projects/qupzilla
