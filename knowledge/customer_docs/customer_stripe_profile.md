# Customer STRIPE - Internal Account Overview & Technical Profile

## 1. Account Metadata & Commercial Terms
- **Customer ID**: `STRIPE`
- **Legal Entity**: Stripe Inc. (San Francisco, CA & Dublin, Ireland)
- **Industry & Domain**: Global Financial Infrastructure, Merchant Payment Gateway, and Billing Automation SaaS
- **Contract Tier**: Enterprise Mission-Critical (Five-Nines Tier)
- **Financial Profile**:
  - **Annual Contract Value (ARR)**: $5,200,000 / year
  - **Monthly Recurring Revenue (MRR)**: $433,333 / month
  - **Payment Terms**: Semi-annual upfront wire, NET 15 days
  - **Contract Period**: 36-Month Strategic Enterprise Agreement (Signed: 2023-11-30 | Scheduled Renewal: 2026-11-30)
  - **Upcoming Renewal Status**: Formal renewal negotiations active; targeting 3-year extension at $6.0M ARR with Latin America (LATAM) cross-border settlements expansion

## 2. Key Stakeholders & Account Roster
- **Executive Sponsor**: David Singleton, Chief Technology Officer (`david.s@stripe.example.com`)
- **Head of Reliability Engineering**: Michelle Wu, VP Infrastructure & Platform (`michelle.wu@stripe.example.com`)
- **Assigned Account Executive**: Sarah Jenkins (Senior Enterprise AE, Commercial Sales)
- **Assigned Operations Lead**: Alex Chen (Lead Support Operations Architect)
- **Dedicated Principal TAM**: Marcus Vance (Principal Technical Account Manager, 24/7 financial war room access)

## 3. Cloud Architecture & Technical Blueprint
Stripe requires extreme, zero-tolerance reliability and operates an active-active dual-region cloud infrastructure deployed across Amazon Web Services:
- **Primary Cloud Regions**: AWS `us-east-1` (N. Virginia) and `us-west-2` (Oregon) with dedicated AWS Direct Connect fiber interconnects.
- **Transaction Pipeline Topology**:
  - Processes over **4.8 billion monthly payment API calls**, merchant checkout intents, and payout transactions.
  - Strict idempotent transaction processing: every write request enforces a unique UUID idempotency key with distributed Redis lock leases.
  - Multi-region database architecture utilizes distributed CockroachDB and Citus PostgreSQL clusters with synchronous multi-availability zone replication.
- **Hardware Security & Tokenization**:
  - All credit card and account token payloads pass through dedicated Hardware Security Modules (HSMs) with end-to-end envelope encryption (AES-256-GCM).
  - Webhook delivery infrastructure delivers merchant notifications with automated exponential backoff and 99.999% delivery guarantee within 2 seconds.

## 4. Telemetry Benchmarks & Service Level Agreements (SLA)
- **Contractual SLA**: Mission-Critical **99.999% Availability Guarantee (Five-Nines)** — allows less than 26 seconds of unscheduled downtime per month.
- **SLA Response Windows**:
  - Severity 1 (Payment Gateway or Ledger Disruption): **< 5 minutes response** (Immediate live war room bridge).
  - Severity 2 (Reporting or Merchant Dashboard Degraded): **< 30 minutes response**.
  - Severity 3 (Non-critical API queries): **< 2 business hours**.
- **Real-Time Operational Benchmarks**:
  - **Monthly API Call Volume**: 4,800,000,000 calls / month
  - **P99 Transaction Latency**: 5.8 ms | **P95 Latency**: 3.9 ms
  - **Overall Transaction Error Rate**: 0.00005 (0.005%)
  - **SLA Compliance (Trailing 12 Months)**: 99.999% (Perfect SLA adherence)
  - **Net Promoter Score (NPS)**: 89 | **Churn Probability Score**: 1.0% (Zero immediate churn risk)
  - **Error Budget Remaining (Current Quarter)**: 94.2%

## 5. Reliability History & Incident Postmortems
- **Sev-1 Drill (2025-04-12)**:
  - *Scenario*: Simulated catastrophic fiber cut and regional outage of AWS `us-east-1`.
  - *Result*: Automated Route 53 health checks and BGP anycast rerouted 100% of payment traffic to `us-west-2` in 42 seconds with zero dropped transaction records and zero duplicate ledger entries.
- **Sev-2 Incident (2025-09-18)**:
  - *Symptom*: Webhook dispatch backlog reached 120,000 queued events due to third-party bank endpoint timeouts in Europe.
  - *Mitigation*: Triggered dynamic rate-limiting circuit breakers per acquiring bank; queue drained within 14 minutes.
- **PCI-DSS Recertification Audit (2025-10-18)**:
  - Level 1 Service Provider compliance validated by external Qualified Security Assessor (QSA) with zero findings across encryption, key rotation, and network segmentation.

## 6. Security, Compliance & Governance Profile
- **PCI-DSS Level 1**: Certified annually under PCI-DSS v4.0 standards.
- **SOC1 Type II & SOC2 Type II**: Certified for financial reporting and security controls.
- **Global Financial Regulations**: Certified under European Central Bank PSD2 (Strong Customer Authentication), UK FCA, and US FinCEN AML/KYC directives.
- **Audit Logging**: Immutable, write-once-read-many (WORM) audit trail streaming directly to AWS S3 Glacier with cryptographic signature validation.

## 7. Active Operational Notes & Pending Follow-Up Tasks
- **Renewal Execution Target**: Contract expires on November 30, 2026. Account team is finalizing terms for a 36-month renewal with $6.0M ARR commitment and LATAM expansion clause.
- **Open Task #1 (Due 2026-10-25)**: Deliver Q3 executive health dossier and SLA compliance audit report to David Singleton. Assignee: Sarah Jenkins.
- **Open Task #2 (Due 2026-11-05)**: Finalize technical staging environment for LATAM multi-currency settlement gateway tests. Assignee: Alex Chen.
