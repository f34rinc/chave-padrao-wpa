#!/usr/bin/env python3
"""
schemes.py — VIVO / VIVOFIBRA (Telefónica Brasil) default-WPA-key scheme.

Chave-Padrão WPA keeps CLARO and its cable-brand sibling NET on the main script's
"octet-3 + SSID tail" path (they share that construction). VIVO and VIVOFIBRA use a
different rule, handled here:

    default SSID  = VIVO-<4H>  /  VIVOFIBRA-<4H>     (last 4 hex of the base MAC)
                    also VIVOFIBRA-WIFI6-<4H> and a trailing -5G / -5GHz band tag
    default key   = the MAC minus its first octet    (last 5 bytes = 10 hex)
                    VIVO-      -> UPPERCASE   e.g. MAC AA:BB:CC:DD:EE:FF -> BBCCDDEEFF
                    VIVOFIBRA- -> lowercase   e.g. MAC AA:BB:CC:DD:EE:FF -> bbccddeeff
                    (example MAC fabricated; all examples here are illustrative)

DETECT-ONLY POLICY
------------------
Field data (a ~150k-network WiGLE survey, 2026) shows the derivable KEY is a trait of
OLD MitraStar firmware only, and that those OUIs cover barely ~0.3% of the deployed
VIVOFIBRA base — ~92% sit on OUIs not yet researched. Emitting a "likely key" for those
would be a confidently-wrong guess. So this module DERIVES a key in exactly ONE case:

    gate == "weak"  AND  the capture is the base MAC
    (the SSID's 4-hex tail equals the BSSID's last 4 hex)

Everything else — a hardened OUI, an un-researched ("unknown") OUI, a weak OUI captured
on its 5 GHz/secondary BSSID, or a renamed SSID — is IDENTIFIED and explained, but no
key is presented (`key` is None, `determined` is False). The base-MAC check matters:
the key is baseMAC[1:], and a 5 GHz/virtual BSSID's lower bytes differ from the base
MAC, so BSSID[2:] off the wrong radio is a wrong key. The SSID tail only reveals the
base MAC's last 4 hex, so a non-base capture cannot be fully derived from the name.

OUI sets come from independent label + handshake research (2026); extend WEAK_OUIS as
more labels land — each addition turns a whole block from "identify only" into
"derivable". Implementation is original — the derivation was reconstructed from hardware
labels and verified against captured handshakes, not copied from any tool.
"""

import re

# MitraStar OUIs whose weak-era firmware sets key = MAC minus 1st octet (label-confirmed).
WEAK_OUIS = {"345760", "acc682", "acc662", "a433d7", "9897d1"}

# OUIs confirmed to ship RANDOM keys — never derive on these.
HARDENED_OUIS = {
    "840bbb",                        # MitraStar GPT-2741 / GPT-2541-N2 (new gen)
    "94eaea", "fc1263",              # Askey (BR RTF3507, ES RTF8115)
    "107223",                        # Tellescom-built Askey RTF3507VW (VIVOFIBRA label = random key)
    "e4ab89", "ccd4a1",              # Movistar MitraStar
    "e04136",                        # Made-in-China DSL-100HN-T1
    "d47226", "44e4ee", "149448",    # ZTE / WNC / Blu Castle — the Vivo-Internet line
}

_VIVOFIBRA_RE = re.compile(r"^VIVOFIBRA-", re.I)
# VIVO-<hex> but NOT "Vivo-Internet-" (a different, hardened multi-ODM line). A real
# VIVO-<4H> tail is hex, so it can never begin with the non-hex word "INTERNET".
_VIVO_RE = re.compile(r"^VIVO-(?!INTERNET)", re.I)

# Strict DEFAULT-form tail: the 4-hex device marker, allowing the VIVOFIBRA "WIFI6-"
# infix and an optional trailing band tag. A renamed SSID (VIVO-NALA, "VIVOFIBRA 149",
# VIVO-5G) has no such tail and parses to None — mirrors the CLARO path returning None
# for renamed networks, so the tool never guesses off a name it doesn't recognise.
_BAND = r"(?:[ _-]?(?:5G(?:HZ)?|5|2\.4G|2G))?"
_VIVO_TAIL = re.compile(r"^VIVO-([0-9A-Fa-f]{4})" + _BAND + r"$", re.I)
_VIVOFIBRA_TAIL = re.compile(r"^VIVOFIBRA-(?:WIFI6-)?([0-9A-Fa-f]{4})" + _BAND + r"$", re.I)


def _norm(mac):
    """'aa:bb:..' / 'AABB..' -> 12-char lowercase hex, or None if not a full MAC."""
    h = re.sub(r"[^0-9A-Fa-f]", "", mac or "")
    return h.lower() if len(h) == 12 else None


def detect(essid):
    """'VIVOFIBRA' | 'VIVO' | None for a Telefónica SSID prefix (default OR renamed)."""
    e = (essid or "").strip()
    if _VIVOFIBRA_RE.match(e):
        return "VIVOFIBRA"
    if _VIVO_RE.match(e):
        return "VIVO"
    return None


def parse_tail(essid):
    """The 4-hex device tail of a DEFAULT-form VIVO/VIVOFIBRA SSID (lowercased), else
    None. None means the SSID is renamed / non-default — nothing to derive from the name."""
    e = (essid or "").strip()
    m = _VIVOFIBRA_TAIL.match(e) or _VIVO_TAIL.match(e)
    return m.group(1).lower() if m else None


def derive(essid, bssid):
    """
    Scheme result for a VIVO/VIVOFIBRA SSID, else None (not a Telefónica SSID, or a
    malformed BSSID).

    Returns a dict:
        isp        'VIVO' | 'VIVOFIBRA'
        oui        lowercased 6-hex OUI of the BSSID
        tail       the SSID's 4-hex device marker, or None if renamed/non-default
        default    True when the SSID is the recognised default form (tail is not None)
        gate       'weak' | 'hardened' | 'unknown'      (OUI confidence)
        base_mac   True when this capture IS the key-source MAC (tail == BSSID last 4)
        determined True ONLY when gate == 'weak' AND base_mac (the one derivable case)
        key        the derived key when `determined`, else None (detect-only elsewhere)
        case       'upper' (VIVO) | 'lower' (VIVOFIBRA)
        keyspace   1 when determined, else None
        note       one-line human explanation of why (not) derivable
    """
    isp = detect(essid)
    if not isp:
        return None
    b = _norm(bssid)
    if not b:
        return None

    oui = b[:6]
    tail = parse_tail(essid)
    default = tail is not None
    case = "lower" if isp == "VIVOFIBRA" else "upper"

    if oui in WEAK_OUIS:
        gate = "weak"
    elif oui in HARDENED_OUIS:
        gate = "hardened"
    else:
        gate = "unknown"

    base_mac = default and b[-4:] == tail
    determined = default and gate == "weak" and base_mac

    if determined:
        key = b[2:].lower() if isp == "VIVOFIBRA" else b[2:].upper()
        keyspace = 1
    else:
        key, keyspace = None, None

    if not default:
        note = "renamed / non-default SSID - the name reveals no key."
    elif gate == "hardened":
        note = "hardened ODM (random factory key) - not derivable; needs real cracking."
    elif gate == "weak":
        if base_mac:
            note = "confirmed-weak MitraStar block, base-MAC capture: key = MAC minus its 1st octet."
        else:
            note = ("weak MitraStar OUI, but this is the 5 GHz/secondary BSSID - the key "
                    "needs the 2.4 GHz base MAC; capture that radio.")
    else:  # unknown
        note = ("OUI not yet researched - VIVOFIBRA key derivation is unconfirmed for this "
                "hardware. Identify only; capture a handshake to crack it directly.")

    return {"isp": isp, "oui": oui, "tail": tail, "default": default, "gate": gate,
            "base_mac": base_mac, "determined": determined, "key": key, "case": case,
            "keyspace": keyspace, "note": note}
