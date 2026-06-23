import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Workstream Pricing Intelligence",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded",
)

# ── Brand Colors ──────────────────────────────────────────────────────────────
PRIMARY = "#1B3FE4"
NAVY    = "#0F1B2D"
BG      = "#EEF2FF"
WHITE   = "#FFFFFF"
GREEN   = "#00B67A"
AMBER   = "#FFA500"
RED     = "#FF4444"
GRAY    = "#6B7280"

# ── Constants ─────────────────────────────────────────────────────────────────
LIST_PRICES  = {"Hiring": 75.0, "HR": 100.0, "Payroll": 14.0}
FLOOR_PRICES = {"Hiring": 60.0, "HR": 80.0,  "Payroll": 11.0}
REF_DATE     = pd.Timestamp("2026-06-20")

SEG_COLORS = {"A": GREEN, "B": PRIMARY, "C": AMBER, "D": RED}
STATUS_COLORS = {
    "Locked":      PRIMARY,
    "Expired M2M": AMBER,
    "No Contract": GRAY,
    "No SF Link":  RED,
}
RISK_COLORS = {1: GREEN, 2: "#66D4A8", 3: AMBER, 4: "#FF8C00", 5: RED}

def get_path(filename):
    return os.path.join(os.path.dirname(__file__), "..", "Input", filename)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  [data-testid="stSidebar"] {{ background:{NAVY} !important; }}
  [data-testid="stSidebar"] label {{ color:rgba(255,255,255,.85) !important; font-size:12px !important; }}
  [data-testid="stSidebar"] .stSelectbox label {{ color:rgba(255,255,255,.7) !important; font-size:11px !important; font-weight:600; text-transform:uppercase; letter-spacing:.05em; }}
  [data-testid="stSidebar"] .stRadio label {{ color:white !important; }}
  [data-testid="stSidebar"] p {{ color:rgba(255,255,255,.6) !important; }}
  .kpi-card {{
    background:{WHITE}; border-radius:10px; padding:16px 18px;
    box-shadow:0 1px 4px rgba(0,0,0,.07); border-top:3px solid {PRIMARY};
    margin-bottom:8px;
  }}
  .kpi-card.green {{ border-top-color:{GREEN}; }}
  .kpi-card.amber {{ border-top-color:{AMBER}; }}
  .kpi-card.red   {{ border-top-color:{RED};   }}
  .kpi-card.gray  {{ border-top-color:{GRAY};  }}
  .kpi-card.navy  {{ border-top-color:{NAVY};  }}
  .kpi-label {{ font-size:10px; font-weight:700; color:{GRAY}; text-transform:uppercase; letter-spacing:.08em; }}
  .kpi-value {{ font-size:22px; font-weight:800; color:{NAVY}; margin:3px 0 1px; line-height:1.1; }}
  .kpi-sub   {{ font-size:11px; color:{GRAY}; }}
  .section-title {{ font-size:13px; font-weight:700; color:{NAVY}; padding-bottom:6px; border-bottom:1px solid #dde3f0; margin-bottom:10px; }}
  .page-banner {{ background:linear-gradient(120deg,{PRIMARY} 0%,{NAVY} 100%); border-radius:10px; padding:16px 24px; margin-bottom:16px; }}
  .page-banner h2 {{ color:white; margin:0; font-size:18px; font-weight:800; }}
  .page-banner p  {{ color:rgba(255,255,255,.75); margin:3px 0 0; font-size:12px; }}
  .insight-box {{ background:{WHITE}; border-radius:8px; padding:12px 16px; border-left:4px solid {PRIMARY}; margin:10px 0; font-size:13px; color:{NAVY}; }}
  .empty-state {{ text-align:center; padding:32px; color:{GRAY}; background:{WHITE}; border-radius:10px; border:1px dashed #ccd1e4; }}
  .summary-row {{ background:{WHITE}; border-radius:8px; padding:14px 18px; display:flex; gap:32px; align-items:center; margin-top:12px; }}
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def kpi(label, value, sub="", variant=""):
    st.markdown(f"""
    <div class="kpi-card {variant}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

def section(title):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)

def banner(title, subtitle=""):
    st.markdown(f'<div class="page-banner"><h2>{title}</h2><p>{subtitle}</p></div>',
                unsafe_allow_html=True)

def empty_state(msg="No matching records"):
    st.markdown(f'<div class="empty-state">📭 {msg}</div>', unsafe_allow_html=True)

def download_btn(df, label="Download CSV", filename="export.csv"):
    if len(df) > 0:
        st.download_button(label, df.to_csv(index=False).encode(), filename, "text/csv",
                           use_container_width=True)

def safe_table(df, key, height=380):
    if len(df) == 0:
        empty_state()
        return df
    q = st.text_input("🔍 Search", key=f"srch_{key}", placeholder="Filter table…", label_visibility="collapsed")
    if q:
        mask = df.astype(str).apply(lambda c: c.str.contains(q, case=False, na=False)).any(axis=1)
        df = df[mask]
    if len(df) == 0:
        empty_state(f'No records match "{q}"')
    else:
        st.dataframe(df, use_container_width=True, height=height, hide_index=True)
    return df

def fmt_arr(v):
    if v >= 1_000_000: return f"${v/1_000_000:.2f}M"
    if v >= 1_000:     return f"${v/1_000:.0f}K"
    return f"${v:,.0f}"

# ── Data ──────────────────────────────────────────────────────────────────────
@st.cache_data
def build_line_df():
    df = pd.read_csv(get_path("stripeXsfdc.csv"))
    df["unit_price"]        = df["unit_amount"] / 100
    df.loc[df["billing_interval"] == "year", "unit_price"] /= 12
    df["last_billing_date"] = pd.to_datetime(df["last_billing_date"])
    df["days_since"]        = (REF_DATE - df["last_billing_date"]).dt.days
    df["is_active"]         = (
        ((df["billing_interval"] == "month") & (df["days_since"] <= 60)) |
        ((df["billing_interval"] == "year")  & (df["days_since"] <= 400))
    )
    df["list_price"]        = df["price_nickname"].map(LIST_PRICES)
    df["floor_price"]       = df["price_nickname"].map(FLOOR_PRICES)
    df["monthly_rev"]       = df["unit_price"]   * df["quantity"]
    df["list_monthly_rev"]  = df["list_price"]   * df["quantity"]
    df["floor_gap_monthly"] = (df["floor_price"] - df["unit_price"]).clip(lower=0) * df["quantity"]
    df["below_floor"]       = df["unit_price"] < df["floor_price"]
    df["end_date"]          = pd.to_datetime(df["end_date"], errors="coerce")
    df["has_sf"]            = df["metadata_salesforce_id"].notna() & (df["metadata_salesforce_id"] != "")
    df["has_contract"]      = df["contract_id"].notna() & (df["contract_id"] != "")
    return df


@st.cache_data
def build_customer_df():
    line_df = build_line_df()
    active  = line_df[line_df["is_active"]].copy()

    def agg(g):
        mr   = (g["unit_price"] * g["quantity"]).sum()
        lr   = (g["list_price"] * g["quantity"]).sum()
        fg   = g["floor_gap_monthly"].sum() * 12
        pct  = mr / lr if lr > 0 else 0
        inc  = max(0, (1 / pct - 1) * 100) if pct > 0 else 999

        has_sf       = g["has_sf"].any()
        has_contract = g["has_contract"].any()
        end_date     = g["end_date"].max()
        created      = pd.to_datetime(g["created"].min())
        tenure_years = (REF_DATE - created).days / 365.25

        csm_s    = g["csm_name__c"].dropna()
        csm_s    = csm_s[csm_s.str.strip() != ""]
        has_csm  = len(csm_s) > 0
        csm_name = csm_s.iloc[0] if has_csm else ""

        ae_s    = g["account_ae"].dropna()
        ae_s    = ae_s[ae_s.str.strip() != ""]
        ae_name = ae_s.iloc[0] if len(ae_s) > 0 else "—"

        if has_contract and pd.notna(end_date) and end_date > REF_DATE:
            status = "Locked"
        elif has_contract and pd.notna(end_date) and end_date <= REF_DATE:
            status = "Expired M2M"
        elif not has_sf:
            status = "No SF Link"
        else:
            status = "No Contract"

        products = ", ".join(sorted(g["price_nickname"].unique()))

        return pd.Series({
            "monthly_mrr":      mr,
            "annual_arr":       mr * 12,
            "list_annual_arr":  lr * 12,
            "pct_of_list":      pct,
            "increase_pct":     inc,
            "floor_gap_annual": fg,
            "any_below_floor":  g["below_floor"].any(),
            "contract_status":  status,
            "end_date":         end_date,
            "tenure_years":     tenure_years,
            "has_csm":          has_csm,
            "csm_name":         csm_name,
            "account_ae":       ae_name,
            "has_sf":           has_sf,
            "products":         products,
        })

    cust = active.groupby("stripe_customer_id").apply(agg).reset_index()

    name_map = active.groupby("stripe_customer_id")["name"].first()
    cust["name"] = cust["stripe_customer_id"].map(name_map).fillna("Unknown")

    # Segment
    cust["segment"] = cust["pct_of_list"].apply(
        lambda p: "A" if p >= 1.0 else ("B" if p >= 0.9 else ("C" if p >= 0.75 else "D"))
    )

    # Revenue opportunity (gap to list, annualised)
    cust["revenue_opportunity"] = (cust["list_annual_arr"] - cust["annual_arr"]).clip(lower=0)

    # Churn risk scoring (non-locked only, from report methodology)
    def churn_risk(row):
        if row["contract_status"] == "Locked":
            return np.nan
        p, inc, yrs, st_ = (row["pct_of_list"], row["increase_pct"],
                             row["tenure_years"], row["contract_status"])
        dd = 1 if p >= 1.0 else (2 if p >= 0.9 else (3 if p >= 0.75 else (4 if p >= 0.6 else 5)))
        cp = 3 if st_ == "Expired M2M" else 5
        t  = 1 if yrs >= 4 else (2 if yrs >= 3 else (3 if yrs >= 2 else (4 if yrs >= 1 else 5)))
        im = 1 if inc <= 0 else (2 if inc <= 9 else (3 if inc <= 29 else (4 if inc <= 40 else 5)))
        return int(np.clip(round(0.30*dd + 0.30*cp + 0.20*t + 0.20*im), 1, 5))

    cust["churn_risk"] = cust.apply(churn_risk, axis=1)

    # Phase assignment
    def phase_fn(row):
        if pd.isna(row["churn_risk"]): return np.nan
        s = row["churn_risk"]
        return 1 if s <= 2 else (2 if s == 3 else 3)

    cust["phase"] = cust.apply(phase_fn, axis=1)

    # Recommended action (derived from contract status + risk)
    def rec_action(row):
        st_ = row["contract_status"]
        pct = row["pct_of_list"]
        rsk = row["churn_risk"]
        if st_ == "Locked":
            return "Price review at renewal" if pct < 1.0 else "Maintain — at list"
        elif st_ == "Expired M2M":
            return "Immediate price reset"
        elif st_ == "No SF Link":
            return "Resolve Salesforce link"
        elif st_ == "No Contract":
            if not pd.isna(rsk) and rsk >= 4:
                return "Urgent: contract + price action"
            return "Execute contract, then price"
        return "Review pricing"

    cust["recommended_action"] = cust.apply(rec_action, axis=1)

    # Renewal buckets (locked only)
    def renewal_bucket(row):
        if row["contract_status"] != "Locked" or pd.isna(row["end_date"]):
            return None
        months = (row["end_date"] - REF_DATE).days / 30.44
        if months <= 3:    return "0–3 Months"
        elif months <= 6:  return "3–6 Months"
        elif months <= 12: return "6–12 Months"
        else:               return "12+ Months"

    cust["renewal_bucket"] = cust.apply(renewal_bucket, axis=1)

    return cust


# ── Sidebar (Navigation + Filters) ───────────────────────────────────────────
cust_all = build_customer_df()
line_all = build_line_df()
active_all = line_all[line_all["is_active"]].copy()

with st.sidebar:
    st.markdown(f"""
    <div style='padding:6px 0 18px'>
      <div style='font-size:21px;font-weight:900;color:white;letter-spacing:-.03em'>⚡ Workstream</div>
      <div style='font-size:10px;color:rgba(255,255,255,.45);margin-top:2px;font-weight:600;letter-spacing:.08em;text-transform:uppercase'>Pricing Intelligence</div>
    </div>""", unsafe_allow_html=True)

    page = st.radio(
        "nav",
        ["Executive Summary", "Pricing Opportunity", "Risk & Readiness", "Action Center"],
        label_visibility="collapsed",
    )

    st.markdown("<hr style='border-color:rgba(255,255,255,.12);margin:12px 0'>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:10px;font-weight:700;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px'>Global Filters</div>", unsafe_allow_html=True)

    ae_opts   = ["All"] + sorted([x for x in cust_all["account_ae"].dropna().unique() if str(x).strip() and x != "—"])
    csm_opts  = ["All"] + sorted([x for x in cust_all["csm_name"].dropna().unique() if str(x).strip()])
    prod_opts = ["All"] + sorted(active_all["price_nickname"].dropna().unique().tolist())

    f_ae     = st.selectbox("AE Owner",        ae_opts)
    f_seg    = st.selectbox("Segment",         ["All", "A", "B", "C", "D"])
    f_status = st.selectbox("Contract Status", ["All", "Locked", "Expired M2M", "No Contract", "No SF Link"])
    f_prod   = st.selectbox("Product",         prod_opts)
    f_csm    = st.selectbox("CSM",             csm_opts)

    st.markdown("<hr style='border-color:rgba(255,255,255,.12);margin:12px 0'>", unsafe_allow_html=True)
    st.caption(f"Data through {REF_DATE.strftime('%b %d, %Y')}")


# ── Filter Application ────────────────────────────────────────────────────────
def apply_filters(df):
    d = df.copy()
    if f_ae != "All":
        d = d[d["account_ae"] == f_ae]
    if f_seg != "All":
        d = d[d["segment"] == f_seg]
    if f_status != "All":
        d = d[d["contract_status"] == f_status]
    if f_prod != "All":
        d = d[d["products"].str.contains(f_prod, na=False)]
    if f_csm != "All":
        d = d[d["csm_name"] == f_csm]
    return d


def apply_line_filters(line_df, cust_df):
    ids = set(cust_df["stripe_customer_id"])
    d   = line_df[line_df["stripe_customer_id"].isin(ids)].copy()
    if f_prod != "All":
        d = d[d["price_nickname"] == f_prod]
    return d


cust         = apply_filters(cust_all)
active_lines = apply_line_filters(active_all, cust)


# ── Named Chart Functions (reusable across pages) ─────────────────────────────

def chart_arr_projection_updated(cust_df, ph1=0.88, ph2=0.85, ph3=0.83):
    """ARR Projection: baseline vs phased scenario over 12 months."""
    scored = cust_df[cust_df["phase"].notna()].copy()
    scored["phase"] = scored["phase"].astype(int)

    locked_arr = cust_df[cust_df["contract_status"] == "Locked"]["annual_arr"].sum()
    baseline   = cust_df["annual_arr"].sum() if len(cust_df) > 0 else 0

    def ph_uplift(ph_num, ret):
        ph = scored[scored["phase"] == ph_num]
        if len(ph) == 0:
            return 0
        below = ph[ph["pct_of_list"] < 1.0]
        max_up = max(0, below["list_annual_arr"].sum() - below["annual_arr"].sum())
        return ret * max_up

    u1 = ph_uplift(1, ph1)
    u2 = ph_uplift(2, ph2)
    u3 = ph_uplift(3, ph3)

    months  = [0, 3, 6, 12]
    base_ln = [baseline] * 4
    sc_ln   = [baseline, baseline + u1, baseline + u1 + u2, baseline + u1 + u2 + u3]

    fig = go.Figure()
    fig.add_scatter(x=months, y=base_ln, name="Baseline",
                    line=dict(color=GRAY, dash="dash", width=2), mode="lines+markers",
                    marker=dict(size=7))
    fig.add_scatter(x=months, y=sc_ln, name="Scenario",
                    line=dict(color=PRIMARY, width=3), mode="lines+markers",
                    marker=dict(size=8), fill="tonexty",
                    fillcolor=f"rgba(27,63,228,.08)")
    fig.update_layout(
        height=280, margin=dict(t=10, b=30, l=10, r=10),
        xaxis=dict(title="Month", tickvals=[0, 3, 6, 12]),
        yaxis=dict(tickformat="$,.0f", title=""),
        legend=dict(orientation="h", y=1.08, x=0),
        plot_bgcolor=WHITE, paper_bgcolor=WHITE,
        font=dict(family="sans-serif", size=11),
    )
    return fig


def chart_churn_risk_updated(cust_df):
    """Churn risk distribution bar chart (non-locked customers only)."""
    df = cust_df[cust_df["churn_risk"].notna()].copy()
    if len(df) == 0:
        return go.Figure().add_annotation(text="No data", showarrow=False)

    counts = df["churn_risk"].astype(int).value_counts().sort_index().reindex([1,2,3,4,5], fill_value=0)
    labels = {1: "1 – Very Low", 2: "2 – Low", 3: "3 – Medium", 4: "4 – High", 5: "5 – Very High"}
    colors = [RISK_COLORS[i] for i in counts.index]

    fig = go.Figure(go.Bar(
        x=[labels[i] for i in counts.index],
        y=counts.values,
        marker_color=colors,
        text=counts.values,
        textposition="outside",
    ))
    fig.update_layout(
        height=280, margin=dict(t=10, b=30, l=10, r=10),
        xaxis_title="", yaxis_title="Customers",
        plot_bgcolor=WHITE, paper_bgcolor=WHITE,
        font=dict(family="sans-serif", size=11),
    )
    return fig


def chart_pricing_today(line_df):
    """Pricing landscape: actual unit price per product vs list/floor reference lines."""
    df = line_df[line_df["is_active"]].copy() if "is_active" in line_df.columns else line_df.copy()
    if len(df) == 0:
        return go.Figure().add_annotation(text="No data", showarrow=False)

    # Merge segment from customer df for color coding
    seg_map = cust_all.set_index("stripe_customer_id")["segment"].to_dict()
    df["segment"] = df["stripe_customer_id"].map(seg_map).fillna("D")

    products = df["price_nickname"].dropna().unique().tolist()
    fig = go.Figure()

    seg_order = ["A", "B", "C", "D"]
    for seg in seg_order:
        sub = df[df["segment"] == seg]
        if len(sub) == 0:
            continue
        fig.add_scatter(
            x=sub["price_nickname"] + " " + (sub.index % 3).astype(str),
            y=sub["unit_price"],
            mode="markers",
            name=f"Seg {seg}",
            marker=dict(color=SEG_COLORS[seg], size=7, opacity=0.75,
                        line=dict(color="white", width=0.5)),
            customdata=sub[["price_nickname","unit_price","quantity"]].values,
            hovertemplate="<b>%{customdata[0]}</b><br>Price: $%{customdata[1]:.2f}/mo<br>Qty: %{customdata[2]}<extra>Seg " + seg + "</extra>",
        )

    # Reference lines (list and floor per product)
    for prod in ["Hiring", "HR", "Payroll"]:
        sub = df[df["price_nickname"] == prod]
        if len(sub) == 0:
            continue
        xs = sub["price_nickname"] + " " + (sub.index % 3).astype(str)
        x_range = [xs.min(), xs.max()]
        fig.add_shape(type="line", x0=x_range[0], x1=x_range[1],
                      y0=LIST_PRICES[prod], y1=LIST_PRICES[prod],
                      line=dict(color=GREEN, width=1.5, dash="dot"), xref="x", yref="y")
        fig.add_shape(type="line", x0=x_range[0], x1=x_range[1],
                      y0=FLOOR_PRICES[prod], y1=FLOOR_PRICES[prod],
                      line=dict(color=RED, width=1.5, dash="dot"), xref="x", yref="y")

    fig.update_layout(
        height=320, margin=dict(t=10, b=30, l=10, r=10),
        xaxis=dict(title="", tickangle=-30, showticklabels=False),
        yaxis=dict(title="Monthly Price per Unit ($)"),
        plot_bgcolor=WHITE, paper_bgcolor=WHITE,
        legend=dict(orientation="h", y=1.08, x=0),
        font=dict(family="sans-serif", size=11),
    )
    return fig


def chart_segments_updated(cust_df):
    """Segment distribution donut chart."""
    if len(cust_df) == 0:
        return go.Figure().add_annotation(text="No data", showarrow=False)
    counts = cust_df["segment"].value_counts().reindex(["A","B","C","D"], fill_value=0)
    fig = go.Figure(go.Pie(
        labels=[f"Seg {s}" for s in counts.index],
        values=counts.values,
        hole=0.55,
        marker_colors=[SEG_COLORS[s] for s in counts.index],
        textinfo="label+percent",
        hovertemplate="<b>Segment %{label}</b><br>Customers: %{value}<br>Share: %{percent}<extra></extra>",
    ))
    fig.update_layout(
        height=260, margin=dict(t=10, b=10, l=10, r=10),
        showlegend=False,
        paper_bgcolor=WHITE,
        font=dict(family="sans-serif", size=11),
    )
    return fig


def chart_contract_status_updated(cust_df):
    """Contract status distribution donut chart."""
    if len(cust_df) == 0:
        return go.Figure().add_annotation(text="No data", showarrow=False)
    order  = ["Locked", "Expired M2M", "No Contract", "No SF Link"]
    counts = cust_df["contract_status"].value_counts().reindex(order, fill_value=0)
    fig = go.Figure(go.Pie(
        labels=counts.index.tolist(),
        values=counts.values,
        hole=0.55,
        marker_colors=[STATUS_COLORS[s] for s in counts.index],
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>Customers: %{value}<br>Share: %{percent}<extra></extra>",
    ))
    fig.update_layout(
        height=260, margin=dict(t=10, b=10, l=10, r=10),
        showlegend=False,
        paper_bgcolor=WHITE,
        font=dict(family="sans-serif", size=11),
    )
    return fig


# ── Waterfall helper ──────────────────────────────────────────────────────────
def waterfall_data(cust_df):
    """Non-overlapping waterfall: floor recovery + seg B/C/D above-floor gaps."""
    if len(cust_df) == 0:
        return 0, 0, 0, 0, 0, 0

    current_arr    = cust_df["annual_arr"].sum()
    total_opp      = cust_df["revenue_opportunity"].sum()
    floor_recovery = cust_df["floor_gap_annual"].sum()

    def seg_above_floor(seg_label):
        sub = cust_df[cust_df["segment"] == seg_label]
        if len(sub) == 0:
            return 0.0
        return (sub["revenue_opportunity"] - sub["floor_gap_annual"]).clip(lower=0).sum()

    sb = seg_above_floor("B")
    sc = seg_above_floor("C")
    sd = seg_above_floor("D")
    potential_arr = current_arr + total_opp
    return current_arr, floor_recovery, sb, sc, sd, potential_arr


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — EXECUTIVE SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
def page_executive_summary():
    banner("Executive Summary",
           "Should Workstream execute the pricing program?")

    if len(cust) == 0:
        empty_state("No data matches current filters.")
        return

    current_arr, floor_rec, sb, sc, sd, potential_arr = waterfall_data(cust)
    total_opp    = potential_arr - current_arr
    eligible     = cust[cust["contract_status"] != "Locked"]
    high_risk    = cust[cust["churn_risk"] >= 4]
    locked_custs = cust[cust["contract_status"] == "Locked"]

    # Base case uplift at default retention (88/85/83%) using phase model
    scored = cust[cust["phase"].notna()].copy()
    scored["phase"] = scored["phase"].astype(int) if len(scored) > 0 else scored["phase"]
    def ph_uplift(ph_num, ret):
        ph = scored[scored["phase"] == ph_num] if len(scored) > 0 else pd.DataFrame()
        if len(ph) == 0: return 0
        below = ph[ph["pct_of_list"] < 1.0]
        return ret * max(0, below["list_annual_arr"].sum() - below["annual_arr"].sum())
    base_uplift = ph_uplift(1, 0.88) + ph_uplift(2, 0.85) + ph_uplift(3, 0.83)

    # KPI row
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: kpi("Current ARR",      fmt_arr(current_arr),  f"{len(cust)} customers", "navy")
    with c2: kpi("Potential ARR",     fmt_arr(potential_arr), "At list pricing", "green")
    with c3: kpi("Base Case Uplift",  fmt_arr(base_uplift),  "88/85/83% retention", "green")
    with c4: kpi("Eligible Customers",str(len(eligible)),    "Non-locked", "")
    with c5: kpi("High Risk",         str(len(high_risk)),   "Score 4–5", "red")
    with c6: kpi("Locked",            str(len(locked_custs)), "Under contract", "")

    st.markdown("")

    # Main visual row
    col_left, col_right = st.columns([1, 1])

    with col_left:
        section("ARR Projection (12-Month Scenario)")
        fig_proj = chart_arr_projection_updated(cust)
        if len(cust) > 0:
            st.plotly_chart(fig_proj, use_container_width=True)
        else:
            empty_state()

    with col_right:
        section("Revenue Opportunity Waterfall")
        if current_arr > 0:
            wf_measures = ["absolute", "relative", "relative", "relative", "relative", "total"]
            wf_x = ["Current ARR", "Floor Recovery", "Seg B Opp", "Seg C Opp", "Seg D Opp", "Potential ARR"]
            wf_y = [current_arr, floor_rec, sb, sc, sd, potential_arr]
            fig_wf = go.Figure(go.Waterfall(
                orientation="v",
                measure=wf_measures,
                x=wf_x,
                y=wf_y,
                connector=dict(line=dict(color=GRAY, width=1)),
                increasing=dict(marker_color=GREEN),
                decreasing=dict(marker_color=RED),
                totals=dict(marker_color=PRIMARY),
                text=[fmt_arr(v) for v in wf_y],
                textposition="outside",
            ))
            fig_wf.update_layout(
                height=280, margin=dict(t=10, b=30, l=10, r=10),
                yaxis=dict(tickformat="$,.0f", title=""),
                plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                font=dict(family="sans-serif", size=11),
            )
            st.plotly_chart(fig_wf, use_container_width=True)
        else:
            empty_state()

    # Supporting row
    st.markdown("")
    col_left2, col_right2 = st.columns([1, 1])

    with col_left2:
        section("Customer Segments")
        st.plotly_chart(chart_segments_updated(cust), use_container_width=True)

    with col_right2:
        section("Contract Status")
        st.plotly_chart(chart_contract_status_updated(cust), use_container_width=True)

    # Insight box
    if total_opp > 0 and current_arr > 0:
        pct_gap = total_opp / current_arr * 100
        st.markdown(f"""
        <div class="insight-box">
          <b>Key Insight:</b> There is <b>{fmt_arr(total_opp)} ({pct_gap:.1f}%)</b> of annual pricing
          opportunity across <b>{(len(cust[cust['segment']!='A']))} customers</b> priced below list.
          Floor recovery alone represents <b>{fmt_arr(floor_rec)}</b>.
          Base-case scenario delivers <b>{fmt_arr(base_uplift)}</b> with standard retention assumptions.
        </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — PRICING OPPORTUNITY
# ═══════════════════════════════════════════════════════════════════════════════
def page_pricing_opportunity():
    banner("Pricing Opportunity",
           "Where is Workstream underpriced and by how much?")

    if len(cust) == 0:
        empty_state("No data matches current filters.")
        return

    # Hero chart
    section("Pricing Today — Current Prices vs List and Floor Benchmarks")
    active_f = active_lines[active_lines["is_active"]] if "is_active" in active_lines.columns else active_lines
    if len(active_f) > 0:
        st.plotly_chart(chart_pricing_today(active_f), use_container_width=True)
    else:
        empty_state()

    # --- Opportunity by Product ---
    st.markdown("")
    section("Opportunity by Product")

    prod_rows = []
    prods_in_filter = [f_prod] if f_prod != "All" else ["Hiring", "HR", "Payroll"]
    for prod in prods_in_filter:
        prod_lines = active_lines[active_lines["price_nickname"] == prod] if "price_nickname" in active_lines.columns else pd.DataFrame()
        if len(prod_lines) == 0:
            continue
        # Customers with this product
        prod_cust_ids = prod_lines["stripe_customer_id"].unique()
        prod_custs    = cust[cust["stripe_customer_id"].isin(prod_cust_ids)]

        median_price  = prod_lines["unit_price"].median() if len(prod_lines) > 0 else 0
        list_p        = LIST_PRICES.get(prod, 0)
        floor_p       = FLOOR_PRICES.get(prod, 0)
        opp_lines     = prod_lines[prod_lines["unit_price"] < list_p]
        opportunity   = ((list_p - opp_lines["unit_price"]) * opp_lines["quantity"]).sum() * 12
        arr_impact    = opportunity

        prod_rows.append({
            "Product":         prod,
            "Customers":       len(prod_custs),
            "Current Median":  f"${median_price:.2f}/mo",
            "Floor Price":     f"${floor_p:.2f}/mo",
            "List Price":      f"${list_p:.2f}/mo",
            "Opportunity":     fmt_arr(opportunity),
            "ARR Impact":      fmt_arr(arr_impact),
        })

    if prod_rows:
        prod_df = pd.DataFrame(prod_rows)
        col_p1, col_p2, col_p3 = st.columns(len(prod_rows))
        cols = [col_p1, col_p2, col_p3][:len(prod_rows)]
        for i, (_, row) in enumerate(prod_df.iterrows()):
            with cols[i]:
                st.markdown(f"""
                <div class="kpi-card">
                  <div class="kpi-label">{row['Product']}</div>
                  <div style='font-size:12px;color:{GRAY};margin:6px 0 2px'>Current Median: <b style='color:{NAVY}'>{row['Current Median']}</b></div>
                  <div style='font-size:12px;color:{GRAY}'>Floor: <b style='color:{AMBER}'>{row['Floor Price']}</b> &nbsp;|&nbsp; List: <b style='color:{GREEN}'>{row['List Price']}</b></div>
                  <div style='margin-top:8px;font-size:13px;font-weight:700;color:{PRIMARY}'>ARR Impact: {row['ARR Impact']}</div>
                  <div style='font-size:11px;color:{GRAY}'>{row['Customers']} customers with this product</div>
                </div>""", unsafe_allow_html=True)
    else:
        empty_state()

    # --- Opportunity by Segment ---
    st.markdown("")
    section("Opportunity by Segment")

    seg_rows = []
    for seg in ["A", "B", "C", "D"]:
        sub = cust[cust["segment"] == seg]
        if len(sub) == 0:
            continue
        seg_rows.append({
            "Segment":   seg,
            "Customers": len(sub),
            "ARR":       fmt_arr(sub["annual_arr"].sum()),
            "Opportunity": fmt_arr(sub["revenue_opportunity"].sum()),
            "Avg % of List": f"{sub['pct_of_list'].mean()*100:.1f}%",
        })

    if seg_rows:
        seg_df = pd.DataFrame(seg_rows)
        st.dataframe(seg_df, use_container_width=True, hide_index=True, height=190)
    else:
        empty_state()

    # --- Below Floor Customer Table ---
    st.markdown("")
    section("Customers Priced Below Floor")

    bf_lines = active_lines[active_lines["below_floor"]].copy() if "below_floor" in active_lines.columns else pd.DataFrame()
    if len(bf_lines) > 0:
        seg_map  = cust.set_index("stripe_customer_id")["segment"].to_dict()
        ae_map   = cust.set_index("stripe_customer_id")["account_ae"].to_dict()
        name_map = cust.set_index("stripe_customer_id")["name"].to_dict()

        bf_lines["Customer"]      = bf_lines["stripe_customer_id"].map(name_map).fillna("—")
        bf_lines["AE"]            = bf_lines["stripe_customer_id"].map(ae_map).fillna("—")
        bf_lines["Segment"]       = bf_lines["stripe_customer_id"].map(seg_map).fillna("—")
        bf_lines["Product"]       = bf_lines["price_nickname"]
        bf_lines["Current Price"] = bf_lines["unit_price"].round(2)
        bf_lines["Floor Price"]   = bf_lines["floor_price"]
        bf_lines["Gap"]           = (bf_lines["floor_price"] - bf_lines["unit_price"]).round(2)
        bf_lines["ARR Impact"]    = ((bf_lines["floor_price"] - bf_lines["unit_price"]) * bf_lines["quantity"] * 12).round(0).astype(int)

        display_bf = bf_lines[["Customer","AE","Segment","Product","Current Price","Floor Price","Gap","ARR Impact"]].copy()
        display_bf = display_bf.sort_values("ARR Impact", ascending=False).reset_index(drop=True)

        col_dl, _ = st.columns([1, 4])
        with col_dl:
            download_btn(display_bf, "⬇ Download CSV", "below_floor_customers.csv")

        safe_table(display_bf, "below_floor", height=350)
    else:
        empty_state("No customers are priced below floor with current filters.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — RISK & READINESS
# ═══════════════════════════════════════════════════════════════════════════════
def page_risk_readiness():
    banner("Risk & Readiness",
           "What risks block execution of the pricing program?")

    if len(cust) == 0:
        empty_state("No data matches current filters.")
        return

    no_csm     = cust[~cust["has_csm"]]
    no_sf      = cust[~cust["has_sf"]]
    no_contract= cust[cust["contract_status"].isin(["No Contract", "No SF Link"])]
    high_risk  = cust[cust["churn_risk"] >= 4]

    # KPI cards
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("No CSM",            str(len(no_csm)),      "Customers without CSM", "red")
    with c2: kpi("No Salesforce Link", str(len(no_sf)),       "Missing SF ID", "amber")
    with c3: kpi("No Contract",        str(len(no_contract)), "No active contract", "amber")
    with c4: kpi("High Risk",          str(len(high_risk)),   "Churn score 4–5", "red")

    st.markdown("")

    # Main charts
    col_left, col_right = st.columns(2)
    with col_left:
        section("Churn Risk Distribution")
        st.plotly_chart(chart_churn_risk_updated(cust), use_container_width=True)

    with col_right:
        section("Contract Status Distribution")
        st.plotly_chart(chart_contract_status_updated(cust), use_container_width=True)

    # Renewal pipeline
    st.markdown("")
    section("Renewal Pipeline (Locked Customers by Expiry)")

    locked = cust[cust["contract_status"] == "Locked"].copy()
    if len(locked) > 0:
        bucket_order = ["0–3 Months", "3–6 Months", "6–12 Months", "12+ Months"]
        renewal_df   = (
            locked[locked["renewal_bucket"].notna()]
            .groupby("renewal_bucket")
            .agg(Customers=("annual_arr","count"), ARR=("annual_arr","sum"))
            .reindex(bucket_order, fill_value=0)
            .reset_index()
            .rename(columns={"renewal_bucket":"Renewal Window"})
        )
        renewal_df["ARR"] = renewal_df["ARR"].apply(fmt_arr)

        cols = st.columns(4)
        for i, row in renewal_df.iterrows():
            variant = "red" if row["Renewal Window"] == "0–3 Months" else ("amber" if row["Renewal Window"] == "3–6 Months" else "")
            with cols[i % 4]:
                kpi(row["Renewal Window"], str(row["Customers"]) + " customers", row["ARR"] + " ARR", variant)
    else:
        empty_state("No locked customers with current filters.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — ACTION CENTER
# ═══════════════════════════════════════════════════════════════════════════════
def page_action_center():
    banner("Action Center",
           "Who should Workstream target first and what is the expected impact?")

    if len(cust) == 0:
        empty_state("No data matches current filters.")
        return

    # --- Customer Prioritization Matrix ---
    section("Customer Prioritization Matrix — Risk vs Opportunity")
    scored_m = cust[cust["churn_risk"].notna()].copy()

    if len(scored_m) > 0:
        scored_m["risk_label"] = "Risk " + scored_m["churn_risk"].astype(int).astype(str)
        fig_matrix = px.scatter(
            scored_m,
            x="churn_risk",
            y="revenue_opportunity",
            size="annual_arr",
            color="segment",
            color_discrete_map=SEG_COLORS,
            hover_name="name",
            hover_data={"annual_arr": ":$,.0f", "pct_of_list": ":.1%",
                        "contract_status": True, "churn_risk": True,
                        "segment": False},
            labels={
                "churn_risk":          "Churn Risk Score (1=Low, 5=High)",
                "revenue_opportunity": "Revenue Opportunity (Annual $)",
                "annual_arr":          "Current ARR",
                "segment":             "Segment",
            },
            size_max=40,
        )
        fig_matrix.update_layout(
            height=380, margin=dict(t=10, b=30, l=10, r=10),
            yaxis=dict(tickformat="$,.0f"),
            xaxis=dict(tickvals=[1, 2, 3, 4, 5]),
            plot_bgcolor=BG, paper_bgcolor=WHITE,
            legend=dict(orientation="h", y=1.05),
            font=dict(family="sans-serif", size=11),
        )
        st.plotly_chart(fig_matrix, use_container_width=True)
    else:
        empty_state("Churn risk data unavailable with current filters (check if Contract Status = Locked).")

    # --- Opportunity by AE ---
    st.markdown("")
    section("Opportunity by AE Owner")

    ae_df = (
        cust[cust["account_ae"] != "—"]
        .groupby("account_ae")
        .agg(
            Customers     = ("annual_arr",          "count"),
            ARR           = ("annual_arr",          "sum"),
            Opportunity   = ("revenue_opportunity", "sum"),
        )
        .reset_index()
        .rename(columns={"account_ae": "AE Owner"})
        .sort_values("Opportunity", ascending=False)
    )
    if len(ae_df) > 0:
        ae_display = ae_df.copy()
        ae_display["ARR"]         = ae_display["ARR"].apply(fmt_arr)
        ae_display["Opportunity"] = ae_display["Opportunity"].apply(fmt_arr)
        st.dataframe(ae_display, use_container_width=True, hide_index=True, height=210)
    else:
        empty_state()

    # --- Priority Customers Table ---
    st.markdown("")
    section("Priority Customers")

    priority_df = cust[cust["revenue_opportunity"] > 0].copy()
    priority_df = priority_df.sort_values("revenue_opportunity", ascending=False)

    if len(priority_df) > 0:
        def risk_badge(r):
            if pd.isna(r): return "—"
            r = int(r)
            if r <= 2: return f"🟢 {r}"
            elif r == 3: return f"🟡 {r}"
            else: return f"🔴 {r}"

        display_prio = pd.DataFrame({
            "Customer":          priority_df["name"].values,
            "AE":                priority_df["account_ae"].values,
            "CSM":               priority_df["csm_name"].values,
            "Segment":           priority_df["segment"].values,
            "ARR":               priority_df["annual_arr"].apply(fmt_arr).values,
            "Risk Score":        priority_df["churn_risk"].apply(risk_badge).values,
            "Contract Status":   priority_df["contract_status"].values,
            "Recommended Action":priority_df["recommended_action"].values,
            "Expected ARR Impact":priority_df["revenue_opportunity"].apply(fmt_arr).values,
        })

        col_dl, _ = st.columns([1, 4])
        with col_dl:
            download_btn(
                priority_df[["name","account_ae","csm_name","segment","annual_arr",
                              "churn_risk","contract_status","recommended_action","revenue_opportunity"]],
                "⬇ Download CSV", "priority_customers.csv"
            )
        safe_table(display_prio, "priority", height=400)
    else:
        empty_state("No customers with pricing opportunity under current filters.")

    # ── Scenario Modeling ─────────────────────────────────────────────────────
    st.markdown("")
    st.markdown(f'<div class="page-banner"><h2>Scenario Modeling</h2><p>Adjust retention rates to model revenue impact by phase</p></div>', unsafe_allow_html=True)

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        ph1_ret = st.slider("Phase 1 Retention (Score 1–2)", 0, 100, 88, format="%d%%", key="ph1") / 100
    with col_s2:
        ph2_ret = st.slider("Phase 2 Retention (Score 3)",   0, 100, 85, format="%d%%", key="ph2") / 100
    with col_s3:
        ph3_ret = st.slider("Phase 3 Retention (Score 4–5)", 0, 100, 83, format="%d%%", key="ph3") / 100

    scored6 = cust[cust["phase"].notna()].copy()
    scored6["phase"] = scored6["phase"].astype(int) if len(scored6) > 0 else scored6["phase"]
    locked_arr   = cust[cust["contract_status"] == "Locked"]["annual_arr"].sum()
    baseline_arr = cust["annual_arr"].sum()

    def phase_scenario(ph_num, ret):
        ph    = scored6[scored6["phase"] == ph_num] if len(scored6) > 0 else pd.DataFrame()
        if len(ph) == 0:
            return {"customers": 0, "current_arr": 0.0, "potential_arr": 0.0, "incremental_arr": 0.0, "retention": ret}
        below     = ph[ph["pct_of_list"] < 1.0]
        curr      = ph["annual_arr"].sum()
        max_up    = max(0, below["list_annual_arr"].sum() - below["annual_arr"].sum())
        pot_arr   = curr + max_up
        sc_uplift = ret * max_up
        return {
            "customers":      len(ph),
            "current_arr":    curr,
            "potential_arr":  pot_arr,
            "incremental_arr":sc_uplift,
            "retention":      ret,
        }

    ph_ret_map  = {1: ph1_ret, 2: ph2_ret, 3: ph3_ret}
    ph_results  = {i: phase_scenario(i, ph_ret_map[i]) for i in [1, 2, 3]}
    total_incr  = sum(ph_results[i]["incremental_arr"] for i in [1, 2, 3])
    projected   = locked_arr + sum(ph_results[i]["current_arr"] + ph_results[i]["incremental_arr"] for i in [1, 2, 3])
    pct_uplift  = total_incr / baseline_arr * 100 if baseline_arr > 0 else 0

    # Scenario KPIs
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1: kpi("Current ARR",    fmt_arr(baseline_arr), "",              "navy")
    with sc2: kpi("Projected ARR",  fmt_arr(projected),    "After scenario","green")
    with sc3: kpi("Incremental ARR",fmt_arr(total_incr),   "Net new revenue","green")
    with sc4: kpi("% Uplift",       f"{pct_uplift:.1f}%",  "On current ARR","")

    # ARR Projection chart with live slider values
    st.markdown("")
    section("ARR Trajectory (12-Month Ramp)")
    st.plotly_chart(
        chart_arr_projection_updated(cust, ph1_ret, ph2_ret, ph3_ret),
        use_container_width=True,
    )

    # Scenario table
    st.markdown("")
    section("Phase Scenario Detail")
    ph_labels = {1: "Phase 1 — Score 1–2", 2: "Phase 2 — Score 3", 3: "Phase 3 — Score 4–5"}
    sc_tbl = pd.DataFrame([
        {
            "Phase":          ph_labels[i],
            "Customers":      ph_results[i]["customers"],
            "Current ARR":    fmt_arr(ph_results[i]["current_arr"]),
            "Potential ARR":  fmt_arr(ph_results[i]["potential_arr"]),
            "Incremental ARR":fmt_arr(ph_results[i]["incremental_arr"]),
            "Retention":      f"{ph_ret_map[i]*100:.0f}%",
        }
        for i in [1, 2, 3]
    ])
    st.dataframe(sc_tbl, use_container_width=True, hide_index=True, height=142)

    # Do Nothing vs Pricing Program summary
    st.markdown("")
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown(f"""
        <div class="kpi-card red">
          <div class="kpi-label">Do Nothing Scenario</div>
          <div class="kpi-value" style='color:{RED}'>{fmt_arr(baseline_arr)}</div>
          <div class="kpi-sub">ARR stays flat. Pricing gaps compound over time.</div>
        </div>""", unsafe_allow_html=True)
    with col_r:
        st.markdown(f"""
        <div class="kpi-card green">
          <div class="kpi-label">Pricing Program Scenario</div>
          <div class="kpi-value" style='color:{GREEN}'>{fmt_arr(projected)}</div>
          <div class="kpi-sub">+{fmt_arr(total_incr)} incremental ARR ({pct_uplift:.1f}% uplift).</div>
        </div>""", unsafe_allow_html=True)

    download_btn(sc_tbl, "⬇ Download Scenario Summary", "scenario_summary.csv")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTING
# ═══════════════════════════════════════════════════════════════════════════════
if page == "Executive Summary":
    page_executive_summary()
elif page == "Pricing Opportunity":
    page_pricing_opportunity()
elif page == "Risk & Readiness":
    page_risk_readiness()
elif page == "Action Center":
    page_action_center()
