#!/usr/bin/env python3
"""Unit tests for the Claro default-key logic. Stdlib only:

    python -m unittest discover -s tests -v      # or:  python tests/test_claro.py

Covers SSID parsing (every field variant), OUI extraction, the beacon-derivation
(BSSID octet 3 + SSID tail), the .hc22000 parser, and the WiGLE analyzer's
single-vs-split classification and locally-administered-BSSID handling. All data
here is fabricated.
"""
import os
import sys
import json
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "utils"))

import chave_padrao as k            # noqa: E402
import analyze_wigle as w          # noqa: E402
import charset_mask as cm          # noqa: E402
import schemes as sc               # noqa: E402


class TestSsidParsing(unittest.TestCase):
    def test_variants(self):
        cases = {
            "CLARO_2G3A9C2D":       ("3a9c2d", None),   # banded 2.4G
            "CLARO_5G3A9C2D":       ("3a9c2d", None),   # banded 5G
            "CLARO_2.4G3A9C2D":     ("3a9c2d", None),   # explicit 2.4G token
            "CLARO_3A9C2D":         ("3a9c2d", None),   # no band
            "CLARO_3A9C2D-5G-BH":   ("3a9c2d", None),   # mesh backhaul suffix
            "CLARO_112233-IoT":     ("112233", None),   # IoT suffix
            "CLARO_2G12345678":     ("345678", "12345678"),  # embedded full-8
            "NET_5G3A9C2D":         ("3a9c2d", None),   # NET = Claro cable brand, same scheme
            "NET_2G112233":         ("112233", None),
        }
        for essid, expected in cases.items():
            self.assertEqual(k.parse_claro_ssid(essid), expected, essid)

    def test_case_insensitive(self):
        self.assertEqual(k.parse_claro_ssid("claro_2g3a9c2d"), ("3a9c2d", None))

    def test_non_default_rejected(self):
        for essid in ("CLARO_MOVEL", "CLARO_Mesh", "NET_VIRTUA_9988",
                      "MyHomeWiFi", "", "CLARO_"):
            self.assertEqual(k.parse_claro_ssid(essid), (None, None), essid)


class TestOuiAndDerivation(unittest.TestCase):
    def test_oui_of(self):
        self.assertEqual(k.oui_of("aabb12ddee00"), "AA:BB:12")
        self.assertEqual(k.oui_of("743AEF3A9C2D"), "74:3A:EF")

    def test_derived_key(self):
        # The single-OUI derivation used in handle_net: BSSID octet 3 + SSID tail.
        bssid, essid = "aabb12ddee00", "CLARO_5G345678"
        tail6, _ = k.parse_claro_ssid(essid)
        key = bssid[4:6].upper() + tail6.upper()
        self.assertEqual(key, "12345678")

    def test_full8_is_determined(self):
        tail6, full8 = k.parse_claro_ssid("CLARO_2G12345678")
        self.assertEqual(full8.upper(), "12345678")


class TestCaptureParser(unittest.TestCase):
    LINE = ("WPA*02*68330658ae024a468fba3ba845aaaad2*AABB12DDEE00*ca45f2ff68f2*"
            "434c41524f5f3547333435363738*"
            "561815e0306c26c6460ab0e2d45b4d64bfbaeedadf3bf0a3998c34d3e7399eeb*"
            "0103005f02010a00000000000000000001*02\n")

    def test_parse_22000(self):
        with tempfile.NamedTemporaryFile("w", suffix=".hc22000",
                                         delete=False, encoding="utf-8") as fh:
            fh.write(self.LINE)
            path = fh.name
        try:
            nets = k.parse_22000(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(nets), 1)
        self.assertEqual(nets[0]["essid"], "CLARO_5G345678")
        self.assertEqual(nets[0]["bssid"], "aabb12ddee00")


class TestSqliteParser(unittest.TestCase):
    def _make_db(self, d):
        import sqlite3
        p = os.path.join(d, "WiGLE Database Backup")     # extensionless, like the real export
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE network (bssid TEXT, ssid TEXT, type TEXT)")
        con.executemany("INSERT INTO network VALUES (?,?,?)", [
            ("AA:BB:CC:DD:EE:FF", "CLARO_5GDDEEFF", "W"),
            ("11:22:33:44:55:66", "SomeWifi", "W"),
            ("99:88:77:66:55:44", "MyHeadphones", "E"),   # bluetooth -> must be skipped
        ])
        con.commit()
        con.close()
        return p

    def test_detects_and_parses_sqlite(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._make_db(d)
            self.assertTrue(w._is_sqlite(p))              # detected by magic, no extension
            txt = os.path.join(d, "x.csv")
            with open(txt, "w") as fh:
                fh.write("MAC,SSID\n")
            self.assertFalse(w._is_sqlite(txt))           # a text file is not sqlite
            got = {r["bssid"]: r["essid"] for r in w.parse_any(p)}   # routes via magic
            self.assertEqual(got, {"aabbccddeeff": "CLARO_5GDDEEFF",
                                   "112233445566": "SomeWifi"})       # BT row dropped, bssid normalized


class TestAnalyzerLocalAdmin(unittest.TestCase):
    def test_is_local_admin(self):
        self.assertTrue(w.is_local_admin("aabb12ddee00"))    # 0xAA U/L bit set
        self.assertTrue(w.is_local_admin("223543f00000"))    # 0x22 U/L bit set
        self.assertFalse(w.is_local_admin("743aef3a9c2d"))   # 0x74 universal
        self.assertFalse(w.is_local_admin("203543f00000"))   # 0x20 universal

    def test_base_oui_clears_ul_bit(self):
        # U/L bit lives in octet 1 only; octet 3 (the key byte) is never touched.
        self.assertEqual(w.base_oui_of("223543f00000"), "20:35:43")
        self.assertEqual(w.base_oui_of("22:35:43"), "20:35:43")
        self.assertEqual(w.base_oui_of("aabb12ddee00"), "A8:BB:12")

    def test_ssid_variant_labels(self):
        self.assertEqual(w.ssid_variant("CLARO_2G3A9C2D"), "banded 2.4GHz")
        self.assertEqual(w.ssid_variant("CLARO_5G3A9C2D"), "banded 5GHz")
        self.assertEqual(w.ssid_variant("CLARO_3A9C2D"), "no-band")
        self.assertEqual(w.ssid_variant("CLARO_ABCDEF-5G-BH"), "mesh backhaul (-5G-BH)")
        self.assertEqual(w.ssid_variant("CLARO_112233-IoT"), "IoT (-IoT)")


class TestAnalyzerClassify(unittest.TestCase):
    def test_single_oui(self):
        c = w.classify({"essid": "CLARO_2G3A9C2D", "bssid": "743aef3a9c2d"})
        self.assertTrue(c["kind"].startswith("single-OUI"))
        self.assertFalse(c["local"])

    def test_split_oui_arris(self):
        # C8:52:61 is the confirmed ARRIS/CommScope split-OUI router block.
        c = w.classify({"essid": "CLARO_ABCDEF", "bssid": "c85261abcdef"})
        self.assertTrue(c["kind"].startswith("split-OUI"))

    def test_renamed_is_not_a_gateway(self):
        self.assertIsNone(w.classify({"essid": "MyHomeWiFi", "bssid": "743aef3a9c2d"}))


class TestCharsetMaskPositional(unittest.TestCase):
    def test_positional_collapses_and_contains_key(self):
        # Fabricated: BSSID A0:B1:C2:3A:9C:2E, SSID CLARO_2G3A9C2D.
        # Derived key = C2 (BSSID octet 3) + 3A9C2D = C23A9C2D. Only the last
        # nibble differs (E in the radio MAC vs D in the SSID tail).
        cand = cm.positional_candidates("a0b1c23a9c2e", "CLARO_2G3A9C2D", 8)
        cmd, ks = cm.positional_command("cap.hc22000", cand)
        self.assertEqual(ks, 2)                                  # keyspace collapses to 2
        key = "C23A9C2D"
        self.assertTrue(all(key[i] in cand[i] for i in range(8)))   # still contains the key
        self.assertIn("C23A9C2", cmd)                            # high bytes are literals

    def test_positional_always_includes_ssid_tail(self):
        cand = cm.positional_candidates("a1b2c3250b33", "CLARO_5G250B2E", 8)
        key = "C3250B2E"                                         # C3 + 250B2E
        self.assertTrue(all(key[i] in cand[i] for i in range(8)))


class TestCharsetMaskOptions(unittest.TestCase):
    # ---- max-length parsing/validation (min stays pinned at 8) ----
    def test_max_len_valid(self):
        self.assertEqual(cm.coerce_max_len("10", 8), (10, None))

    def test_max_len_boundaries_ok(self):
        self.assertEqual(cm.coerce_max_len("8", 8), (8, None))
        self.assertEqual(cm.coerce_max_len("63", 8), (63, None))

    def test_max_len_below_min_rejected(self):
        val, err = cm.coerce_max_len("7", 8)
        self.assertEqual(val, 8)                 # keeps current
        self.assertIsNotNone(err)

    def test_max_len_above_max_rejected(self):
        val, err = cm.coerce_max_len("64", 8)
        self.assertEqual(val, 8)
        self.assertIsNotNone(err)

    def test_max_len_non_integer_rejected(self):
        val, err = cm.coerce_max_len("abc", 12)
        self.assertEqual(val, 12)                # keeps whatever was current
        self.assertIsNotNone(err)

    # ---- case parsing/validation ----
    def test_case_valid_and_case_insensitive(self):
        self.assertEqual(cm.coerce_case("lower", "upper"), ("lower", None))
        self.assertEqual(cm.coerce_case("MIXED", "upper"), ("mixed", None))

    def test_case_bogus_rejected(self):
        val, err = cm.coerce_case("sideways", "upper")
        self.assertEqual(val, "upper")           # keeps current
        self.assertIsNotNone(err)

    # ---- interactive prompt control commands vs. paths ----
    def test_prompt_len_command(self):
        self.assertEqual(cm.parse_prompt_command("len 10"), ("len", "10"))
        self.assertEqual(cm.parse_prompt_command("maxlen 12"), ("len", "12"))

    def test_prompt_case_command(self):
        self.assertEqual(cm.parse_prompt_command("case lower"), ("case", "lower"))

    def test_prompt_bare_case_words(self):
        self.assertEqual(cm.parse_prompt_command("lower"), ("case", "lower"))
        self.assertEqual(cm.parse_prompt_command("MIXED"), ("case", "mixed"))
        self.assertEqual(cm.parse_prompt_command("upper"), ("case", "upper"))

    def test_prompt_positional_toggle(self):
        for word in ("pos", "positional", "-p"):
            self.assertEqual(cm.parse_prompt_command(word), ("positional", None), word)

    def test_prompt_help(self):
        for word in ("help", "h", "-h"):
            self.assertEqual(cm.parse_prompt_command(word), ("help", None), word)

    def test_prompt_path_passthrough(self):
        line = r"C:\caps\CLARO_handshake.hc22000"
        self.assertEqual(cm.parse_prompt_command(line), ("path", line))

    # ---- charset case modes ----
    def test_hex_charset_upper_is_default(self):
        cs = cm.hex_charset("6802b816dcc0", "")
        self.assertEqual(cs, cs.upper())
        self.assertIn("B", cs)

    def test_hex_charset_lower(self):
        cs = cm.hex_charset("6802b816dcc0", "", case="lower")
        self.assertEqual(cs, cs.lower())
        self.assertIn("b", cs)
        self.assertNotIn("B", cs)

    def test_hex_charset_mixed_has_both_cases(self):
        cs = cm.hex_charset("6802b816dcc0", "", case="mixed")
        self.assertIn("B", cs)                   # letter present in both cases
        self.assertIn("b", cs)
        self.assertEqual(cs.count("0"), 1)       # digit not duplicated

    # ---- positional tier honours case ----
    def test_positional_lower_uses_lowercase(self):
        cand = cm.positional_candidates("a0b1c23a9c2e", "CLARO_2G3A9C2D", 8, case="lower")
        cmd, ks = cm.positional_command("cap.hc22000", cand, case="lower")
        self.assertEqual(ks, 2)
        self.assertIn("c23a9c2", cmd)            # high-byte literals now lowercase
        self.assertNotIn("C23A9C2", cmd)

    def test_positional_mixed_doubles_letters(self):
        cand = cm.positional_candidates("a0b1c23a9c2e", "CLARO_2G3A9C2D", 8, case="mixed")
        self.assertIn("C", cand[0])              # high nibble 'C' -> {C, c}
        self.assertIn("c", cand[0])


class TestCharsetMaskScheme(unittest.TestCase):
    # VIVO/VIVOFIBRA default keys are the MAC minus octet 1 = 10 hex; VIVO upper,
    # VIVOFIBRA lower. charset_mask auto-defaults length/case for those SSIDs.

    # ---- scheme_defaults: (isp, max_len, case) hint from the SSID ----
    def test_scheme_vivo(self):
        self.assertEqual(cm.scheme_defaults("VIVO-BBCC"), ("VIVO", 10, "upper"))

    def test_scheme_vivofibra(self):
        self.assertEqual(cm.scheme_defaults("VIVOFIBRA-1234"), ("VIVOFIBRA", 10, "lower"))

    def test_scheme_vivofibra_wifi6_band(self):
        self.assertEqual(cm.scheme_defaults("VIVOFIBRA-WIFI6-1234-5G"),
                         ("VIVOFIBRA", 10, "lower"))

    def test_scheme_vivo_renamed_still_detected(self):
        self.assertEqual(cm.scheme_defaults("VIVO-NALA"), ("VIVO", 10, "upper"))

    def test_scheme_vivo_internet_excluded(self):
        self.assertEqual(cm.scheme_defaults("VIVO-INTERNET-1234"), (None, None, None))

    def test_scheme_non_vivo(self):
        self.assertEqual(cm.scheme_defaults("CLARO_2G3A9C2D"), (None, None, None))

    # ---- resolve_settings: explicit value wins, else scheme hint, else defaults ----
    def test_resolve_vivofibra_auto(self):
        self.assertEqual(cm.resolve_settings("VIVOFIBRA-1234", None, None),
                         ("VIVOFIBRA", 10, "lower"))

    def test_resolve_vivo_auto(self):
        self.assertEqual(cm.resolve_settings("VIVO-BBCC", None, None),
                         ("VIVO", 10, "upper"))

    def test_resolve_explicit_max_len_wins(self):
        self.assertEqual(cm.resolve_settings("VIVO-BBCC", 8, None), ("VIVO", 8, "upper"))

    def test_resolve_explicit_case_wins(self):
        self.assertEqual(cm.resolve_settings("VIVOFIBRA-1234", None, "upper"),
                         ("VIVOFIBRA", 10, "upper"))

    def test_resolve_non_vivo_defaults(self):
        self.assertEqual(cm.resolve_settings("CLARO_2G3A9C2D", None, None),
                         (None, 8, "upper"))

    def test_resolve_non_vivo_explicit(self):
        self.assertEqual(cm.resolve_settings("MyHomeWiFi", 12, "mixed"),
                         (None, 12, "mixed"))


class TestCharsetMaskRun(unittest.TestCase):
    # ---- run-mode launch flags ----
    def test_parse_flags_run_auto(self):
        positional, max_len, case, no_color, run_mode, files = cm._parse_flags(
            ["-y", "cap.hc22000"])
        self.assertEqual(run_mode, "auto")
        self.assertEqual(files, ["cap.hc22000"])

    def test_parse_flags_ask(self):
        *_, run_mode, files = cm._parse_flags(["--ask", "cap.hc22000"])
        self.assertEqual(run_mode, "ask")

    def test_parse_flags_norun(self):
        *_, run_mode, _files = cm._parse_flags(["-n", "cap.hc22000"])
        self.assertEqual(run_mode, "off")

    def test_parse_flags_default_off(self):
        *_, run_mode, _files = cm._parse_flags(["cap.hc22000"])
        self.assertEqual(run_mode, "off")

    # ---- run-mode prompt words ----
    def test_prompt_run_words(self):
        self.assertEqual(cm.parse_prompt_command("run"), ("run", "auto"))
        self.assertEqual(cm.parse_prompt_command("ask"), ("run", "ask"))
        self.assertEqual(cm.parse_prompt_command("norun"), ("run", "off"))

    # ---- argv construction (pure) ----
    def test_build_argv(self):
        self.assertEqual(
            cm._build_argv("hashcat", "cap.hc22000", "-1 ABCD ?1?1"),
            ["hashcat", "-m", "22000", "-a", "3", "cap.hc22000", "-1", "ABCD", "?1?1"])

    def test_build_argv_positional_tail(self):
        argv = cm._build_argv("hashcat", "cap.hc22000", "-1 56 -2 0D B81?1?2")
        self.assertEqual(argv[:6],
                         ["hashcat", "-m", "22000", "-a", "3", "cap.hc22000"])
        self.assertIn("B81?1?2", argv)


class TestCharsetMaskCascade(unittest.TestCase):
    # The run cascade (auto mode) with the hashcat process stubbed: we assert on the
    # order/number of invocations and which mask each got, never on the stub itself.
    UNIFORM = "-1 ABCD ?1?1?1?1?1?1?1?1"
    POS = "-1 56 B81?1?1?1?1?1"

    def _invocations(self, positional_tail, exit_codes):
        calls, codes = [], list(exit_codes)

        def fake_run(argv, cwd=None):
            calls.append(argv)
            return mock.Mock(returncode=codes.pop(0))

        with mock.patch.object(cm.shutil, "which", return_value="hashcat"), \
             mock.patch.object(cm.subprocess, "run", side_effect=fake_run):
            cm._maybe_run("cap.hc22000", self.UNIFORM, "1.0 s",
                          positional_tail, 16, "auto")
        return calls

    def test_positional_then_uniform_on_miss(self):
        calls = self._invocations(self.POS, [1, 1])   # positional exhausts, then uniform
        self.assertEqual(len(calls), 2)
        self.assertIn("B81?1?1?1?1?1", calls[0])       # positional ran first
        self.assertIn("ABCD", calls[1])                # uniform ran second

    def test_stops_when_positional_cracks(self):
        calls = self._invocations(self.POS, [0])       # positional cracks -> no fallback
        self.assertEqual(len(calls), 1)
        self.assertIn("B81?1?1?1?1?1", calls[0])

    def test_uniform_only_when_no_positional(self):
        calls = self._invocations(None, [1])           # nothing positional -> uniform only
        self.assertEqual(len(calls), 1)
        self.assertIn("ABCD", calls[0])


class TestCrackLog(unittest.TestCase):
    def test_band_token(self):
        self.assertEqual(k.band_token("CLARO_2G3A9C2D"), "2.4G")
        self.assertEqual(k.band_token("CLARO_5G3A9C2D"), "5G")
        self.assertEqual(k.band_token("CLARO_3A9C2D"), "no-band")
        self.assertEqual(k.band_token("CLARO_ABCDEF-5G-BH"), "mesh-BH")
        self.assertEqual(k.band_token("CLARO_112233-IoT"), "IoT")

    def test_crack_record_fields(self):
        # Fabricated single-OUI Kaon gateway: BSSID octet 3 = EF, SSID tail 3A9C2D.
        net = {"essid": "CLARO_5G3A9C2D", "bssid": "743aef3a9c2d"}
        rec = k.crack_record(net, "EF3A9C2D", cls="single-OUI",
                             source="beacon-derived", confirmed=True,
                             attempts=1, keyspace=1, capture="/tmp/test.hc22000")
        self.assertEqual(rec["oui"], "74:3A:EF")
        self.assertEqual(rec["vendor"], "Kaon")
        self.assertEqual(rec["band"], "5G")
        self.assertEqual(rec["leading_byte"], "EF")
        self.assertEqual(rec["attempts"], 1)
        self.assertEqual(rec["capture"], "test.hc22000")   # basename only, no path
        self.assertFalse(rec["compal_case"])               # BSSID tail == SSID tail

    def test_crack_record_compal_case(self):
        # Same OUI, BSSID tail (3A9C2E) differs from SSID tail (3A9C2D) -> Compal case.
        net = {"essid": "CLARO_5G3A9C2D", "bssid": "743aef3a9c2e"}
        rec = k.crack_record(net, "EF3A9C2D", cls="single-OUI",
                             source="beacon-derived", confirmed=True,
                             attempts=1, keyspace=1, capture="x.hc22000")
        self.assertTrue(rec["compal_case"])

    def test_compal_case_only_for_single_oui(self):
        # full8 / split-OUI: the Compal comparison is meaningless -> null, never a bool.
        net = {"essid": "CLARO_2GAB12CD34", "bssid": "d83139ab12cd"}
        full8 = k.crack_record(net, "AB12CD34", cls="full8", source="beacon-derived",
                               confirmed=True, attempts=1, keyspace=1, capture="c")
        self.assertIsNone(full8["compal_case"])
        split = k.crack_record({"essid": "CLARO_5G7A79B5", "bssid": "c852617a79b5"},
                               "437A79B5", cls="split-OUI", source="handshake-brute",
                               confirmed=True, attempts=68, keyspace=256, capture="c")
        self.assertIsNone(split["compal_case"])

    def test_save_crack_dedup(self):
        # Point the log at a temp file; identical records must not pile up (dedup, C).
        tmp = tempfile.mkdtemp()
        old_file, old_save = k.CRACK_FILE, k.SAVE_CRACKS
        k.CRACK_FILE, k.SAVE_CRACKS = os.path.join(tmp, "cracked.jsonl"), True
        try:
            net = {"essid": "CLARO_5G3A9C2D", "bssid": "743aef3a9c2d"}
            rec = k.crack_record(net, "EF3A9C2D", cls="single-OUI",
                                 source="beacon-derived", confirmed=True,
                                 attempts=1, keyspace=1, capture="a.hc22000")
            self.assertEqual(k.save_crack(rec)[0], "saved")
            self.assertEqual(k.save_crack(rec)[0], "duplicate")   # same identity -> skipped
            other = dict(rec, password="AA3A9C2D")                # different key -> new row
            self.assertEqual(k.save_crack(other)[0], "saved")
            with open(k.CRACK_FILE, encoding="utf-8") as fh:
                lines = [l for l in fh if l.strip()]
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["password"], "EF3A9C2D")
        finally:
            k.CRACK_FILE, k.SAVE_CRACKS = old_file, old_save


class TestSchemesVivo(unittest.TestCase):
    """VIVO / VIVOFIBRA scheme (schemes.py) under the DETECT-ONLY policy: a key is
    presented in exactly one case - a confirmed-weak MitraStar OUI captured on its base
    MAC (SSID 4-hex tail == BSSID last 4). Every other case is identified but keyless.
    Real vendor OUI *prefixes* are public IEEE data (as in data/claro_ouis.csv); every
    full BSSID and key below is FABRICATED."""

    def test_weak_base_mac_upper(self):
        # Weak OUI 34:57:60, and the SSID tail (BBCC) == BSSID last 4 -> base MAC -> KEY.
        r = sc.derive("VIVO-BBCC", "34:57:60:AA:BB:CC")
        self.assertEqual(r["isp"], "VIVO")
        self.assertEqual(r["gate"], "weak")
        self.assertTrue(r["base_mac"])
        self.assertTrue(r["determined"])
        self.assertEqual(r["key"], "5760AABBCC")     # MAC minus 1st octet, UPPER (VIVO-)

    def test_weak_base_mac_lower(self):
        # VIVOFIBRA weak OUI 98:97:D1, tail 2233 == BSSID last 4 -> lowercase KEY.
        r = sc.derive("VIVOFIBRA-2233", "98:97:D1:11:22:33")
        self.assertEqual(r["isp"], "VIVOFIBRA")
        self.assertTrue(r["determined"])
        self.assertEqual(r["key"], "97d1112233")     # lowercase (VIVOFIBRA-)

    def test_wifi6_variant_and_band_suffix(self):
        # VIVOFIBRA-WIFI6-<4H> infix + a trailing -5G band tag both parse to the tail,
        # and a weak base-MAC capture still derives. Weak OUI AC:C6:62.
        self.assertEqual(sc.parse_tail("VIVOFIBRA-WIFI6-E058"), "e058")
        self.assertEqual(sc.parse_tail("VIVO-AA48-5G"), "aa48")
        r = sc.derive("VIVOFIBRA-WIFI6-E058", "AC:C6:62:AA:E0:58")
        self.assertTrue(r["determined"])
        self.assertEqual(r["key"], "c662aae058")

    def test_weak_but_not_base_mac_no_key(self):
        # Weak OUI, but the capture is the 5 GHz/secondary BSSID (tail != BSSID last 4):
        # detect-only -> no key, and the note points at the 2.4 GHz base MAC.
        r = sc.derive("VIVOFIBRA-7658-5G", "A4:33:D7:AA:BB:CC")
        self.assertEqual(r["gate"], "weak")
        self.assertFalse(r["base_mac"])
        self.assertFalse(r["determined"])
        self.assertIsNone(r["key"])
        self.assertIn("base MAC", r["note"])

    def test_hardened_oui_no_key(self):
        # 84:0B:BB is a confirmed-hardened (random-key) block, even on a base-MAC capture.
        r = sc.derive("VIVOFIBRA-3456", "84:0B:BB:12:34:56")
        self.assertEqual(r["gate"], "hardened")
        self.assertFalse(r["determined"])
        self.assertIsNone(r["key"])

    def test_tellescom_askey_hardened(self):
        # 10:72:23 (Tellescom-built Askey RTF3507VW) ships random keys - a VIVOFIBRA-4DDB
        # label showed a non-MAC-derived key - so it must gate hardened, not derive.
        r = sc.derive("VIVOFIBRA-4DDB", "10:72:23:FB:4D:DB")
        self.assertEqual(r["gate"], "hardened")
        self.assertFalse(r["determined"])
        self.assertIsNone(r["key"])

    def test_unknown_oui_no_key(self):
        # Detect-only: an un-researched OUI is IDENTIFIED but never guessed.
        r = sc.derive("VIVO-1234", "AA:BB:CC:11:12:34")
        self.assertEqual(r["gate"], "unknown")
        self.assertTrue(r["base_mac"])               # it *is* the base MAC ...
        self.assertFalse(r["determined"])            # ... but the OUI isn't researched
        self.assertIsNone(r["key"])                  # so no key is produced

    def test_renamed_is_not_default(self):
        # Renamed but still <prefix>-<junk>: detected as Telefónica, but not default form.
        for essid in ("VIVO-NALA", "VIVO-5G", "VIVOFIBRA- 149. 5G"):
            self.assertIsNone(sc.parse_tail(essid), essid)
            r = sc.derive(essid, "AC:C6:62:AA:BB:CC")
            self.assertIsNotNone(r, essid)           # still detected as Telefónica ...
            self.assertFalse(r["default"], essid)    # ... but not the default form
            self.assertIsNone(r["key"], essid)

    def test_spaced_rename_not_detected(self):
        # A spaced rename ("VIVOFIBRA 149") has no default-form hyphen prefix, so it isn't
        # a derive target at all -> falls to the generic skip, not handle_vivo.
        for essid in ("VIVOFIBRA 149", "VIVO FIBRA 803"):
            self.assertIsNone(sc.detect(essid), essid)
            self.assertIsNone(sc.derive(essid, "AC:C6:62:AA:BB:CC"), essid)

    def test_vivo_internet_excluded(self):
        # Vivo-Internet-<4H> is a different, hardened multi-ODM line (ZTE/WNC/Blu Castle)
        # -> not a VIVO- target. SSID + BSSID here are fabricated.
        self.assertIsNone(sc.detect("Vivo-Internet-1234"))
        self.assertIsNone(sc.derive("Vivo-Internet-1234", "AA:BB:CC:DD:12:34"))

    def test_non_telefonica_is_none(self):
        self.assertIsNone(sc.derive("CLARO_5G3A9C2D", "743aef3a9c2d"))
        self.assertIsNone(sc.derive("MyHomeWiFi", "743aef3a9c2d"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
