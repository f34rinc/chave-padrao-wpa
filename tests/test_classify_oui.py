import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import classify_oui as c


class TestClassifyOui(unittest.TestCase):
    def setUp(self):
        # vendor indexes built the way the tool builds them from the real CSVs
        self.isp = c.vendor_index([
            ("98:00:6A", "ZTE"), ("3C:B7:4B", "Vantiva/Technicolor"),
            ("C0:F6:C2", "Huawei"), ("30:24:78", "Sagemcom"), ("E0:37:BF", "WNC"),
            ("AA", "Arris/CommScope"), ("BB", "Arris/CommScope router"),
            ("CC", "Vantiva/Technicolor"), ("DD", "Technicolor"),  # Vantiva is dominant
            ("EE", "SEI Robotics"),
        ])
        self.cons = c.vendor_index([
            ("3C:64:CF", "TP-Link"), ("34:0A:33", "D-Link"),
            ("04:A1:51", "NETGEAR"), ("oui", "vendor"),  # placeholder skipped
        ])

    def test_words_tokenizes_and_drops_corporate_filler(self):
        self.assertEqual(c._words("TP-Link Systems Inc"), {"tplink"})
        self.assertEqual(c._words("Vantiva/Technicolor"), {"vantiva", "technicolor"})
        self.assertEqual(c._words("HUAWEI TECHNOLOGIES CO.,LTD"), {"huawei"})

    def test_vendor_index_prefers_dominant_canonical(self):
        self.assertEqual(self.isp["arris"], "Arris/CommScope")            # over "... router"
        self.assertEqual(self.isp["technicolor"], "Vantiva/Technicolor")  # over bare "Technicolor"

    def test_vendor_index_skips_placeholder(self):
        self.assertNotIn("vendor", self.cons)

    def test_classify_isp_vendors(self):
        for company, want in [("ZTE Corporation", "ZTE"),
                              ("Vantiva USA LLC", "Vantiva/Technicolor"),
                              ("HUAWEI TECHNOLOGIES CO.,LTD", "Huawei"),
                              ("Sagemcom Broadband SAS", "Sagemcom"),
                              ("WNC Corporation", "WNC")]:
            self.assertEqual(c.classify(company, self.isp, self.cons), ("claro", want))

    def test_classify_consumer_vendors(self):
        self.assertEqual(c.classify("TP-LINK TECHNOLOGIES CO.,LTD.", self.isp, self.cons),
                         ("consumer", "TP-Link"))
        self.assertEqual(c.classify("D-Link International", self.isp, self.cons),
                         ("consumer", "D-Link"))

    def test_classify_unknown_and_empty(self):
        self.assertEqual(c.classify("Acme Widgets Inc", self.isp, self.cons), ("unknown", None))
        self.assertEqual(c.classify("", self.isp, self.cons), ("unknown", None))

    def test_row_for(self):
        self.assertEqual(c.row_for("98:00:6A", "claro", "ZTE"), "98:00:6A,ZTE,")
        self.assertEqual(c.row_for("40:AE:30", "consumer", "TP-Link", today="2026-10-18"),
                         "40:AE:30,TP-Link,consumer/renamed,2026-10-18")

    def test_lookup_parses_company_and_survives_errors(self):
        good = lambda url: '{"macPrefix":"98006A","company":"ZTE Corporation","country":"CN"}'
        self.assertEqual(c.lookup("98:00:6A", fetch=good), "ZTE Corporation")
        def boom(url): raise OSError("net down")
        self.assertEqual(c.lookup("98:00:6A", fetch=boom), "")


if __name__ == "__main__":
    unittest.main()
