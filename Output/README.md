# Workstream Pricing Intelligence Dashboard

Executive-style Streamlit dashboard for RevOps pricing analysis — Stripe × Salesforce data.

## Pages

| Page | Business Question |
|------|-------------------|
| **Executive Summary** | Should Workstream execute the pricing program? |
| **Pricing Opportunity** | Where is Workstream underpriced and by how much? |
| **Risk & Readiness** | What risks block execution? |
| **Action Center** | Who should we target first and what is the expected impact? |

## Running Locally

```bash
cd "4. Dashboard/Output"
pip install -r requirements.txt
streamlit run dashboard.py
```

The app reads all CSV files from `../Input/` (relative to `dashboard.py`).

## Deploying to Streamlit Community Cloud

1. Push this repository to GitHub (include both `Output/` and `Input/` folders).
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your GitHub repo.
3. Set **Main file path** to `4. Dashboard/Output/dashboard.py`.
4. Ensure all data files are present in `4. Dashboard/Input/`.
5. Click **Deploy**.

## Folder Structure

```
RevOps Case Study/
├── 4. Dashboard/
│   ├── Input/
│   │   ├── stripeXsfdc.csv          ← Primary dataset
│   │   ├── stripe_customers.csv
│   │   ├── stripe_subscriptions.csv
│   │   ├── sfdc_accounts.csv
│   │   └── sfdc_contracts.csv
│   └── Output/
│       ├── dashboard.py             ← Main app
│       ├── requirements.txt
│       ├── README.md
│       └── .streamlit/
│           └── config.toml
```

## Required Input Files

| File | Description |
|------|-------------|
| `stripeXsfdc.csv` | Primary joined dataset (Stripe × Salesforce) — 788 rows, 26 columns |
| `stripe_customers.csv` | Raw Stripe customer records |
| `stripe_subscriptions.csv` | Raw Stripe subscription line items |
| `sfdc_accounts.csv` | Salesforce account records |
| `sfdc_contracts.csv` | Salesforce contract records |

## Global Filters

All pages respond to the sidebar filters:
- **AE Owner** — filter by account executive
- **Segment** — A (≥100% of list), B (90–99%), C (75–89%), D (<75%)
- **Contract Status** — Locked, Expired M2M, No Contract, No SF Link
- **Product** — Hiring, HR, Payroll
- **CSM** — filter by customer success manager

Scenario sliders (Phase 1/2/3 retention) are on the **Action Center** page only.
