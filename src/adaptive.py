"""Adaptive questioning: ask the most informative question next, and stop once the model is
confident, instead of always asking all 35.

The deployed model (results/model.joblib) is used unchanged. This script adds three things:

1. question_frequencies.json: for each question and condition, how often the training
   partition answered yes, no or not asked (Laplace-smoothed). The backend uses it to pick
   the next question by expected information gain.
2. adaptive_validation.csv: the questioning policy simulated on the validation partition for
   several stop thresholds. The stop threshold is chosen here, by the rule below.
3. adaptive_test.json (with --test): the chosen policy evaluated on the test partition. This
   is a second, declared use of the test set: the model and every threshold were fixed on
   validation before it runs, and nothing is changed afterwards.

Policy, as the backend runs it: the three danger signs are always asked first, and a Yes ends
questioning (urgent referral). After that, the next question is the one that minimises the
expected entropy of the condition, using a Naive Bayes posterior over the answers so far.
Questioning stops when the deployed model's top probability reaches the stop threshold, or
when every question has been asked. The result is the deployed model's output with every
unasked question sent as 'not asked'.

Stop-threshold rule: the lowest threshold whose final answer agrees with the full 35-question
answer for at least 99.5% of non-urgent validation patients, and whose malaria and
URTI/pneumonia recall are no lower than with all 35 questions.

Run:  python -m src.adaptive          (frequencies + validation)
      python -m src.adaptive --test   (also the single test evaluation)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, recall_score

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
SPLITS = ROOT / "data" / "splits"
VALUES = (-1, 0, 1)
VALUE_NAMES = {-1: "unknown", 0: "no", 1: "yes"}
CANDIDATE_STOPS = (0.80, 0.85, 0.90, 0.95)
MIN_AGREEMENT = 0.995
HIGH_SEVERITY = ("malaria", "urti_pneumonia")


def load():
    bundle = joblib.load(RESULTS / "model.joblib")
    symptoms = [f for f in bundle["feature_order"] if f not in ("age_band", "sex")]
    return bundle, symptoms


def answer_frequencies(train: pd.DataFrame, symptoms: list[str], conditions: list[str]) -> np.ndarray:
    """P[q, k, v]: share of training records of condition k answering question q with value v."""
    P = np.zeros((len(symptoms), len(conditions), len(VALUES)))
    for qi, q in enumerate(symptoms):
        for ki, k in enumerate(conditions):
            col = train.loc[train["label"] == k, q]
            for vi, v in enumerate(VALUES):
                P[qi, ki, vi] = ((col == v).sum() + 1) / (len(col) + len(VALUES))
    return P


def entropy(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-12, 1.0)
    return -(p * np.log(p)).sum(-1)


def next_question(post: np.ndarray, P: np.ndarray, asked: np.ndarray) -> np.ndarray:
    """For each row, the unasked question with the lowest expected posterior entropy."""
    pv = np.einsum("nk,qkv->nqv", post, P)
    after = post[:, None, :, None] * P[None]
    after = after / after.sum(2, keepdims=True)
    exp_h = (pv * entropy(np.swapaxes(after, 2, 3))).sum(-1)
    exp_h[asked] = np.inf
    return exp_h.argmin(1)


def naive_bayes_posterior(truth: np.ndarray, asked: np.ndarray, P: np.ndarray) -> np.ndarray:
    logp = np.zeros((truth.shape[0], P.shape[1]))
    for qi in range(P.shape[0]):
        vi = np.searchsorted(VALUES, truth[:, qi])
        logp += np.where(asked[:, [qi]], np.log(P[qi][:, vi].T), 0.0)
    post = np.exp(logp - logp.max(1, keepdims=True))
    return post / post.sum(1, keepdims=True)


def simulate(data: pd.DataFrame, bundle: dict, symptoms: list[str], P: np.ndarray, stop: float):
    """Run the policy on every record; returns questions asked and final model probabilities."""
    model, order = bundle["model"], bundle["feature_order"]
    truth = data[symptoms].to_numpy()
    danger = [symptoms.index(d) for d in bundle["danger_signs"]]
    asked = np.zeros(truth.shape, bool)
    asked[:, danger] = True
    active = np.ones(len(data), bool)
    frame = data[order].copy()

    def probs_now():
        frame[symptoms] = np.where(asked, truth, -1)
        return model.predict_proba(frame[order])

    while True:
        probs = probs_now()
        urgent = (np.where(asked[:, danger], truth[:, danger], 0) == 1).any(1)
        active &= ~((probs.max(1) >= stop) | asked.all(1) | urgent)
        if not active.any():
            break
        # P is indexed in the model's own class order, so the posterior lines up with it.
        nxt = next_question(naive_bayes_posterior(truth, asked, P), P, asked)
        rows = np.where(active)[0]
        asked[rows, nxt[rows]] = True
    return asked.sum(1), probs_now()


def evaluate(data, bundle, symptoms, P, stop) -> dict:
    model = bundle["model"]
    labels = list(model.classes_)
    y = data["label"].to_numpy()
    full = np.array(labels)[model.predict_proba(data[bundle["feature_order"]]).argmax(1)]
    urgent = (data[bundle["danger_signs"]].to_numpy() == 1).any(1)
    nu = ~urgent
    n, probs = simulate(data, bundle, symptoms, P, stop)
    pred = np.array(labels)[probs.argmax(1)]
    rec_a = recall_score(y[nu], pred[nu], average=None, labels=labels)
    rec_f = recall_score(y[nu], full[nu], average=None, labels=labels)
    out = {
        "stop_threshold": stop,
        "patients": int(len(data)),
        "urgent_share": float(urgent.mean()),
        "mean_questions_all": float(n.mean()),
        "mean_questions_non_urgent": float(n[nu].mean()),
        "median_questions_non_urgent": float(np.median(n[nu])),
        "share_stopping_before_35_non_urgent": float((n[nu] < len(symptoms)).mean()),
        "agreement_with_full_non_urgent": float((pred[nu] == full[nu]).mean()),
        "macro_f1_adaptive_non_urgent": float(f1_score(y[nu], pred[nu], average="macro")),
        "macro_f1_full_non_urgent": float(f1_score(y[nu], full[nu], average="macro")),
    }
    for c in HIGH_SEVERITY:
        out[f"recall_{c}_adaptive"] = float(rec_a[labels.index(c)])
        out[f"recall_{c}_full"] = float(rec_f[labels.index(c)])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="also run the single test-set evaluation")
    args = ap.parse_args()

    bundle, symptoms = load()
    labels = list(bundle["model"].classes_)
    train = pd.read_csv(SPLITS / "train.csv")
    val = pd.read_csv(SPLITS / "validation.csv")
    P = answer_frequencies(train, symptoms, labels)

    rows = [evaluate(val, bundle, symptoms, P, s) for s in CANDIDATE_STOPS]
    pd.DataFrame(rows).to_csv(RESULTS / "adaptive_validation.csv", index=False, float_format="%.4f")
    ok = [r for r in rows if r["agreement_with_full_non_urgent"] >= MIN_AGREEMENT
          and all(r[f"recall_{c}_adaptive"] >= r[f"recall_{c}_full"] for c in HIGH_SEVERITY)]
    chosen = min(ok, key=lambda r: r["stop_threshold"]) if ok else rows[-1]
    print(pd.DataFrame(rows).round(4).to_string(index=False))
    print(f"chosen stop threshold: {chosen['stop_threshold']}")

    freq = {
        "description": "P(answer | condition) from the training partition, Laplace-smoothed. Used to choose the next question.",
        "model_version": bundle["model_version"],
        "config_hash": bundle["config_hash"],
        "stop_threshold": chosen["stop_threshold"],
        "conditions": labels,
        "questions": {q: {k: {VALUE_NAMES[v]: round(float(P[qi, ki, vi]), 6) for vi, v in enumerate(VALUES)}
                          for ki, k in enumerate(labels)} for qi, q in enumerate(symptoms)},
    }
    (RESULTS / "question_frequencies.json").write_text(json.dumps(freq, indent=1), encoding="utf-8")

    if args.test:
        out = RESULTS / "adaptive_test.json"
        if out.exists():
            raise SystemExit("adaptive_test.json already exists: the test partition is evaluated once.")
        test = pd.read_csv(SPLITS / "test.csv")
        res = evaluate(test, bundle, symptoms, P, chosen["stop_threshold"])
        res["note"] = "Second, declared use of the test partition; every setting was fixed on validation first."
        out.write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
