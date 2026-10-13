# Customer SHOPIFY - Internal Account Overview & Technical Profile

## 1. Account Metadata & Commercial Terms
- **Customer ID**: `SHOPIFY`
- **Legal Entity**: Shopify Inc. (Ottawa, Ontario, Canada)
- **Industry & Domain**: Global Omnichannel Commerce, Merchant Operations, and Checkout Infrastructure
- **Contract Tier**: Enterprise Tier 2 (Gold High-Burst Tier)
- **Financial Profile**:
  - **Annual Contract Value (ARR)**: $4,100,000 / year
  - **Monthly Recurring Revenue (MRR)**: $341,666 / month
  - **Payment Terms**: Annual upfront wire, NET 30 days
  - **Contract Period**: 36-Month Strategic Retail Agreement (Signed: 2023-12-31 | Scheduled Renewal: 2026-12-31)
  - **Upcoming Renewal Horizon**: Contract renewal execution target is December 2026; negotiations ongoing to transition account into Platinum Tier with global multi-cloud edge cache deployment

## 2. Key Stakeholders & Account Roster
- **Executive Sponsor**: Farhan Thawar, VP of Engineering (`farhan.t@shopify.example.com`)
- **Director of Platform Scaling**: Jean-Michel Lemieux, Technical Advisor (`jm.lemieux@shopify.example.com`)
- **Assigned Operations Lead**: Alex Chen (Lead Support Operations Architect)
- **Assigned Commercial Lead**: Sarah Jenkins (Senior Enterprise AE)
- **Dedicated Enterprise TAM**: Dev Patel (Principal Technical Account Manager)

## 3. Cloud Architecture & Technical Blueprint
Shopify powers millions of merchants globally and runs on a modular, isolated "Pod" cloud architecture hosted on Google Cloud Platform:
- **Primary Cloud Regions**: GCP `us-east4` (N. Virginia), `us-central1` (Iowa), and `northamerica-northeast1` (Montreal).
- **Pod Architecture Isolation**:
  - Each Pod is a self-contained, fully autonomous deployment partition containing web workers, MySQL database shards, and Redis caching tiers.
  - Failure in one Pod cannot cascade or disrupt merchants hosted on other Pods. Enterprise flagship merchants (Shopify Plus) occupy dedicated high-memory Pod partitions.
- **Black Friday / Cyber Monday (BFCM) Burst Scaling**:
  - Ingests up to **120 million requests per minute (rpm)** during global flash-sales and synchronized product drops.
  - Pre-approved 4.0x capacity burst headroom configured across GCP worker nodes with automated auto-scaling triggers at 65% CPU threshold.
- **Data Persistence & Ledger Consistency**:
  - Vitess-sharded MySQL database tier running semi-synchronous replication to guarantee zero data loss on order ledger commits.
  - Multi-tier Redis caching for product catalog, storefront inventory counts, and cart session state.

## 4. Telemetry Benchmarks & Service Level Agreements (SLA)
- **Contractual SLA**: Enterprise Gold **99.95% Availability Guarantee** (< 21.9 minutes allowable downtime/month).
- **SLA Response Windows**:
  - Severity 1 (Storefront Checkout Down or Merchant Payment Failure): **< 30 minutes response** (escalated to < 15 minutes during Q4 holiday freeze).
  - Severity 2 (Merchant Admin Panel or Inventory Telemetry Delayed): **< 2 hours response**.
  - Severity 3 (General Inquiries or Billing Adjustments): **< 8 business hours**.
- **Real-Time Operational Benchmarks**:
  - **Monthly API Call Volume**: 3,100,000,000 calls / month
  - **P99 Checkout Latency**: 16.8 ms | **P95 Latency**: 11.2 ms
  - **Overall Telemetry Error Rate**: 0.0003 (0.03%)
  - **SLA Compliance (Trailing 12 Months)**: 99.960%
  - **Net Promoter Score (NPS)**: 75 | **Churn Probability Score**: 6.0% (Low Risk, High Retention)
  - **Black Friday Burst Headroom**: 400% pre-authorized quota

## 5. Reliability History & Incident Postmortems
- **Sev-1 Incident (2024-11-29)**:
  - *Symptom*: 8-minute checkout latency elevation during Black Friday flash sale for a top cosmetics merchant.
  - *Root Cause*: Hot database shard contention on inventory lock counters for a single viral SKU.
  - *Remediation*: Implemented distributed Redis reservation locks and vitess key-range reshuffling; transaction latency restored to 14ms.
- **BFCM Peak Record (2025-11-28)**:
  - Processed a record $9.3B in merchant sales across Cyber Week with 99.998% uptime and zero dropped payment sessions across all Pods.
- **Pod Infrastructure Rollout (2026-03-15)**:
  - Successfully migrated 800 flagship enterprise Plus brands into isolated GCP hardware partitions with dedicated network egress routes.

## 6. Security, Compliance & Governance Profile
- **PCI-DSS Level 1**: Certified merchant service provider and payment application.
- **SOC2 Type II & SOC3**: Certified across Security, Availability, and Confidentiality.
- **Data Residency**: Supports localized checkout and merchant data compliance across EU (GDPR) and Canada (PIPEDA).

## 7. Active Operational Notes & Pending Follow-Up Tasks
- **Holiday Freeze Planning**: Technical freeze period begins November 15, 2026. All major cluster upgrades must complete prior to October 31.
- **Open Task #1 (Due 2026-10-30)**: Complete Q4 BFCM capacity planning and burst quota provisioning review with Farhan Thawar. Assignee: Alex Chen.
- **Open Task #2 (Due 2026-12-10)**: Deliver 2027 renewal proposal offering Platinum Tier SLA and multi-cloud edge cache deployment. Assignee: Sarah Jenkins.
