"""Checks for preparation safety; no model fitting or real-data writes."""

from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from src.prepare_data import (
    PARTITION_FRACTIONS,
    conflict_audit,
    grouped_split,
    model_inputs,
    one_answer_apart,
    symptom_groups,
    write_partitions,
)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.symptoms = [f"symptom_{number}" for number in range(12)]
        self.schema = pd.DataFrame(
            {
                "item_id": self.symptoms + ["age_band", "sex"],
                "data_type": ["binary"] * 12 + ["categorical"] * 2,
            }
        )
        self.conditions = ["malaria", "typhoid", "urti_pneumonia", "diarrhoeal", "uti"]
        self.corpus = pd.DataFrame(
            [
                [(record // (3 ** (offset // 2))) % 3 - 1 for offset in range(12)]
                for record in range(400)
            ],
            columns=self.symptoms,
        )
        self.corpus["record_id"] = range(400)
        self.corpus["age_band"] = "15_to_49"
        self.corpus["sex"] = "female"
        self.corpus["label"] = [self.conditions[record // 80] for record in range(400)]
        repeated = self.corpus.iloc[:10].copy()
        repeated["record_id"] = range(400, 410)
        repeated["age_band"] = "50_plus"
        repeated["sex"] = "male"
        repeated.loc[0, "label"] = "uti"
        self.corpus = pd.concat([self.corpus, repeated], ignore_index=True)

    def test_same_seed_repeats_split_without_changing_original(self):
        original = self.corpus.copy(deep=True)
        first = grouped_split(self.corpus, self.schema, 42)
        second = grouped_split(self.corpus, self.schema, 42)
        pd.testing.assert_frame_equal(first, second)
        pd.testing.assert_frame_equal(self.corpus, original)

    def test_complete_disjoint_groups_with_all_diseases(self):
        manifest = grouped_split(self.corpus, self.schema, 42)
        self.assertEqual(set(manifest["record_id"]), set(self.corpus["record_id"]))
        self.assertTrue(manifest["record_id"].is_unique)
        self.assertTrue(manifest.groupby("symptom_group")["split"].nunique().eq(1).all())
        for original_row in range(10):
            self.assertEqual(
                manifest.loc[original_row, "split"],
                manifest.loc[400 + original_row, "split"],
            )
        for name, fraction in PARTITION_FRACTIONS.items():
            selected = manifest["split"].eq(name)
            self.assertEqual(set(self.corpus.loc[selected, "label"]), set(self.conditions))
            self.assertAlmostEqual(float(selected.mean()), fraction, delta=0.01)
            self.assertEqual(
                manifest.loc[selected, "row_in_split"].tolist(),
                list(range(int(selected.sum()))),
            )

    def test_inputs_exclude_identifiers_metadata_and_answer(self):
        enriched = self.corpus.assign(generated_from="malaria", label_flipped=False)
        features, labels = model_inputs(enriched, self.schema)
        self.assertEqual(list(features), self.schema["item_id"].tolist())
        self.assertFalse({"record_id", "label", "generated_from", "label_flipped"} & set(features))
        pd.testing.assert_series_equal(labels, self.corpus["label"])

    def test_schema_cannot_whitelist_a_leaking_identifier(self):
        for forbidden in ["record_id", "label", "generated_from", "symptom_group"]:
            with self.subTest(forbidden=forbidden):
                bad_schema = pd.concat(
                    [self.schema, pd.DataFrame({"item_id": [forbidden], "data_type": ["binary"]})],
                    ignore_index=True,
                )
                with self.assertRaisesRegex(ValueError, "cannot be features"):
                    model_inputs(self.corpus, bad_schema)

    def test_too_few_groups_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least 3"):
            grouped_split(self.corpus.iloc[:2], self.schema, 42)

    def test_large_mixed_label_group_preserves_target_counts(self):
        large_group = pd.concat([self.corpus.iloc[[0]]] * 200, ignore_index=True)
        large_group["record_id"] = range(1000, 1200)
        large_group["label"] = [self.conditions[record % 5] for record in range(200)]
        corpus = pd.concat([self.corpus, large_group], ignore_index=True)
        original = corpus.copy(deep=True)
        manifest = grouped_split(corpus, self.schema, 42)
        large_members = manifest["symptom_group"].eq(manifest.loc[0, "symptom_group"])
        self.assertEqual(int(large_members.sum()), 202)
        self.assertEqual(manifest.loc[large_members, "split"].unique().tolist(), ["train"])
        self.assertTrue(manifest.groupby("symptom_group")["split"].nunique().eq(1).all())
        for name, fraction in PARTITION_FRACTIONS.items():
            selected = manifest["split"].eq(name)
            self.assertAlmostEqual(float(selected.mean()), fraction, delta=0.01)
            for condition in self.conditions:
                total = int(corpus["label"].eq(condition).sum())
                actual = int((corpus["label"].eq(condition) & selected).sum())
                self.assertAlmostEqual(actual, total * fraction, delta=2)
        self.assertEqual(len(manifest), len(corpus))
        pd.testing.assert_frame_equal(corpus, original)

    def test_unattainable_targets_do_not_break_a_large_group(self):
        large_group = pd.concat([self.corpus.iloc[[0]]] * 1200, ignore_index=True)
        large_group["record_id"] = range(1000, 2200)
        large_group["label"] = [self.conditions[record % 5] for record in range(1200)]
        corpus = pd.concat([self.corpus, large_group], ignore_index=True)
        manifest = grouped_split(corpus, self.schema, 42)
        large_members = manifest["symptom_group"].eq(manifest.loc[0, "symptom_group"])
        self.assertGreater(float(large_members.mean()), PARTITION_FRACTIONS["train"])
        self.assertEqual(manifest.loc[large_members, "split"].nunique(), 1)
        self.assertEqual(len(manifest), len(corpus))
        for name in PARTITION_FRACTIONS:
            self.assertEqual(
                set(corpus.loc[manifest["split"].eq(name), "label"]), set(self.conditions)
            )

    def test_near_groups_keep_chains_duplicates_and_unknown_answers_together(self):
        symptoms = ["first", "second", "third", "fourth"]
        corpus = pd.DataFrame(
            [[0, 0, 0, 0], [1, 0, 0, 0], [1, 1, 0, 0], [0, 0, 0, 0],
             [1, 1, 1, 1], [-1, 0, 0, 0]],
            columns=symptoms,
            index=[10, 20, 30, 40, 50, 60],
        )
        corpus["label"] = ["malaria", "typhoid", "uti", "diarrhoeal", "uti", "malaria"]
        groups = symptom_groups(corpus, symptoms)
        self.assertEqual(groups.loc[[10, 20, 30, 40, 60]].nunique(), 1)
        self.assertNotEqual(groups.loc[10], groups.loc[50])
        self.assertEqual(groups.index.tolist(), corpus.index.tolist())
        shuffled = corpus.iloc[::-1]
        shuffled_groups = symptom_groups(shuffled, symptoms).reindex(corpus.index)
        for first, second in combinations(corpus.index, 2):
            self.assertEqual(
                groups.loc[first] == groups.loc[second],
                shuffled_groups.loc[first] == shuffled_groups.loc[second],
            )

    def test_groups_with_no_edges_and_single_symptom(self):
        separated = pd.DataFrame([[0, 0], [1, 1], [-1, -1]], columns=["first", "second"])
        self.assertEqual(symptom_groups(separated, ["first", "second"]).nunique(), 3)
        self.assertEqual(symptom_groups(separated.iloc[:1], ["first", "second"]).nunique(), 1)
        self.assertEqual(symptom_groups(separated, ["first"]).nunique(), 1)

    def test_one_answer_pairs_do_not_cross_actual_split(self):
        near_match = self.corpus.iloc[[0]].copy()
        near_match["record_id"] = 999
        near_match[self.symptoms[0]] = 0
        near_match["label"] = "uti"
        corpus = pd.concat([self.corpus, near_match], ignore_index=True)
        manifest = grouped_split(corpus, self.schema, 42)
        neighbours = one_answer_apart(corpus, self.symptoms, manifest)
        self.assertGreater(neighbours["unique_pattern_pairs"], 0)
        self.assertEqual(neighbours["pairs_across_partitions"], 0)
        self.assertEqual(manifest.loc[0, "split"], manifest.iloc[-1]["split"])
        self.assertEqual(len(manifest), len(corpus))

    def test_near_match_counts_equal_direct_comparison(self):
        patterns = pd.DataFrame(
            [[0, 0], [0, 0], [1, 0], [-1, 0], [1, 1], [0, 1], [-1, -1]],
            columns=["first", "second"],
        )
        manifest = pd.DataFrame(
            {"split": ["train", "train", "test", "validation", "test", "train", "test"]}
        )
        actual = one_answer_apart(patterns, ["first", "second"], manifest)
        unique = patterns.assign(partition=manifest["split"]).drop_duplicates(
            subset=["first", "second"]
        ).reset_index(drop=True)
        expected_pairs = 0
        expected_crossing = 0
        involved = set()
        for first, second in combinations(range(len(unique)), 2):
            difference = unique.loc[first, ["first", "second"]].ne(
                unique.loc[second, ["first", "second"]]
            ).sum()
            if difference == 1:
                expected_pairs += 1
                involved.update([first, second])
                expected_crossing += int(unique.loc[first, "partition"] != unique.loc[second, "partition"])
        self.assertEqual(actual["unique_pattern_pairs"], expected_pairs)
        self.assertEqual(actual["pairs_across_partitions"], expected_crossing)
        self.assertEqual(actual["patterns_with_a_neighbour"], len(involved))

    def test_conflict_metadata_is_joined_by_id_not_row_order(self):
        corpus = self.corpus.iloc[[0, 400]].copy().reset_index(drop=True)
        corpus["age_band"] = "15_to_49"
        corpus["sex"] = "female"
        meta = pd.DataFrame(
            {
                "record_id": [400, 0],
                "generated_from": ["malaria", "malaria"],
                "label_flipped": [True, False],
            }
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "meta.csv"
            meta.to_csv(path, index=False)
            report = conflict_audit(corpus, self.schema, path)
            self.assertEqual(report["identical_input_groups_with_different_labels"], 1)
            self.assertEqual(report["rows_in_conflicting_groups"], 2)
            self.assertEqual(report["flagged_label_changes_in_conflicting_rows"], 1)
            meta["label_flipped"] = False
            meta.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "disagree"):
                conflict_audit(corpus, self.schema, path)

    def test_saved_partitions_preserve_labels_and_cannot_be_overwritten(self):
        manifest = grouped_split(self.corpus, self.schema, 42)
        with TemporaryDirectory() as directory:
            output = Path(directory) / "splits"
            write_partitions(output, self.corpus, self.schema, manifest, {"seed": 42})
            for name in PARTITION_FRACTIONS:
                saved = pd.read_csv(output / f"{name}.csv")
                expected = self.corpus.loc[
                    manifest["split"].eq(name), self.schema["item_id"].tolist() + ["label"]
                ].reset_index(drop=True)
                pd.testing.assert_frame_equal(saved, expected, check_dtype=False)
            audit = pd.read_csv(output / "split_audit.csv")
            pd.testing.assert_frame_equal(audit, manifest, check_dtype=False)
            before = (output / "train.csv").read_bytes()
            with self.assertRaises(FileExistsError):
                write_partitions(output, self.corpus, self.schema, manifest, {})
            self.assertEqual((output / "train.csv").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()