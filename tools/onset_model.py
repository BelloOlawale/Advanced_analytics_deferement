#!/usr/bin/env python3
"""
onset_model.py - Slice 9: onset labels, Layer 2 v1 backtest and rules comparison.

WHAT IT DOES
    1. Reads the Fabric gold snapshot (or a local reference snapshot).
    2. Builds three 7-day onset labels:
         - large_loss      : deferred oil reaches the station p90 after 3 quiet days
         - coded_material  : a coded episode starts with deferred oil >= station p90
         - material        : union of the two (primary target)
    3. Trains a regularised logistic-regression model on process/deviation features.
    4. Runs a chronological 3-fold backtest (no random split).
    5. Compares the model with rules v1 on:
         - PR-AUC / ROC-AUC
         - precision / recall at top 10% and 20%
         - alerts at the same budget as rules v1
         - confirmed / false alarms / median lead time
    6. Writes CSV/JSON evidence under --output-dir.

IMPORTANT
    This is a small-sample experiment (5 stations, 90 days, ~34 material events).
    It is a directional test, not a production model validation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

REPO = Path(__file__).resolve().parent.parent

# Feature set: deviations, process levels and sequential features. Rules-v1
# outputs (risk_score, alert fields) are deliberately excluded so the model is
# a genuine challenger, not a copy of the champion.
METRICS = ["oil", "deferred_oil", "deferment_pct", "target_gap_pct", "uptime", "thp", "bean", "water_cut"]


def feature_columns(df: pd.DataFrame) -> list[str]:
    cols = [f"z_{m}" for m in METRICS] + [f"dev_{m}" for m in METRICS]
    cols += ["deviation_score", "signals_deviated"]
    cols += [
        "actual_oil", "deferred_oil", "deferment_pct", "target_gap_pct",
        "uptime_avg", "thp_avg", "bean_avg", "water_rf_avg",
    ]
    cols += [
        "oil_lag_1", "oil_lag_7", "oil_delta_1", "oil_delta_7",
        "oil_roll_mean_7", "oil_roll_std_7", "oil_roll_mean_28",
        "oil_ewma_7_prev", "oil_slope_7", "oil_cusum_pos", "oil_cusum_neg",
        "uptime_roll_mean_7", "uptime_roll_mean_28", "uptime_slope_7",
        "uptime_cusum_pos", "uptime_cusum_neg",
        "deferment_pct_roll_mean_7", "deferment_pct_roll_mean_28",
        "deferment_pct_slope_7", "deferment_pct_cusum_pos", "deferment_pct_cusum_neg",
        "deferred_oil_roll_mean_7", "deferred_oil_roll_sum_7",
        "deferred_value_usd_roll_mean_7", "deferred_value_usd_roll_sum_7",
        "event_count", "coded_event_count", "event_count_roll_sum_7",
        "coded_event_count_roll_sum_7", "weekday_num", "is_weekend",
    ]
    return [c for c in cols if c in df.columns]


def load_tables(fabric_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    need = [
        "gold_entity_day_features", "gold_risk_daily", "gold_entity_baseline",
        "gold_alert", "silver_deferment_episode",
    ]
    frames = {name: pd.read_csv(fabric_dir / f"{name}.csv", low_memory=False) for name in need}
    for col in ("gold_entity_day_features", "gold_risk_daily"):
        frames[col]["date"] = pd.to_datetime(frames[col]["date"])
    frames["gold_alert"]["alert_date"] = pd.to_datetime(frames["gold_alert"]["alert_date"])
    frames["silver_deferment_episode"]["episode_start"] = pd.to_datetime(
        frames["silver_deferment_episode"]["episode_start"]
    )
    return (
        frames["gold_entity_day_features"], frames["gold_risk_daily"],
        frames["gold_entity_baseline"], frames["gold_alert"],
        frames["silver_deferment_episode"],
    )


def build_events(
    risk: pd.DataFrame,
    baseline: pd.DataFrame,
    episodes: pd.DataFrame,
    horizon: int = 7,
) -> dict[str, pd.DataFrame]:
    p90 = dict(
        zip(
            baseline.query("metric == 'deferred_oil'").entity_id,
            baseline.query("metric == 'deferred_oil'").p90,
        )
    )
    observed = risk[risk.is_observed][["station_id", "date", "deferred_oil"]].sort_values(
        ["station_id", "date"]
    )
    loss_rows = []
    for sid, group in observed.groupby("station_id"):
        group = group.sort_values("date").reset_index(drop=True)
        threshold = p90.get(sid)
        if threshold is None or pd.isna(threshold):
            continue
        for _, row in group.iterrows():
            if pd.isna(row.deferred_oil) or row.deferred_oil < threshold:
                continue
            previous = group[group.date < row.date].tail(3)
            if len(previous) == 3 and (previous.deferred_oil < threshold).all():
                loss_rows.append({"station_id": sid, "date": row.date})
    large_loss = pd.DataFrame(loss_rows)

    coded = episodes[episodes.has_coded_event == True][
        ["station_id", "episode_start", "deferred_oil", "cause_code"]
    ].rename(columns={"episode_start": "date"})
    coded_material = coded[
        coded.apply(lambda row: row.deferred_oil >= p90.get(row.station_id, 1e18), axis=1)
    ].copy()
    material = pd.concat([large_loss, coded_material], ignore_index=True).drop_duplicates(
        ["station_id", "date"]
    )
    return {
        "large_loss": large_loss,
        "coded_material": coded_material,
        "material": material,
    }


def build_dataset(features: pd.DataFrame, risk: pd.DataFrame, horizon: int = 7) -> pd.DataFrame:
    df = features[(features.is_observed) & (features.baseline_phase == "scored")].copy()
    df = df.merge(
        risk[["station_id", "date", "risk_score", "max_bad_z", "primary_bad_z",
              "weighted_severity", "risk_tier"]],
        on=["station_id", "date"],
        how="left",
    )
    df["label_complete"] = df["date"] + pd.Timedelta(days=horizon) <= risk["date"].max()
    return df


def label_for(df: pd.DataFrame, events: pd.DataFrame, horizon: int = 7) -> pd.Series:
    y = np.zeros(len(df), dtype=int)
    for i, row in df.iterrows():
        end = row.date + pd.Timedelta(days=horizon)
        y[i] = int(
            ((events.station_id == row.station_id) & (events.date > row.date) & (events.date <= end)).any()
        )
    return pd.Series(y, index=df.index, name="y")


def make_model():
    # Regularised logistic regression is deliberately simple: n is small and
    # interpretability matters more than squeezing the last point of AP.
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=0.1, class_weight="balanced", max_iter=3000, random_state=42),
    )


def backtest(
    df: pd.DataFrame,
    X: pd.DataFrame,
    y: pd.Series,
    n_splits: int = 3,
) -> tuple[np.ndarray, np.ndarray, list[dict], list[tuple], pd.Index]:
    dates = pd.Index(sorted(df[df.label_complete].date.unique()))
    splits = list(TimeSeriesSplit(n_splits=n_splits).split(dates))
    pred = np.full(len(df), np.nan)
    train_pred = np.full(len(df), np.nan)
    fold_meta = []
    folds = []
    for k, (tr_idx, te_idx) in enumerate(splits, 1):
        tr_dates, te_dates = dates[tr_idx], dates[te_idx]
        tr = df.date.isin(tr_dates) & df.label_complete
        te = df.date.isin(te_dates) & df.label_complete
        model = make_model()
        model.fit(X[tr], y[tr])
        pred[te.to_numpy()] = model.predict_proba(X[te])[:, 1]
        train_pred[tr.to_numpy()] = model.predict_proba(X[tr])[:, 1]
        fold_meta.append((k, tr_dates, te_dates, tr, te))
        folds.append({
            "fold": k,
            "train_start": str(tr_dates.min().date()),
            "train_end": str(tr_dates.max().date()),
            "train_rows": int(tr.sum()),
            "train_pos": int(y[tr].sum()),
            "test_start": str(te_dates.min().date()),
            "test_end": str(te_dates.max().date()),
            "test_rows": int(te.sum()),
            "test_pos": int(y[te].sum()),
            "model_ap": float(average_precision_score(y[te], pred[te.to_numpy()]))
            if y[te].nunique() > 1 else None,
            "rules_ap": float(average_precision_score(y[te], df.loc[te, "risk_score"]))
            if y[te].nunique() > 1 else None,
        })
    return pred, train_pred, folds, fold_meta, dates


def ranking_metrics(y: np.ndarray, model_score: np.ndarray, rules_score: np.ndarray) -> dict:
    out = {
        "rows": int(len(y)),
        "positives": int(y.sum()),
        "base_rate": float(y.mean()),
        "model": {
            "ap": float(average_precision_score(y, model_score)),
            "auc": float(roc_auc_score(y, model_score)),
        },
        "rules_v1": {
            "ap": float(average_precision_score(y, rules_score)),
            "auc": float(roc_auc_score(y, rules_score)),
        },
    }
    for frac in (0.10, 0.20):
        k = int(np.ceil(len(y) * frac))
        for name, score in (("model", model_score), ("rules_v1", rules_score)):
            idx = np.argsort(-score)[:k]
            out[f"{name}_top_{int(frac*100)}pct"] = {
                "k": k,
                "precision": float(y[idx].mean()),
                "recall": float(y[idx].sum() / y.sum()),
            }
    return out


def simulate_alerts(pred: np.ndarray, fold_meta: list[tuple], df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    alerts = []
    for k, tr_dates, te_dates, tr, te in fold_meta:
        last = {}
        for d in te_dates:
            for sid in sorted(df.station_id.unique()):
                sel = (df.station_id == sid) & (df.date == d) & df.label_complete
                if not sel.any():
                    continue
                s = pred[sel.to_numpy()][0]
                if pd.isna(s):
                    continue
                if s >= threshold and (sid not in last or (d - last[sid]).days >= 3):
                    alerts.append({"station_id": sid, "alert_date": d, "score": float(s), "fold": k})
                    last[sid] = d
    return pd.DataFrame(alerts)


def evaluate_alerts(alerts: pd.DataFrame, events: pd.DataFrame, horizon: int = 7) -> dict:
    confirmed, lead = [], []
    for _, row in alerts.iterrows():
        end = row.alert_date + pd.Timedelta(days=horizon)
        hit = events[
            (events.station_id == row.station_id)
            & (events.date > row.alert_date)
            & (events.date <= end)
        ]
        confirmed.append(len(hit) > 0)
        if len(hit):
            lead.append((hit.date.min() - row.alert_date).days)
    n = len(confirmed)
    c = int(sum(confirmed))
    return {
        "alerts": n,
        "confirmed": c,
        "false": n - c,
        "precision": round(c / n, 4) if n else None,
        "median_lead_days": float(pd.Series(lead).median()) if lead else None,
        "lead_days": lead,
    }


def budget_matched_alerts(
    pred: np.ndarray,
    fold_meta: list[tuple],
    df: pd.DataFrame,
    target_alerts: int,
) -> tuple[pd.DataFrame, float]:
    """Choose a score threshold that gets as close as possible to the rules alert budget.

    The threshold is chosen from the score distribution only; labels are not used.
    This is a budget-matched ranking comparison, not a production threshold.
    """
    mask = df.label_complete & ~np.isnan(pred)
    candidates = np.unique(np.quantile(pred[mask], np.linspace(0.50, 0.995, 250)))
    best = None
    for threshold in candidates:
        alerts = simulate_alerts(pred, fold_meta, df, float(threshold))
        diff = abs(len(alerts) - target_alerts)
        if best is None or diff < best[0]:
            best = (diff, float(threshold), alerts)
    return best[2], best[1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Slice 9 onset-model backtest.")
    ap.add_argument("--fabric-dir", default="test_data/parity/fabric",
                    help="directory holding the Fabric CSV snapshot")
    ap.add_argument("--output-dir", default="test_data/slice9",
                    help="where to write labels, scores and metrics")
    ap.add_argument("--horizon", type=int, default=7)
    ap.add_argument("--splits", type=int, default=3)
    args = ap.parse_args()

    fabric_dir = (REPO / args.fabric_dir).resolve() if not Path(args.fabric_dir).is_absolute() else Path(args.fabric_dir)
    output_dir = (REPO / args.output_dir).resolve() if not Path(args.output_dir).is_absolute() else Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    features, risk, baseline, rule_alerts, episodes = load_tables(fabric_dir)
    events = build_events(risk, baseline, episodes, args.horizon)
    df = build_dataset(features, risk, args.horizon)
    cols = feature_columns(df)
    X = df[cols].apply(pd.to_numeric, errors="coerce")

    # Rules baseline in the same evaluation window as the model's test folds.
    dates = pd.Index(sorted(df[df.label_complete].date.unique()))
    splits = list(TimeSeriesSplit(n_splits=args.splits).split(dates))
    test_start = dates[splits[0][1][0]]
    test_end = dates[splits[-1][1][-1]]
    rules_window = rule_alerts[
        (rule_alerts.alert_date >= test_start) & (rule_alerts.alert_date <= test_end)
    ].copy()
    target_alerts = len(rules_window)

    result = {
        "horizon_days": args.horizon,
        "splits": args.splits,
        "feature_count": len(cols),
        "features": cols,
        "eval_window": {"start": str(test_start.date()), "end": str(test_end.date())},
        "rules_window_alerts": target_alerts,
        "targets": {},
    }

    for target_name, target_events in events.items():
        y = label_for(df, target_events, args.horizon)
        pred, train_pred, folds, fold_meta, _ = backtest(df, X, y, args.splits)
        mask = df.label_complete & ~np.isnan(pred)
        y_eval = y[mask].to_numpy()
        metrics = ranking_metrics(y_eval, pred[mask], df.loc[mask, "risk_score"].to_numpy())
        metrics["folds"] = folds
        metrics["events"] = int(len(target_events))
        metrics["positive_rate_complete"] = float(y[df.label_complete].mean())

        # Rules alert outcomes in the same window, against this target.
        rules_eval = evaluate_alerts(rules_window, target_events, args.horizon)
        model_alerts, threshold = budget_matched_alerts(pred, fold_meta, df, target_alerts)
        model_eval = evaluate_alerts(model_alerts, target_events, args.horizon)
        metrics["rules_alerts"] = rules_eval
        metrics["model_alerts"] = model_eval
        metrics["model_threshold"] = threshold
        metrics["model_alert_rows"] = model_alerts.to_dict(orient="records")
        model_lead = model_eval["median_lead_days"] or 0.0
        rules_lead = rules_eval["median_lead_days"] or 0.0
        false_delta = model_eval["false"] - rules_eval["false"]
        lead_gain = model_lead - rules_lead
        gate_pass = false_delta <= 0 and lead_gain > 0
        metrics["gate"] = {
            "lead_gain_days": lead_gain,
            "false_alarm_delta": false_delta,
            "pass": bool(gate_pass),
            "rule": "keep Layer 2 only if it adds median lead time at no more false alarms",
        }
        metrics["recommendation"] = (
            "promote model as challenger" if gate_pass else "keep rules v1"
        )
        result["targets"][target_name] = metrics
        print(
            f"{target_name:15s} events={len(target_events):3d} rows={metrics['rows']:3d} "
            f"pos={metrics['positives']:3d} base={metrics['base_rate']:.3f} | "
            f"model AP={metrics['model']['ap']:.3f} rules AP={metrics['rules_v1']['ap']:.3f} | "
            f"model alerts={model_eval['alerts']} (c={model_eval['confirmed']}, f={model_eval['false']}, "
            f"lead={model_eval['median_lead_days']}) | rules alerts={rules_eval['alerts']} "
            f"(c={rules_eval['confirmed']}, f={rules_eval['false']}, lead={rules_eval['median_lead_days']})"
        )

        # Write target-specific evidence
        target_df = df[["station_id", "date", "label_complete", "risk_score", "primary_bad_z"]].copy()
        target_df["y"] = y.values
        target_df["model_score"] = pred
        target_df.to_csv(output_dir / f"scores_{target_name}.csv", index=False)
        if len(model_alerts):
            model_alerts.to_csv(output_dir / f"alerts_model_{target_name}.csv", index=False)
        if len(rules_window):
            rules_window.to_csv(output_dir / "alerts_rules_window.csv", index=False)

    primary = result["targets"].get("material", {})
    result["overall_recommendation"] = (
        "keep rules v1"
        if not primary.get("gate", {}).get("pass", False)
        else "promote model as challenger"
    )
    (output_dir / "backtest_metrics.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nWrote {output_dir / 'backtest_metrics.json'}")
    print("Verdict is per target; see the JSON and docs/slice9-onset-model-report.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
