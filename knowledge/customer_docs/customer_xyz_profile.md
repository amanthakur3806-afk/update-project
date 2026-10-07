# Customer XYZ - FinTech & Algorithmic Trading Profile

## Account Metadata
- **Customer ID**: XYZ
- **Company Name**: XYZ FinTech Global Holdings
- **Industry**: Financial Services, Algorithmic Trading & High-Frequency Clearing
- **Tier**: Enterprise Tier 1 (Platinum)
- **Primary Technical Contact**: Elena Rostova, Head of Core Infrastructure (e.rostova@xyzfintech.example.com)
- **Account Executive**: Michael Chang
- **Contract Term**: 24-Month Enterprise Master Agreement (Signed: 2024-11-30, Renewal: 2026-11-30)
- **Annual Recurring Revenue (ARR)**: $720,000 | Monthly Recurring Revenue (MRR): $60,000

## Architecture & Integration Architecture
XYZ FinTech connects directly to our platform via dedicated AWS DirectConnect and VPC Peering with ultra-low latency gateways.
1. **FIX Protocol & Ultra-Low-Latency WebSockets**: Consuming 250,000 order settlement events per minute.
2. **Dedicated Cloud Hardware**: Dedicated isolated multi-tenant pods located in AWS us-east-1 and eu-west-1.
3. **Hardware Security Module (HSM)**: KMS-backed client key management for regulatory transaction signing.

## SLA & Support Commitments
- **SLA Tier**: Platinum Mission-Critical Tier 1 (99.99% monthly uptime guarantee).
- **Incident Response Time**: Severity 1 incidents have a 15-minute SLA with immediate war-room paging.
- **Dedicated TAM**: Jordan Hayes (Senior Technical Account Manager).
- **Compliance Certification**: SOC2 Type II, ISO 27001, and PCI-DSS Level 1 audited environment.

## Current Health & Churn Risk Context
- **Health Score / NPS**: 42 (At-risk status due to recent market volatility latency spikes).
- **Recent Feedback**: Customer reported two transient 45ms jitter events during peak market open hours in Q3.
- **Action Plan**: Infrastructure engineering is deploying specialized eBPF kernel bypass routes to drop p99 latency below 8ms before contract renewal discussions in November.
