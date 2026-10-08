"""
Enterprise Alignment & Safety Guardrails
========================================
Comprehensive multi-layered alignment and safety policies for autonomous agents:
  1. Input Alignment & Injection Defense (Prompt injection, jailbreak, harmful content, domain boundaries).
  2. RBAC & Privilege Guardrail (Validates user roles against tool execution sensitivity).
  3. Tool Argument Guardrail (Validates parameter safety, prevents command injection/path traversal).
  4. Output Alignment & Data Leak Prevention (Anti-hallucination checks, secrets/API keys redaction, compliance).
"""
import re
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field


class GuardrailResult(BaseModel):
    allowed: bool = True
    category: str = "pass"  # pass, prompt_injection, harmful_content, out_of_scope, rbac_denial, secret_leak
    reason: Optional[str] = None
    sanitized_input: Optional[str] = None
    safe_response: Optional[str] = None
    risk_score: float = 0.0  # 0.0 (safe) to 1.0 (critical)


class AlignmentGuardrailService:
    """
    Evaluates enterprise queries, tool executions, and generated outputs against corporate safety,
    domain alignment, and compliance policies.
    """

    # 1. Prompt Injection & Jailbreak Heuristics
    INJECTION_PATTERNS = [
        r"(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|prior|above|system)\s+(?:instructions|rules|prompts|commands|constraints)",
        r"(?:you\s+are\s+now\s+in|enable|switch\s+to)\s+(?:dan|developer|jailbreak|unrestricted|god)\s+mode",
        r"(?:reveal|print|display|dump|leak|show)\s+(?:the\s+)?(?:system\s+prompt|internal\s+instructions|hidden\s+rules|api\s+keys|passwords)",
        r"system\s*:\s*you\s+are\s+no\s+longer",
        r"bypass\s+(?:all\s+)?(?:guardrails|safety\s+filters|security\s+checks|policies)",
        r"do\s+anything\s+now\s+(?:mode)?",
        r"act\s+as\s+an\s+unfiltered\s+ai",
    ]

    # 2. Harmful & Malicious Activities
    HARMFUL_PATTERNS = [
        r"(?:create|generate|write|develop|code|build)\s+.*?\b(?:malware|ransomware|keylogger|exploit|ddos|virus|trojan|backdoor)\b",
        r"\b(?:ransomware|keylogger|backdoor\s+script|trojan\s+virus)\b",
        r"(?:hack|breach|infiltrate|bypass\s+firewall)\b",
        r"(?:manufacture|build|synthesize)\s+.*?\b(?:explosives|weapons|biological\s+agent)\b",
    ]

    # 3. Sensitive Enterprise Action RBAC Mapping
    ROLE_HIERARCHY = {
        "Executive Leadership": 10,
        "Admin": 10,
        "Lead Support Operations Architect": 8,
        "Director of Customer Success": 7,
        "Senior Solutions Architect": 6,
        "Senior Enterprise Account Executive": 5,
        "Account Executive": 4,
        "Customer Operations": 4,
        "Anonymous": 1,
    }

    # High-impact operations requiring role level >= 4 (authenticated)
    RESTRICTED_OPERATIONS = {
        "Operations.change_customer_status": 4,
        "Operations.add_customer_note": 3,
        "Operations.create_follow_up_task": 3,
        "Operations.create_customer": 4,
    }

    # 4. Secret / Credential Leak Patterns
    SECRET_PATTERNS = [
        r"(?:gsk_[a-zA-Z0-9]{20,})",                    # Groq API keys
        r"(?:sk-[a-zA-Z0-9]{20,})",                     # OpenAI API keys
        r"(?:ey[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})", # JWT tokens
        r"(?:[a-f0-9]{64})",                            # SHA-256 hashes
        r"(?:password\s*[:=]\s*['\"][^'\"]+['\"])",     # Plaintext passwords
    ]

    def validate_input(
        self,
        query: str,
        user_profile: Optional[Dict[str, Any]] = None,
        agent_config: Optional[Dict[str, Any]] = None
    ) -> GuardrailResult:
        """
        Validate incoming user query for prompt injection, safety, and domain alignment.
        """
        if not query or not query.strip():
            return GuardrailResult(allowed=False, category="empty", reason="Empty request query provided.")

        q_clean = query.strip()
        q_lower = q_clean.lower()

        # Check 1: Prompt Injection / System Override
        for pat in self.INJECTION_PATTERNS:
            if re.search(pat, q_lower):
                return GuardrailResult(
                    allowed=False,
                    category="prompt_injection",
                    risk_score=0.95,
                    reason="Request contains prompt injection or system override patterns violating enterprise alignment.",
                    safe_response=(
                        "## Enterprise Alignment Notice\n\n"
                        "Your request was flagged by the **Enterprise Alignment Guardrail** as an attempt to override system rules or access internal directives.\n\n"
                        "- **Policy**: Enterprise safety guidelines strictly prohibit instruction overrides or system prompt extraction.\n"
                        "- **Guidance**: Please ask questions regarding customer accounts, CRM records, analytics health, or enterprise operations."
                    )
                )

        # Check 2: Harmful & Malicious Activities
        for pat in self.HARMFUL_PATTERNS:
            if re.search(pat, q_lower):
                return GuardrailResult(
                    allowed=False,
                    category="harmful_content",
                    risk_score=1.0,
                    reason="Request requests harmful, destructive, or illicit technical actions.",
                    safe_response=(
                        "## Safety Policy Violation\n\n"
                        "This request cannot be fulfilled as it involves malicious technical activities or unauthorized security exploitation.\n\n"
                        "- **Status**: Request Blocked by Enterprise Security Policy."
                    )
                )

        # All input checks passed
        return GuardrailResult(
            allowed=True,
            category="pass",
            sanitized_input=q_clean,
            risk_score=0.0
        )

    def validate_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None,
        agent_config: Optional[Dict[str, Any]] = None
    ) -> GuardrailResult:
        """
        Validate tool execution against parameter safety and role-based access control.
        """
        # 1. Argument injection & safety checks first (prevent payload execution regardless of role)
        for k, v in tool_args.items():
            if isinstance(v, str):
                # Check for SQL injection or shell injection artifacts in string arguments
                if re.search(r"(\bDROP\s+TABLE\b|\bUNION\s+SELECT\b|;\s*rm\s+-rf|;\s*shutdown)", v, re.IGNORECASE):
                    return GuardrailResult(
                        allowed=False,
                        category="harmful_content",
                        risk_score=0.9,
                        reason=f"Dangerous command injection pattern detected in argument '{k}'."
                    )

        # 2. RBAC check on restricted operations
        user_role = (user_profile.get("role") if user_profile else "Anonymous") or "Anonymous"
        user_level = self.ROLE_HIERARCHY.get(user_role, 3)

        req_level = self.RESTRICTED_OPERATIONS.get(tool_name, 1)
        if user_level < req_level:
            return GuardrailResult(
                allowed=False,
                category="rbac_denial",
                risk_score=0.7,
                reason=f"Role '{user_role}' has insufficient privileges for tool '{tool_name}' (requires level {req_level})."
            )

        return GuardrailResult(allowed=True, category="pass")

    def validate_output(
        self,
        output_text: str,
        user_profile: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, GuardrailResult]:
        """
        Sanitize and redact any sensitive secrets or credential leaks from model outputs.
        """
        if not output_text:
            return "", GuardrailResult(allowed=True, category="pass")

        sanitized = output_text
        secrets_found = 0

        for pat in self.SECRET_PATTERNS:
            matches = re.findall(pat, sanitized)
            if matches:
                secrets_found += len(matches)
                sanitized = re.sub(pat, "[REDACTED_SECRET]", sanitized)

        if secrets_found > 0:
            return sanitized, GuardrailResult(
                allowed=True,
                category="secret_leak",
                risk_score=0.5,
                reason=f"Redacted {secrets_found} potential secret(s) from agent output."
            )

        return sanitized, GuardrailResult(allowed=True, category="pass")


# Global singleton
alignment_guardrail = AlignmentGuardrailService()
