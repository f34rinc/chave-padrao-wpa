#!/usr/bin/env python3
"""classify_oui.py - classify NEW OUI prefixes (the ones analyze_wigle.py flags)
as ISP-CPE (-> data/claro_ouis.csv) or consumer/3rd-party (-> data/consumer_ouis.csv).

It looks up each OUI's vendor on maclookup.app, then classifies it by matching
that vendor against the vendor names ALREADY catalogued in the two CSVs. That
makes it self-maintaining: every vendor the project has ever filed is "known",
so repeats auto-resolve and only a genuinely new vendor is flagged UNKNOWN for a
human decision. Output is the verdict plus the ready-to-paste CSV row.

Only public IEEE OUI data is used - no coordinates, no credentials, nothing
sensitive. Safe to run and to share.

Usage:
    python tools/classify_oui.py 44:E4:EE 40:AE:30 98:00:6A
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
CLARO_CSV = os.path.join(DATA, "claro_ouis.csv")
CONSUMER_CSV = os.path.join(DATA, "consumer_ouis.csv")

# generic corporate filler that doesn't identify a brand
_STOP = {"corporation", "corp", "inc", "incorporated", "ltd", "limited", "co",
         "company", "technologies", "technology", "tech", "broadband",
         "international", "systems", "system", "usa", "llc", "sas", "gmbh", "ag",
         "bv", "networks", "network", "electronics", "communications",
         "communication", "router", "modem", "the", "of", "and", "home",
         "connected", "digital", "devices", "device"}


def _words(name):
    """Distinctive lowercase word tokens of a vendor/company string, minus
    corporate filler. 'TP-Link Systems Inc' -> {'tplink'};
    'Vantiva/Technicolor' -> {'vantiva','technicolor'}."""
    out = set()
    for part in re.split(r"[\s/.,]+", (name or "").lower()):
        w = re.sub(r"[^a-z0-9]", "", part)
        if w and w not in _STOP:
            out.add(w)
    return out


def load_rows(csv_path):
    """[(oui, vendor), ...] from an OUI CSV, skipping comments/blank lines."""
    rows = []
    with open(csv_path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            p = s.split(",")
            rows.append((p[0], p[1] if len(p) > 1 else ""))
    return rows


def vendor_index(rows):
    """Build {brand_word: canonical_vendor} from CSV rows. When a word maps to
    several catalogued spellings, prefer the DOMINANT one (most rows), tie-broken
    by the shorter name - so 'arris' -> 'Arris/CommScope' and 'technicolor' ->
    'Vantiva/Technicolor'. The 'vendor' placeholder row is ignored."""
    freq = Counter(v for _, v in rows if v and v.lower() != "vendor")
    best = {}   # word -> (count, vendor)
    for vendor, cnt in freq.items():
        for w in _words(vendor):
            cur = best.get(w)
            if (cur is None or cnt > cur[0]
                    or (cnt == cur[0] and len(vendor) < len(cur[1]))):
                best[w] = (cnt, vendor)
    return {w: v for w, (_, v) in best.items()}


def classify(company, isp_idx, consumer_idx):
    """(category, canonical_vendor) for a looked-up company string:
    'claro' (ISP-CPE), 'consumer', or 'unknown' when no known brand word matches."""
    words = _words(company)
    for w in words:
        if w in isp_idx:
            return "claro", isp_idx[w]
    for w in words:
        if w in consumer_idx:
            return "consumer", consumer_idx[w]
    return "unknown", None


def row_for(oui, category, vendor, today=None):
    """The ready-to-paste CSV line for the destination file."""
    if category == "claro":
        return f"{oui},{vendor},"
    if category == "consumer":
        today = today or datetime.date.today().isoformat()
        return f"{oui},{vendor},consumer/renamed,{today}"
    return None


def lookup(oui, fetch=None):
    """Vendor company string for an OUI via maclookup.app, or '' on any failure."""
    if fetch is None:
        def fetch(url):
            req = urllib.request.Request(url, headers={"User-Agent": "chave-padrao-oui-classify"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.read().decode()
    try:
        return (json.loads(fetch(f"https://api.maclookup.app/v2/macs/{oui}")).get("company") or "").strip()
    except (urllib.error.URLError, ValueError, OSError):
        return ""


def main(argv):
    ouis = [a.strip().upper() for a in argv if a.strip()]
    if not ouis:
        print("usage: python tools/classify_oui.py <OUI> [OUI ...]   e.g. 44:E4:EE 40:AE:30")
        return 2
    isp = vendor_index(load_rows(CLARO_CSV))
    cons = vendor_index(load_rows(CONSUMER_CSV))
    today = datetime.date.today().isoformat()

    results = []
    for i, oui in enumerate(ouis):
        if i:
            time.sleep(1.2)   # be polite to maclookup.app's free tier
        company = lookup(oui)
        cat, vendor = classify(company, isp, cons)
        results.append((oui, company, cat, vendor))

    unknown = [r for r in results if r[2] == "unknown"]
    if unknown:
        print("=== UNKNOWN vendor - classify by hand (add to the right CSV) ===")
        for oui, company, _, _ in unknown:
            print(f"  {oui}  vendor={company or '(no IEEE registration)'}  -> claro vs consumer?")
        print()

    classified = [r for r in results if r[2] != "unknown"]
    if classified:
        print("=== ready to paste ===")
        for oui, company, cat, vendor in classified:
            dest = "data/claro_ouis.csv" if cat == "claro" else "data/consumer_ouis.csv"
            print(f"  # {oui} = {company} -> {dest}")
            print(f"  {row_for(oui, cat, vendor, today)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
