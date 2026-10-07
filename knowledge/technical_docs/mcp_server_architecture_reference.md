# Technical Architecture: Model Context Protocol (MCP) Server Infrastructure

## 1. Overview & Transport Protocol
The Nexus AI platform orchestrates intelligent agents through standardized Model Context Protocol (MCP) servers:
1. **CRM MCP Server (`crm_mcp`)**: Exposes customer lookups, search directory, and operational note updates.
2. **Analytics MCP Server (`analytics_mcp`)**: Exposes ARR/MRR financial telemetry, NPS health, churn risk forecasting, and historical event timelines.
3. **Customer Operations MCP Server (`operations_mcp`)**: Exposes transactional customer creation, status updates, notes, follow-up task tracking, and audit logging.

## 2. Canonical Tool Registry & Resolution
- All tools use strict canonical dot-notation: `<ServerCategory>.<tool_name>` (e.g. `Operations.create_customer`, `CRM.get_customer`, `Analytics.get_customer_metrics`).
- Exact O(1) registry mapping ensures zero ambiguity and prevents unauthorized cross-tenant execution.

## 3. Safe Retries, Idempotency & Failure Handling
- **Read-Only Tools**: (`CRM.get_customer`, `Analytics.get_customer_metrics`, `Operations.list_customers`) are marked `safe_to_retry=True`.
- **State-Mutating Tools**: (`Operations.create_customer`, `Operations.update_customer_status`) are transactional and marked `safe_to_retry=False` to prevent double-write anomalies.
