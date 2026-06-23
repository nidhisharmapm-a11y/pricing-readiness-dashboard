import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(
    page_title="Workstream Pricing Intelligence",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed",
)

# ── Brand Colors ──────────────────────────────────────────────────────────────
PRIMARY = "#1B3FE4"
NAVY    = "#0F1B2D"
BG      = "#EEF2FF"
WHITE   = "#FFFFFF"
GREEN   = "#00B67A"
AMBER   = "#FFA500"
PURPLE  = "#7C5CBF"
GRAY    = "#6B7280"

LIST_PRICES  = {"Hiring": 75.0, "HR": 100.0, "Payroll": 14.0}
FLOOR_PRICES = {"Hiring": 60.0, "HR": 80.0,  "Payroll": 11.0}
REF_DATE     = pd.Timestamp("2026-06-20")

SEG_COLORS    = {"A": GREEN, "B": PRIMARY, "C": AMBER, "D": PURPLE}
STATUS_COLORS = {
    "Locked":      PRIMARY,
    "Expired M2M": AMBER,
    "No Contract": GRAY,
    "No SF Link":  PURPLE,
}
RISK_COLORS = {1: GREEN, 2: "#66D4A8", 3: AMBER, 4: "#FF8C00", 5: PURPLE}


def get_path(filename):
    return os.path.join(os.path.dirname(__file__), "..", "Input", filename)


def get_enriched_path():
    return get_path("customers_enriched.csv")


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  body {{ font-family: sans-serif; }}
  .kpi {{ background:{WHITE}; border-radius:10px; padding:18px 22px;
           box-shadow:0 1px 4px rgba(0,0,0,.07); border-top:4px solid {PRIMARY}; }}
  .kpi.green  {{ border-top-color:{GREEN};  }}
  .kpi.amber  {{ border-top-color:{AMBER};  }}
  .kpi.purple {{ border-top-color:{PURPLE}; }}
  .kpi.navy   {{ border-top-color:{NAVY};   }}
  .kpi-label {{ font-size:14px; font-weight:700; color:{GRAY}; text-transform:uppercase; letter-spacing:.06em; }}
  .kpi-value {{ font-size:32px; font-weight:800; color:{NAVY}; margin:6px 0 4px; line-height:1.1; }}
  .kpi-sub   {{ font-size:13px; color:{GRAY}; line-height:1.5; }}
  .kpi-delta {{ font-size:13px; font-weight:700; color:{GRAY}; margin-top:5px; }}
  .sec {{ font-size:16px; font-weight:700; color:{NAVY}; border-bottom:2px solid #dde3f0;
          padding-bottom:6px; margin-bottom:14px; text-transform:uppercase; letter-spacing:.04em; }}
  .tab-h  {{ font-size:26px; font-weight:800; color:{NAVY}; margin-bottom:4px; }}
  .tab-sh {{ font-size:15px; color:{GRAY}; margin-bottom:20px; line-height:1.5; }}
  .ph-card {{ background:{BG}; border-radius:10px; padding:20px; }}
  .note {{ background:{BG}; border-radius:8px; padding:14px 18px;
           border-left:4px solid {PRIMARY}; font-size:14px; color:{NAVY}; margin-top:14px; line-height:1.6; }}
  .gate {{ background:#f5f0ff; border-radius:8px; padding:18px 22px;
           border-left:5px solid {PURPLE}; font-size:15px; color:{NAVY}; margin-top:16px; line-height:1.7; }}
  .seg-card {{ border-radius:12px; padding:22px 24px;
               box-shadow:0 1px 6px rgba(0,0,0,.08); background:{WHITE}; height:100%; }}
  .seg-action {{ background:{BG}; border-radius:8px; padding:12px 14px; margin-top:12px;
                 font-size:14px; color:{NAVY}; line-height:1.6; }}
  .filter-label {{ font-size:14px; font-weight:700; color:{GRAY}; text-transform:uppercase;
                   letter-spacing:.06em; margin-bottom:8px; }}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def kpi(label, value, sub="", variant="", delta=""):
    d = f'<div class="kpi-delta">{delta}</div>' if delta else ""
    st.markdown(f"""
    <div class="kpi {variant}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      <div class="kpi-sub">{sub}</div>{d}
    </div>""", unsafe_allow_html=True)


def sec(title):
    st.markdown(f'<div class="sec">{title}</div>', unsafe_allow_html=True)


def fmt_m(v):
    if abs(v) >= 1_000_000: return f"${v/1_000_000:.2f}M"
    if abs(v) >= 1_000:     return f"${v/1_000:.0f}K"
    return f"${v:,.0f}"


CHART    = dict(plot_bgcolor=WHITE, paper_bgcolor=WHITE, font=dict(family="sans-serif", size=13))
AX_FONT  = dict(size=13)


# ── Data Loading ──────────────────────────────────────────────────────────────
@st.cache_data
def build_line_df():
    """Active subscription lines from the verified 388-customer dataset."""
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
    df["floor_gap_monthly"] = (df["floor_price"] - df["unit_price"]).clip(lower=0) * df["quantity"]
    df["end_date"]          = pd.to_datetime(df["end_date"], errors="coerce")
    df["has_sf"]            = (
        df["metadata_salesforce_id"].notna() &
        (df["metadata_salesforce_id"].astype(str).str.strip() != "")
    )
    df["has_contract"]      = (
        df["contract_id"].notna() &
        (df["contract_id"].astype(str).str.strip() != "")
    )
    return df


@st.cache_data
def build_customer_df():
    """388 customers from stripeXsfdc.csv + verified churn_risk_score from enriched CSV."""
    line_df = build_line_df()
    active  = line_df[line_df["is_active"]].copy()

    def agg(g):
        mr   = (g["unit_price"] * g["quantity"]).sum()
        lr   = (g["list_price"] * g["quantity"]).sum()
        fg   = g["floor_gap_monthly"].sum() * 12
        far  = (g["floor_price"] * g["quantity"]).sum() * 12
        pct  = mr / lr if lr > 0 else 0
        inc  = max(0, (1 / pct - 1) * 100) if pct > 0 else 999
        has_sf       = g["has_sf"].any()
        has_contract = g["has_contract"].any()
        end_date     = g["end_date"].max()
        created      = pd.to_datetime(g["created"].min())
        tenure_years = (REF_DATE - created).days / 365.25
        csm_s  = g["csm_name__c"].dropna(); csm_s = csm_s[csm_s.str.strip() != ""]
        has_csm = len(csm_s) > 0
        if has_contract and pd.notna(end_date) and end_date > REF_DATE:
            status = "Locked"
        elif has_contract and pd.notna(end_date) and end_date <= REF_DATE:
            status = "Expired M2M"
        elif not has_sf:
            status = "No SF Link"
        else:
            status = "No Contract"
        return pd.Series({
            "annual_arr":       mr * 12,
            "list_annual_arr":  lr * 12,
            "floor_annual_arr": far,
            "floor_gap_annual": fg,
            "pct_of_list":      pct,
            "increase_pct":     inc,
            "contract_status":  status,
            "end_date":         end_date,
            "tenure_years":     tenure_years,
            "has_csm":          has_csm,
            "has_sf":           has_sf,
        })

    cust = active.groupby("stripe_customer_id", group_keys=False).apply(agg).reset_index()

    cust["segment"] = cust["pct_of_list"].apply(
        lambda p: "A" if p >= 1.0 else ("B" if p >= 0.9 else ("C" if p >= 0.75 else "D"))
    )

    def target_fn(row):
        s = row["segment"]
        if s == "A": return row["annual_arr"]
        if s == "B": return row["list_annual_arr"]
        if s == "C": return row["list_annual_arr"] * 0.9
        return row["floor_annual_arr"]
    cust["target_annual_arr"] = cust.apply(target_fn, axis=1)
    cust["max_uplift"]        = (cust["target_annual_arr"] - cust["annual_arr"]).clip(lower=0)

    def renewal_bucket(row):
        if row["contract_status"] != "Locked" or pd.isna(row["end_date"]): return None
        m = (row["end_date"] - REF_DATE).days / 30.44
        return ("0-3 Months" if m <= 3 else "3-6 Months" if m <= 6
                else "6-12 Months" if m <= 12 else "12+ Months")
    cust["renewal_bucket"] = cust.apply(renewal_bucket, axis=1)

    def phase_fn(row):
        st_ = row["contract_status"]
        bkt = row["renewal_bucket"]
        if st_ == "Locked":
            return 1 if bkt in ("0-3 Months", "3-6 Months") else np.nan
        if st_ == "Expired M2M":   return 2
        if st_ in ("No Contract", "No SF Link"): return 3
        return np.nan
    cust["phase"] = cust.apply(phase_fn, axis=1)

    # display_contract_status: same as contract_status (No SF Link already distinct)
    cust["display_contract_status"] = cust["contract_status"]

    # Merge verified churn_risk_score from enriched CSV (left join — covers 383 of 388)
    enc = pd.read_csv(get_enriched_path())[["stripe_customer_id", "churn_risk_score"]]
    enc["churn_risk_score"] = pd.to_numeric(enc["churn_risk_score"], errors="coerce")
    cust = cust.merge(enc, on="stripe_customer_id", how="left")

    # Fallback formula for the 5 customers absent from enriched CSV
    def churn_risk_fallback(row):
        if pd.notna(row["churn_risk_score"]): return row["churn_risk_score"]
        if row["contract_status"] == "Locked": return np.nan
        p, inc, yrs, st_ = (row["pct_of_list"], row["increase_pct"],
                             row["tenure_years"], row["contract_status"])
        dd = 1 if p >= 1.0 else (2 if p >= 0.9 else (3 if p >= 0.75 else (4 if p >= 0.6 else 5)))
        cp = 3 if st_ == "Expired M2M" else 5
        t  = 1 if yrs >= 4 else (2 if yrs >= 3 else (3 if yrs >= 2 else (4 if yrs >= 1 else 5)))
        im = 1 if inc <= 0 else (2 if inc <= 9 else (3 if inc <= 29 else (4 if inc <= 40 else 5)))
        return int(np.clip(round(0.30*dd + 0.30*cp + 0.20*t + 0.20*im), 1, 5))
    cust["churn_risk_score"] = cust.apply(churn_risk_fallback, axis=1)

    return cust


@st.cache_data
def build_accounts_df():
    """Per-product repricing rows built from stripeXsfdc.csv active lines."""
    line_df = build_line_df()
    active  = line_df[line_df["is_active"]].copy()
    cust    = build_customer_df()

    eligible_ids = set(cust[
        (~cust["contract_status"].isin(["Locked"])) &
        (cust["segment"].isin(["B", "C", "D"]))
    ]["stripe_customer_id"])

    active_elig = active[active["stripe_customer_id"].isin(eligible_ids)].copy()

    def prod_agg(g):
        qty = g["quantity"].sum()
        ppu = (g["unit_price"] * g["quantity"]).sum() / qty if qty > 0 else 0
        return pd.Series({"unit_price": ppu, "quantity": qty})

    prod_df = (
        active_elig
        .groupby(["stripe_customer_id", "price_nickname"], group_keys=False)
        .apply(prod_agg)
        .reset_index()
    )

    cust_slim = cust[["stripe_customer_id", "segment", "phase",
                       "churn_risk_score", "has_csm"]].copy()
    prod_df = prod_df.merge(cust_slim, on="stripe_customer_id", how="left")

    rows = []
    for _, r in prod_df.iterrows():
        prod = r["price_nickname"]
        if prod not in LIST_PRICES: continue
        seg = r["segment"]
        ppu = float(r["unit_price"])
        qty = float(r["quantity"])
        if seg == "B": target = LIST_PRICES[prod]
        elif seg == "C": target = LIST_PRICES[prod] * 0.9
        else:            target = FLOOR_PRICES[prod]
        inc = max(0.0, target - ppu)
        if inc <= 0: continue
        rows.append({
            "Customer ID":     r["stripe_customer_id"],
            "Segment":         seg,
            "Product":         prod,
            "Current Price":   ppu,
            "Target Price":    target,
            "Increase ($)":    inc,
            "Increase (%)":    inc / ppu * 100 if ppu > 0 else 0,
            "Current ARR":     ppu * qty * 12,
            "Incremental ARR": inc * qty * 12,
            "Phase":           int(r["phase"]) if pd.notna(r["phase"]) else None,
            "Churn Risk":      int(r["churn_risk_score"]) if pd.notna(r["churn_risk_score"]) else None,
            "CSM Assigned":    "Yes" if r["has_csm"] else "No",
        })
    return pd.DataFrame(rows)


@st.cache_data
def get_product_medians():
    """Median unit prices per product from active stripeXsfdc.csv lines."""
    line_df = build_line_df()
    active  = line_df[line_df["is_active"]]
    return {
        prod: active[active["price_nickname"] == prod]["unit_price"].median()
        for prod in ["Hiring", "HR", "Payroll"]
    }


# ── Load data ─────────────────────────────────────────────────────────────────
cust_all  = build_customer_df()
_medians  = get_product_medians()
acc_df    = build_accounts_df()

# ── Pre-compute program-level figures ─────────────────────────────────────────
n_all            = len(cust_all)
baseline_arr     = cust_all["annual_arr"].sum()
floor_gap_annual = cust_all["floor_gap_annual"].sum()
seg_a_unlocked   = cust_all[
    (cust_all["segment"] == "A") & (cust_all["contract_status"] != "Locked")
]["annual_arr"].sum()
cost_of_inaction = floor_gap_annual + seg_a_unlocked * 0.05

_phase_info = {}
for _ph in [1, 2, 3]:
    _sub = cust_all[cust_all["phase"] == _ph]
    _phase_info[_ph] = {
        "customers":   len(_sub),
        "current_arr": _sub["annual_arr"].sum(),
        "max_uplift":  _sub["max_uplift"].sum(),
    }

RET = {
    "Maximum":   {1: 1.00, 2: 1.00, 3: 1.00},
    "Base Case": {1: 0.88, 2: 0.85, 3: 0.83},
    "Downside":  {1: 0.83, 2: 0.80, 3: 0.78},
}

def calc_scenario(ret_map):
    per_ph, total = {}, 0
    for ph in [1, 2, 3]:
        inc = ret_map[ph] * _phase_info[ph]["max_uplift"]
        per_ph[ph] = inc
        total += inc
    return total, per_ph

sc_data = {}
for sc_name, ret_map in RET.items():
    total, per_ph = calc_scenario(ret_map)
    sc_data[sc_name] = {
        "total_uplift": total,
        "new_arr":      baseline_arr + total,
        "vs_inaction":  (baseline_arr + total) - (baseline_arr - cost_of_inaction),
        "per_ph":       per_ph,
        "ret":          ret_map,
    }

_months = [0, 3, 6, 12]

def trajectory(per_ph):
    u1, u2, u3 = per_ph[1], per_ph[2], per_ph[3]
    return [baseline_arr, baseline_arr+u1, baseline_arr+u1+u2, baseline_arr+u1+u2+u3]

traj = {
    "Inaction":  [baseline_arr - cost_of_inaction * m / 12 for m in _months],
    "Downside":  trajectory(sc_data["Downside"]["per_ph"]),
    "Base Case": trajectory(sc_data["Base Case"]["per_ph"]),
    "Maximum":   trajectory(sc_data["Maximum"]["per_ph"]),
}

_min_vs_inaction = min(sc_data[s]["vs_inaction"] for s in sc_data)
_n_hr_all        = int((cust_all["churn_risk_score"] >= 4).sum())


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "  ⚡ The Business  ",
    "  🔍 The Diagnosis  ",
    "  📋 The Accounts  ",
    "  📈 The Program  ",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — THE BUSINESS
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="tab-h">The Business</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="tab-sh">{fmt_m(baseline_arr)} ARR across {n_all} active customers '
        f'— but pricing compliance and contract coverage tell a different story</div>',
        unsafe_allow_html=True,
    )

    avg_per_cust  = baseline_arr / n_all if n_all > 0 else 0
    below_floor_n = (cust_all["floor_gap_annual"] > 0).sum()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Current ARR Base", fmt_m(baseline_arr),
            f"Across {n_all} active customers — Stripe verified, June 2026", "navy")
    with c2:
        kpi("Revenue Per Customer", fmt_m(avg_per_cust),
            "Healthy unit economics — the pricing model works when enforced")
    with c3:
        kpi("Billing Below Their Own Floor", str(below_floor_n),
            "These customers aren't getting a discount — they're paying less than Workstream's stated minimum",
            "amber")
    with c4:
        kpi("What Inaction Costs Per Year", fmt_m(cost_of_inaction),
            "Every month without a program running is $13,500 that doesn't come back",
            "purple",
            delta=f"{fmt_m(floor_gap_annual)} floor under-collection + {fmt_m(seg_a_unlocked * 0.05)} Seg A erosion risk")

    st.markdown("<br>", unsafe_allow_html=True)

    # Chart 1: Price benchmarks
    sec("WORKSTREAM'S PRICES ARE HOLDING — MEDIANS SIT CLOSE TO LIST ACROSS ALL THREE PRODUCTS")

    _products   = ["Hiring", "HR", "Payroll"]
    _pct_labels = {_p: f"{_medians[_p] / LIST_PRICES[_p] * 100:.0f}% of list" for _p in _products}

    fig_price = go.Figure()
    fig_price.add_bar(
        name="Floor", x=_products,
        y=[FLOOR_PRICES[p] for p in _products],
        marker_color=PURPLE, opacity=0.70,
        text=[f"${FLOOR_PRICES[p]:.0f}" for p in _products],
        textposition="inside", textfont=dict(color=WHITE, size=12),
    )
    fig_price.add_bar(
        name="Median Actual", x=_products,
        y=[_medians[p] for p in _products],
        marker_color=PRIMARY,
        text=[f"${_medians[p]:.2f} ({_pct_labels[p]})" for p in _products],
        textposition="outside", textfont=dict(size=12),
    )
    fig_price.add_bar(
        name="List Price", x=_products,
        y=[LIST_PRICES[p] for p in _products],
        marker_color=GREEN, opacity=0.70,
        text=[f"${LIST_PRICES[p]:.0f}" for p in _products],
        textposition="inside", textfont=dict(color=WHITE, size=12),
    )
    fig_price.update_layout(
        barmode="group", height=320,
        margin=dict(t=20, b=20, l=10, r=10),
        yaxis=dict(title="Monthly Price per Unit ($)", tickformat="$,.0f",
                   title_font=AX_FONT, tickfont=AX_FONT),
        xaxis=dict(title="", tickfont=AX_FONT),
        legend=dict(orientation="h", y=1.14, x=0, font=dict(size=13)),
        **CHART,
    )
    st.plotly_chart(fig_price, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_l, col_r = st.columns(2)
    _seg_counts = cust_all["segment"].value_counts().reindex(["A","B","C","D"], fill_value=0)
    _seg_arr    = cust_all.groupby("segment")["annual_arr"].sum().reindex(["A","B","C","D"], fill_value=0)
    _seg_labels = {
        "A": f"Seg A  ≥100% of list  ({_seg_counts['A']})",
        "B": f"Seg B  90–99%  ({_seg_counts['B']})",
        "C": f"Seg C  75–89%  ({_seg_counts['C']})",
        "D": f"Seg D  <75%    ({_seg_counts['D']})",
    }

    with col_l:
        sec("SEGMENT A IS THE LARGEST COHORT — AND THE ONLY ONE WHERE THE PRIORITY IS PROTECTION, NOT INCREASE")
        fig_cnt = go.Figure(go.Bar(
            x=_seg_counts.values,
            y=[_seg_labels[s] for s in _seg_counts.index],
            orientation="h",
            marker_color=[SEG_COLORS[s] for s in _seg_counts.index],
            text=[f"{v}" for v in _seg_counts.values],
            textposition="outside",
            textfont=dict(size=13),
        ))
        fig_cnt.update_layout(
            height=260, margin=dict(t=10, b=10, l=10, r=60),
            xaxis=dict(title="Customers", title_font=AX_FONT, tickfont=AX_FONT),
            yaxis=dict(title="", autorange="reversed", tickfont=dict(size=13)),
            **CHART,
        )
        st.plotly_chart(fig_cnt, use_container_width=True)

    with col_r:
        sec("46% OF ARR SITS IN SEGMENT A — AT RISK IF LEFT UNCONTRACTED")
        fig_arr = go.Figure(go.Bar(
            x=_seg_arr.values,
            y=[_seg_labels[s] for s in _seg_arr.index],
            orientation="h",
            marker_color=[SEG_COLORS[s] for s in _seg_arr.index],
            text=[fmt_m(v) for v in _seg_arr.values],
            textposition="outside",
            textfont=dict(size=13),
        ))
        fig_arr.update_layout(
            height=260, margin=dict(t=10, b=10, l=10, r=80),
            xaxis=dict(title="Annual ARR ($)", tickformat="$,.0f",
                       title_font=AX_FONT, tickfont=AX_FONT),
            yaxis=dict(title="", autorange="reversed", tickfont=dict(size=13)),
            **CHART,
        )
        st.plotly_chart(fig_arr, use_container_width=True)

    _pct_no_contract = (cust_all["contract_status"] != "Locked").sum() / n_all * 100
    st.markdown(f"""
    <div class="note">
    Segment A's {_seg_counts.get('A', 0)} customers at or above list price prove the pricing model is
    commercially viable — customers will pay it. The problem isn't the price. It's that
    {_pct_no_contract:.1f}% of the base has no contract locking it in, and {below_floor_n} customers
    are already slipping below floor without any enforcement mechanism to catch them.
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — THE DIAGNOSIS
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="tab-h">The Diagnosis</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="tab-sh">Three structural gaps must be closed before any pricing action can be safely executed</div>',
        unsafe_allow_html=True,
    )

    _no_contract_n = cust_all[cust_all["contract_status"] != "Locked"].shape[0]
    _no_csm_n      = (~cust_all["has_csm"]).sum()
    _no_sf_n       = (~cust_all["has_sf"]).sum()

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi("Unprotected from Repricing", str(_no_contract_n),
            f"{_no_contract_n} of {n_all} customers have no active contract — no legal basis to hold any price",
            "amber")
    with c2:
        kpi("No Relationship Owner", str(_no_csm_n),
            f"{_no_csm_n} customers have no CSM — pricing conversations have no one to lead them",
            "purple")
    with c3:
        kpi("Off the Radar Entirely", str(_no_sf_n),
            f"{_no_sf_n} customers are billing in Stripe but don't exist in Salesforce — no AE, no contract, no visibility",
            "purple")

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        f'<div class="filter-label">Explore Risk by Pricing Segment</div>',
        unsafe_allow_html=True,
    )
    sel_segs = st.multiselect(
        "Segment filter", options=["A", "B", "C", "D"], default=["A", "B", "C", "D"],
        format_func=lambda s: (
            f"Segment {s}  "
            f"({'≥100%' if s=='A' else '90-99%' if s=='B' else '75-89%' if s=='C' else '<75%'} of list)"
        ),
        label_visibility="collapsed",
    )
    if not sel_segs:
        sel_segs = ["A", "B", "C", "D"]

    cust_f = cust_all[cust_all["segment"].isin(sel_segs)]

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2)

    with col_l:
        sec("MOST CUSTOMERS HAVE NO CONTRACT — CONCENTRATED IN SEGMENTS C AND D WHERE REPRICING RISK IS HIGHEST")
        if len(cust_f) == 0:
            st.info("No data for selected segments.")
        else:
            fig_cs = go.Figure()
            _status_order = ["Locked", "Expired M2M", "No Contract", "No SF Link"]
            _seg_order    = [s for s in ["A", "B", "C", "D"] if s in sel_segs]
            for _st in _status_order:
                _ys = [
                    cust_f[
                        (cust_f["segment"] == s) &
                        (cust_f["display_contract_status"] == _st)
                    ].shape[0]
                    for s in _seg_order
                ]
                fig_cs.add_bar(
                    name=_st,
                    x=[f"Seg {s}" for s in _seg_order],
                    y=_ys,
                    marker_color=STATUS_COLORS[_st],
                    text=[str(v) if v > 0 else "" for v in _ys],
                    textposition="inside",
                    textfont=dict(size=13, color=WHITE),
                )
            fig_cs.update_layout(
                barmode="stack", height=360,
                margin=dict(t=10, b=30, l=10, r=10),
                yaxis=dict(title="Customers", title_font=AX_FONT, tickfont=AX_FONT),
                xaxis=dict(title="", tickfont=AX_FONT),
                legend=dict(orientation="h", y=1.1, x=0, font=dict(size=13)),
                **CHART,
            )
            st.plotly_chart(fig_cs, use_container_width=True)

    with col_r:
        sec(f"HALF THE ELIGIBLE BASE IS MEDIUM RISK — BUT {_n_hr_all} ACCOUNTS NEED A HUMAN CONVERSATION BEFORE ANY NOTICE GOES OUT")
        risk_df = cust_f[cust_f["churn_risk_score"].notna()]
        if len(risk_df) == 0:
            st.info("No risk data for selected segments.")
        else:
            _rcounts = (
                risk_df["churn_risk_score"].astype(int)
                .value_counts().sort_index()
                .reindex([1, 2, 3, 4, 5], fill_value=0)
            )
            _rlabels = {
                1: "1 – Low",
                2: "2 – Low-Med",
                3: "3 – Medium",
                4: "4 – High ⚠️",
                5: "5 – Highest ⚠️",
            }
            fig_risk = go.Figure(go.Bar(
                x=[_rlabels[i] for i in _rcounts.index],
                y=_rcounts.values,
                marker_color=[RISK_COLORS[i] for i in _rcounts.index],
                text=_rcounts.values,
                textposition="outside",
                textfont=dict(size=13),
            ))
            fig_risk.update_layout(
                height=360, margin=dict(t=10, b=30, l=10, r=10),
                yaxis=dict(title="Customers", title_font=AX_FONT, tickfont=AX_FONT),
                xaxis=dict(title="", tickfont=AX_FONT),
                **CHART,
            )
            st.plotly_chart(fig_risk, use_container_width=True)

    _hr_n      = int(cust_f[cust_f["churn_risk_score"] >= 4].shape[0])
    _hr_no_csm = int(cust_f[(cust_f["churn_risk_score"] >= 4) & (~cust_f["has_csm"])].shape[0])
    _hr_no_sf  = int(cust_f[(cust_f["churn_risk_score"] >= 4) & (~cust_f["has_sf"])].shape[0])
    if _hr_n > 0:
        st.markdown(f"""
        <div class="gate">
        <b>{_hr_n} customers</b> in the selected segments are high or highest risk — they need a CSM-
        or AE-led conversation before any rate notice is issued. Of these,
        <b>{_hr_no_csm}</b> have no CSM assigned and <b>{_hr_no_sf}</b> don't exist in Salesforce.
        No notice should go out to any of these accounts until coverage is in place.
        This is a hard pre-launch gate, not a guideline.
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — THE ACCOUNTS
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="tab-h">The Accounts</div>', unsafe_allow_html=True)

    # ── Segment card data ─────────────────────────────────────────────────────
    _pct_range = {
        "A": "≥100% of list", "B": "90–99% of list",
        "C": "75–89% of list", "D": "<75% of list",
    }
    _seg_clr = {"A": GREEN, "B": PRIMARY, "C": AMBER, "D": PURPLE}

    _sd = {}
    for _s in ["A", "B", "C", "D"]:
        _rows      = cust_all[cust_all["segment"] == _s]
        _nonlocked = _rows[_rows["contract_status"] != "Locked"]
        _sd[_s] = {
            "n":         len(_rows),
            "arr":       _rows["annual_arr"].sum(),
            "n_nonlocked": len(_nonlocked),
            "max_uplift":  _nonlocked["max_uplift"].sum(),
        }

    _b_avg_gap = (
        _sd["B"]["max_uplift"] / _sd["B"]["n_nonlocked"]
        if _sd["B"]["n_nonlocked"] > 0 else 0
    )

    def _seg_card(s, col):
        d   = _sd[s]
        clr = _seg_clr[s]
        if s == "A":
            action = (
                f"Contract execution — protect above-list rates. "
                f"{d['n_nonlocked']} of {d['n']} are uncontracted."
            )
            uplift_html = (
                f'<div style="margin-top:14px;padding:10px 14px;background:#fff8e6;'
                f'border-radius:6px;border-left:3px solid {AMBER};font-size:14px;color:{NAVY};line-height:1.5">'
                f'⚠️&nbsp; Rate erosion risk if uncontracted at renewal</div>'
            )
        elif s == "B":
            action = (
                f"Raise to list — {d['n_nonlocked']} non-locked eligible. "
                f"Avg gap ~${_b_avg_gap:,.0f}/customer/yr."
            )
            uplift_html = (
                f'<div style="margin-top:14px">'
                f'<div style="font-size:12px;font-weight:700;color:{GRAY};text-transform:uppercase;letter-spacing:.06em">Max Uplift</div>'
                f'<div style="font-size:26px;font-weight:800;color:{clr}">{fmt_m(d["max_uplift"])}</div>'
                f'</div>'
            )
        elif s == "C":
            action = (
                f"Step to 90% of list — {d['n_nonlocked']} non-locked eligible. "
                f"Single step avoids a 15%+ jump."
            )
            uplift_html = (
                f'<div style="margin-top:14px">'
                f'<div style="font-size:12px;font-weight:700;color:{GRAY};text-transform:uppercase;letter-spacing:.06em">Max Uplift</div>'
                f'<div style="font-size:26px;font-weight:800;color:{clr}">{fmt_m(d["max_uplift"])}</div>'
                f'</div>'
            )
        else:
            action = (
                f"Correct to floor — {d['n_nonlocked']} non-locked eligible. "
                f"Frame as floor restoration, not increase."
            )
            uplift_html = (
                f'<div style="margin-top:14px">'
                f'<div style="font-size:12px;font-weight:700;color:{GRAY};text-transform:uppercase;letter-spacing:.06em">Max Uplift</div>'
                f'<div style="font-size:26px;font-weight:800;color:{clr}">{fmt_m(d["max_uplift"])}</div>'
                f'</div>'
            )
        with col:
            st.markdown(f"""
            <div class="seg-card" style="border-left:5px solid {clr}">
              <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:6px">
                <div style="font-size:20px;font-weight:800;color:{clr}">Segment {s}</div>
                <div style="font-size:14px;color:{GRAY}">{_pct_range[s]}</div>
              </div>
              <div style="font-size:15px;color:{NAVY};margin-bottom:10px">
                <b>{d['n']} customers</b> &nbsp;·&nbsp; {fmt_m(d['arr'])} ARR
              </div>
              <div class="seg-action">{action}</div>
              {uplift_html}
            </div>""", unsafe_allow_html=True)

    # Row 1: A and B
    row1 = st.columns(2)
    _seg_card("A", row1[0])
    _seg_card("B", row1[1])

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Row 2: C and D
    row2 = st.columns(2)
    _seg_card("C", row2[0])
    _seg_card("D", row2[1])

    # Total strip
    _total_nl_bcd  = sum(_sd[s]["n_nonlocked"] for s in ["B", "C", "D"])
    _total_max_bcd = sum(_sd[s]["max_uplift"]   for s in ["B", "C", "D"])
    st.markdown(f"""
    <div style="background:{NAVY};border-radius:10px;padding:16px 26px;margin-top:14px;
                display:flex;align-items:center;justify-content:space-between">
      <div style="font-size:15px;font-weight:600;color:rgba(255,255,255,.65)">
        Total non-locked eligible max uplift
      </div>
      <div style="font-size:20px;font-weight:800;color:{GREEN}">
        {fmt_m(_total_max_bcd)}&nbsp; across &nbsp;{_total_nl_bcd} customers
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Account-level repricing table ─────────────────────────────────────────
    sec("WHO GETS RAISED AND BY HOW MUCH — ACCOUNT-LEVEL DETAIL")
    st.markdown(
        f'<div style="font-size:14px;color:{GRAY};margin-bottom:16px">'
        f'All eligible non-locked customers, ranked by incremental ARR opportunity</div>',
        unsafe_allow_html=True,
    )

    f1, f2 = st.columns(2)
    with f1:
        _ph_sel = st.selectbox("Phase", ["All", "Phase 1", "Phase 2", "Phase 3"], index=0)
    with f2:
        _risk_sel = st.selectbox("Churn Risk", ["All", "Low–Medium (1–3)", "High–Highest (4–5)"], index=0)

    _tbl = acc_df.copy()
    if _ph_sel != "All":
        _ph_num = int(_ph_sel.split()[-1])
        _tbl    = _tbl[_tbl["Phase"] == _ph_num]
    if _risk_sel == "Low–Medium (1–3)":
        _tbl = _tbl[_tbl["Churn Risk"].notna() & (_tbl["Churn Risk"] <= 3)]
    elif _risk_sel == "High–Highest (4–5)":
        _tbl = _tbl[_tbl["Churn Risk"].notna() & (_tbl["Churn Risk"] >= 4)]

    _tbl = _tbl.sort_values("Incremental ARR", ascending=False).reset_index(drop=True)

    def _highlight_risk(row):
        cr = row["Churn Risk"]
        if cr is not None and pd.notna(cr) and int(cr) >= 4:
            return ["background-color: #f5f0ff"] * len(row)
        return [""] * len(row)

    _styled = (
        _tbl.style
        .apply(_highlight_risk, axis=1)
        .format({
            "Current Price":   "${:.2f}",
            "Target Price":    "${:.2f}",
            "Increase ($)":    "${:.2f}",
            "Increase (%)":    "{:.1f}%",
            "Current ARR":     "${:,.0f}",
            "Incremental ARR": "${:,.0f}",
            "Churn Risk":      lambda x: str(int(x)) if pd.notna(x) else "—",
            "Phase":           lambda x: f"Phase {int(x)}" if pd.notna(x) else "—",
        })
    )
    st.dataframe(_styled, use_container_width=True, hide_index=True, height=520)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — THE PROGRAM
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="tab-h">The Program</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="tab-sh">Even the most conservative execution scenario outperforms inaction '
        f'by {fmt_m(_min_vs_inaction)} over 12 months</div>',
        unsafe_allow_html=True,
    )

    _sc_sel = st.radio(
        "Scenario", ["Base Case", "Maximum", "Downside"],
        horizontal=True, label_visibility="collapsed",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    _sc_order = [
        ("Maximum",   GREEN,   "Best case: every account accepts the new rate"),
        ("Base Case", PRIMARY, "Realistic: industry-standard retention by phase"),
        ("Downside",  AMBER,   "Conservative: 5 points below base case at every phase"),
    ]
    sc_cols = st.columns(3)
    for _col, (_name, _color, _desc) in zip(sc_cols, _sc_order):
        _d   = sc_data[_name]
        _sel = (_name == _sc_sel)
        _bg  = BG if _sel else WHITE
        _bdr = f"border:2px solid {PRIMARY}" if _sel else "border:2px solid transparent"
        with _col:
            st.markdown(f"""
            <div style="background:{_bg};border-radius:10px;padding:22px;{_bdr};
                        box-shadow:0 1px 6px rgba(0,0,0,.08)">
              <div style="font-size:14px;font-weight:700;color:{GRAY};
                          text-transform:uppercase;letter-spacing:.06em">{_name}</div>
              <div style="font-size:13px;color:{GRAY};margin-bottom:12px">{_desc}</div>
              <div style="font-size:32px;font-weight:800;color:{_color}">{fmt_m(_d['total_uplift'])}</div>
              <div style="font-size:13px;color:{GRAY};margin-bottom:12px">incremental ARR by Month 12</div>
              <div style="font-size:16px;font-weight:700;color:{NAVY}">{fmt_m(_d['new_arr'])}</div>
              <div style="font-size:13px;color:{GRAY};margin-bottom:8px">total ARR at Month 12</div>
              <div style="font-size:14px;font-weight:700;color:{GREEN}">+{fmt_m(_d['vs_inaction'])} vs inaction</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Trajectory chart
    sec("EVERY EXECUTION SCENARIO GROWS ARR — INACTION IS THE ONLY PATH THAT ERODES IT")

    _line_cfg = {
        "Inaction":  dict(color=PURPLE,  dash="dot",   width=2),
        "Downside":  dict(color=AMBER,   dash="solid", width=2),
        "Base Case": dict(color=PRIMARY, dash="solid", width=2),
        "Maximum":   dict(color=GREEN,   dash="solid", width=2),
    }

    fig_traj = go.Figure()
    for _ln_name, _ln_traj in traj.items():
        _is_sel  = (_ln_name == _sc_sel)
        _opacity = 1.0 if (_is_sel or _ln_name == "Inaction") else 0.35
        _width   = 4 if _is_sel else _line_cfg[_ln_name]["width"]
        _cfg     = _line_cfg[_ln_name].copy()
        _cfg["width"] = _width
        fig_traj.add_scatter(
            x=_months, y=_ln_traj,
            name=_ln_name,
            line=_cfg,
            opacity=_opacity,
            mode="lines+markers",
            marker=dict(size=8 if _is_sel else 6),
            text=[fmt_m(v) for v in _ln_traj],
            hovertemplate=f"<b>{_ln_name}</b>  Month %{{x}}: %{{text}}<extra></extra>",
        )

    for _ln_name, _ln_traj in traj.items():
        fig_traj.add_annotation(
            x=12, y=_ln_traj[-1],
            text=f"  {fmt_m(_ln_traj[-1])}",
            showarrow=False, xanchor="left",
            font=dict(size=12, color=_line_cfg[_ln_name]["color"]),
        )

    fig_traj.update_layout(
        height=400, margin=dict(t=20, b=30, l=10, r=110),
        xaxis=dict(title="", tickvals=[0, 3, 6, 12],
                   ticktext=["Now", "Month 3", "Month 6", "Month 12"],
                   tickfont=AX_FONT),
        yaxis=dict(title="ARR ($)", tickformat="$,.0f",
                   title_font=AX_FONT, tickfont=AX_FONT),
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=13)),
        **CHART,
    )
    st.plotly_chart(fig_traj, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Phase tiles
    sec("EXECUTION PHASES — BASE CASE UPLIFT BREAKDOWN")

    _ph_names  = {
        1: "Phase 1 — Lock In Renewals Before They Slip",
        2: "Phase 2 — Reprice Customers Already Billing Without a Contract",
        3: "Phase 3 — Convert and Reprice the Largest Cohort",
    }
    _ph_timing = {1: "Months 1–3", 2: "Months 3–6", 3: "Months 6–12"}
    _ph_colors = {1: GREEN, 2: PRIMARY, 3: AMBER}
    _base_ret  = RET["Base Case"]

    ph_cols = st.columns(3)
    for _ph, _col in zip([1, 2, 3], ph_cols):
        _pi       = _phase_info[_ph]
        _base_inc = _base_ret[_ph] * _pi["max_uplift"]
        _ret_pct  = int(_base_ret[_ph] * 100)
        with _col:
            st.markdown(f"""
            <div class="ph-card" style="border-left:4px solid {_ph_colors[_ph]}">
              <div style="font-size:15px;font-weight:700;color:{NAVY};margin-bottom:4px">{_ph_names[_ph]}</div>
              <div style="font-size:13px;color:{GRAY};margin-bottom:16px">{_ph_timing[_ph]}</div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px 10px">
                <div>
                  <div style="font-size:11px;font-weight:700;color:{GRAY};
                              text-transform:uppercase;letter-spacing:.06em">Customers</div>
                  <div style="font-size:24px;font-weight:800;color:{NAVY}">{_pi['customers']}</div>
                </div>
                <div>
                  <div style="font-size:11px;font-weight:700;color:{GRAY};
                              text-transform:uppercase;letter-spacing:.06em">Current ARR</div>
                  <div style="font-size:24px;font-weight:800;color:{NAVY}">{fmt_m(_pi['current_arr'])}</div>
                </div>
                <div>
                  <div style="font-size:11px;font-weight:700;color:{GRAY};
                              text-transform:uppercase;letter-spacing:.06em">Base Uplift</div>
                  <div style="font-size:24px;font-weight:800;color:{_ph_colors[_ph]}">{fmt_m(_base_inc)}</div>
                </div>
                <div>
                  <div style="font-size:11px;font-weight:700;color:{GRAY};
                              text-transform:uppercase;letter-spacing:.06em">Retention Target</div>
                  <div style="font-size:24px;font-weight:800;color:{NAVY}">{_ret_pct}%</div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)

    # Bottom summary bar
    st.markdown("<br>", unsafe_allow_html=True)
    _sel_d = sc_data[_sc_sel]
    st.markdown(f"""
    <div style="background:{NAVY};border-radius:10px;padding:20px 28px;
                display:flex;align-items:center;justify-content:space-between">
      <div>
        <div style="font-size:13px;font-weight:700;color:rgba(255,255,255,.5);
                    text-transform:uppercase;letter-spacing:.08em">Selected Scenario — {_sc_sel}</div>
        <div style="font-size:28px;font-weight:800;color:{GREEN};margin:6px 0">
          +{fmt_m(_sel_d['total_uplift'])} in incremental ARR — already in the base, waiting to be collected
        </div>
        <div style="font-size:14px;color:rgba(255,255,255,.7)">
          {fmt_m(_sel_d['vs_inaction'])} better than doing nothing
          &nbsp;·&nbsp; Total ARR at Month 12: {fmt_m(_sel_d['new_arr'])}
        </div>
      </div>
      <div style="text-align:right;min-width:200px">
        <div style="font-size:13px;font-weight:700;color:rgba(255,255,255,.5);
                    text-transform:uppercase;letter-spacing:.08em">The Cost of Waiting</div>
        <div style="font-size:28px;font-weight:800;color:{PURPLE}">{fmt_m(baseline_arr - cost_of_inaction)}</div>
        <div style="font-size:13px;color:rgba(255,255,255,.7)">
          ARR at Month 12 if no program launches — actively eroding
        </div>
      </div>
    </div>""", unsafe_allow_html=True)
