"""Baseline safety checks using small fixtures, not the project dataset."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning

from src.train import (
    build_pipeline,
    fit_baseline,
    load_development_data,
    save_baseline,
    validate_partition,
)


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.symptoms = ["fever", "cough", "pain"]
        self.schema = pd.DataFrame({
            "item_id": self.symptoms + ["age_band", "sex"],
            "data_type": ["binary"] * 3 + ["categorical"] * 2,
        })
        self.conditions = ["malaria", "typhoid", "urti_pneumonia", "diarrhoeal", "uti"]
        self.config = {
            "corpus": {"conditions": self.conditions},
            "unanswered": {"encoding": -1},
            "covariates": {
                "age_band": {"values": ["under_5", "15_to_49"]},
                "sex": {"values": ["female", "male"]},
            },
        }
        rows = [
            [condition_number % 2, (condition_number // 2) % 2, condition_number // 4,
             "15_to_49", "female", condition]
            for condition_number, condition in enumerate(self.conditions)
        ]
        self.validation = pd.DataFrame(rows, columns=self.schema["item_id"].tolist() + ["label"])
        self.training = pd.concat([self.validation] * 10, ignore_index=True)
        self.validation["age_band"] = "under_5"

    def write_fixture(self, directory: Path) -> None:
        counts = {}
        audit_rows = []
        next_id = 0
        for name, frame in [("train", self.training), ("validation", self.validation),
                            ("test", self.validation)]:
            counts[name] = {**frame["label"].value_counts().to_dict(), "total": len(frame)}
            for position in range(len(frame)):
                audit_rows.append([next_id, next_id, name, position])
                next_id += 1
            if name != "test":
                frame.to_csv(directory / f"{name}.csv", index=False)
        pd.DataFrame(audit_rows, columns=["record_id", "symptom_group", "split", "row_in_split"]).to_csv(
            directory / "split_audit.csv", index=False
        )
        summary = {"features": self.schema["item_id"].tolist(), "label": "label", "counts": counts, "seed": 42}
        (directory / "preparation.json").write_text(json.dumps(summary), encoding="utf-8")

    def test_encoder_distinguishes_unanswered_no_and_yes(self):
        pipeline = build_pipeline(self.schema, self.config, 42)
        inputs = self.training.drop(columns="label")
        encoder = pipeline.named_steps["encode"]
        encoder.fit(inputs)
        probes = inputs.iloc[:3].copy()
        for symptom in self.symptoms:
            probes[symptom] = 0
        probes["fever"] = [-1, 0, 1]
        encoded = encoder.transform(probes)
        if hasattr(encoded, "toarray"):
            encoded = encoded.toarray()
        self.assertFalse(np.array_equal(encoded[0], encoded[1]))
        self.assertFalse(np.array_equal(encoded[1], encoded[2]))
        self.assertFalse(np.array_equal(encoded[0], encoded[2]))
        encoder.transform(self.validation.drop(columns="label"))
        self.assertEqual(len(encoder.get_feature_names_out()), 13)

    def test_fit_uses_only_training_rows_and_reports_validation(self):
        pipeline = build_pipeline(self.schema, self.config, 42)
        original = self.training.copy(deep=True)
        with patch("src.train.build_pipeline", return_value=pipeline):
            with patch.object(pipeline, "fit", wraps=pipeline.fit) as fit:
                _, report = fit_baseline(self.training, self.validation, self.schema, self.config, 42)
        self.assertEqual(fit.call_count, 1)
        fitted_inputs, fitted_labels = fit.call_args.args
        pd.testing.assert_frame_equal(fitted_inputs, self.training.drop(columns="label"))
        pd.testing.assert_series_equal(fitted_labels, self.training["label"])
        pd.testing.assert_frame_equal(self.training, original)
        self.assertEqual(report["evaluation_partition"], "validation")
        self.assertEqual(int(np.asarray(report["confusion_matrix"]).sum()), len(self.validation))
        self.assertEqual(report["confusion_matrix_labels"], self.conditions)
        self.assertFalse(report["final_test_evaluated"])
        self.assertFalse(report["calibrated"])
        self.assertGreaterEqual(report["macro_f1"], 0)
        self.assertLessEqual(report["macro_f1"], 1)
        if report["macro_f1"] > 0.95:
            self.assertTrue(any("separability" in message for message in report["warnings"]))

    def test_repeated_fit_is_reproducible(self):
        first, first_report = fit_baseline(self.training, self.validation, self.schema, self.config, 42)
        second, second_report = fit_baseline(self.training, self.validation, self.schema, self.config, 42)
        inputs = self.validation.drop(columns="label")
        np.testing.assert_allclose(first.predict_proba(inputs), second.predict_proba(inputs))
        self.assertEqual(first_report["macro_f1"], second_report["macro_f1"])

    def test_rejects_leaking_columns_invalid_answers_and_missing_classes(self):
        bad_answer = self.training.copy()
        bad_answer.loc[0, "fever"] = 2
        bad_covariate = self.training.copy()
        bad_covariate.loc[0, "age_band"] = "unknown"
        for frame in [self.training.assign(record_id=range(len(self.training))),
                      self.training.assign(generated_from="malaria"), bad_answer, bad_covariate,
                      self.training.loc[self.training["label"].ne("uti")]]:
            with self.subTest(columns=frame.columns.tolist()):
                with self.assertRaises(ValueError):
                    validate_partition(frame, self.schema, self.config, "train")

    def test_loader_never_reads_test_data(self):
        read_csv = pd.read_csv

        def guarded_read(path, *args, **kwargs):
            self.assertNotEqual(Path(path).name, "test.csv")
            return read_csv(path, *args, **kwargs)

        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_fixture(directory)
            self.assertFalse((directory / "test.csv").exists())
            with patch("src.train.pd.read_csv", side_effect=guarded_read):
                frames, preparation = load_development_data(directory, self.schema, self.config)
            self.assertEqual(set(frames), {"train", "validation"})
            self.assertEqual(preparation["seed"], 42)
            pd.testing.assert_frame_equal(frames["train"], self.training, check_dtype=False)

    def test_loader_rejects_cross_partition_groups(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_fixture(directory)
            audit_path = directory / "split_audit.csv"
            audit = pd.read_csv(audit_path)
            audit.loc[audit["split"].eq("validation"), "symptom_group"] = 0
            audit.to_csv(audit_path, index=False)
            with self.assertRaisesRegex(ValueError, "crosses partitions"):
                load_development_data(directory, self.schema, self.config)

    def test_loader_rejects_changed_row_count(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_fixture(directory)
            self.training.iloc[:-1].to_csv(directory / "train.csv", index=False)
            with self.assertRaisesRegex(ValueError, "row count"):
                load_development_data(directory, self.schema, self.config)

    def test_pipeline_round_trip_and_no_overwrite(self):
        pipeline, report = fit_baseline(self.training, self.validation, self.schema, self.config, 42)
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "baseline"
            save_baseline(output, pipeline, report)
            restored = joblib.load(output / "pipeline.joblib")
            inputs = self.validation.drop(columns="label")
            np.testing.assert_allclose(pipeline.predict_proba(inputs), restored.predict_proba(inputs))
            saved_report = json.loads((output / "validation_report.json").read_text(encoding="utf-8"))
            self.assertEqual(saved_report["macro_f1"], report["macro_f1"])
            before = (output / "pipeline.joblib").read_bytes()
            with self.assertRaises(FileExistsError):
                save_baseline(output, pipeline, report)
            self.assertEqual(before, (output / "pipeline.joblib").read_bytes())

    def test_nonconverged_fit_stops_instead_of_reporting_success(self):
        pipeline = build_pipeline(self.schema, self.config, 42)
        with patch("src.train.build_pipeline", return_value=pipeline):
            with patch.object(pipeline, "fit", side_effect=ConvergenceWarning("Not converged")):
                with self.assertRaises(ConvergenceWarning):
                    fit_baseline(self.training, self.validation, self.schema, self.config, 42)


if __name__ == "__main__":
    unittest.main()