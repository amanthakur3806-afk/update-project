# Enterprise Data Privacy, Security & Compliance Standards

## 1. Compliance Frameworks & Certifications
Our platform adheres to rigorous international security frameworks:
- **SOC 2 Type II**: Annual independent audit covering Security, Availability, Processing Integrity, and Confidentiality.
- **HIPAA / HITECH**: Comprehensive BAA agreements executed for healthcare customers (e.g., NovaHealth).
- **ISO/IEC 27001:2022**: Certified Information Security Management System (ISMS).
- **GDPR / CCPA**: Compliant data processing addenda with EU Standard Contractual Clauses (SCCs).

## 2. Cryptographic Controls
- **Encryption at Rest**: AES-256 GCM applied to all databases, vector indices, and blob object storage.
- **Encryption in Transit**: Strict TLS 1.3 enforced for all public APIs and internal MCP server RPCs.
- **Customer-Managed Encryption Keys (CMEK)**: Available for Tier 1 Platinum accounts with automated key rotation.

## 3. Data Retention & Agent Access Restrictions
- **Zero Raw Secret Storage**: Agent tools must redact API keys, JWT tokens, and passwords prior to synthesis logging.
- **Audit Immutability**: All tool executions and agent modifications are captured in SQLite / WORM audit records with microsecond timestamps and operator attribution.
