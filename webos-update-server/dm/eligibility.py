"""
Per-baseline OTA eligibility resolver.

Consumes a device fingerprint (from device-scripts/fingerprint.sh) and the policy
in packages/eligibility.json, and returns which packages the device should receive.

Design:
  - The fingerprint VERDICT gates everything. UNSUPPORTED / HAZARD / UNKNOWN -> empty
    plan (refused), regardless of axes.
  - For a real baseline (A-E), each package is evaluated against the capabilities the
    device already has (derived from the L/T/Q axes). A package is eligible when the
    device LACKS the capability it provides ("needs_capability"), or "always", and is
    never eligible when marked "never" (deprecated).
  - auto=true packages go in `deliver` (auto-push); auto=false in `offer` (opt-in).

Dependency-free (stdlib only) so it runs standalone:  python3 dm/eligibility.py
"""
import json
import os
from pathlib import Path

REFUSE_VERDICTS = ("UNSUPPORTED", "HAZARD", "UNKNOWN")

# L/T/Q axis triples for the five defined baselines.
BASELINE_AXES = {
    "A": {"L": 1, "T": 1, "Q": 1},
    "B": {"L": 0, "T": 1, "Q": 0},
    "C": {"L": 1, "T": 0, "Q": 1},
    "D": {"L": 0, "T": 0, "Q": 0},
    "E": {"L": 1, "T": 1, "Q": 0},
}

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "packages" / "eligibility.json"


def load_policy(path=None):
    with open(path or DEFAULT_POLICY_PATH) as f:
        return json.load(f)


def _device_has(capability, axes):
    """Map fingerprint axes -> capabilities the device already has."""
    return {
        "modern_tls": axes.get("T") == 1,
        "modern_browser": axes.get("Q") == 1,
        "lunace_launcher": axes.get("L") == 1,
    }.get(capability, False)


def resolve(fingerprint, policy=None):
    """
    fingerprint: dict with at least {"baseline": "A".."E" | "UNSUPPORTED"|"HAZARD"|"UNKNOWN"}.
                 For A-E the axes are looked up from BASELINE_AXES; callers may also pass
                 explicit "L"/"T"/"Q" to override (e.g. for an UNKNOWN combo you still want
                 to reason about).
    Returns a plan dict.
    """
    policy = policy or load_policy()
    baseline = fingerprint.get("baseline", "UNKNOWN")

    if baseline in REFUSE_VERDICTS:
        return {
            "baseline": baseline,
            "refused": True,
            "reason": policy["gates"]["refuse_verdicts"].get(baseline, "refused"),
            "deliver": [],
            "offer": [],
            "skipped": [],
        }

    axes = {k: fingerprint.get(k) for k in ("L", "T", "Q")}
    if any(axes[k] is None for k in axes):
        axes = BASELINE_AXES.get(baseline, {"L": 0, "T": 0, "Q": 0})

    deliver, offer, skipped = [], [], []
    for pkg in policy["packages"]:
        elig = pkg["eligibility"]
        if elig.get("never"):
            eligible, why = False, "deprecated — never delivered"
        elif elig.get("always"):
            eligible, why = True, "always"
        elif "needs_capability" in elig:
            cap = elig["needs_capability"]
            has = _device_has(cap, axes)
            eligible = not has
            why = ("device lacks %s" % cap) if eligible else ("device already has %s" % cap)
        else:
            eligible, why = False, "no eligibility rule"

        entry = {"id": pkg["id"], "title": pkg["title"], "why": why, "auto": pkg.get("auto", False)}
        if pkg.get("conflict_watch"):
            entry["conflict_watch"] = pkg["conflict_watch"]

        if not eligible:
            skipped.append(entry)
        elif pkg.get("auto"):
            deliver.append(entry)
        else:
            offer.append(entry)

    return {
        "baseline": baseline,
        "refused": False,
        "axes": axes,
        "deliver": deliver,
        "offer": offer,
        "skipped": skipped,
    }


def parse_oneline(line):
    """Parse a fingerprint.sh --oneline string into a dict for resolve()."""
    fp = {}
    for tok in line.strip().split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            if k in ("L", "T", "Q"):
                fp[k] = int(v) if v.isdigit() else None
            elif k == "baseline":
                fp[k] = v
    return fp


def _fmt(entries):
    return ", ".join(e["id"] for e in entries) if entries else "-"


if __name__ == "__main__":
    policy = load_policy()
    print("Policy v%s — %s\n" % (policy["policy_version"], DEFAULT_POLICY_PATH.name))

    print("=== Defined baselines (A-E) ===")
    hdr = "%-4s %-9s  %-26s  %-34s  %s" % ("base", "L/T/Q", "DELIVER (auto)", "OFFER (opt-in)", "SKIPPED")
    print(hdr); print("-" * len(hdr))
    for b in "ABCDE":
        plan = resolve({"baseline": b}, policy)
        axes = plan["axes"]
        print("%-4s %-9s  %-26s  %-34s  %s" % (
            b, "%d/%d/%d" % (axes["L"], axes["T"], axes["Q"]),
            _fmt(plan["deliver"]), _fmt(plan["offer"]), _fmt(plan["skipped"])))

    print("\n=== Gate verdicts (fingerprint refuses before any package) ===")
    for v in REFUSE_VERDICTS:
        plan = resolve({"baseline": v}, policy)
        print("%-12s -> deliver=%s   (%s)" % (v, _fmt(plan["deliver"]), plan["reason"][:70]))

    print("\n=== Why, per baseline ===")
    for b in "ABCDE":
        plan = resolve({"baseline": b}, policy)
        print("\nBaseline %s:" % b)
        for e in plan["deliver"]:
            print("  DELIVER %-16s %s" % (e["id"], e["why"]))
        for e in plan["offer"]:
            print("  offer   %-16s %s" % (e["id"], e["why"]))
        for e in plan["skipped"]:
            print("  skip    %-16s %s" % (e["id"], e["why"]))
