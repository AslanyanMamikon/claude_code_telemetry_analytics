#!/usr/bin/env python3
"""
dashboard.py — Claude Code Usage Analytics Dashboard
Run with: streamlit run dashboard.py
"""

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_PATH = "analytics.duckdb"

st.set_page_config(
    page_title="Claude Code Analytics",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;600;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Syne', sans-serif;
    }

    .stMetric {
        background: linear-gradient(135deg, #0f1117 0%, #1a1d2e 100%);
        border: 1px solid #2d3561;
        border-radius: 12px;
        padding: 1rem 1.2rem;
    }

    .stMetric label {
        color: #8b9dc3 !important;
        font-size: 0.75rem !important;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }

    .stMetric [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.8rem !important;
        color: #e2e8f0 !important;
    }

    .stMetric [data-testid="stMetricDelta"] {
        font-family: 'JetBrains Mono', monospace;
    }

    h1, h2, h3 {
        font-family: 'Syne', sans-serif !important;
        font-weight: 800;
    }

    .section-header {
        font-family: 'Syne', sans-serif;
        font-size: 1.1rem;
        font-weight: 600;
        color: #8b9dc3;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        border-left: 3px solid #4f6ef7;
        padding-left: 0.75rem;
        margin: 2rem 0 1rem 0;
    }

    .stSelectbox label, .stMultiSelect label, .stSlider label {
        font-family: 'Syne', sans-serif;
        font-weight: 600;
        color: #8b9dc3;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    [data-testid="stSidebar"] {
        background: #0a0d1a;
        border-right: 1px solid #1e2340;
    }

    .stPlotlyChart {
        border-radius: 12px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# DB Connection (cached)
# ---------------------------------------------------------------------------

@st.cache_resource
def get_conn():
    return duckdb.connect(DB_PATH, read_only=True)

@st.cache_data(ttl=300)
def query(sql, params=None):
    conn = get_conn()
    if params:
        return conn.execute(sql, params).df()
    return conn.execute(sql).df()

# ---------------------------------------------------------------------------
# Chart theme
# ---------------------------------------------------------------------------

COLORS = ["#4f6ef7", "#7c3aed", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#ec4899", "#84cc16"]

LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Syne, sans-serif", color="#8b9dc3"),
    title_font=dict(family="Syne, sans-serif", color="#e2e8f0", size=14),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#8b9dc3")),
    margin=dict(t=40, b=40, l=40, r=20),
)

AXIS = dict(
    gridcolor="#1e2340",
    zerolinecolor="#1e2340",
    tickfont=dict(color="#8b9dc3"),
    title_font=dict(color="#8b9dc3"),
)

# ---------------------------------------------------------------------------
# Sidebar Filters
# ---------------------------------------------------------------------------

st.sidebar.markdown("## 🔍 Filters")

practices     = query("SELECT DISTINCT practice FROM employees ORDER BY 1")["practice"].tolist()
levels        = query("SELECT DISTINCT level FROM employees ORDER BY level")["level"].tolist()
locations     = query("SELECT DISTINCT location FROM employees ORDER BY 1")["location"].tolist()
models        = query("SELECT DISTINCT model FROM api_requests ORDER BY 1")["model"].tolist()

sel_practices = st.sidebar.multiselect("Engineering Practice", practices, default=practices)
sel_levels    = st.sidebar.multiselect("Seniority Level", levels, default=levels)
sel_locations = st.sidebar.multiselect("Location", locations, default=locations)
sel_models    = st.sidebar.multiselect("Model", models, default=models)

date_range = query("SELECT MIN(timestamp)::DATE as mn, MAX(timestamp)::DATE as mx FROM api_requests")
min_date = pd.to_datetime(date_range["mn"].iloc[0])
max_date = pd.to_datetime(date_range["mx"].iloc[0])

col_d1, col_d2 = st.sidebar.columns(2)
start_date = col_d1.date_input("From", min_date, min_value=min_date, max_value=max_date)
end_date   = col_d2.date_input("To",   max_date, min_value=min_date, max_value=max_date)

# Build filter clause helper
def emp_filter():
    p  = ", ".join(f"'{x}'" for x in sel_practices)
    lv = ", ".join(f"'{x}'" for x in sel_levels)
    lo = ", ".join(f"'{x}'" for x in sel_locations)
    return f"e.practice IN ({p}) AND e.level IN ({lv}) AND e.location IN ({lo})"

def model_filter():
    m = ", ".join(f"'{x}'" for x in sel_models)
    return f"model IN ({m})"

def date_filter(tbl="r"):
    return f"{tbl}.timestamp BETWEEN '{start_date}' AND '{end_date}'"

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("# 🤖 Claude Code Analytics")
st.markdown("<p style='color:#8b9dc3; margin-top:-0.5rem;'>Developer telemetry dashboard — usage, cost & behavior insights</p>", unsafe_allow_html=True)
st.markdown("---")

# ---------------------------------------------------------------------------
# KPI Row
# ---------------------------------------------------------------------------

kpi = query(f"""
    SELECT
        COUNT(DISTINCT r.session_id)                        AS total_sessions,
        COUNT(*)                                            AS total_api_calls,
        ROUND(SUM(r.cost_usd), 2)                          AS total_cost,
        ROUND(AVG(r.cost_usd), 4)                          AS avg_cost_per_call,
        SUM(r.input_tokens + r.output_tokens)              AS total_tokens,
        COUNT(DISTINCT r.user_email)                        AS active_users
    FROM api_requests r
    JOIN employees e ON r.user_email = e.email
    WHERE {emp_filter()} AND {model_filter()} AND {date_filter()}
""")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Sessions",    f"{int(kpi['total_sessions'].iloc[0]):,}")
c2.metric("API Calls",         f"{int(kpi['total_api_calls'].iloc[0]):,}")
c3.metric("Total Cost",        f"${kpi['total_cost'].iloc[0]:,.2f}")
c4.metric("Avg Cost / Call",   f"${kpi['avg_cost_per_call'].iloc[0]:.4f}")
c5.metric("Total Tokens",      f"{int(kpi['total_tokens'].iloc[0]):,}")
c6.metric("Active Engineers",  f"{int(kpi['active_users'].iloc[0]):,}")

# ---------------------------------------------------------------------------
# Row 1: Model Usage + Cost by Practice
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">Model & Cost Breakdown</div>', unsafe_allow_html=True)
col1, col2 = st.columns(2)

with col1:
    df_model = query(f"""
        SELECT model,
               COUNT(*)            AS api_calls,
               ROUND(SUM(cost_usd),2) AS total_cost
        FROM api_requests r
        JOIN employees e ON r.user_email = e.email
        WHERE {emp_filter()} AND {model_filter()} AND {date_filter()}
        GROUP BY model ORDER BY api_calls DESC
    """)
    # Shorten model names for display
    df_model["model_short"] = df_model["model"].str.replace("claude-", "").str.replace("-2025\d+", "", regex=True)
    fig = px.bar(df_model, x="model_short", y="api_calls",
                 color="model_short", color_discrete_sequence=COLORS,
                 title="API Calls by Model",
                 labels={"model_short": "Model", "api_calls": "API Calls"})
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(**AXIS)
    fig.update_yaxes(**AXIS)
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    df_cost_practice = query(f"""
        SELECT e.practice,
               ROUND(SUM(r.cost_usd), 2) AS total_cost,
               COUNT(*)                   AS api_calls
        FROM api_requests r
        JOIN employees e ON r.user_email = e.email
        WHERE {emp_filter()} AND {model_filter()} AND {date_filter()}
        GROUP BY e.practice ORDER BY total_cost DESC
    """)
    fig2 = px.pie(df_cost_practice, names="practice", values="total_cost",
                  color_discrete_sequence=COLORS,
                  title="Total Cost by Engineering Practice",
                  hole=0.45)
    fig2.update_layout(**LAYOUT)
    fig2.update_traces(textfont=dict(color="#e2e8f0"))
    st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
# Row 2: Usage Over Time + Hourly Heatmap
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">Usage Patterns Over Time</div>', unsafe_allow_html=True)
col3, col4 = st.columns(2)

with col3:
    df_daily = query(f"""
        SELECT r.timestamp::DATE AS day,
               COUNT(*)          AS api_calls,
               ROUND(SUM(r.cost_usd), 2) AS daily_cost
        FROM api_requests r
        JOIN employees e ON r.user_email = e.email
        WHERE {emp_filter()} AND {model_filter()} AND {date_filter()}
        GROUP BY day ORDER BY day
    """)
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=df_daily["day"], y=df_daily["api_calls"],
        mode="lines", fill="tozeroy",
        line=dict(color="#4f6ef7", width=2),
        fillcolor="rgba(79,110,247,0.15)",
        name="API Calls"
    ))
    fig3.update_layout(title="Daily API Calls", **LAYOUT)
    fig3.update_xaxes(**AXIS)
    fig3.update_yaxes(**AXIS)
    st.plotly_chart(fig3, use_container_width=True)

with col4:
    df_hour = query(f"""
        SELECT HOUR(r.timestamp) AS hour,
               DAYOFWEEK(r.timestamp) AS dow,
               COUNT(*) AS calls
        FROM api_requests r
        JOIN employees e ON r.user_email = e.email
        WHERE {emp_filter()} AND {model_filter()} AND {date_filter()}
        GROUP BY hour, dow
    """)
    days_map = {1:"Sun", 2:"Mon", 3:"Tue", 4:"Wed", 5:"Thu", 6:"Fri", 7:"Sat"}
    df_hour["day_name"] = df_hour["dow"].map(days_map)
    pivot = df_hour.pivot_table(index="day_name", columns="hour", values="calls", aggfunc="sum", fill_value=0)
    day_order = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    pivot = pivot.reindex([d for d in day_order if d in pivot.index])
    fig4 = px.imshow(pivot, color_continuous_scale=[[0,"#0f1117"],[0.5,"#2d3561"],[1,"#4f6ef7"]],
                     title="Usage Heatmap (Hour × Day)",
                     labels=dict(x="Hour of Day", y="Day", color="Calls"))
    fig4.update_layout(**LAYOUT)
    fig4.update_xaxes(tickfont=dict(color="#8b9dc3"))
    fig4.update_yaxes(tickfont=dict(color="#8b9dc3"))
    st.plotly_chart(fig4, use_container_width=True)

# ---------------------------------------------------------------------------
# Row 3: Token Usage by Level + Tool Usage
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">Token Consumption & Tool Usage</div>', unsafe_allow_html=True)
col5, col6 = st.columns(2)

with col5:
    df_tokens = query(f"""
        SELECT e.level,
               ROUND(AVG(r.input_tokens + r.output_tokens), 0)  AS avg_tokens,
               ROUND(AVG(r.cost_usd), 5)                        AS avg_cost
        FROM api_requests r
        JOIN employees e ON r.user_email = e.email
        WHERE {emp_filter()} AND {model_filter()} AND {date_filter()}
        GROUP BY e.level
        ORDER BY e.level
    """)
    fig5 = px.bar(df_tokens, x="level", y="avg_tokens",
                  color="avg_cost", color_continuous_scale=["#1a1d2e","#4f6ef7","#7c3aed"],
                  title="Avg Tokens per Call by Seniority Level",
                  labels={"level":"Level","avg_tokens":"Avg Tokens","avg_cost":"Avg Cost ($)"})
    fig5.update_layout(**LAYOUT)
    fig5.update_xaxes(**AXIS)
    fig5.update_yaxes(**AXIS)
    st.plotly_chart(fig5, use_container_width=True)

with col6:
    df_tools = query(f"""
        SELECT t.tool_name,
               COUNT(*) AS uses,
               ROUND(100.0 * SUM(CASE WHEN t.success THEN 1 ELSE 0 END) / COUNT(*), 1) AS success_rate
        FROM tool_events t
        JOIN employees e ON t.user_email = e.email
        WHERE t.event_type = 'result'
          AND {emp_filter().replace('r.', 't.')}
          AND t.timestamp BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY t.tool_name
        ORDER BY uses DESC
        LIMIT 12
    """)
    fig6 = px.bar(df_tools, x="uses", y="tool_name", orientation="h",
                  color="success_rate",
                  color_continuous_scale=["#ef4444","#f59e0b","#10b981"],
                  title="Top Tools — Usage & Success Rate",
                  labels={"uses":"Times Used","tool_name":"Tool","success_rate":"Success %"})
    fig6.update_layout(**LAYOUT)
    fig6.update_xaxes(**AXIS)
    fig6.update_yaxes(**AXIS, categoryorder="total ascending")
    st.plotly_chart(fig6, use_container_width=True)

# ---------------------------------------------------------------------------
# Row 4: Error Analysis + Cost by Location
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">Errors & Geographic Distribution</div>', unsafe_allow_html=True)
col7, col8 = st.columns(2)

with col7:
    df_errors = query(f"""
        SELECT ae.model,
               ae.error_message,
               COUNT(*) AS occurrences
        FROM api_errors ae
        JOIN employees e ON ae.user_email = e.email
        WHERE {emp_filter()} AND ae.timestamp BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY ae.model, ae.error_message
        ORDER BY occurrences DESC
        LIMIT 10
    """)
    df_errors["label"] = df_errors["error_message"].str[:45] + "..."
    fig7 = px.bar(df_errors, x="occurrences", y="label", orientation="h",
                  color="model", color_discrete_sequence=COLORS,
                  title="Top API Errors",
                  labels={"occurrences":"Count","label":"Error"})
    fig7.update_layout(**LAYOUT)
    fig7.update_xaxes(**AXIS)
    fig7.update_yaxes(**AXIS, categoryorder="total ascending")
    st.plotly_chart(fig7, use_container_width=True)

with col8:
    df_loc = query(f"""
        SELECT e.location,
               ROUND(SUM(r.cost_usd), 2)  AS total_cost,
               COUNT(DISTINCT e.email)     AS engineers,
               COUNT(*)                    AS api_calls
        FROM api_requests r
        JOIN employees e ON r.user_email = e.email
        WHERE {emp_filter()} AND {model_filter()} AND {date_filter()}
        GROUP BY e.location ORDER BY total_cost DESC
    """)
    fig8 = px.bar(df_loc, x="location", y="total_cost",
                  color="engineers", color_continuous_scale=["#1a1d2e","#06b6d4"],
                  title="Total Cost by Location",
                  labels={"location":"Location","total_cost":"Total Cost ($)","engineers":"Engineers"})
    fig8.update_layout(**LAYOUT)
    fig8.update_xaxes(**AXIS)
    fig8.update_yaxes(**AXIS)
    st.plotly_chart(fig8, use_container_width=True)

# ---------------------------------------------------------------------------
# Row 5: Top Engineers Table
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">Top Engineers by Usage</div>', unsafe_allow_html=True)

df_top = query(f"""
    SELECT e.full_name,
           e.practice,
           e.level,
           e.location,
           COUNT(DISTINCT r.session_id)              AS sessions,
           COUNT(*)                                  AS api_calls,
           ROUND(SUM(r.cost_usd), 2)                AS total_cost,
           SUM(r.input_tokens + r.output_tokens)    AS total_tokens
    FROM api_requests r
    JOIN employees e ON r.user_email = e.email
    WHERE {emp_filter()} AND {model_filter()} AND {date_filter()}
    GROUP BY e.full_name, e.practice, e.level, e.location
    ORDER BY total_cost DESC
    LIMIT 20
""")

st.dataframe(
    df_top,
    use_container_width=True,
    column_config={
        "full_name":    st.column_config.TextColumn("Engineer"),
        "practice":     st.column_config.TextColumn("Practice"),
        "level":        st.column_config.TextColumn("Level"),
        "location":     st.column_config.TextColumn("Location"),
        "sessions":     st.column_config.NumberColumn("Sessions", format="%d"),
        "api_calls":    st.column_config.NumberColumn("API Calls", format="%d"),
        "total_cost":   st.column_config.NumberColumn("Total Cost ($)", format="$%.2f"),
        "total_tokens": st.column_config.NumberColumn("Total Tokens", format="%d"),
    },
    hide_index=True,
)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#4a5568; font-size:0.8rem; font-family: JetBrains Mono, monospace;'>"
    "Claude Code Usage Analytics · Synthetic telemetry dataset · Built with DuckDB + Streamlit"
    "</p>",
    unsafe_allow_html=True
)