"""Business logic and selection for ``sm_df_early_warning``.

``model_spec.py`` holds the physical column schema (generated from the gold
tables).  This file selects the tables that belong in the serving model and
adds measures, relationships and descriptions.

Direct Lake resolves the physical Delta table by the *model table name*, so
model table names are identical to the ``lh_gold`` table names.
"""

MODEL_NAME = "sm_df_early_warning"
MODEL_CULTURE = "en-GB"
MODEL_DESCRIPTION = "Deferment early warning - gold serving model (rules v1)."

# The seven tables exposed to the report.  DQ tables and the wide feature table
# are deliberately excluded: they are build artefacts, not serving objects.
TABLES_IN_MODEL = [
    "gold_risk_daily",
    "gold_deviation_daily",
    "gold_alert",
    "gold_alert_outcome",
    "gold_entity_baseline",
    "gold_df_dim_date",
    "gold_df_dim_station",
]

TABLE_DESCRIPTIONS = {
    "gold_risk_daily": "Daily station risk score, tier and value at risk (rules v1).",
    "gold_deviation_daily": "Long-form deviations from the station baseline, one row per station-date-metric.",
    "gold_alert": "Fired alerts. Fire-on-change; deterministic backfill.",
    "gold_alert_outcome": "Outcome and realised lead time per alert. Preserved across runs.",
    "gold_entity_baseline": "Per-station robust normal range, one row per station-metric.",
    "gold_df_dim_date": "Calendar dimension for the gold window.",
    "gold_df_dim_station": "Station dimension.",
}

# (table, name, DAX expression, format string)
MEASURES = [
    # --- risk -------------------------------------------------------------
    ("gold_risk_daily", "Scored Days",
     'CALCULATE(COUNTROWS(\'gold_risk_daily\'), \'gold_risk_daily\'[baseline_phase] = "scored", \'gold_risk_daily\'[is_observed] = TRUE())',
     "#,##0"),
    ("gold_risk_daily", "Observed Days",
     'CALCULATE(COUNTROWS(\'gold_risk_daily\'), \'gold_risk_daily\'[is_observed] = TRUE())',
     "#,##0"),
    ("gold_risk_daily", "Data Coverage %",
     'DIVIDE([Observed Days], COUNTROWS(\'gold_risk_daily\'))',
     "0.0%"),
    ("gold_risk_daily", "Red Days",
     'CALCULATE(COUNTROWS(\'gold_risk_daily\'), \'gold_risk_daily\'[risk_tier] = "Red", \'gold_risk_daily\'[is_observed] = TRUE())',
     "#,##0"),
    ("gold_risk_daily", "Amber Days",
     'CALCULATE(COUNTROWS(\'gold_risk_daily\'), \'gold_risk_daily\'[risk_tier] = "Amber", \'gold_risk_daily\'[is_observed] = TRUE())',
     "#,##0"),
    ("gold_risk_daily", "Green Days",
     'CALCULATE(COUNTROWS(\'gold_risk_daily\'), \'gold_risk_daily\'[risk_tier] = "Green", \'gold_risk_daily\'[is_observed] = TRUE())',
     "#,##0"),
    ("gold_risk_daily", "Excess Value at Risk (USD)",
     'SUM(\'gold_risk_daily\'[exp_usd])',
     "$#,##0"),
    ("gold_risk_daily", "Deferred Oil (bbl)",
     'SUM(\'gold_risk_daily\'[deferred_oil])',
     "#,##0.0"),
    ("gold_risk_daily", "Latest Risk Score",
     'VAR d = CALCULATE(MAX(\'gold_risk_daily\'[date]), \'gold_risk_daily\'[is_observed] = TRUE())\n'
     'RETURN CALCULATE(MAX(\'gold_risk_daily\'[risk_score]), \'gold_df_dim_date\'[date] = d)',
     "0.000"),
    ("gold_risk_daily", "Risk Score",
     'MAX(\'gold_risk_daily\'[risk_score])',
     "0.000"),
    ("gold_risk_daily", "Latest Risk Tier",
     'VAR d = CALCULATE(MAX(\'gold_risk_daily\'[date]), \'gold_risk_daily\'[is_observed] = TRUE())\n'
     'RETURN CALCULATE(FIRSTNONBLANK(\'gold_risk_daily\'[risk_tier], 1), \'gold_df_dim_date\'[date] = d, \'gold_risk_daily\'[is_observed] = TRUE())',
     None),
    ("gold_risk_daily", "Stations at Red (latest)",
     'VAR d = CALCULATE(MAX(\'gold_risk_daily\'[date]), \'gold_risk_daily\'[is_observed] = TRUE())\n'
     'RETURN COALESCE(CALCULATE(DISTINCTCOUNT(\'gold_risk_daily\'[station_id]), \'gold_df_dim_date\'[date] = d, \'gold_risk_daily\'[risk_tier] = "Red"), 0)',
     "#,##0"),
    ("gold_risk_daily", "Latest Observed Date",
     'CALCULATE(MAX(\'gold_risk_daily\'[date]), \'gold_risk_daily\'[is_observed] = TRUE())',
     "yyyy-mm-dd"),

    # --- alerts -----------------------------------------------------------
    ("gold_alert", "Alerts Fired",
     'COUNTROWS(\'gold_alert\')',
     "#,##0"),
    ("gold_alert", "Red Alerts",
     'CALCULATE(COUNTROWS(\'gold_alert\'), \'gold_alert\'[tier] = "Red")',
     "#,##0"),
    ("gold_alert", "Amber Alerts",
     'CALCULATE(COUNTROWS(\'gold_alert\'), \'gold_alert\'[tier] = "Amber")',
     "#,##0"),
    ("gold_alert", "Open Alerts",
     'CALCULATE(COUNTROWS(\'gold_alert\'), NOT(\'gold_alert\'[alert_status] IN {"Closed", "Resolved", "Dismissed"}))',
     "#,##0"),
    ("gold_alert", "Excess USD at Alert",
     'SUM(\'gold_alert\'[exp_usd])',
     "$#,##0"),
    ("gold_alert", "Largest Alert (USD)",
     'MAX(\'gold_alert\'[exp_usd])',
     "$#,##0"),
    ("gold_alert", "Alerted Stations",
     'DISTINCTCOUNT(\'gold_alert\'[station_id])',
     "#,##0"),
    ("gold_alert", "Alert Rate per Station per Week",
     'VAR n_alerts = COUNTROWS(\'gold_alert\')\n'
     'VAR n_stations = DISTINCTCOUNT(\'gold_alert\'[station_id])\n'
     'VAR first_d = MIN(\'gold_alert\'[alert_date])\n'
     'VAR last_d = MAX(\'gold_alert\'[alert_date])\n'
     'VAR days = DATEDIFF(first_d, last_d, DAY) + 1\n'
     'RETURN DIVIDE(n_alerts, n_stations * DIVIDE(days, 7))',
     "0.00"),

    # --- outcomes ---------------------------------------------------------
    ("gold_alert_outcome", "Alerts with Outcome",
     'COALESCE(CALCULATE(COUNTROWS(\'gold_alert_outcome\'), NOT(ISBLANK(\'gold_alert_outcome\'[event_occurred]))), 0)',
     "#,##0"),
    ("gold_alert_outcome", "Alerts Confirmed",
     'COALESCE(CALCULATE(COUNTROWS(\'gold_alert_outcome\'), \'gold_alert_outcome\'[event_occurred] = TRUE()), 0)',
     "#,##0"),
    ("gold_alert_outcome", "Alert Precision %",
     'DIVIDE([Alerts Confirmed], [Alerts with Outcome])',
     "0.0%"),
    ("gold_alert_outcome", "False Alarm Rate %",
     'DIVIDE([Alerts with Outcome] - [Alerts Confirmed], [Alerts with Outcome])',
     "0.0%"),
    ("gold_alert_outcome", "Median Lead Time (days)",
     'CALCULATE(MEDIAN(\'gold_alert_outcome\'[actual_lead_days]), \'gold_alert_outcome\'[event_occurred] = TRUE())',
     "0.0"),
    ("gold_alert_outcome", "Average Lead Time (days)",
     'CALCULATE(AVERAGE(\'gold_alert_outcome\'[actual_lead_days]), \'gold_alert_outcome\'[event_occurred] = TRUE())',
     "0.0"),
    ("gold_alert_outcome", "Alerts Awaiting Outcome",
     '[Alerts Fired] - [Alerts with Outcome]',
     "#,##0"),
    ("gold_alert_outcome", "Precision Display",
     'IF([Alerts with Outcome] = 0, "No evaluated outcomes yet", FORMAT([Alert Precision %], "0.0%"))',
     None),
    ("gold_alert_outcome", "Lead Time Display",
     'IF([Alerts with Outcome] = 0, "No evaluated outcomes yet", FORMAT([Median Lead Time (days)], "0.0") & " days")',
     None),

    # --- deviations -------------------------------------------------------
    ("gold_deviation_daily", "Bad Z",
     'AVERAGEX(\'gold_deviation_daily\', IF(\'gold_deviation_daily\'[higher_is_bad], \'gold_deviation_daily\'[robust_z], -\'gold_deviation_daily\'[robust_z]))',
     "0.00"),
    ("gold_deviation_daily", "Actual Oil",
     'CALCULATE(SUM(\'gold_deviation_daily\'[value]), \'gold_deviation_daily\'[metric] = "oil")',
     "#,##0.0"),
    ("gold_deviation_daily", "Expected Oil",
     'CALCULATE(SUM(\'gold_deviation_daily\'[expected]), \'gold_deviation_daily\'[metric] = "oil")',
     "#,##0.0"),
    ("gold_deviation_daily", "Bad Z (scored)",
     'CALCULATE([Bad Z], \'gold_deviation_daily\'[baseline_phase] = "scored")',
     "0.00"),
    ("gold_deviation_daily", "Max Bad Z (scored)",
     'CALCULATE(MAXX(\'gold_deviation_daily\', IF(\'gold_deviation_daily\'[higher_is_bad], \'gold_deviation_daily\'[robust_z], -\'gold_deviation_daily\'[robust_z])), \'gold_deviation_daily\'[baseline_phase] = "scored")',
     "0.00"),
]

# (from_table, from_column, to_table, to_column)
RELATIONSHIPS = [
    ("gold_risk_daily", "date", "gold_df_dim_date", "date"),
    ("gold_deviation_daily", "date", "gold_df_dim_date", "date"),
    ("gold_alert", "alert_date", "gold_df_dim_date", "date"),
    ("gold_risk_daily", "station_id", "gold_df_dim_station", "station_id"),
    ("gold_deviation_daily", "entity_id", "gold_df_dim_station", "station_id"),
    ("gold_alert", "station_id", "gold_df_dim_station", "station_id"),
    ("gold_entity_baseline", "entity_id", "gold_df_dim_station", "station_id"),
    ("gold_alert_outcome", "alert_id", "gold_alert", "alert_id"),
]
