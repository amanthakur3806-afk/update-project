# Enterprise Service Level Agreements (SLA) & Uptime Policy

## 1. Scope and Tier Classification
This document governs SLA commitments, uptime guarantees, response windows, and financial credit penalties for all enterprise clients.

### Tier Structure & Guarantees
- **Mission-Critical Five-Nines (99.999% Uptime Guarantee)**:
  - *Assigned Accounts*: **Stripe Inc.** (`STRIPE`).
  - *Allowable Downtime*: Less than 26 seconds per calendar month.
  - *Response Time Targets*: Sev-1 < 5 minutes (Immediate 24/7 War Room bridge), Sev-2 < 30 minutes.
  - *Service Credits*: 25% monthly billing credit if uptime drops below 99.995%; 50% credit if below 99.990%.
- **Platinum Ultra (99.99% Uptime Guarantee)**:
  - *Assigned Accounts*: **Spotify AB** (`SPOTIFY`), **Datadog Inc.** (`DATADOG`), **ABC Logistics** (`ABC`).
  - *Allowable Downtime*: Less than 4.32 minutes per calendar month.
  - *Response Time Targets*: Sev-1 < 15 minutes, Sev-2 < 1 hour, Sev-3 < 4 hours.
  - *Service Credits*: 15% monthly billing credit if uptime drops below 99.95%.
- **Enterprise Gold High-Burst (99.95% Uptime Guarantee)**:
  - *Assigned Accounts*: **Shopify Inc.** (`SHOPIFY`).
  - *Allowable Downtime*: Less than 21.6 minutes per calendar month.
  - *Response Time Targets*: Sev-1 < 30 minutes (escalated to < 15 mins during Q4 holiday freeze), Sev-2 < 2 hours.
  - *Burst Headroom*: 4.0x pre-authorized burst allowance with zero rate-limiting during Black Friday / Cyber Monday.

## 2. Incident Severity Definitions
- **Severity 1 (Critical Outage)**: Core transaction or ingestion path completely offline (e.g. payment ledger unreachable, Kafka streaming pipeline halted, or storefront checkout failing).
- **Severity 2 (High Degradation)**: Major business feature degraded; workaround available (e.g. latency jitter over 50ms, webhook delay over 2 minutes, or dashboard query timeouts).
- **Severity 3 (Medium / Normal)**: Non-critical query degradation or admin portal issue.
- **Severity 4 (Low / Advisory)**: General inquiries, telemetry documentation questions, or cosmetic requests.

## 3. Escalation Procedure
When an enterprise account triggers a Sev-1 incident:
1. Automated PagerDuty escalation alerts the On-Call Incident Commander and Principal TAM within 2 minutes.
2. An active Incident War Room bridge is established with audio/video links transmitted to the customer technical lead.
3. Executive notification dispatched to Elena Rostova (EVP Operations) and the designated AE (Sarah Jenkins or Alex Chen) within 15 minutes.
