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
RED     = "#FF4444"
GRAY    = "#6B7280"

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
  body {{ font-family: sans-serif; }}
  .kpi {{ background:{WHITE}; border-radius:10px; padding:16px 20px;
           box-shadow:0 1px 4px rgba(0,0,0,.07); border-top:3px solid {PRIMARY}; }}
  .kpi.green {{ border-top-color:{GREEN}; }}
  .kpi.amber {{ border-top-color:{AMBER}; }}
  .kpi.red   {{ border-top-color:{RED};   }}
  .kpi.navy  {{ border-top-color:{NAVY};  }}
  .kpi-label {{ font-size:10px; font-weight:700; color:{GRAY}; text-transform:uppercase; letter-spacing:.08em; }}
  .kpi-value {{ font-size:26px; font-weight:800; color:{NAVY}; margin:4px 0 2px; line-height:1.1; }}
  .kpi-sub   {{ font-size:11px; color:{GRAY}; }}
  .kpi-delta {{ font-size:12px; font-weight:700; color:{GREEN}; margin-top:3px; }}
  .sec {{ font-size:12px; font-weight:700; color:{NAVY}; border-bottom:1px solid #dde3f0;
          padding-bottom:5px; margin-bottom:12px; text-transform:uppercase; letter-spacing:.05em; }}
  .tab-h  {{ font-size:22px; font-weight:800; color:{NAVY}; margin-bottom:2px; }}
  .tab-sh {{ font-size:13px; color:{GRAY}; margin-bottom:18px; }}
  .sc-card {{ background:{WHITE}; border-radius:10px; padding:20px;
              box-shadow:0 1px 4px rgba(0,0,0,.07); border:2px solid transparent; }}
  .sc-card.sel {{ border-color:{PRIMARY}; background:{BG}; box-shadow:0 2px 12px rgba(27,63,228,.15); }}
  .ph-card {{ background:{BG}; border-radius:10px; padding:18px; }}
  .note {{ background:{BG}; border-radius:8px; padding:12px 16px;
           border-left:4px solid {PRIMARY}; font-size:13px; color:{NAVY}; margin-top:12px; }}
  .note.red {{ border-left-color:{RED}; }}
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

def pct_fmt(v): return f"{v:.1f}%"

CHART = dict(plot_bgcolor=WHITE, paper_bgcolor=WHITE, font=dict(family="sans-serif", size=12))

# ── Data Loading ──────────────────────────────────────────────────────────────
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
        far  = (g["floor_price"] * g["quantity"]).sum() * 12
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
            "account_ae":       ae_name,
        })

    cust = active.groupby("stripe_customer_id").apply(agg).reset_index()

    # Segment: quantity-weighted avg % of list per customer
    cust["segment"] = cust["pct_of_list"].apply(
        lambda p: "A" if p >= 1.0 else ("B" if p >= 0.9 else ("C" if p >= 0.75 else "D"))
    )

    # Segment-specific max uplift: B→list, C→90% of list, D→floor, A→0
    def target_fn(row):
        s = row["segment"]
        if s == "A": return row["annual_arr"]
        if s == "B": return row["list_annual_arr"]
        if s == "C": return row["list_annual_arr"] * 0.9
        return row["floor_annual_arr"]

    cust["target_annual_arr"] = cust.apply(target_fn, axis=1)
    cust["max_uplift"] = (cust["target_annual_arr"] - cust["annual_arr"]).clip(lower=0)

    # Churn risk (non-locked only): discount depth 30% + contract protection 30% + tenure 20% + increase magnitude 20%
    def churn_risk(row):
        if row["contract_status"] == "Locked": return np.nan
        p, inc, yrs, st_ = (row["pct_of_list"], row["increase_pct"],
                             row["tenure_years"], row["contract_status"])
        dd = 1 if p >= 1.0 else (2 if p >= 0.9 else (3 if p >= 0.75 else (4 if p >= 0.6 else 5)))
        cp = 3 if st_ == "Expired M2M" else 5
        t  = 1 if yrs >= 4 else (2 if yrs >= 3 else (3 if yrs >= 2 else (4 if yrs >= 1 else 5)))
        im = 1 if inc <= 0 else (2 if inc <= 9 else (3 if inc <= 29 else (4 if inc <= 40 else 5)))
        return int(np.clip(round(0.30*dd + 0.30*cp + 0.20*t + 0.20*im), 1, 5))

    cust["churn_risk"] = cust.apply(churn_risk, axis=1)

    # Renewal bucket (locked only) — needed for phase assignment
    def renewal_bucket(row):
        if row["contract_status"] != "Locked" or pd.isna(row["end_date"]): return None
        m = (row["end_date"] - REF_DATE).days / 30.44
        return ("0-3 Months" if m <= 3 else "3-6 Months" if m <= 6 else
                "6-12 Months" if m <= 12 else "12+ Months")

    cust["renewal_bucket"] = cust.apply(renewal_bucket, axis=1)

    # Phase: contract-status based (Phase 1=Locked<=6mo, Phase 2=Expired M2M, Phase 3=No Contract/SF Link)
    def phase_fn(row):
        st_ = row["contract_status"]
        bkt = row["renewal_bucket"]
        if st_ == "Locked":
            return 1 if bkt in ("0-3 Months", "3-6 Months") else np.nan
        if st_ == "Expired M2M":   return 2
        if st_ in ("No Contract", "No SF Link"): return 3
        return np.nan

    cust["phase"] = cust.apply(phase_fn, axis=1)
    return cust


# ── Load data ─────────────────────────────────────────────────────────────────
cust_all  = build_customer_df()
line_all  = build_line_df()
active_all = line_all[line_all["is_active"]].copy()

# ── Pre-compute program-level figures (unfiltered) ────────────────────────────
baseline_arr     = cust_all["annual_arr"].sum()
floor_gap_annual = cust_all["floor_gap_annual"].sum()
seg_a_unlocked   = cust_all[
    (cust_all["segment"] == "A") & (cust_all["contract_status"] != "Locked")
]["annual_arr"].sum()
cost_of_inaction = floor_gap_annual + seg_a_unlocked * 0.05  # floor gap + 5% Seg A uncontracted drift

# Phase data
_phase_info = {}
for _ph in [1, 2, 3]:
    _sub = cust_all[cust_all["phase"] == _ph]
    _phase_info[_ph] = {
        "customers":   len(_sub),
        "current_arr": _sub["annual_arr"].sum(),
        "max_uplift":  _sub["max_uplift"].sum(),
    }

# Retention maps per scenario
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

# Trajectory points [Month 0, 3, 6, 12]
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


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(["  ⚡ The Business  ", "  🔍 The Diagnosis  ", "  📈 The Program  "])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — THE BUSINESS
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="tab-h">The Business</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="tab-sh">Pricing landscape · {len(cust_all)} active customers · {fmt_m(baseline_arr)} total ARR · data through {REF_DATE.strftime("%b %d, %Y")}</div>',
        unsafe_allow_html=True,
    )

    # KPI row
    avg_per_cust  = baseline_arr / len(cust_all) if len(cust_all) > 0 else 0
    below_floor_n = (cust_all["floor_gap_annual"] > 0).sum()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Total ARR", fmt_m(baseline_arr), f"{len(cust_all)} active customers", "navy")
    with c2:
        kpi("Avg ARR per Customer", fmt_m(avg_per_cust), "Across all active customers")
    with c3:
        kpi("Customers Below Floor", str(below_floor_n),
            f"{fmt_m(floor_gap_annual)}/yr under-collected at minimum prices", "amber")
    with c4:
        kpi("Cost of Inaction", fmt_m(cost_of_inaction),
            "Annual revenue at risk if no program launches", "red",
            delta=f"Floor gap {fmt_m(floor_gap_annual)} + Seg A drift {fmt_m(seg_a_unlocked * 0.05)}")

    st.markdown("<br>", unsafe_allow_html=True)

    # Chart 1: Price benchmarks
    sec("PRICE BENCHMARKS BY PRODUCT — ACTUAL MEDIAN VS FLOOR VS LIST")

    _products = ["Hiring", "HR", "Payroll"]
    _medians  = {}
    for _p in _products:
        _lines = active_all[active_all["price_nickname"] == _p]
        _medians[_p] = _lines["unit_price"].median() if len(_lines) > 0 else 0

    _pct_labels = {
        _p: f"{_medians[_p] / LIST_PRICES[_p] * 100:.0f}% of list" for _p in _products
    }

    fig_price = go.Figure()
    fig_price.add_bar(
        name="Floor", x=_products,
        y=[FLOOR_PRICES[p] for p in _products],
        marker_color=RED, opacity=0.65,
        text=[f"${FLOOR_PRICES[p]:.0f}" for p in _products],
        textposition="inside", textfont=dict(color=WHITE, size=11),
    )
    fig_price.add_bar(
        name="Median Actual", x=_products,
        y=[_medians[p] for p in _products],
        marker_color=PRIMARY,
        text=[f"${_medians[p]:.2f} ({_pct_labels[p]})" for p in _products],
        textposition="outside", textfont=dict(size=11),
    )
    fig_price.add_bar(
        name="List Price", x=_products,
        y=[LIST_PRICES[p] for p in _products],
        marker_color=GREEN, opacity=0.65,
        text=[f"${LIST_PRICES[p]:.0f}" for p in _products],
        textposition="inside", textfont=dict(color=WHITE, size=11),
    )
    fig_price.update_layout(
        barmode="group", height=300,
        margin=dict(t=20, b=20, l=10, r=10),
        yaxis=dict(title="Monthly Price per Unit ($)", tickformat="$,.0f"),
        xaxis=dict(title=""),
        legend=dict(orientation="h", y=1.12, x=0),
        **CHART,
    )
    st.plotly_chart(fig_price, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts 2 + 3: Segment bars
    col_l, col_r = st.columns(2)

    with col_l:
        sec("CUSTOMER COUNT BY SEGMENT")
        _seg_counts = cust_all["segment"].value_counts().reindex(["A","B","C","D"], fill_value=0)
        _seg_labels = {
            "A": f"Seg A  ≥100% of list  ({_seg_counts['A']})",
            "B": f"Seg B  90–99%  ({_seg_counts['B']})",
            "C": f"Seg C  75–89%  ({_seg_counts['C']})",
            "D": f"Seg D  <75%    ({_seg_counts['D']})",
        }
        fig_cnt = go.Figure(go.Bar(
            x=_seg_counts.values,
            y=[_seg_labels[s] for s in _seg_counts.index],
            orientation="h",
            marker_color=[SEG_COLORS[s] for s in _seg_counts.index],
            text=[f"{v}" for v in _seg_counts.values],
            textposition="outside",
        ))
        fig_cnt.update_layout(
            height=240, margin=dict(t=10, b=10, l=10, r=50),
            xaxis=dict(title="Customers"),
            yaxis=dict(title="", autorange="reversed"),
            **CHART,
        )
        st.plotly_chart(fig_cnt, use_container_width=True)

    with col_r:
        sec("ARR BY SEGMENT")
        _seg_arr = cust_all.groupby("segment")["annual_arr"].sum().reindex(["A","B","C","D"], fill_value=0)
        fig_arr = go.Figure(go.Bar(
            x=_seg_arr.values,
            y=[_seg_labels[s] for s in _seg_arr.index],
            orientation="h",
            marker_color=[SEG_COLORS[s] for s in _seg_arr.index],
            text=[fmt_m(v) for v in _seg_arr.values],
            textposition="outside",
        ))
        fig_arr.update_layout(
            height=240, margin=dict(t=10, b=10, l=10, r=70),
            xaxis=dict(title="Annual ARR ($)", tickformat="$,.0f"),
            yaxis=dict(title="", autorange="reversed"),
            **CHART,
        )
        st.plotly_chart(fig_arr, use_container_width=True)

    st.markdown(f"""
    <div class="note">
    <b>What this shows:</b> Segment A ({_seg_counts.get('A', 0)} customers, {fmt_m(_seg_arr.get('A', 0))})
    is the largest revenue pool and proves list prices are commercially achievable.
    {below_floor_n} customers billing below Workstream's own floor price represent {fmt_m(floor_gap_annual)}/year
    in under-collection — no customer negotiation required to fix it.
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — THE DIAGNOSIS
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="tab-h">The Diagnosis</div>', unsafe_allow_html=True)
    st.markdown('<div class="tab-sh">What blocks execution of the pricing program?</div>',
                unsafe_allow_html=True)

    # KPIs
    _no_contract_n   = cust_all[cust_all["contract_status"].isin(
        ["Expired M2M", "No Contract", "No SF Link"])].shape[0]
    _no_contract_pct = _no_contract_n / len(cust_all) * 100 if len(cust_all) > 0 else 0
    _no_csm_n        = (~cust_all["has_csm"]).sum()
    _no_csm_pct      = _no_csm_n / len(cust_all) * 100 if len(cust_all) > 0 else 0
    _no_sf_n         = (~cust_all["has_sf"]).sum()

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi("No Current Contract", f"{_no_contract_pct:.0f}%",
            f"{_no_contract_n} of {len(cust_all)} active customers", "amber")
    with c2:
        kpi("No CSM Assigned", f"{_no_csm_pct:.0f}%",
            f"{_no_csm_n} customers with no relationship owner", "red")
    with c3:
        kpi("Invisible to Salesforce", str(_no_sf_n),
            "No Stripe-SFDC link — AE and contract status unknown", "red")

    st.markdown("<br>", unsafe_allow_html=True)

    # Segment filter
    st.markdown(
        f'<div style="font-size:10px;font-weight:700;color:{GRAY};text-transform:uppercase;'
        f'letter-spacing:.08em;margin-bottom:6px">Filter by Segment</div>',
        unsafe_allow_html=True,
    )
    sel_segs = st.multiselect(
        "Segment filter", options=["A", "B", "C", "D"], default=["A", "B", "C", "D"],
        format_func=lambda s: f"Segment {s}  ({'≥100%' if s=='A' else '90-99%' if s=='B' else '75-89%' if s=='C' else '<75%'} of list)",
        label_visibility="collapsed",
    )
    if not sel_segs:
        sel_segs = ["A", "B", "C", "D"]

    cust_f = cust_all[cust_all["segment"].isin(sel_segs)]

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2)

    with col_l:
        sec("CONTRACT STATUS BY SEGMENT")
        if len(cust_f) == 0:
            st.info("No data for selected segments.")
        else:
            fig_cs = go.Figure()
            _status_order = ["Locked", "Expired M2M", "No Contract", "No SF Link"]
            _seg_order    = [s for s in ["A", "B", "C", "D"] if s in sel_segs]
            for _st in _status_order:
                _ys = [cust_f[(cust_f["segment"] == s) & (cust_f["contract_status"] == _st)].shape[0]
                       for s in _seg_order]
                fig_cs.add_bar(
                    name=_st,
                    x=[f"Seg {s}" for s in _seg_order],
                    y=_ys,
                    marker_color=STATUS_COLORS[_st],
                    text=[str(v) if v > 0 else "" for v in _ys],
                    textposition="inside",
                )
            fig_cs.update_layout(
                barmode="stack", height=340,
                margin=dict(t=10, b=30, l=10, r=10),
                yaxis=dict(title="Customers"),
                xaxis=dict(title=""),
                legend=dict(orientation="h", y=1.1, x=0),
                **CHART,
            )
            st.plotly_chart(fig_cs, use_container_width=True)

    with col_r:
        sec("CHURN RISK DISTRIBUTION — NON-LOCKED CUSTOMERS")
        risk_df = cust_f[cust_f["churn_risk"].notna()]
        if len(risk_df) == 0:
            st.info("No risk data for selected segments (all locked, or no segments selected).")
        else:
            _rcounts = (
                risk_df["churn_risk"].astype(int)
                .value_counts().sort_index()
                .reindex([1, 2, 3, 4, 5], fill_value=0)
            )
            _rlabels = {1: "1 – Low", 2: "2 – Low-Med", 3: "3 – Medium",
                        4: "4 – High", 5: "5 – Highest"}
            fig_risk = go.Figure(go.Bar(
                x=[_rlabels[i] for i in _rcounts.index],
                y=_rcounts.values,
                marker_color=[RISK_COLORS[i] for i in _rcounts.index],
                text=_rcounts.values,
                textposition="outside",
            ))
            fig_risk.update_layout(
                height=340, margin=dict(t=10, b=30, l=10, r=10),
                yaxis=dict(title="Customers"),
                xaxis=dict(title=""),
                **CHART,
            )
            st.plotly_chart(fig_risk, use_container_width=True)

    # Insight
    _hr_n       = cust_f[cust_f["churn_risk"] >= 4].shape[0] if len(cust_f) > 0 else 0
    _hr_no_csm  = cust_f[(cust_f["churn_risk"] >= 4) & (~cust_f["has_csm"])].shape[0] if len(cust_f) > 0 else 0
    _hr_no_sf   = cust_f[(cust_f["churn_risk"] >= 4) & (~cust_f["has_sf"])].shape[0] if len(cust_f) > 0 else 0
    if _hr_n > 0:
        st.markdown(f"""
        <div class="note red">
        <b>Gate rule:</b> {_hr_n} customers in selected segments score 4–5 (high/highest risk)
        and require a CSM- or AE-led conversation before any rate notice is sent.
        {_hr_no_csm} of these have no CSM assigned. {_hr_no_sf} have no Salesforce record.
        CSM coverage for all Score 4–5 accounts is a hard pre-launch requirement.
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — THE PROGRAM
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="tab-h">The Program</div>', unsafe_allow_html=True)
    st.markdown('<div class="tab-sh">12-month ARR projection under three execution scenarios — phased by contract status</div>',
                unsafe_allow_html=True)

    # Scenario toggle
    _sc_sel = st.radio(
        "Scenario", ["Base Case", "Maximum", "Downside"],
        horizontal=True, label_visibility="collapsed",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Three scenario tiles
    _sc_order = [
        ("Maximum",   GREEN,   "100% retention — every customer accepts"),
        ("Base Case", PRIMARY, "88 / 85 / 83% retention by phase"),
        ("Downside",  AMBER,   "83 / 80 / 78% retention — 5pts worse"),
    ]
    sc_cols = st.columns(3)
    for _col, (_name, _color, _desc) in zip(sc_cols, _sc_order):
        _d    = sc_data[_name]
        _sel  = (_name == _sc_sel)
        _bg   = BG if _sel else WHITE
        _bdr  = f"border:2px solid {PRIMARY}" if _sel else "border:2px solid transparent"
        with _col:
            st.markdown(f"""
            <div style="background:{_bg};border-radius:10px;padding:20px;{_bdr};
                        box-shadow:0 1px 6px rgba(0,0,0,.08)">
              <div style="font-size:10px;font-weight:700;color:{GRAY};
                          text-transform:uppercase;letter-spacing:.08em">{_name}</div>
              <div style="font-size:11px;color:{GRAY};margin-bottom:10px">{_desc}</div>
              <div style="font-size:28px;font-weight:800;color:{_color}">{fmt_m(_d['total_uplift'])}</div>
              <div style="font-size:11px;color:{GRAY};margin-bottom:10px">12-month incremental ARR</div>
              <div style="font-size:14px;font-weight:700;color:{NAVY}">{fmt_m(_d['new_arr'])}</div>
              <div style="font-size:11px;color:{GRAY};margin-bottom:6px">New ARR at Month 12</div>
              <div style="font-size:13px;font-weight:700;color:{GREEN}">+{fmt_m(_d['vs_inaction'])} vs inaction</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Line chart — 4 ARR trajectories
    sec("ARR TRAJECTORY — INACTION VS THREE EXECUTION SCENARIOS")

    _line_cfg = {
        "Inaction":  dict(color=RED,     dash="dot",   width=2),
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

    # End-point annotations for month-12 values
    for _ln_name, _ln_traj in traj.items():
        fig_traj.add_annotation(
            x=12, y=_ln_traj[-1],
            text=f"  {fmt_m(_ln_traj[-1])}",
            showarrow=False, xanchor="left",
            font=dict(size=11, color=_line_cfg[_ln_name]["color"]),
        )

    fig_traj.update_layout(
        height=380, margin=dict(t=20, b=30, l=10, r=100),
        xaxis=dict(title="", tickvals=[0, 3, 6, 12],
                   ticktext=["Now", "Month 3", "Month 6", "Month 12"]),
        yaxis=dict(title="ARR ($)", tickformat="$,.0f"),
        legend=dict(orientation="h", y=1.08, x=0),
        **CHART,
    )
    st.plotly_chart(fig_traj, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Phase tiles — always base case, as specified
    sec("EXECUTION PHASES — BASE CASE UPLIFT BREAKDOWN")

    _ph_names   = {1: "Phase 1 — Locked Renewals", 2: "Phase 2 — Expired M2M", 3: "Phase 3 — No Contract"}
    _ph_timing  = {1: "Months 1–3", 2: "Months 3–6", 3: "Months 6–12"}
    _ph_colors  = {1: GREEN, 2: PRIMARY, 3: AMBER}
    _base_ret   = RET["Base Case"]

    ph_cols = st.columns(3)
    for _ph, _col in zip([1, 2, 3], ph_cols):
        _pi       = _phase_info[_ph]
        _base_inc = _base_ret[_ph] * _pi["max_uplift"]
        _ret_pct  = int(_base_ret[_ph] * 100)
        with _col:
            st.markdown(f"""
            <div class="ph-card" style="border-left:4px solid {_ph_colors[_ph]}">
              <div style="font-size:10px;font-weight:700;color:{GRAY};
                          text-transform:uppercase;letter-spacing:.08em">{_ph_names[_ph]}</div>
              <div style="font-size:11px;color:{GRAY};margin-bottom:14px">{_ph_timing[_ph]}</div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px 8px">
                <div>
                  <div style="font-size:9px;font-weight:700;color:{GRAY};
                              text-transform:uppercase;letter-spacing:.06em">Customers</div>
                  <div style="font-size:22px;font-weight:800;color:{NAVY}">{_pi['customers']}</div>
                </div>
                <div>
                  <div style="font-size:9px;font-weight:700;color:{GRAY};
                              text-transform:uppercase;letter-spacing:.06em">Current ARR</div>
                  <div style="font-size:22px;font-weight:800;color:{NAVY}">{fmt_m(_pi['current_arr'])}</div>
                </div>
                <div>
                  <div style="font-size:9px;font-weight:700;color:{GRAY};
                              text-transform:uppercase;letter-spacing:.06em">Base Uplift</div>
                  <div style="font-size:22px;font-weight:800;color:{_ph_colors[_ph]}">{fmt_m(_base_inc)}</div>
                </div>
                <div>
                  <div style="font-size:9px;font-weight:700;color:{GRAY};
                              text-transform:uppercase;letter-spacing:.06em">Retention Target</div>
                  <div style="font-size:22px;font-weight:800;color:{NAVY}">{_ret_pct}%</div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)

    # Program vs inaction summary
    st.markdown("<br>", unsafe_allow_html=True)
    _sel_d = sc_data[_sc_sel]
    st.markdown(f"""
    <div style="background:{NAVY};border-radius:10px;padding:18px 24px;
                display:flex;align-items:center;justify-content:space-between">
      <div>
        <div style="font-size:11px;font-weight:700;color:rgba(255,255,255,.5);
                    text-transform:uppercase;letter-spacing:.08em">Selected Scenario — {_sc_sel}</div>
        <div style="font-size:26px;font-weight:800;color:{GREEN};margin:4px 0">
          +{fmt_m(_sel_d['total_uplift'])} incremental ARR</div>
        <div style="font-size:13px;color:rgba(255,255,255,.7)">
          vs inaction: +{fmt_m(_sel_d['vs_inaction'])} &nbsp;|&nbsp;
          New ARR at Month 12: {fmt_m(_sel_d['new_arr'])}</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:11px;font-weight:700;color:rgba(255,255,255,.5);
                    text-transform:uppercase;letter-spacing:.08em">Do Nothing</div>
        <div style="font-size:26px;font-weight:800;color:{RED}">{fmt_m(baseline_arr - cost_of_inaction)}</div>
        <div style="font-size:13px;color:rgba(255,255,255,.7)">ARR at Month 12 (eroding)</div>
      </div>
    </div>""", unsafe_allow_html=True)
