"""Обучение PD-модели МСБ и проверка её качества.

Схема валидации как в банковской практике:
  * development-выборка (заявки до 2025-10) -> train / valid (ранняя остановка и калибровка);
  * out-of-time (2025-10 .. 2026-06) -> итоговые метрики, которые мы и показываем.
Проверяем различающую способность (Gini, KS), точность (Brier, калибровка по
грейдам) и стабильность (PSI между разработкой и OOT) — те же три свойства,
по которым валидируют внутренние рейтинговые модели.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .decision import GRADES
from .features import CATEGORICAL, MODEL_FEATURES, build_features, monotone_vector
from .synth import generate

OOT_FROM = "2025-10"
TARGET = "default_12m"

LGB_PARAMS = dict(
    objective="binary",
    learning_rate=0.02,
    num_leaves=7,
    min_data_in_leaf=400,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=1,
    lambda_l2=5.0,
    monotone_constraints_method="advanced",
    verbose=-1,
    seed=42,
    num_threads=0,
)


def ks_stat(y, p):
    order = np.argsort(p)
    y = np.asarray(y)[order]
    cum_bad = np.cumsum(y) / max(y.sum(), 1)
    cum_good = np.cumsum(1 - y) / max((1 - y).sum(), 1)
    return float(np.max(np.abs(cum_bad - cum_good)))


def psi(expected, actual, bins=10):
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    e = np.histogram(expected, edges)[0] / len(expected)
    a = np.histogram(actual, edges)[0] / len(actual)
    e, a = np.clip(e, 1e-6, None), np.clip(a, 1e-6, None)
    return float(np.sum((a - e) * np.log(a / e)))


def metrics(y, p) -> dict:
    auc = roc_auc_score(y, p)
    return {
        "auc": round(auc, 4),
        "gini": round(2 * auc - 1, 4),
        "ks": round(ks_stat(y, p), 4),
        "pr_auc": round(average_precision_score(y, p), 4),
        "brier": round(brier_score_loss(y, p), 5),
        "logloss": round(log_loss(y, p), 5),
        "mean_pd": round(float(np.mean(p)), 4),
        "default_rate": round(float(np.mean(y)), 4),
        "n": int(len(y)),
    }


def grade_table(y, p) -> list[dict]:
    rows, lower = [], 0.0
    y, p = np.asarray(y), np.asarray(p)
    for g, upper in GRADES:
        m = (p >= lower) & (p < upper)
        rows.append({
            "grade": g,
            "pd_range": [lower, min(upper, 1.0)],
            "share": round(float(m.mean()), 4),
            "mean_pd": round(float(p[m].mean()), 4) if m.any() else None,
            "observed_dr": round(float(y[m].mean()), 4) if m.any() else None,
            "n": int(m.sum()),
        })
        lower = upper
    return rows


def baseline_logreg():
    num = [f for f in MODEL_FEATURES if f not in CATEGORICAL]
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), list(CATEGORICAL)),
        ("num", StandardScaler(), num),
    ])
    return make_pipeline(pre, LogisticRegression(max_iter=2000, C=0.5))


def train(df: pd.DataFrame, out_dir: Path) -> dict:
    dev = df[df.application_month < OOT_FROM].reset_index(drop=True)
    oot = df[df.application_month >= OOT_FROM].reset_index(drop=True)
    tr, va = train_test_split(dev, test_size=0.25, stratify=dev[TARGET], random_state=42)

    X_tr, X_va, X_oot = (build_features(d) for d in (tr, va, oot))
    y_tr, y_va, y_oot = tr[TARGET].values, va[TARGET].values, oot[TARGET].values

    params = dict(LGB_PARAMS, monotone_constraints=monotone_vector())
    dtr = lgb.Dataset(X_tr, y_tr, categorical_feature=list(CATEGORICAL), free_raw_data=False)
    dva = lgb.Dataset(X_va, y_va, reference=dtr)
    booster = lgb.train(
        params, dtr, num_boost_round=5000, valid_sets=[dva],
        callbacks=[lgb.early_stopping(200, verbose=False), lgb.log_evaluation(0)],
    )

    raw_va = booster.predict(X_va, num_iteration=booster.best_iteration)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=1e-4, y_max=0.9999).fit(raw_va, y_va)

    def predict(X):
        raw = booster.predict(X, num_iteration=booster.best_iteration)
        return np.clip(np.interp(raw, iso.X_thresholds_, iso.y_thresholds_), 1e-4, 0.9999)

    p_tr, p_va, p_oot = predict(X_tr), predict(X_va), predict(X_oot)

    lr = baseline_logreg().fit(X_tr, y_tr)
    p_lr_oot = lr.predict_proba(X_oot)[:, 1]

    gain = booster.feature_importance("gain", iteration=booster.best_iteration)
    importance = sorted(
        ({"feature": f, "gain_share": round(float(g / gain.sum()), 4)} for f, g in zip(MODEL_FEATURES, gain)),
        key=lambda r: -r["gain_share"],
    )

    version = f"pd-smb-lgbm-{date.today():%Y%m%d}"
    report = {
        "model_version": version,
        "trained_on": str(date.today()),
        "algorithm": "LightGBM GBDT, монотонные ограничения + изотоническая калибровка",
        "target": "Дефолт (90+ дней просрочки) в течение 12 месяцев после выдачи",
        "data": {
            "source": "Синтетические заявки (credit_scoring.synth), реальных данных клиентов нет",
            "dev_period": f"{dev.application_month.min()} .. {dev.application_month.max()}",
            "oot_period": f"{oot.application_month.min()} .. {oot.application_month.max()}",
            "n_train": len(tr), "n_valid": len(va), "n_oot": len(oot),
        },
        "best_iteration": booster.best_iteration,
        "params": {k: v for k, v in params.items() if k != "monotone_constraints"},
        "features": MODEL_FEATURES,
        "monotone_constraints": dict(zip(MODEL_FEATURES, monotone_vector())),
        "metrics": {
            "train": metrics(y_tr, p_tr),
            "valid": metrics(y_va, p_va),
            "oot": metrics(y_oot, p_oot),
            "oot_baseline_logreg": metrics(y_oot, p_lr_oot),
        },
        "oracle_oot_gini": (
            round(2 * roc_auc_score(y_oot, oot["_pd_true"]) - 1, 4) if "_pd_true" in oot else None
        ),
        "oracle_note": "Gini «истинного» PD синтетического генератора — теоретический потолок качества",
        "stability": {
            "psi_score_dev_vs_oot": round(psi(np.concatenate([p_tr, p_va]), p_oot), 4),
            "psi_note": "PSI < 0.1 — стабильно, 0.1-0.25 — умеренный сдвиг, > 0.25 — пересмотр модели",
        },
        "grades_oot": grade_table(y_oot, p_oot),
        "feature_importance": importance,
        "limitations": [
            "Обучена на синтетике: метрики показывают, что пайплайн восстанавливает заложенную зависимость, "
            "а не реальное качество на портфеле банка.",
            "Для промышленного использования нужно переобучение на исторических заявках и валидация независимым подразделением.",
            "Скоринг — только оценка риска; итоговое решение принимает кредитная политика (decision.py) и, при необходимости, андеррайтер.",
        ],
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(out_dir / "model.txt"), num_iteration=booster.best_iteration)
    (out_dir / "calibration.json").write_text(json.dumps(
        {"method": "isotonic", "x": iso.X_thresholds_.tolist(), "y": iso.y_thresholds_.tolist()}))
    (out_dir / "model_card.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    ap = argparse.ArgumentParser(description="Обучить PD-модель")
    ap.add_argument("--data", type=Path, help="CSV с заявками; если не задан — генерируется синтетика")
    ap.add_argument("--n", type=int, default=150_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path("artifacts"))
    args = ap.parse_args()

    df = pd.read_csv(args.data) if args.data else generate(args.n, args.seed, with_truth=True)
    r = train(df, args.out)

    m = r["metrics"]
    print(f"Модель {r['model_version']}, деревьев: {r['best_iteration']}")
    for name in ("train", "valid", "oot", "oot_baseline_logreg"):
        x = m[name]
        print(f"  {name:20s} Gini={x['gini']:.3f} KS={x['ks']:.3f} Brier={x['brier']:.4f} "
              f"PD={x['mean_pd']:.3%} DR={x['default_rate']:.3%}")
    print(f"  Потолок (истинный PD) OOT Gini: {r['oracle_oot_gini']}")
    print(f"  PSI dev->oot: {r['stability']['psi_score_dev_vs_oot']}")
    print("  Грейды (OOT):")
    for g in r["grades_oot"]:
        print(f"    {g['grade']}: доля {g['share']:.1%}, PD {g['mean_pd']}, факт DR {g['observed_dr']}")
    print("  Топ факторов:", ", ".join(f"{x['feature']}={x['gain_share']:.2f}" for x in r["feature_importance"][:8]))


if __name__ == "__main__":
    main()
