"""The pre-declared selection rules for reweighting and thresholds."""

import unittest

import numpy as np

from src.finalise import choose_thresholds, choose_weight, named_mask


def trial(weight, malaria, others_ok=True, macro_ok=True):
    floors = {"malaria": malaria >= 0.90, "typhoid": others_ok, "uti": True}
    return {"weight": weight, "result": {"per_class_recall": {"malaria": malaria},
                                         "recall_floors_met": floors,
                                         "macro_f1_floor_met": macro_ok}}


class WeightRuleTests(unittest.TestCase):
    def test_smallest_weight_reaching_target_wins(self):
        chosen, reached = choose_weight([trial(1, 0.80), trial(2, 0.91), trial(3, 0.95)])
        self.assertEqual(chosen["weight"], 2)
        self.assertTrue(reached)

    def test_weight_breaking_another_floor_is_excluded(self):
        chosen, reached = choose_weight([trial(1, 0.80), trial(2, 0.85), trial(3, 0.92, others_ok=False)])
        self.assertEqual(chosen["weight"], 2)
        self.assertFalse(reached)

    def test_no_eligible_weight_raises(self):
        with self.assertRaises(ValueError):
            choose_weight([trial(1, 0.95, macro_ok=False)])


class ThresholdRuleTests(unittest.TestCase):
    def test_named_mask_needs_confidence_and_lead(self):
        probs = np.array([[0.8, 0.1, 0.1], [0.45, 0.40, 0.15], [0.35, 0.33, 0.32]])
        self.assertEqual(named_mask(probs, 0.5, 0.1).tolist(), [True, False, False])

    def test_choice_meets_precision_target(self):
        rng = np.random.default_rng(0)
        probs = rng.dirichlet([1, 1, 1, 1, 1], size=500)
        correct = probs.max(axis=1) > 0.5  # confident rows are the correct ones
        choice = choose_thresholds(probs, correct)
        named = named_mask(probs, choice["low_confidence"], choice["proximity_margin"])
        self.assertGreaterEqual(correct[named].mean(), 0.90)


if __name__ == "__main__":
    unittest.main()
