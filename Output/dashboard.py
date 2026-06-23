import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="Workstream Pricing Dashboard", layout="wide", page_icon="💰")

# ── Brand colors ──────────────────────────────────────────────────────────────
PRIMARY = "#1B3FE4"
NAVY    = "#0F1B2D"
BG      = "#EEF2FF"
WHITE   = "#FFFFFF"
YELLOW  = "#FFE600"
GREEN   = "#00B67A"
RED     = "#FF4444"
GRAY    = "#6B7280"

# ── Constants ─────────────────────────────────────────────────────────────────
LIST_PRICES  = {"Hiring": 75.0,  "HR": 100.0, "Payroll": 14.0}
FLOOR_PRICES = {"Hiring": 60.0,  "HR": 80.0,  "Payroll": 11.0}
REF_DATE     = pd.Timestamp("2026-06-20")

STATUS_COLORS = {
    "Locked":      PRIMARY,
    "Expired M2M": YELLOW,
    "No Contract": GRAY,
    "No SF Link":  RED,
}
SEG_COLORS = {"A": GREEN, "B": PRIMARY, "C": YELLOW, "D": RED}

def get_path(filename):
    return os.path.join(os.path.dirname(__file__), "..", "Input", filename)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  .metric-card {{
    background: {WHITE}; border-radius: 10px; padding: 18px 22px;
    box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-bottom: 8px;
  }}
  .metric-label {{ font-size: 13px; color: {GRAY}; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }}
  .metric-value {{ font-size: 28px; font-weight: 700; color: {NAVY}; margin: 4px 0 2px; }}
  .metric-sub   {{ font-size: 13px; color: {GRAY}; }}
  .section-header {{ font-size: 16px; font-weight: 700; color: {NAVY}; margin: 12px 0 6px; }}
</style>
""", unsafe_allow_html=True)

def metric_card(label, value, sub="", color=None):
    color = color or PRIMARY
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-value" style="color:{color}">{value}</div>
      <div class="metric-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

# ── Data Loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_raw():
    sx   = pd.read_csv(get_path("stripeXsfdc.csv"))
    sc   = pd.read_csv(get_path("stripe_customers.csv"))
    ss   = pd.read_csv(get_path("stripe_subscriptions.csv"))
    sfa  = pd.read_csv(get_path("sfdc_accounts.csv"))
    sfc  = pd.read_csv(get_path("sfdc_contracts.csv"))
    return sx, sc, ss, sfa, sfc


@st.cache_data
def build_line_df():
    sx, *_ = load_raw()
    df = sx.copy()

    # Normalise unit price → monthly per unit
    df["unit_price"] = df["unit_amount"] / 100
    df.loc[df["billing_interval"] == "year", "unit_price"] /= 12

    # Activity flag
    df["last_billing_date"] = pd.to_datetime(df["last_billing_date"])
    df["days_since"] = (REF_DATE - df["last_billing_date"]).dt.days
    df["is_active"] = (
        ((df["billing_interval"] == "month") & (df["days_since"] <= 60)) |
        ((df["billing_interval"] == "year") & (df["days_since"] <= 400))
    )

    # List / floor / revenue
    df["list_price"]      = df["price_nickname"].map(LIST_PRICES)
    df["floor_price"]     = df["price_nickname"].map(FLOOR_PRICES)
    df["monthly_rev"]     = df["unit_price"]   * df["quantity"]
    df["list_monthly_rev"]= df["list_price"]   * df["quantity"]
    df["floor_gap_monthly"]= (df["floor_price"] - df["unit_price"]).clip(lower=0) * df["quantity"]
    df["below_floor"]     = df["unit_price"] < df["floor_price"]

    # Flags
    df["end_date"]    = pd.to_datetime(df["end_date"], errors="coerce")
    df["has_sf"]      = df["metadata_salesforce_id"].notna() & (df["metadata_salesforce_id"] != "")
    df["has_contract"]= df["contract_id"].notna() & (df["contract_id"] != "")

    return df


@st.cache_data
def build_customer_df():
    df = build_line_df()
    active = df[df["is_active"]].copy()

    def agg(g):
        monthly_rev  = (g["unit_price"]    * g["quantity"]).sum()
        list_rev     = (g["list_price"]    * g["quantity"]).sum()
        floor_gap_an = g["floor_gap_monthly"].sum() * 12
        pct          = monthly_rev / list_rev if list_rev > 0 else 0
        increase_pct = max(0, (1 / pct - 1) * 100) if pct > 0 else 999

        has_sf       = g["has_sf"].any()
        has_contract = g["has_contract"].any()
        end_date     = g["end_date"].max()
        created      = pd.to_datetime(g["created"].min())
        tenure_years = (REF_DATE - created).days / 365.25

        csm_ser  = g["csm_name__c"].dropna()
        csm_ser  = csm_ser[csm_ser != ""]
        has_csm  = len(csm_ser) > 0
        csm_name = csm_ser.iloc[0] if has_csm else ""

        ae_ser  = g["account_ae"].dropna()
        ae_ser  = ae_ser[ae_ser != ""]
        ae_name = ae_ser.iloc[0] if len(ae_ser) > 0 else "—"

        state = g["billing_state"].dropna()
        state = state[state != ""]
        state_val = state.iloc[0] if len(state) > 0 else ""

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
            "monthly_mrr":    monthly_rev,
            "annual_arr":     monthly_rev * 12,
            "list_annual_arr":list_rev * 12,
            "pct_of_list":    pct,
            "increase_pct":   increase_pct,
            "floor_gap_annual": floor_gap_an,
            "any_below_floor":  g["below_floor"].any(),
            "contract_status":  status,
            "end_date":         end_date,
            "tenure_years":     tenure_years,
            "has_csm":          has_csm,
            "csm_name":         csm_name,
            "account_ae":       ae_name,
            "billing_state":    state_val,
            "has_sf":           has_sf,
            "products":         products,
        })

    cust = active.groupby("stripe_customer_id").apply(agg).reset_index()
    name_map  = active.groupby("stripe_customer_id")["name"].first()
    email_map = active.groupby("stripe_customer_id")["email"].first()
    lbd_map   = active.groupby("stripe_customer_id")["last_billing_date"].max()

    cust["name"]              = cust["stripe_customer_id"].map(name_map)
    cust["email"]             = cust["stripe_customer_id"].map(email_map)
    cust["last_billing_date"] = cust["stripe_customer_id"].map(lbd_map)

    # Segment
    def seg(p):
        if p >= 1.0:  return "A"
        elif p >= 0.9:return "B"
        elif p >= 0.75:return "C"
        else:          return "D"
    cust["segment"] = cust["pct_of_list"].apply(seg)

    # Churn risk (non-locked only)
    def churn_risk(row):
        if row["contract_status"] == "Locked":
            return np.nan

        p   = row["pct_of_list"]
        inc = row["increase_pct"]
        yrs = row["tenure_years"]
        st_ = row["contract_status"]

        if p >= 1.0:  dd = 1
        elif p >= 0.9:dd = 2
        elif p >= 0.75:dd = 3
        elif p >= 0.6: dd = 4
        else:          dd = 5

        if st_ == "Expired M2M": cp = 3
        else:                     cp = 5

        if yrs >= 4:  t = 1
        elif yrs >= 3:t = 2
        elif yrs >= 2:t = 3
        elif yrs >= 1:t = 4
        else:         t = 5

        if inc <= 0:   im = 1
        elif inc <= 9: im = 2
        elif inc <= 29:im = 3
        elif inc <= 40:im = 4
        else:          im = 5

        raw = 0.30*dd + 0.30*cp + 0.20*t + 0.20*im
        return int(np.clip(round(raw), 1, 5))

    def primary_risk(row):
        if row["contract_status"] == "Locked" or pd.isna(row["churn_risk"]):
            return ""
        p   = row["pct_of_list"]
        inc = row["increase_pct"]
        yrs = row["tenure_years"]
        st_ = row["contract_status"]

        if p >= 1.0:  dd = 1
        elif p >= 0.9:dd = 2
        elif p >= 0.75:dd = 3
        elif p >= 0.6: dd = 4
        else:          dd = 5

        if st_ == "Expired M2M": cp = 3
        else:                     cp = 5

        if yrs >= 4:  t = 1
        elif yrs >= 3:t = 2
        elif yrs >= 2:t = 3
        elif yrs >= 1:t = 4
        else:         t = 5

        if inc <= 0:   im = 1
        elif inc <= 9: im = 2
        elif inc <= 29:im = 3
        elif inc <= 40:im = 4
        else:          im = 5

        scores = {"Discount depth": 0.30*dd, "Contract risk": 0.30*cp,
                  "Short tenure": 0.20*t, "Price increase needed": 0.20*im}
        return max(scores, key=scores.get)

    cust["churn_risk"]    = cust.apply(churn_risk, axis=1)
    cust["primary_risk"]  = cust.apply(primary_risk, axis=1)

    # Phase assignment for non-locked
    def phase(row):
        if pd.isna(row["churn_risk"]): return np.nan
        s = row["churn_risk"]
        if s <= 2: return 1
        elif s == 3: return 2
        else: return 3
    cust["phase"] = cust.apply(phase, axis=1)

    return cust


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"<div style='font-size:22px;font-weight:800;color:{PRIMARY};letter-spacing:-.02em;'>Workstream</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:11px;color:{GRAY};margin-top:-4px;margin-bottom:12px;'>Data source: Stripe + Salesforce</div>", unsafe_allow_html=True)
    st.divider()

    cust_all = build_customer_df()

    seg_filter = st.selectbox("Segment", ["All", "A", "B", "C", "D"])
    status_filter = st.selectbox("Contract Status",
        ["All", "Locked", "Expired M2M", "No Contract", "No SF Link"])
    ae_options = ["All"] + sorted(cust_all["account_ae"].dropna().unique().tolist())
    ae_filter = st.selectbox("AE Name", ae_options)

    st.divider()
    st.markdown("**Revenue Impact Phases**")
    ph1_ret = st.slider("Phase 1 Retention %", 50, 100, 88, format="%d%%") / 100
    ph2_ret = st.slider("Phase 2 Retention %", 50, 100, 85, format="%d%%") / 100
    ph3_ret = st.slider("Phase 3 Retention %", 50, 100, 83, format="%d%%") / 100

# ── Apply filters ─────────────────────────────────────────────────────────────
def apply_filters(df):
    d = df.copy()
    if seg_filter != "All":
        d = d[d["segment"] == seg_filter]
    if status_filter != "All":
        d = d[d["contract_status"] == status_filter]
    if ae_filter != "All":
        d = d[d["account_ae"] == ae_filter]
    return d

cust = apply_filters(cust_all)

# ── Helper: download button ───────────────────────────────────────────────────
def download_btn(df, label="Download CSV", filename="export.csv"):
    st.download_button(label, df.to_csv(index=False).encode(), filename, "text/csv")

# ── Searchable table helper ───────────────────────────────────────────────────
def searchable_table(df, key, height=400):
    q = st.text_input("🔍 Search", key=f"search_{key}", placeholder="Type to filter…")
    if q:
        mask = df.astype(str).apply(lambda col: col.str.contains(q, case=False, na=False)).any(axis=1)
        df = df[mask]
    st.dataframe(df, use_container_width=True, height=height)
    return df

# ═══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Data Overview",
    "📋 Contract Status",
    "👥 Customers & Segmentation",
    "💲 Pricing Analysis",
    "⚠️ Churn Risk",
    "📈 Revenue Impact",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Data Overview
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    _, sc, ss, sfa, sfc = load_raw()
    df_line = build_line_df()

    total_stripe   = df_line["stripe_customer_id"].nunique()
    active_custs   = df_line[df_line["is_active"]]["stripe_customer_id"].nunique()
    sf_linked_all  = df_line[df_line["has_sf"]]["stripe_customer_id"].nunique()
    no_sf_all      = total_stripe - sf_linked_all

    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Total Stripe Customers", f"{total_stripe:,}", color=NAVY)
    with c2: metric_card("Active Customers", f"{active_custs:,}", sub="Last billed ≤60d (monthly) / ≤400d (annual)", color=GREEN)
    with c3: metric_card("Linked to Salesforce", f"{sf_linked_all:,}", sub=f"{sf_linked_all/total_stripe*100:.1f}% of total", color=PRIMARY)
    with c4: metric_card("No SF Link", f"{no_sf_all:,}", sub=f"{no_sf_all/total_stripe*100:.1f}% of total", color=RED)

    st.divider()
    st.markdown(f'<div class="section-header">Source File Summary</div>', unsafe_allow_html=True)
    src_tbl = pd.DataFrame({
        "Source":    ["stripe_customers.csv", "stripe_subscriptions.csv", "sfdc_accounts.csv", "sfdc_contracts.csv"],
        "Records":   [len(sc), len(ss), len(sfa), len(sfc)],
        "Key Field": ["stripe_customer_id", "subscription_item_id", "account_id", "contract_id"],
    })
    st.dataframe(src_tbl, use_container_width=True, hide_index=True, height=178)

    st.info(
        "**How the join works:** Each Stripe customer is matched to a Salesforce account via "
        "the `metadata_salesforce_id` field on the customer record. Salesforce contracts are then "
        "joined to accounts via `account_id`, bringing contract dates and ACV into a single row "
        "for every subscription line item."
    )

    st.divider()
    st.markdown(f'<div class="section-header">Subscription Lines by Product (Active)</div>', unsafe_allow_html=True)
    active_lines = df_line[df_line["is_active"]]
    prod_stats = (
        active_lines.groupby("price_nickname")
        .agg(line_count=("subscription_item_id","count"), arr=("monthly_rev", lambda x: x.sum()*12))
        .reindex(["Hiring","HR","Payroll"]).reset_index()
    )
    fig_prod = go.Figure()
    fig_prod.add_bar(x=prod_stats["price_nickname"], y=prod_stats["line_count"],
                     name="Line Count", marker_color=PRIMARY)
    fig_prod.add_bar(x=prod_stats["price_nickname"], y=prod_stats["arr"]/1000,
                     name="ARR ($K)", marker_color=GREEN, yaxis="y2")
    fig_prod.update_layout(
        barmode="group", height=320, margin=dict(t=20,b=20,l=20,r=20),
        yaxis=dict(title="Line Count", color=NAVY),
        yaxis2=dict(title="ARR ($K)", overlaying="y", side="right", color=GREEN),
        legend=dict(orientation="h", y=1.08),
        plot_bgcolor=BG, paper_bgcolor="white",
    )
    st.plotly_chart(fig_prod, use_container_width=True)

    with st.expander(f"🔗 {no_sf_all} Customers with No Salesforce Link"):
        no_sf_mask = df_line["has_sf"] == False
        no_sf_custs = (
            df_line[no_sf_mask]
            .groupby("stripe_customer_id")
            .agg(
                name=("name","first"),
                email=("email","first"),
                last_billing_date=("last_billing_date","max"),
                monthly_mrr=("monthly_rev","sum"),
            ).reset_index()
            .rename(columns={"stripe_customer_id":"Stripe ID","name":"Name","email":"Email",
                              "last_billing_date":"Last Billing","monthly_mrr":"Monthly MRR"})
        )
        no_sf_custs["Monthly MRR"] = no_sf_custs["Monthly MRR"].map("${:,.2f}".format)
        no_sf_disp = searchable_table(no_sf_custs, "no_sf")
        download_btn(no_sf_custs, "Download No-SF Customers", "no_sf_customers.csv")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Contract Status
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    locked  = cust[cust["contract_status"] == "Locked"]
    expired = cust[cust["contract_status"] == "Expired M2M"]
    no_cont = cust[cust["contract_status"].isin(["No Contract","No SF Link"])]
    no_sf   = cust[cust["contract_status"] == "No SF Link"]

    c1,c2,c3,c4 = st.columns(4)
    with c1: metric_card("Locked", f"{len(locked):,}", f"${locked['annual_arr'].sum():,.0f} ARR", color=PRIMARY)
    with c2: metric_card("Expired M2M", f"{len(expired):,}", f"${expired['annual_arr'].sum():,.0f} ARR", color=YELLOW)
    with c3: metric_card("No Contract", f"{len(no_cont):,}", f"${no_cont['annual_arr'].sum():,.0f} ARR", color=GRAY)
    with c4: metric_card("No SF Link", f"{len(no_sf):,}", f"${no_sf['annual_arr'].sum():,.0f} ARR", color=RED)

    st.divider()
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown(f'<div class="section-header">Contract Status by Segment</div>', unsafe_allow_html=True)
        stacked = (
            cust.groupby(["segment","contract_status"])["stripe_customer_id"]
            .count().reset_index(name="count")
        )
        statuses = ["Locked","Expired M2M","No Contract","No SF Link"]
        fig_stacked = go.Figure()
        for st_ in statuses:
            sub = stacked[stacked["contract_status"] == st_]
            fig_stacked.add_bar(
                y=sub["segment"], x=sub["count"], orientation="h",
                name=st_, marker_color=STATUS_COLORS.get(st_, GRAY)
            )
        fig_stacked.update_layout(
            barmode="stack", height=300, margin=dict(t=20,b=20,l=20,r=20),
            legend=dict(orientation="h", y=1.08),
            plot_bgcolor=BG, paper_bgcolor="white",
            xaxis_title="Customers", yaxis_title="Segment",
        )
        st.plotly_chart(fig_stacked, use_container_width=True)

    with col_r:
        st.markdown(f'<div class="section-header">Customers by Contract Status</div>', unsafe_allow_html=True)
        donut_data = cust.groupby("contract_status")["stripe_customer_id"].count().reset_index()
        fig_donut = go.Figure(go.Pie(
            labels=donut_data["contract_status"],
            values=donut_data["stripe_customer_id"],
            hole=0.55,
            marker_colors=[STATUS_COLORS.get(s, GRAY) for s in donut_data["contract_status"]],
        ))
        fig_donut.update_layout(
            height=300, margin=dict(t=20,b=20,l=20,r=20),
            legend=dict(orientation="h", y=-0.1),
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    st.divider()
    st.markdown(f'<div class="section-header">Locked Renewal Pipeline</div>', unsafe_allow_html=True)
    now = REF_DATE
    def months_to_expiry(d):
        if pd.isna(d): return np.nan
        return (d - now).days / 30.44

    locked2 = locked.copy()
    locked2["months_left"] = locked2["end_date"].apply(months_to_expiry)

    def bucket(m):
        if pd.isna(m):  return "12+mo"
        if m <= 3:       return "≤3mo"
        elif m <= 6:     return "3-6mo"
        elif m <= 12:    return "6-12mo"
        else:            return "12+mo"

    locked2["bucket"] = locked2["months_left"].apply(bucket)
    pipeline = (
        locked2.groupby("bucket")
        .agg(customers=("stripe_customer_id","count"), arr=("annual_arr","sum"))
        .reindex(["≤3mo","3-6mo","6-12mo","12+mo"]).reset_index()
        .rename(columns={"bucket":"Renewal Window","customers":"Customers","arr":"Annual ARR"})
    )
    pipeline["Annual ARR"] = pipeline["Annual ARR"].map("${:,.0f}".format)
    st.dataframe(pipeline, use_container_width=True, hide_index=True, height=178)

    st.divider()
    st.markdown(f'<div class="section-header">All Customers</div>', unsafe_allow_html=True)
    disp = cust[["name","account_ae","segment","contract_status","end_date","monthly_mrr","annual_arr"]].copy()
    disp.columns = ["Name","AE","Segment","Contract Status","Contract End","Monthly MRR","Annual ARR"]
    disp["Monthly MRR"] = disp["Monthly MRR"].map("${:,.2f}".format)
    disp["Annual ARR"]  = disp["Annual ARR"].map("${:,.0f}".format)
    disp["Contract End"]= disp["Contract End"].dt.strftime("%Y-%m-%d").fillna("—")
    _ = searchable_table(disp, "contracts")
    download_btn(disp, "Download Contract Data", "contract_status.csv")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Customers & Segmentation
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    total_active   = len(cust_all)   # unfiltered active
    # Churned = all customers that were ever in stripe but not active
    df_line_all = build_line_df()
    all_cust_ids    = df_line_all["stripe_customer_id"].nunique()
    active_cust_ids = df_line_all[df_line_all["is_active"]]["stripe_customer_id"].nunique()
    churned_count   = all_cust_ids - active_cust_ids

    c1, c2 = st.columns(2)
    with c1:
        metric_card("Active Customers", f"{active_cust_ids:,}",
                    f"{active_cust_ids/all_cust_ids*100:.1f}% of total", color=GREEN)
    with c2:
        metric_card("Churned / Inactive", f"{churned_count:,}",
                    f"{churned_count/all_cust_ids*100:.1f}% of total", color=RED)

    st.info(
        "**Segments:** A = ≥100% of list price · B = 90-99% · C = 75-89% · D = <75%  "
        "Weighted avg % of list = Σ(unit_price × qty) / Σ(list_price × qty) per customer."
    )

    seg_stats = (
        cust.groupby("segment")
        .agg(
            count=("stripe_customer_id","count"),
            arr=("annual_arr","sum"),
            avg_pct=("pct_of_list","mean"),
            non_locked=("contract_status", lambda x: (x != "Locked").sum()),
        ).reindex(["A","B","C","D"]).reset_index()
    )
    cols = st.columns(4)
    for i, row in seg_stats.iterrows():
        if pd.isna(row["count"]): continue
        with cols[i]:
            metric_card(
                f"Segment {row['segment']}",
                f"{int(row['count']):,} customers",
                f"${row['arr']:,.0f} ARR · {row['avg_pct']*100:.1f}% of list · {int(row['non_locked'])} non-locked",
                color=SEG_COLORS.get(row["segment"], GRAY),
            )

    st.divider()
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown(f'<div class="section-header">Customers & ARR by Segment</div>', unsafe_allow_html=True)
        fig_seg = go.Figure()
        fig_seg.add_bar(x=seg_stats["segment"], y=seg_stats["count"],
                        name="Customers", marker_color=[SEG_COLORS.get(s, GRAY) for s in seg_stats["segment"]])
        fig_seg.add_bar(x=seg_stats["segment"], y=seg_stats["arr"]/1000,
                        name="ARR ($K)", marker_color=NAVY, yaxis="y2")
        fig_seg.update_layout(
            barmode="group", height=320, margin=dict(t=20,b=20,l=20,r=20),
            yaxis=dict(title="Customers"),
            yaxis2=dict(title="ARR ($K)", overlaying="y", side="right", color=NAVY),
            legend=dict(orientation="h", y=1.08),
            plot_bgcolor=BG, paper_bgcolor="white",
        )
        st.plotly_chart(fig_seg, use_container_width=True)

    with col_r:
        st.markdown(f'<div class="section-header">MRR vs % of List (by Segment)</div>', unsafe_allow_html=True)
        fig_scatter = px.scatter(
            cust, x="monthly_mrr", y=cust["pct_of_list"]*100,
            color="segment",
            color_discrete_map=SEG_COLORS,
            hover_data={"name":True,"account_ae":True,"segment":True,"monthly_mrr":":.2f"},
            labels={"monthly_mrr":"Monthly MRR ($)","y":"% of List Price","segment":"Segment"},
            height=320,
        )
        fig_scatter.update_layout(
            margin=dict(t=20,b=20,l=20,r=20), plot_bgcolor=BG, paper_bgcolor="white"
        )
        fig_scatter.update_traces(marker_size=7)
        st.plotly_chart(fig_scatter, use_container_width=True)

    st.divider()
    st.markdown(f'<div class="section-header">Customer Detail</div>', unsafe_allow_html=True)
    disp3 = cust[["name","account_ae","csm_name","segment","products","pct_of_list",
                   "monthly_mrr","annual_arr","contract_status","churn_risk"]].copy()
    disp3.columns = ["Name","AE","CSM","Segment","Products","% of List",
                     "Monthly MRR","Annual ARR","Contract Status","Churn Risk"]
    disp3["% of List"]    = (disp3["% of List"]*100).map("{:.1f}%".format)
    disp3["Monthly MRR"]  = disp3["Monthly MRR"].map("${:,.2f}".format)
    disp3["Annual ARR"]   = disp3["Annual ARR"].map("${:,.0f}".format)
    disp3["Churn Risk"]   = disp3["Churn Risk"].apply(lambda x: f"{int(x)}" if pd.notna(x) else "—")
    _ = searchable_table(disp3, "segmentation", height=450)
    download_btn(disp3, "Download Customer Detail", "customers.csv")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — Pricing Analysis
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    df_line_a = build_line_df()
    df_line_a = df_line_a[df_line_a["is_active"]]

    # Filter line-level by active customer IDs after sidebar filter
    active_ids = set(cust["stripe_customer_id"].tolist())
    lines_f = df_line_a[df_line_a["stripe_customer_id"].isin(active_ids)]

    c1, c2, c3 = st.columns(3)
    for col, prod in zip([c1,c2,c3], ["Hiring","HR","Payroll"]):
        prod_lines = lines_f[lines_f["price_nickname"] == prod]
        med = prod_lines["unit_price"].median()
        pct = med / LIST_PRICES[prod] * 100
        with col:
            metric_card(f"{prod} Median Price", f"${med:.2f}",
                        f"{pct:.1f}% of list (${LIST_PRICES[prod]:.0f})", color=PRIMARY)

    st.divider()
    col_l, col_r = st.columns([3,2])

    with col_l:
        st.markdown(f'<div class="section-header">Distribution: % of List Price (Active Customers)</div>', unsafe_allow_html=True)
        pct_vals = cust["pct_of_list"].dropna() * 100
        fig_hist = go.Figure()
        # Colour zones
        x_range = np.linspace(pct_vals.min()*0.98, pct_vals.max()*1.02, 300)
        bins = np.histogram(pct_vals, bins=40)
        bin_centers = (bins[1][:-1] + bins[1][1:]) / 2
        bin_counts  = bins[0]
        colors_hist = []
        for bc in bin_centers:
            if bc < 80:   colors_hist.append(RED)
            elif bc < 100:colors_hist.append(YELLOW)
            else:         colors_hist.append(GREEN)

        fig_hist.add_bar(x=bin_centers, y=bin_counts, marker_color=colors_hist, showlegend=False)
        for x_val, label, lcolor in [
            (80, "Floor ≈80%", RED),
            (100, "List = 100%", GREEN),
        ]:
            fig_hist.add_vline(x=x_val, line_dash="dash", line_color=lcolor,
                               annotation_text=label, annotation_font_color=lcolor)
        fig_hist.update_layout(
            height=320, margin=dict(t=20,b=20,l=20,r=20),
            xaxis_title="% of List Price", yaxis_title="Customers",
            plot_bgcolor=BG, paper_bgcolor="white",
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_r:
        st.markdown(f'<div class="section-header">Pricing Summary by Product</div>', unsafe_allow_html=True)
        for prod in ["Hiring","HR","Payroll"]:
            prod_lines = lines_f[lines_f["price_nickname"] == prod]
            avg_price   = prod_lines["unit_price"].mean()
            pct_below_fl= (prod_lines["unit_price"] < FLOOR_PRICES[prod]).mean() * 100
            pct_at_list = (prod_lines["unit_price"] >= LIST_PRICES[prod]).mean() * 100
            pct_above_l = (prod_lines["unit_price"] > LIST_PRICES[prod]).mean() * 100
            st.markdown(f"**{prod}** — avg ${avg_price:.2f}/unit")
            st.markdown(
                f"Below floor: `{pct_below_fl:.1f}%` · "
                f"At list: `{pct_at_list:.1f}%` · "
                f"Above list: `{pct_above_l:.1f}%`"
            )
            st.divider()

    st.divider()
    floor_total   = cust["floor_gap_annual"].sum()
    floor_by_prod = (
        lines_f[lines_f["below_floor"]]
        .groupby("price_nickname")
        .agg(gap=("floor_gap_monthly", lambda x: x.sum()*12))
        .reindex(["Hiring","HR","Payroll"])
    )

    st.markdown(f'<div class="section-header">Below-Floor Pricing Impact</div>', unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    with c1: metric_card("Total Annual Floor Gap", f"${floor_total:,.0f}", color=RED)
    for col, prod in zip([c2,c3,c4], ["Hiring","HR","Payroll"]):
        gap = floor_by_prod.loc[prod, "gap"] if prod in floor_by_prod.index else 0
        with col: metric_card(f"{prod} Floor Gap", f"${gap:,.0f}", color=YELLOW)

    # Below-floor customer table (line-level)
    bf_lines = lines_f[lines_f["below_floor"]].copy()
    bf_lines["gap_per_unit"]  = bf_lines["floor_price"] - bf_lines["unit_price"]
    bf_lines["annual_gap"]    = bf_lines["gap_per_unit"] * bf_lines["quantity"] * 12
    bf_lines["name"]          = bf_lines["stripe_customer_id"].map(
        build_line_df()[build_line_df()["is_active"]].groupby("stripe_customer_id")["name"].first()
    )
    ae_map = cust.set_index("stripe_customer_id")["account_ae"]
    bf_lines["ae"] = bf_lines["stripe_customer_id"].map(ae_map)
    disp4 = bf_lines[["name","ae","price_nickname","unit_price","floor_price","gap_per_unit","annual_gap"]].copy()
    disp4.columns = ["Name","AE","Product","Current Price","Floor Price","Gap/Unit","Annual Gap"]
    disp4["Current Price"]= disp4["Current Price"].map("${:.2f}".format)
    disp4["Floor Price"]  = disp4["Floor Price"].map("${:.2f}".format)
    disp4["Gap/Unit"]     = disp4["Gap/Unit"].map("${:.2f}".format)
    disp4["Annual Gap"]   = disp4["Annual Gap"].map("${:,.0f}".format)
    st.markdown(f'<div class="section-header">Below-Floor Customers</div>', unsafe_allow_html=True)
    _ = searchable_table(disp4, "below_floor", height=380)
    download_btn(disp4, "Download Below-Floor Data", "below_floor.csv")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — Churn Risk
# ─────────────────────────────────────────────────────────────────────────────
with tab5:
    scored = cust[cust["churn_risk"].notna()].copy()
    scored["churn_risk"] = scored["churn_risk"].astype(int)

    eligible    = len(scored)
    high_risk   = scored[scored["churn_risk"] >= 4]
    med_risk    = scored[scored["churn_risk"] == 3]
    no_csm_high = high_risk[~high_risk["has_csm"]]

    c1,c2,c3,c4 = st.columns(4)
    with c1: metric_card("Eligible Scored", f"{eligible:,}", "Non-locked active", color=NAVY)
    with c2: metric_card("High Risk (4+5)", f"{len(high_risk):,}",
                         f"{len(high_risk)/eligible*100:.1f}% of eligible", color=RED)
    with c3: metric_card("No CSM (High Risk)", f"{len(no_csm_high):,}",
                         f"{len(no_csm_high)/len(high_risk)*100:.1f}% of high risk", color=YELLOW)
    with c4: metric_card("Medium Risk (3)", f"{len(med_risk):,}",
                         f"{len(med_risk)/eligible*100:.1f}% of eligible", color=GRAY)

    st.divider()
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown(f'<div class="section-header">Customers by Churn Risk Score</div>', unsafe_allow_html=True)
        score_counts = scored.groupby("churn_risk")["stripe_customer_id"].count().reset_index()
        score_colors = {1:GREEN, 2:"#7BC47F", 3:YELLOW, 4:"#FF8C42", 5:RED}
        fig_bar_risk = go.Figure(go.Bar(
            x=score_counts["churn_risk"].astype(str),
            y=score_counts["stripe_customer_id"],
            marker_color=[score_colors.get(s, GRAY) for s in score_counts["churn_risk"]],
        ))
        fig_bar_risk.update_layout(
            height=300, margin=dict(t=20,b=20,l=20,r=20),
            xaxis_title="Churn Risk Score", yaxis_title="Customers",
            plot_bgcolor=BG, paper_bgcolor="white",
        )
        st.plotly_chart(fig_bar_risk, use_container_width=True)

    with col_r:
        st.markdown(f'<div class="section-header">MRR vs Churn Risk (by Segment)</div>', unsafe_allow_html=True)
        fig_s2 = px.scatter(
            scored, x="monthly_mrr", y="churn_risk",
            color="segment", color_discrete_map=SEG_COLORS,
            hover_data={"name":True,"account_ae":True,"churn_risk":True},
            labels={"monthly_mrr":"Monthly MRR ($)","churn_risk":"Churn Risk Score","segment":"Segment"},
            height=300,
        )
        fig_s2.update_layout(
            margin=dict(t=20,b=20,l=20,r=20), plot_bgcolor=BG, paper_bgcolor="white"
        )
        fig_s2.update_traces(marker_size=7)
        st.plotly_chart(fig_s2, use_container_width=True)

    st.divider()
    st.markdown(f'<div class="section-header">High Risk Customers (Score 4+5)</div>', unsafe_allow_html=True)
    disp5 = high_risk[["name","account_ae","csm_name","segment","monthly_mrr",
                        "churn_risk","primary_risk"]].copy()
    disp5.columns = ["Name","AE","CSM","Segment","Monthly MRR","Score","Primary Risk Factor"]
    disp5["Monthly MRR"] = disp5["Monthly MRR"].map("${:,.2f}".format)
    disp5 = disp5.sort_values("Score", ascending=False)
    _ = searchable_table(disp5, "high_risk", height=380)
    download_btn(disp5, "Download High Risk Customers", "high_risk.csv")

    st.divider()
    st.markdown(f'<div class="section-header">Locked Renewal Pipeline</div>', unsafe_allow_html=True)
    locked_t5 = cust[cust["contract_status"] == "Locked"].copy()
    locked_t5["months_left"] = locked_t5["end_date"].apply(
        lambda d: (d - REF_DATE).days / 30.44 if pd.notna(d) else np.nan
    )
    def bucket5(m):
        if pd.isna(m):  return "12+mo"
        if m <= 3:       return "≤3mo"
        elif m <= 6:     return "3-6mo"
        elif m <= 12:    return "6-12mo"
        else:            return "12+mo"
    locked_t5["bucket"] = locked_t5["months_left"].apply(bucket5)
    pipeline5 = (
        locked_t5.groupby("bucket")
        .agg(customers=("stripe_customer_id","count"), arr=("annual_arr","sum"))
        .reindex(["≤3mo","3-6mo","6-12mo","12+mo"]).reset_index()
        .rename(columns={"bucket":"Renewal Window","customers":"Customers","arr":"Annual ARR"})
    )
    pipeline5["Annual ARR"] = pipeline5["Annual ARR"].map("${:,.0f}".format)
    st.dataframe(pipeline5, use_container_width=True, hide_index=True, height=178)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 6 — Revenue Impact
# ─────────────────────────────────────────────────────────────────────────────
with tab6:
    # Phases: 1=low risk (score 1+2), 2=medium (score 3), 3=high (score 4+5)
    ph_ret = {1: ph1_ret, 2: ph2_ret, 3: ph3_ret}

    scored6 = cust[cust["phase"].notna()].copy()
    scored6["phase"] = scored6["phase"].astype(int)

    locked_arr = cust[cust["contract_status"] == "Locked"]["annual_arr"].sum()

    # Partial-capture model: all customers stay, but we close retention% of the pricing gap.
    # Scenario uplift = retention × max_uplift (no churn assumed).
    def phase_scenario(phase_num, ret_rate):
        ph_custs = scored6[scored6["phase"] == phase_num]
        below    = ph_custs[ph_custs["pct_of_list"] < 1.0]
        current_arr  = ph_custs["annual_arr"].sum()
        max_uplift   = max(0, below["list_annual_arr"].sum() - below["annual_arr"].sum())
        scenario_uplift = ret_rate * max_uplift
        return {
            "customers":      len(ph_custs),
            "current_arr":    current_arr,
            "max_uplift":     max_uplift,
            "scenario_uplift": scenario_uplift,
        }

    ph_results = {i: phase_scenario(i, ph_ret[i]) for i in [1,2,3]}

    baseline_arr  = cust["annual_arr"].sum()
    projected_arr = (
        locked_arr
        + sum(ph_results[i]["current_arr"] + ph_results[i]["scenario_uplift"]
              for i in [1,2,3])
    )
    incremental   = projected_arr - baseline_arr
    pct_uplift    = incremental / baseline_arr * 100 if baseline_arr > 0 else 0

    c1,c2,c3,c4 = st.columns(4)
    with c1: metric_card("Baseline ARR",   f"${baseline_arr:,.0f}",  color=NAVY)
    with c2: metric_card("Projected ARR",  f"${projected_arr:,.0f}", color=PRIMARY)
    with c3: metric_card("Incremental ARR",f"${incremental:,.0f}",   color=GREEN if incremental >= 0 else RED)
    with c4: metric_card("% Uplift",       f"{pct_uplift:.1f}%",     color=PRIMARY)

    st.divider()

    # Phase table
    st.markdown(f'<div class="section-header">Phase Summary (Live)</div>', unsafe_allow_html=True)
    ph_tbl = pd.DataFrame([
        {"Phase": f"Phase {i}", "Customers": ph_results[i]["customers"],
         "Current ARR": f"${ph_results[i]['current_arr']:,.0f}",
         "Max Uplift":  f"${ph_results[i]['max_uplift']:,.0f}",
         "Scenario Uplift": f"${ph_results[i]['scenario_uplift']:,.0f}"}
        for i in [1,2,3]
    ])
    st.dataframe(ph_tbl, use_container_width=True, hide_index=True, height=142)

    st.divider()

    # ARR trajectory line chart
    st.markdown(f'<div class="section-header">ARR Trajectory (Months 0 → 12)</div>', unsafe_allow_html=True)
    months = [0, 3, 6, 12]

    # Baseline: flat
    baseline_line = [baseline_arr] * 4

    # Scenario: accumulate phase impacts at M3, M6, M12
    def scenario_line(rets):
        arr0 = baseline_arr
        # M3: phase 1 impact
        ph1 = phase_scenario(1, rets[1])
        arr3 = arr0 + ph1["scenario_uplift"]
        ph2 = phase_scenario(2, rets[2])
        arr6 = arr3 + ph2["scenario_uplift"]
        ph3 = phase_scenario(3, rets[3])
        arr12= arr6 + ph3["scenario_uplift"]
        return [arr0, arr3, arr6, arr12]

    scen_line  = scenario_line(ph_ret)
    down_ret   = {i: max(0.0, ph_ret[i] - 0.05) for i in [1,2,3]}
    down_line  = scenario_line(down_ret)

    fig_arr = go.Figure()
    fig_arr.add_scatter(x=months, y=baseline_line, name="Baseline",
                        line=dict(color=GRAY, dash="dash"), mode="lines+markers")
    fig_arr.add_scatter(x=months, y=scen_line, name="Scenario",
                        line=dict(color=PRIMARY, width=3), mode="lines+markers")
    fig_arr.add_scatter(x=months, y=down_line, name="Downside (-5pp)",
                        line=dict(color=YELLOW, dash="dot"), mode="lines+markers")
    fig_arr.update_layout(
        height=350, margin=dict(t=20,b=20,l=20,r=20),
        xaxis=dict(title="Month", tickvals=[0,3,6,12]),
        yaxis=dict(title="Annual ARR ($)", tickformat="$,.0f"),
        legend=dict(orientation="h", y=1.08),
        plot_bgcolor=BG, paper_bgcolor="white",
    )
    st.plotly_chart(fig_arr, use_container_width=True)

    st.divider()

    # Cost of inaction
    st.markdown(f'<div class="section-header">Cost of Inaction</div>', unsafe_allow_html=True)
    # Rate erosion = discount gap from list for Expired M2M customers
    m2m_custs     = cust[cust["contract_status"] == "Expired M2M"]
    rate_erosion  = (m2m_custs["list_annual_arr"] - m2m_custs["annual_arr"]).clip(lower=0).sum()
    floor_gap_tot = cust["floor_gap_annual"].sum()
    inaction_total= rate_erosion + floor_gap_tot

    c1, c2, c3 = st.columns(3)
    with c1: metric_card("Rate Erosion (M2M Gap)", f"${rate_erosion:,.0f}",
                         "Annual discount gap for Expired M2M customers", color=YELLOW)
    with c2: metric_card("Below-Floor Gap", f"${floor_gap_tot:,.0f}",
                         "Annual shortfall from below-floor pricing", color=RED)
    with c3: metric_card("Total Cost of Inaction", f"${inaction_total:,.0f}",
                         "Rate erosion + floor gap", color=RED)

    st.markdown(f"""
    <div style='background:{BG};border-radius:10px;padding:16px 20px;margin-top:12px;'>
      <b>Act vs Don't Act:</b>&nbsp;&nbsp;
      <span style='color:{GREEN}'>▲ Scenario Uplift: ${max(0,incremental):,.0f}</span>
      &nbsp;|&nbsp;
      <span style='color:{RED}'>▼ Cost of Inaction: ${inaction_total:,.0f}</span>
      &nbsp;|&nbsp;
      <b>Gap: ${max(0,incremental)+inaction_total:,.0f}</b>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    rev_export = pd.DataFrame([
        {"Metric":"Baseline ARR","Value":f"${baseline_arr:,.0f}"},
        {"Metric":"Projected ARR","Value":f"${projected_arr:,.0f}"},
        {"Metric":"Incremental ARR","Value":f"${incremental:,.0f}"},
        {"Metric":"% Uplift","Value":f"{pct_uplift:.1f}%"},
        {"Metric":"Rate Erosion","Value":f"${rate_erosion:,.0f}"},
        {"Metric":"Floor Gap","Value":f"${floor_gap_tot:,.0f}"},
        {"Metric":"Total Cost of Inaction","Value":f"${inaction_total:,.0f}"},
    ])
    download_btn(rev_export, "Download Revenue Impact Summary", "revenue_impact.csv")
