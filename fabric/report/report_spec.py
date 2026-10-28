"""PBIR specification for ``rpt_df_early_warning``.

The report is generated as PBIR (Power BI enhanced report format) instead of a
binary .pbix so it can be reviewed and versioned like code.

Pages:
    execOverview     - executive overview (Slice 2)
    stationDetail    - station drill-down (Slice 3)
    deviationHeatmap - metric x month deviation heatmap (Slice 4)
"""

REPORT_NAME = "rpt_df_early_warning"
REPORT_DESCRIPTION = "Deferment early warning - executive overview and alert drill-down."

PAGE_ID = "execOverview"
PAGE_NAME = "Executive overview"
STATION_PAGE_ID = "stationDetail"
STATION_PAGE_NAME = "Station detail"
HEAT_PAGE_ID = "deviationHeatmap"
HEAT_PAGE_NAME = "Deviation heatmap"
ALERT_PAGE_ID = "alertLog"
ALERT_PAGE_NAME = "Alert log"
OUTCOME_PAGE_ID = "outcomes"
OUTCOME_PAGE_NAME = "Outcomes & lead time"

# Canvas geometry (1280 x 720, the Power BI default).
W, H = 1280, 720


# --- PBIR field helpers ----------------------------------------------------

def measure(entity: str, prop: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}},
                        "Property": prop}}


def column(entity: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}},
                       "Property": prop}}


def proj(field: dict, query_ref: str, active: bool | None = None,
         display: str | None = None) -> dict:
    p = {"field": field, "queryRef": query_ref}
    if active is not None:
        p["active"] = active
    if display:
        p["displayName"] = display
    return p


def title(text: str, size: str = "12") -> dict:
    return {
        "title": [{
            "properties": {
                "show": {"expr": {"Literal": {"Value": "true"}}},
                "text": {"expr": {"Literal": {"Value": f"'{text}'"}}},
                "fontSize": {"expr": {"Literal": {"Value": f"'{size}'"}}},
            }
        }]
    }


def visual(name: str, vtype: str, x: float, y: float, w: float, h: float,
           query_state: dict | None = None, sort: list | None = None,
           objects: dict | None = None,
           container_objects: dict | None = None,
           z: int = 1000) -> dict:
    v = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.2.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w,
                     "tabOrder": z},
        "visual": {"visualType": vtype},
    }
    if query_state is not None:
        query = {"queryState": query_state}
        if sort:
            query["sortDefinition"] = {"sort": sort}
        v["visual"]["query"] = query
    if objects:
        v["visual"]["objects"] = objects
    if container_objects:
        v["visual"]["visualContainerObjects"] = container_objects
    v["visual"]["drillFilterOtherVisuals"] = True
    return v


# --- visual builders -------------------------------------------------------

def card(name: str, x: float, label: str, entity: str, prop: str,
         z: int = 1000, y: float = 85, h: float = 100,
         w: float = 240, size: str = "26") -> dict:
    return visual(
        name, "card", x, y, w, h,
        query_state={"Values": {"projections": [
            proj(measure(entity, prop), f"{entity}.{prop}")
        ]}},
        objects={
            "labels": [{"properties": {
                "fontSize": {"expr": {"Literal": {"Value": f"'{size}'"}}}
            }}],
            "categoryLabels": [{"properties": {
                "show": {"expr": {"Literal": {"Value": "false"}}}
            }}],
        },
        container_objects=title(label, "11"),
        z=z,
    )


def textbox(name: str, paragraphs: list[dict], z: int = 1000,
            x: float = 20, y: float = 15, w: float = 1240,
            h: float = 65) -> dict:
    # 65px leaves room for a 24pt title plus a 10pt subtitle; 55px clipped the
    # second paragraph in the PDF renderer.
    return visual(
        name, "textbox", x, y, w, h,
        objects={"general": [{"properties": {"paragraphs": paragraphs}}]},
        z=z,
    )


def executive_page() -> list[dict]:
    visuals: list[dict] = []

    visuals.append(textbox(
        "exec_title",
        [
            {"textRuns": [{
                "value": "Deferment Early Warning",
                "textStyle": {"fontSize": "24pt", "fontWeight": "bold"},
            }]},
            {"textRuns": [{
                "value": "Executive overview  ·  gold v1  ·  rules-based  ·  seed window 2026-07-10 to 2026-10-07",
                "textStyle": {"fontSize": "10pt"},
            }]},
        ],
    ))

    # KPI cards
    visuals.append(card("card_alerts", 20, "Alerts fired",
                        "gold_alert", "Alerts Fired", z=1100))
    visuals.append(card("card_open", 270, "Open alerts",
                        "gold_alert", "Open Alerts", z=1200))
    visuals.append(card("card_usd", 520, "Excess value at risk",
                        "gold_risk_daily", "Excess Value at Risk (USD)", z=1300))
    visuals.append(card("card_red", 770, "Stations at Red (latest)",
                        "gold_risk_daily", "Stations at Red (latest)", z=1400))
    visuals.append(card("card_coverage", 1020, "Data coverage",
                        "gold_risk_daily", "Data Coverage %", z=1500))

    # Ranking: value at risk by station, horizontal bars, largest first.
    visuals.append(visual(
        "rank_station", "clusteredBarChart", 20, 215, 580, 330,
        query_state={
            "Category": {"projections": [
                proj(column("gold_df_dim_station", "station_name"),
                     "gold_df_dim_station.station_name", active=True),
            ]},
            "Y": {"projections": [
                proj(measure("gold_risk_daily", "Excess Value at Risk (USD)"),
                     "gold_risk_daily.Excess Value at Risk (USD)"),
            ]},
        },
        sort=[{
            "field": measure("gold_risk_daily", "Excess Value at Risk (USD)"),
            "direction": "Descending",
        }],
        container_objects=title("Excess value at risk by station"),
        z=2000,
    ))

    # Scored risk-day mix.
    visuals.append(visual(
        "mix_tier", "donutChart", 620, 215, 320, 330,
        query_state={
            "Category": {"projections": [
                proj(column("gold_risk_daily", "risk_tier"),
                     "gold_risk_daily.risk_tier", active=True),
            ]},
            "Y": {"projections": [
                proj(measure("gold_risk_daily", "Scored Days"),
                     "gold_risk_daily.Scored Days"),
            ]},
        },
        container_objects=title("Scored risk-day mix"),
        z=2100,
    ))

    # Latest alerts table.
    visuals.append(visual(
        "latest_alerts", "tableEx", 960, 215, 300, 330,
        query_state={"Values": {"projections": [
            proj(column("gold_alert", "alert_date"),
                 "gold_alert.alert_date"),
            proj(column("gold_df_dim_station", "station_name"),
                 "gold_df_dim_station.station_name"),
            proj(column("gold_alert", "tier"),
                 "gold_alert.tier"),
            proj(column("gold_alert", "exp_usd"),
                 "gold_alert.exp_usd", display="Excess USD"),
        ]}},
        sort=[{"field": column("gold_alert", "alert_date"),
               "direction": "Descending"}],
        container_objects=title("Latest alerts"),
        z=2200,
    ))

    # Alert trend by date and tier.
    visuals.append(visual(
        "trend_alerts", "columnChart", 20, 560, 1240, 145,
        query_state={
            "Category": {"projections": [
                proj(column("gold_df_dim_date", "date"),
                     "gold_df_dim_date.date", active=True),
            ]},
            "Series": {"projections": [
                proj(column("gold_alert", "tier"),
                     "gold_alert.tier"),
            ]},
            "Y": {"projections": [
                proj(measure("gold_alert", "Alerts Fired"),
                     "gold_alert.Alerts Fired"),
            ]},
        },
        container_objects=title("Alerts by date and tier", "11"),
        z=2300,
    ))

    return visuals


def station_slicer(name: str = "station_slicer", x: float = 20,
                   y: float = 80, w: float = 240, h: float = 140,
                   default_station: str | None = "Test Station B",
                   mode: str = "Basic") -> dict:
    """Station slicer.

    The default is a slicer selection state, not a page filter, so the user can
    change it. Test Station B is the outage example and has five alerts. Pass
    ``default_station=None`` for an unfiltered (all-station) view.
    """
    default_selection = {
        "filter": {
            "Version": 2,
            "From": [{"Name": "s", "Entity": "gold_df_dim_station", "Type": 0}],
            "Where": [{
                "Condition": {
                    "In": {
                        "Expressions": [{
                            "Column": {
                                "Expression": {"SourceRef": {"Source": "s"}},
                                "Property": "station_name",
                            }
                        }],
                        "Values": [[{"Literal": {"Value": f"'{default_station}'"}}]],
                    }
                }
            }],
        }
    }
    objects = {
        "data": [{"properties": {
            "mode": {"expr": {"Literal": {"Value": f"'{mode}'"}}},
        }}],
        "selection": [{"properties": {
            "singleSelect": {"expr": {"Literal": {"Value": "true"}}},
            "selectAllCheckboxEnabled": {"expr": {"Literal": {"Value": "false"}}},
        }}],
    }
    if default_station:
        objects["general"] = [{"properties": {"filter": default_selection}}]
    return visual(
        name, "slicer", x, y, w, h,
        query_state={"Values": {"projections": [
            proj(column("gold_df_dim_station", "station_name"),
                 "gold_df_dim_station.station_name", active=True),
        ]}},
        objects=objects,
        container_objects=title("Station"),
        z=1100,
    )


def dimension_slicer(name: str, entity: str, prop: str, label: str,
                     x: float, y: float, w: float = 240,
                     h: float = 60, single: bool = False) -> dict:
    """Compact dropdown slicer for a dimension column (no default filter)."""
    return visual(
        name, "slicer", x, y, w, h,
        query_state={"Values": {"projections": [
            proj(column(entity, prop), f"{entity}.{prop}", active=True),
        ]}},
        objects={
            "data": [{"properties": {
                "mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}},
            }}],
            "selection": [{"properties": {
                "singleSelect": {"expr": {"Literal": {
                    "Value": "true" if single else "false"
                }}},
                "selectAllCheckboxEnabled": {"expr": {"Literal": {"Value": "true"}}},
            }}],
        },
        container_objects=title(label),
        z=1100,
    )


def station_page() -> list[dict]:
    visuals: list[dict] = []

    visuals.append(textbox(
        "station_title",
        [
            {"textRuns": [{
                "value": "Station detail",
                "textStyle": {"fontSize": "22pt", "fontWeight": "bold"},
            }]},
            {"textRuns": [{
                "value": "Pick a station to see current risk, normal range and recent reasons.",
                "textStyle": {"fontSize": "10pt"},
            }]},
        ],
        z=1000,
    ))

    visuals.append(station_slicer())

    visuals.append(card("st_risk_score", 280, "Latest risk score",
                        "gold_risk_daily", "Latest Risk Score", z=1200,
                        y=80, h=110, w=230))
    visuals.append(card("st_risk_tier", 520, "Latest risk tier",
                        "gold_risk_daily", "Latest Risk Tier", z=1300,
                        y=80, h=110, w=230))
    visuals.append(card("st_observed", 760, "Latest observed date",
                        "gold_risk_daily", "Latest Observed Date", z=1400,
                        y=80, h=110, w=230))
    visuals.append(card("st_usd", 1000, "Excess value at risk",
                        "gold_risk_daily", "Excess Value at Risk (USD)", z=1500,
                        y=80, h=110, w=230))

    # Risk score over time for the selected station.
    visuals.append(visual(
        "st_risk_line", "lineChart", 20, 240, 610, 210,
        query_state={
            "Category": {"projections": [
                proj(column("gold_df_dim_date", "date"),
                     "gold_df_dim_date.date", active=True),
            ]},
            "Y": {"projections": [
                proj(measure("gold_risk_daily", "Risk Score"),
                     "gold_risk_daily.Risk Score"),
            ]},
        },
        container_objects=title("Risk score over time"),
        z=2000,
    ))

    # Oil actual vs expected. The measures are metric-specific, so no visual
    # filter is needed and the chart cannot accidentally sum across metrics.
    visuals.append(visual(
        "st_oil_line", "lineChart", 650, 240, 610, 210,
        query_state={
            "Category": {"projections": [
                proj(column("gold_df_dim_date", "date"),
                     "gold_df_dim_date.date", active=True),
            ]},
            "Y": {"projections": [
                proj(measure("gold_deviation_daily", "Actual Oil"),
                     "gold_deviation_daily.Actual Oil"),
                proj(measure("gold_deviation_daily", "Expected Oil"),
                     "gold_deviation_daily.Expected Oil"),
            ]},
        },
        container_objects=title("Oil: actual vs expected"),
        z=2100,
    ))

    # Normal range for the selected station.
    visuals.append(visual(
        "st_baseline", "tableEx", 20, 470, 610, 230,
        query_state={"Values": {"projections": [
            proj(column("gold_entity_baseline", "metric"),
                 "gold_entity_baseline.metric"),
            proj(column("gold_entity_baseline", "median"),
                 "gold_entity_baseline.median", display="Median"),
            proj(column("gold_entity_baseline", "p10"),
                 "gold_entity_baseline.p10", display="P10"),
            proj(column("gold_entity_baseline", "p90"),
                 "gold_entity_baseline.p90", display="P90"),
            proj(column("gold_entity_baseline", "robust_scale"),
                 "gold_entity_baseline.robust_scale", display="Robust scale"),
        ]}},
        sort=[{"field": column("gold_entity_baseline", "metric"),
               "direction": "Ascending"}],
        container_objects=title("Station normal range"),
        z=2200,
    ))

    # Recent reasons: newest first.
    visuals.append(visual(
        "st_reasons", "tableEx", 650, 470, 610, 230,
        query_state={"Values": {"projections": [
            proj(column("gold_df_dim_date", "date"),
                 "gold_df_dim_date.date"),
            proj(column("gold_risk_daily", "risk_tier"),
                 "gold_risk_daily.risk_tier"),
            proj(measure("gold_risk_daily", "Risk Score"),
                 "gold_risk_daily.Risk Score", display="Risk score"),
            proj(column("gold_risk_daily", "risk_reasons"),
                 "gold_risk_daily.risk_reasons", display="Reasons"),
            proj(column("gold_risk_daily", "exp_usd"),
                 "gold_risk_daily.exp_usd", display="Excess USD"),
        ]}},
        sort=[{"field": column("gold_df_dim_date", "date"),
               "direction": "Descending"}],
        objects={"total": [{"properties": {
            "show": {"expr": {"Literal": {"Value": "false"}}},
        }}]},
        container_objects=title("Recent risk reasons"),
        z=2300,
    ))

    return visuals


def heatmap_page() -> list[dict]:
    visuals: list[dict] = []

    visuals.append(textbox(
        "heat_title",
        [
            {"textRuns": [{
                "value": "Deviation heatmap",
                "textStyle": {"fontSize": "22pt", "fontWeight": "bold"},
            }]},
            {"textRuns": [{
                "value": "Where each signal sits versus its own normal. Positive = worse.",
                "textStyle": {"fontSize": "10pt"},
            }]},
        ],
        z=1000,
    ))

    visuals.append(station_slicer(
        "heat_station", x=20, y=88, w=240, h=60, default_station=None,
        mode="Dropdown",
    ))

    visuals.append(textbox(
        "heat_legend",
        [
            {"textRuns": [{
                "value": "How to read this heatmap",
                "textStyle": {"fontSize": "14pt", "fontWeight": "bold"},
            }]},
            {"textRuns": [{
                "value": (
                    "Each cell is the average bad-direction robust z for a metric in a "
                    "calendar month. Positive = worse than normal; negative = better. "
                    "Blank = no scored, observed data. Use the station slicer to drill "
                    "into one station."
                ),
                "textStyle": {"fontSize": "10pt"},
            }]},
        ],
        z=1100, x=280, y=88, w=980, h=100,
    ))

    fill_rule = {
        "FillRule": {
            "Input": {
                "Measure": {
                    "Expression": {"SourceRef": {"Entity": "gold_deviation_daily"}},
                    "Property": "Bad Z (scored)",
                }
            },
            "FillRule": {
                "linearGradient3": {
                    "min": {
                        "color": {"Literal": {"Value": "'#C8E6C9'"}},
                        "value": {"Literal": {"Value": "-3D"}},
                    },
                    "mid": {
                        "color": {"Literal": {"Value": "'#FFFFFF'"}},
                        "value": {"Literal": {"Value": "0D"}},
                    },
                    "max": {
                        "color": {"Literal": {"Value": "'#EF9A9A'"}},
                        "value": {"Literal": {"Value": "6D"}},
                    },
                    "nullColoringStrategy": {
                        "strategy": {"Literal": {"Value": "'asZero'"}}
                    },
                }
            },
        }
    }

    visuals.append(visual(
        "dev_heatmap", "pivotTable", 20, 215, 1240, 485,
        query_state={
            "Rows": {"projections": [
                proj(column("gold_deviation_daily", "metric"),
                     "gold_deviation_daily.metric", active=True),
            ]},
            "Columns": {"projections": [
                proj(column("gold_df_dim_date", "year_month"),
                     "gold_df_dim_date.year_month", active=True),
            ]},
            "Values": {"projections": [
                proj(measure("gold_deviation_daily", "Bad Z (scored)"),
                     "gold_deviation_daily.Bad Z (scored)"),
            ]},
        },
        sort=[{"field": measure("gold_deviation_daily", "Max Bad Z (scored)"),
               "direction": "Descending"}],
        objects={"values": [{
            "properties": {
                "backColor": {"solid": {"color": {"expr": fill_rule}}},
            },
            "selector": {
                "data": [{"dataViewWildcard": {"matchingOption": 1}}],
                "metadata": "gold_deviation_daily.Bad Z (scored)",
            },
        }]},
        container_objects=title("Average bad-direction z by metric and month"),
        z=2000,
    ))

    return visuals


def alert_log_page() -> list[dict]:
    visuals: list[dict] = []

    visuals.append(textbox(
        "alerts_title",
        [
            {"textRuns": [{
                "value": "Alert log",
                "textStyle": {"fontSize": "22pt", "fontWeight": "bold"},
            }]},
            {"textRuns": [{
                "value": "Every fired alert, newest first. Filter by tier, station or month.",
                "textStyle": {"fontSize": "10pt"},
            }]},
        ],
        z=1000,
    ))

    visuals.append(dimension_slicer(
        "alerts_tier_slicer", "gold_alert", "tier", "Tier", 20, 90))
    visuals.append(dimension_slicer(
        "alerts_station_slicer", "gold_df_dim_station", "station_name",
        "Station", 280, 90))
    visuals.append(dimension_slicer(
        "alerts_month_slicer", "gold_df_dim_date", "year_month",
        "Month", 540, 90))

    visuals.append(card("alerts_card_total", 20, "Alerts fired",
                        "gold_alert", "Alerts Fired", z=1200,
                        y=170, h=90, w=290))
    visuals.append(card("alerts_card_red", 330, "Red alerts",
                        "gold_alert", "Red Alerts", z=1300,
                        y=170, h=90, w=290))
    visuals.append(card("alerts_card_amber", 640, "Amber alerts",
                        "gold_alert", "Amber Alerts", z=1400,
                        y=170, h=90, w=290))
    visuals.append(card("alerts_card_usd", 950, "Excess USD at alert",
                        "gold_alert", "Excess USD at Alert", z=1500,
                        y=170, h=90, w=290))

    visuals.append(visual(
        "alerts_table", "tableEx", 20, 280, 1240, 420,
        query_state={"Values": {"projections": [
            proj(column("gold_df_dim_date", "date"),
                 "gold_df_dim_date.date"),
            proj(column("gold_df_dim_station", "station_name"),
                 "gold_df_dim_station.station_name"),
            proj(column("gold_alert", "tier"),
                 "gold_alert.tier"),
            proj(column("gold_alert", "alert_type"),
                 "gold_alert.alert_type", display="Alert type"),
            proj(column("gold_alert", "top_signal"),
                 "gold_alert.top_signal", display="Top signal"),
            proj(column("gold_alert", "risk_score"),
                 "gold_alert.risk_score", display="Risk score"),
            proj(column("gold_alert", "exp_usd"),
                 "gold_alert.exp_usd", display="Excess USD"),
            proj(column("gold_alert", "risk_reasons"),
                 "gold_alert.risk_reasons", display="Reasons"),
        ]}},
        sort=[{"field": column("gold_df_dim_date", "date"),
               "direction": "Descending"}],
        container_objects=title("Fired alerts"),
        z=2000,
    ))

    return visuals


def outcomes_page() -> list[dict]:
    visuals: list[dict] = []

    visuals.append(textbox(
        "outcomes_title",
        [
            {"textRuns": [{
                "value": "Outcomes & lead time",
                "textStyle": {"fontSize": "22pt", "fontWeight": "bold"},
            }]},
            {"textRuns": [{
                "value": "Recorded outcomes, realised lead time and false-alarm rate.",
                "textStyle": {"fontSize": "10pt"},
            }]},
        ],
        z=1000,
    ))

    visuals.append(textbox(
        "outcomes_note",
        [
            {"textRuns": [{
                "value": (
                    "Outcomes are computed automatically. An alert is confirmed if a "
                    "coded onset or a large-loss onset (deferred oil at or above the "
                    "station's own p90 after 3 quiet days) occurs within 7 days after "
                    "the alert. Pending means the 7-day window extends beyond the data."
                ),
                "textStyle": {"fontSize": "10pt"},
            }]},
        ],
        z=1100, x=20, y=90, w=1240, h=65,
    ))

    visuals.append(card("outcomes_card_count", 20, "Alerts with outcome",
                        "gold_alert_outcome", "Alerts with Outcome",
                        z=1200, y=170, h=100, w=240))
    visuals.append(card("outcomes_card_confirmed", 270, "Alerts confirmed",
                        "gold_alert_outcome", "Alerts Confirmed",
                        z=1300, y=170, h=100, w=240))
    visuals.append(card("outcomes_card_precision", 520, "Alert precision",
                        "gold_alert_outcome", "Precision Display",
                        z=1400, y=170, h=100, w=240, size="18"))
    visuals.append(card("outcomes_card_lead", 770, "Median lead time",
                        "gold_alert_outcome", "Lead Time Display",
                        z=1500, y=170, h=100, w=240, size="18"))
    visuals.append(card("outcomes_card_awaiting", 1020, "Awaiting outcome",
                        "gold_alert_outcome", "Alerts Awaiting Outcome",
                        z=1600, y=170, h=100, w=240))

    visuals.append(visual(
        "outcomes_table", "tableEx", 20, 290, 1240, 410,
        query_state={"Values": {"projections": [
            proj(column("gold_df_dim_date", "date"),
                 "gold_df_dim_date.date", display="Alert date"),
            proj(column("gold_df_dim_station", "station_name"),
                 "gold_df_dim_station.station_name"),
            proj(column("gold_alert", "tier"),
                 "gold_alert.tier"),
            proj(column("gold_alert_outcome", "event_occurred"),
                 "gold_alert_outcome.event_occurred", display="Event"),
            proj(column("gold_alert_outcome", "event_date"),
                 "gold_alert_outcome.event_date", display="Event date"),
            proj(column("gold_alert_outcome", "actual_lead_days"),
                 "gold_alert_outcome.actual_lead_days", display="Lead days"),
            proj(column("gold_alert_outcome", "detection_type"),
                 "gold_alert_outcome.detection_type", display="Detection"),
            proj(column("gold_alert_outcome", "disposition"),
                 "gold_alert_outcome.disposition"),
            proj(column("gold_alert_outcome", "action_note"),
                 "gold_alert_outcome.action_note", display="Action note"),
        ]}},
        sort=[{"field": column("gold_df_dim_date", "date"),
               "direction": "Descending"}],
        container_objects=title("Recorded outcomes"),
        z=2000,
    ))

    return visuals


def build_parts(model_id: str) -> dict[str, str]:
    """Return every PBIR part needed to create the report."""
    import json

    parts: dict[str, str] = {}

    parts["definition.pbir"] = json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {
            "byConnection": {
                "connectionString": f"semanticmodelid={model_id}"
            }
        },
    }, indent=2)

    parts["definition/report.json"] = json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.1.0/schema.json",
        "themeCollection": {},
        "settings": {
            "useStylableVisualContainerHeader": True,
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
        },
    }, indent=2)

    parts["definition/version.json"] = json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    }, indent=2)

    parts["definition/pages/pages.json"] = json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [PAGE_ID, STATION_PAGE_ID, HEAT_PAGE_ID, ALERT_PAGE_ID, OUTCOME_PAGE_ID],
        "activePageName": PAGE_ID,
    }, indent=2)

    pages = [
        (PAGE_ID, PAGE_NAME, executive_page),
        (STATION_PAGE_ID, STATION_PAGE_NAME, station_page),
        (HEAT_PAGE_ID, HEAT_PAGE_NAME, heatmap_page),
        (ALERT_PAGE_ID, ALERT_PAGE_NAME, alert_log_page),
        (OUTCOME_PAGE_ID, OUTCOME_PAGE_NAME, outcomes_page),
    ]
    for page_id, page_name, builder in pages:
        parts[f"definition/pages/{page_id}/page.json"] = json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
            "name": page_id,
            "displayName": page_name,
            "displayOption": "FitToPage",
            "height": H,
            "width": W,
        }, indent=2)
        for v in builder():
            parts[f"definition/pages/{page_id}/visuals/{v['name']}/visual.json"] = json.dumps(
                v, indent=2
            )

    return parts
