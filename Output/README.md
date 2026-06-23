# Workstream Pricing Dashboard

Interactive Streamlit dashboard for RevOps pricing analysis — Stripe × Salesforce data.

## Running Locally

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

The app reads all CSV files from the `../Input/` folder (relative to `dashboard.py`).

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub (include both the `Output/` and `Input/` folders).
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your GitHub repo.
3. Set the **Main file path** to `4. Dashboard/Output/dashboard.py`.
4. Ensure all data files are present in `4. Dashboard/Input/`.
5. Click **Deploy**.

## Data Files Required (in `Input/`)

| File | Description |
|------|-------------|
| `stripeXsfdc.csv` | Primary joined dataset (Stripe × Salesforce) |
| `stripe_customers.csv` | Raw Stripe customer records |
| `stripe_subscriptions.csv` | Raw Stripe subscription line items |
| `sfdc_accounts.csv` | Salesforce account records |
| `sfdc_contracts.csv` | Salesforce contract records |

## Dashboard Tabs

1. **Data Overview** — Source file stats, subscription lines by product, customers with no SF link
2. **Contract Status** — Locked / Expired M2M / No Contract breakdown, renewal pipeline
3. **Customers & Segmentation** — Segment A-D analysis, scatter plots, full customer table
4. **Pricing Analysis** — Below-floor gap, median prices by product, pricing distribution
5. **Churn Risk** — Scored non-locked customers (1-5), high-risk table, renewal pipeline
6. **Revenue Impact** — Live phase scenario with retention sliders, ARR trajectory chart
