"""Checks on the DDXPlus comparison helpers, using small artificial inputs only."""

import unittest

from src.calibration import evidence_codes, nearest_band, verdict

BANDS = {"cardinal": 0.85, "common": 0.60, "frequent": 0.40, "occasional": 0.20, "background": 0.03}


class EvidenceCodes(unittest.TestCase):
    def test_binary_and_valued_codes(self):
        cell = "['E_91', 'E_54_@_V_161', 'E_54_@_V_183', 'E_56_@_4', 'E_201']"
        self.assertEqual(evidence_codes(cell), {"E_91", "E_54", "E_56", "E_201"})

    def test_no_partial_matches(self):
        self.assertEqual(evidence_codes("['E_911']"), {"E_911"})
        self.assertNotIn("E_91", evidence_codes("['E_911']"))


class Bands(unittest.TestCase):
    def test_nearest_band(self):
        self.assertEqual(nearest_band(0.0, BANDS), "background")
        self.assertEqual(nearest_band(0.11, BANDS), "background")
        self.assertEqual(nearest_band(0.13, BANDS), "occasional")
        self.assertEqual(nearest_band(0.70, BANDS), "common")
        self.assertEqual(nearest_band(0.73, BANDS), "cardinal")

    def test_verdict(self):
        self.assertEqual(verdict("common", "common"), "agrees")
        self.assertEqual(verdict("common", "cardinal"), "adjacent")
        self.assertEqual(verdict("background", "frequent"), "diverges")


if __name__ == "__main__":
    unittest.main()
