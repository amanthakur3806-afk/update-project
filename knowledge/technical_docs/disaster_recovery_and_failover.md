# Technical Specification: Disaster Recovery, High Availability & Failover

## 1. High Availability Architecture
- Multi-region active-active deployment across AWS `us-east-1` (Primary) and `eu-west-1` (Secondary).
- Global traffic routing handled via Anycast DNS with health probes every 5 seconds.
- Database replication: Continuous synchronous replication with automated multi-AZ failover under 30 seconds.

## 2. Recovery Objectives (RPO & RTO)
- **Tier 1 Platinum Accounts (e.g. ABC, XYZ, NOVA)**:
  - **Recovery Point Objective (RPO)**: < 1 minute (near-zero data loss).
  - **Recovery Time Objective (RTO)**: < 15 minutes for full service restoration.
- **Tier 2 Gold Accounts (e.g. ACME, VERTEX)**:
  - **RPO**: < 15 minutes.
  - **RTO**: < 1 hour.
- **Tier 3 Silver Accounts (e.g. QUANTUM)**:
  - **RPO**: < 1 hour.
  - **RTO**: < 4 hours.

## 3. Automated Backup & Restoration Drill
- Snapshot backups executed every 6 hours with cross-region replication to cold storage.
- Automated quarterly disaster recovery simulation exercises with post-drill verification reports.
