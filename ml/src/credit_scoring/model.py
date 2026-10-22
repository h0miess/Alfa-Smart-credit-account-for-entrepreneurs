"""Загрузка обученной модели и инференс: PD, скоринговый балл, вклад факторов.

Артефакты без pickle: бустинг в текстовом формате LightGBM, калибровка и
метаданные — JSON. Их можно ревьюить, версионировать и безопасно загружать.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from .features import FEATURE_LABELS, MODEL_FEATURES, MONOTONE, build_features

DEFAULT_ARTIFACTS = Path(__file__).resolve().parents[2] / "artifacts"

# Шкала баллов как у классических скоркарт: 600 баллов при шансах 50:1,
# +50 баллов при удвоении шансов «не дефолт : дефолт».
SCORE_BASE, SCORE_ODDS, SCORE_PDO = 600.0, 50.0, 50.0


def pd_to_score(pd_value: float) -> int:
    p = min(max(pd_value, 1e-6), 1 - 1e-6)
    odds = (1 - p) / p
    factor = SCORE_PDO / math.log(2)
    return int(round(SCORE_BASE + factor * math.log(odds / SCORE_ODDS)))


@dataclass
class Factor:
    feature: str
    label: str
    value: float | str
    impact: float  # вклад в лог-шансы дефолта: >0 повышает риск


@dataclass
class ScoreResult:
    pd: float
    score: int
    risk_factors: list[Factor]
    positive_factors: list[Factor]


class ScoringModel:
    def __init__(self, artifacts_dir: Path | str | None = None):
        d = Path(artifacts_dir or os.environ.get("MODEL_DIR", DEFAULT_ARTIFACTS))
        self.booster = lgb.Booster(model_file=str(d / "model.txt"))
        calib = json.loads((d / "calibration.json").read_text())
        self._cx = np.asarray(calib["x"], dtype=float)
        self._cy = np.asarray(calib["y"], dtype=float)
        self.card = json.loads((d / "model_card.json").read_text())
        if self.booster.feature_name() != MODEL_FEATURES:
            raise RuntimeError("Артефакт модели не совпадает с текущим набором признаков")

    @property
    def version(self) -> str:
        return self.card["model_version"]

    def calibrate(self, raw_pd: np.ndarray) -> np.ndarray:
        # Изотоническая калибровка, сохранённая как кусочно-линейная функция.
        return np.clip(np.interp(raw_pd, self._cx, self._cy), 1e-4, 0.9999)

    def predict_pd(self, raw: pd.DataFrame) -> np.ndarray:
        X = build_features(raw)
        return self.calibrate(self.booster.predict(X))

    def score(self, raw: pd.DataFrame, top_k: int = 4) -> list[ScoreResult]:
        X = build_features(raw)
        raw_pd = self.booster.predict(X)
        pds = self.calibrate(raw_pd)
        # Вклады SHAP (TreeSHAP встроен в LightGBM), последняя колонка — базовое значение.
        contrib = self.booster.predict(X, pred_contrib=True)[:, :-1]

        results = []
        for i in range(len(X)):
            factors = [
                Factor(
                    feature=f,
                    label=FEATURE_LABELS.get(f, f),
                    value=_py(X.iloc[i][f]),
                    impact=round(float(contrib[i, j]), 4),
                )
                for j, f in enumerate(MODEL_FEATURES)
            ]
            risk = sorted((f for f in factors if f.impact > 0.02), key=lambda f: -f.impact)
            good = sorted((f for f in factors if f.impact < -0.02), key=lambda f: f.impact)
            results.append(
                ScoreResult(
                    pd=float(pds[i]),
                    score=pd_to_score(float(pds[i])),
                    risk_factors=risk[:top_k],
                    positive_factors=good[:top_k],
                )
            )
        return results


def _py(v):
    if isinstance(v, (np.floating, float)):
        return round(float(v), 4)
    if isinstance(v, (np.integer, int)):
        return int(v)
    return str(v)


__all__ = ["ScoringModel", "ScoreResult", "Factor", "pd_to_score", "MONOTONE"]
