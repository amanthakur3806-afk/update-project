# Customer DATADOG - Internal Account Overview & Technical Profile

## 1. Account Metadata & Commercial Terms
- **Customer ID**: `DATADOG`
- **Legal Entity**: Datadog Inc. (New York, NY)
- **Industry & Domain**: Cloud Observability, Distributed Tracing, Security Information & Event Management (SIEM)
- **Contract Tier**: Enterprise Tier 1 (Platinum Observability)
- **Financial Profile**:
  - **Annual Contract Value (ARR)**: $2,800,000 / year
  - **Monthly Recurring Revenue (MRR)**: $233,333 / month
  - **Payment Terms**: Quarterly upfront wire, NET 30 days
  - **Contract Period**: 24-Month Enterprise Observability Agreement (Signed: 2025-02-28 | Scheduled Renewal: 2027-02-28)
  - **Expansion Pipeline**: Scoping Cloud Security Posture Management (CSPM) and automated AI anomaly detection add-on ($650k potential ACV) for Q2 2027

## 2. Key Stakeholders & Account Roster
- **Executive Sponsor**: Alexis Lê-Quôc, CTO & Co-Founder (`alexis.l@datadoghq.example.com`)
- **VP of Observability Architecture**: Laurent Sansonetti, Head of Core Systems (`laurent.s@datadoghq.example.com`)
- **Assigned Operations Lead**: Alex Chen (Lead Support Operations Architect)
- **Assigned Account Executive**: Sarah Jenkins (Senior Enterprise AE)
- **Dedicated Platinum TAM**: Dev Patel (Principal Technical Account Manager)

## 3. Cloud Architecture & Technical Blueprint
Datadog represents one of the highest telemetry throughput customers in the enterprise ecosystem, spanning hybrid multi-cloud topologies across AWS and GCP:
- **Primary Cloud Regions**: Dual cloud architecture — AWS `us-east-1` (N. Virginia), AWS `us-west-2` (Oregon), and GCP `europe-west1` (Belgium).
- **Telemetry Ingestion Scale**:
  - Ingests over **25+ trillion metric points, distributed traces, and log lines per month**.
  - Deploys kernel-level **eBPF tracing probes** across more than 18,000 active customer Kubernetes clusters, capturing socket connection lifecycle, DNS latency, and TCP retransmits with less than 0.5% CPU overhead.
- **Log & Trace Pipeline Topology**:
  - Dual-tiered storage model: In-memory NVMe tiered caching for the first 72 hours of hot search telemetry, followed by compressed Parquet indexing on cloud object stores.
  - Endpoints communicate via dedicated AWS PrivateLink and GCP Private Service Connect, bypassing public internet routing entirely.

## 4. Telemetry Benchmarks & Service Level Agreements (SLA)
- **Contractual SLA**: Platinum Mission-Critical **99.99% Availability Guarantee**.
- **SLA Response Windows**:
  - Severity 1 (Telemetry Drop or Agent Ingestion Outage): **< 15 minutes response** (24/7 dedicated escalation channel).
  - Severity 2 (Dashboard Query Slowness or Metric Delay): **< 1 hour response**.
  - Severity 3 (Feature Requests or Minor Ingestion Warns): **< 4 business hours**.
- **Real-Time Operational Benchmarks**:
  - **Monthly API Call Volume**: 6,200,000,000 calls / month
  - **Average Telemetry Ingestion Latency**: 14.1 ms | **P99 Query Latency**: 19.8 ms
  - **Overall Pipeline Error Rate**: 0.0004 (0.04%)
  - **SLA Compliance (Trailing 12 Months)**: 99.980%
  - **Net Promoter Score (NPS)**: 79 | **Churn Probability Score**: 5.0% (Low Risk)
  - **Active Agent Deployments**: 18,450 Kubernetes node daemonsets

## 5. Reliability History & Incident Postmortems
- **Sev-1 Incident (2025-06-11)**:
  - *Symptom*: Transient 4-minute drop in UDP DogStatsD ingest across AWS `us-east-1` due to cloud network interface packet queue contention.
  - *Mitigation*: Configured kernel SO_RCVBUF socket buffers to 32MB and enabled Linux eBPF socket load balancing; packet loss eliminated.
- **Multi-Cloud Rollout Drill (2026-01-10)**:
  - Validated seamless failover of log indexing pipelines between AWS and GCP during simulated regional degradation; 100% of telemetry retained without ingestion throttling.
- **Agent Version 7.58 Upgrade (2026-02-14)**:
  - Deployed upgraded lightweight eBPF tracing probes across 18,000 nodes; memory consumption reduced by 22%.

## 6. Security, Compliance & Governance Profile
- **SOC2 Type II**: Certified across Security, Availability, and Confidentiality trust service criteria.
- **ISO 27001 & FedRAMP Moderate**: Authorized for public sector and regulated financial enterprise telemetry ingestion.
- **Encryption Standards**: Enforces TLS 1.3 in transit and AES-256 with customer-managed encryption keys (CMEK) via AWS KMS.

## 7. Active Operational Notes & Pending Follow-Up Tasks
- **Security Audit Status**: eBPF kernel security verification completed with zero privilege escalation vulnerabilities.
- **Open Task #1 (Due 2026-11-20)**: Complete performance benchmarking for next-generation Parquet log compression tier. Assignee: Alex Chen.
- **Open Task #2 (Due 2027-01-15)**: Review 2027 multi-year expansion proposal with Alexis Lê-Quôc. Assignee: Sarah Jenkins.
