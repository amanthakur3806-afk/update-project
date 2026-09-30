# External Demo Datasets (Nexus AI)

This directory contains external demo fixtures used when the platform operates in **Demo Mode**.

## Philosophy: Separation of Code and Data

- **Python Source Code** (`app/`) contains **only** logic, schemas, workflow, orchestration, and configuration.
- **Data** (`demo_data/` and `knowledge/`) contains **only** external files (JSON, Markdown, PDF, etc.).
- There are **ZERO** hardcoded customer records or metrics in Python files.
- If a customer or metric is removed from this directory, the platform accurately reports `"Customer not found"` or `"No data source configured"` — **ZERO SILENT FALLBACKS**.

---

## Directory Structure

```
demo_data/
├── crm/
│   └── customers.json       # 6 customer records (ABC, XYZ, ACME, NOVA, FINTECH, CLOUD)
├── analytics/
│   ├── metrics.json         # Real-time health metrics (ARR, MRR, churn risk, NPS, SLA)
│   └── history.json         # Chronological event timelines (QBRs, upgrades, incidents)
├── knowledge/
│   ├── customer_docs/       # Customer architecture & operational profiles
│   ├── company_policies/    # Enterprise SLAs & compliance guidelines
│   └── technical_docs/      # API integration & technical specifications
└── README.md                # This document
```

---

## How It Works

1. **Demo Mode Active (`DEMO_MODE=True`)**:
   - The platform loads `demo_data/crm/customers.json` into the CRM Data Service.
   - The platform loads `demo_data/analytics/metrics.json` and `history.json` into the Analytics Data Service.
   - The platform indexes documents from `knowledge/` into the FAISS vector store.

2. **Real / Production Mode (`DEMO_MODE=False`)**:
   - The platform starts with empty customer records unless configured with live databases or external APIs.
   - Missing data returns explicit `"No data available"` responses.

3. **Replacing or Adding Data**:
   - You can edit `customers.json` or `metrics.json` directly.
   - You can also upload new documents and customer records directly through the UI or REST APIs (`POST /data/crm/customers`, `POST /knowledge/upload`).
