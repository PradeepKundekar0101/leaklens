"""Plain-language reasons: every feature with one-sided rz > 2.5, plus the top 3 SHAP contributors."""

import numpy as np

from app.services.anomaly.features import ALL_FEATURES, LABELS, format_value

REASON_THRESHOLD = 2.5


def z_reasons(feature_z: dict[str, dict]) -> list[dict]:
    reasons = []
    for feature, d in sorted(feature_z.items(), key=lambda kv: -kv[1]["one_sided"]):
        if d["one_sided"] <= REASON_THRESHOLD or d["median"] is None:
            continue
        direction = "below" if feature == "days_since_policy_start" else "vs"
        text = (
            f"{LABELS[feature]} {format_value(feature, d['value'])} {direction} "
            f"{format_value(feature, d['median'])} peer median ({d['one_sided']:.1f} robust z)"
        )
        reasons.append({"source": "robust_z", "feature": feature, "text": text, "z": d["one_sided"]})
    return reasons


def shap_contributors(shap_row: np.ndarray, values: np.ndarray, top: int = 3) -> list[dict]:
    """IsolationForest SHAP explains path length: negative values push a claim towards 'anomalous'."""
    order = np.argsort(shap_row)
    out = []
    for idx in order[:top]:
        if shap_row[idx] >= 0:
            break
        feature = ALL_FEATURES[idx]
        out.append(
            {
                "feature": feature,
                "label": LABELS[feature],
                "value": float(values[idx]),
                "display_value": format_value(feature, float(values[idx])),
                "shap": round(float(shap_row[idx]), 4),
            }
        )
    return out


def shap_reasons(contributors: list[dict]) -> list[dict]:
    return [
        {
            "source": "isolation_forest",
            "feature": c["feature"],
            "text": f"{c['label']} ({c['display_value']}) is among the strongest drivers of the unusualness score",
            "shap": c["shap"],
        }
        for c in contributors
    ]
