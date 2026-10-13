# Customer SPOTIFY - Internal Account Overview & Technical Profile

## 1. Account Metadata & Commercial Terms
- **Customer ID**: `SPOTIFY`
- **Legal Entity**: Spotify AB (Stockholm, Sweden)
- **Industry & Domain**: Digital Media, High-Throughput Audio Streaming, and Podcasting Infrastructure
- **Contract Tier**: Enterprise Tier 1 (Platinum Ultra)
- **Financial Profile**:
  - **Annual Contract Value (ARR)**: $3,600,000 / year
  - **Monthly Recurring Revenue (MRR)**: $300,000 / month
  - **Payment Terms**: Annual upfront wire transfer, NET 30 days
  - **Contract Period**: 36-Month Multi-Year Master Grid Agreement (Signed: 2024-04-15 | Scheduled Renewal: 2027-04-15)
  - **Expansion Pipeline**: Scoping $800k add-on for real-time podcast dynamic ad insertion (DAI) telemetry in Q1 2027

## 2. Key Stakeholders & Account Roster
- **Executive Sponsor**: Gustav Söderström, Chief R&D Officer (`gustav.s@spotify.example.com`)
- **VP of Infrastructure**: Niklas Gustavsson, VP Core Engineering (`niklas.g@spotify.example.com`)
- **Assigned Account Executive**: Sarah Jenkins (Senior Enterprise AE, Commercial Sales)
- **Assigned Technical Lead**: Alex Chen (Lead Support Operations Architect)
- **Dedicated Platinum TAM**: Dev Patel (Principal Technical Account Manager, 24/7 pager on call)

## 3. Cloud Architecture & Technical Blueprint
Spotify operates an active-active multi-region cloud deployment hosted primarily on Google Cloud Platform with AWS edge interconnect:
- **Primary Cloud Regions**: GCP `europe-west1` (St. Ghislain, Belgium) and `us-central1` (Council Bluffs, Iowa).
- **Edge Routing & Ingress**: Over 1,200 Envoy proxy mesh sidecars routing traffic with automated circuit breaking and TLS 1.3 termination.
- **Event Telemetry Pipeline**:
  - Ingests over **8.2 billion daily stream events**, user sessions, and playback telemetry via Managed Apache Kafka (450 cluster partitions) and GCP Pub/Sub.
  - Successfully migrated from Apache Flink to Managed Kafka in Q1 2025, slashing end-to-end telemetry lag by 78% (from 110ms to 24ms).
- **Data Persistence Tier**: Distributed Google Cloud Spanner for transactional entitlements and Google Cloud Bigtable for high-velocity playback logs.
- **Identity & Access Management**: Okta SAML 2.0 federation with automated SCIM provisioning, mutual TLS (mTLS) zero-trust service mesh, and European GDPR data residency compliance boundaries.

## 4. Telemetry Benchmarks & Service Level Agreements (SLA)
- **Contractual SLA**: Platinum Mission-Critical **99.99% Availability Guarantee** (< 4.3 minutes downtime/month).
- **SLA Response Windows**:
  - Severity 1 (Critical Service Outage): **< 15 minutes response** (24/7/365 dedicated bridge).
  - Severity 2 (Degraded Telemetry/Ingest): **< 1 hour response**.
  - Severity 3 (General Inquiries/Minor Bugs): **< 4 business hours**.
- **Real-Time Operational Benchmarks**:
  - **Monthly API Call Volume**: 2,450,000,000 calls / month
  - **P99 Query Latency**: 12.4 ms | **P95 Latency**: 8.1 ms
  - **Overall Telemetry Error Rate**: 0.0002 (0.02%)
  - **SLA Compliance (Trailing 12 Months)**: 99.990%
  - **Net Promoter Score (NPS)**: 82 | **Churn Probability Score**: 3.0% (Very Low Risk)
  - **Error Budget Remaining (Current Quarter)**: 86.4%

## 5. Reliability History & Incident Postmortems
- **Sev-1 Incident (2025-08-22)**:
  - *Symptom*: Kafka consumer group rebalance storm caused 6-minute playback metadata buffering across EU West during a major global pop album release.
  - *Root Cause*: High network jitter triggered false-positive heartbeat timeouts on node recycling, causing cascading rebalance loops.
  - *Permanent Remediation*: Heartbeat timeout increased to 45 seconds; consumer partition assignments decoupled to cooperative-sticky rebalance protocol; added 40 standby worker nodes.
- **Sev-2 Incident (2025-11-04)**:
  - *Symptom*: Transient 35ms query latency spike during global telemetry batch ingestion.
  - *Resolution*: Autoscaled memory limits on Envoy ingress pods; telemetry recovered to 12ms within 18 minutes.
- **Disaster Recovery Drill (2025-10-15)**:
  - Full failover drill simulated loss of `europe-west1`. Secondary region `us-central1` absorbed 100% of telemetry within 3 minutes and 42 seconds with zero dropped playback records (RPO: 0 sec, RTO: 3m 42s).

## 6. Security, Privacy & Governance Profile
- **SOC2 Type II**: Validated and renewed January 2026 with zero exceptions.
- **ISO/IEC 27001:2022**: Certified across all European and North American hosting clusters.
- **Data Privacy & GDPR**: Enforces strict EU Chapter V data transfer mechanisms; EU customer telemetry is stored exclusively within European economic area (EEA) storage partitions. Zero unredacted PII is exposed in telemetry headers.

## 7. Active Operational Notes & Pending Follow-Up Tasks
- **Seasonal Burst Pre-Authorization**: Pre-approved 3.5x burst capacity allowance active for the annual "Spotify Wrapped" traffic surge throughout December.
- **Open Task #1 (Due 2026-11-15)**: Conduct joint multi-region failover rehearsal with Spotify reliability team ahead of holiday traffic freeze. Assignee: Alex Chen.
- **Open Task #2 (Due 2027-01-10)**: Prepare executive QBR renewal proposal including Podcast Dynamic Ad Telemetry expansion. Assignee: Sarah Jenkins.
