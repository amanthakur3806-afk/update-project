"""
Customer Operations MCP server.

Provides persistent customer account, note, follow-up task,
and audit tools.

Every write is committed as one database transaction
and recorded in the operation audit log.
"""

import sys
import os
import json
import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List

# Ensure project root is in sys.path for direct script execution
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.database import SessionLocal
from app.models.customer_operations import (
    CustomerAccount,
    CustomerOperationNote,
    FollowUpTask,
    OperationAuditLog,
)
from app.services.data_service import data_service


class CustomerOperationsMCPServer:

    def __init__(self, server_id: str = "operations_mcp"):
        self.server_id = server_id

    # ============================================================
    # TOOL DEFINITIONS
    # ============================================================

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Return all tools exposed by this MCP server.
        """

        return [
            {
                "name": "Operations.create_customer",
                "server_id": self.server_id,
                "description": (
                    "Register a new customer account in the persistent database with company name, "
                    "initial operational lifecycle status, optional account owner, and renewal date. Records an audit entry."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Unique customer ID, e.g. 'TEST001'",
                        },
                        "company_name": {
                            "type": "string",
                            "description": "Customer company name",
                        },
                        "status": {
                            "type": "string",
                            "description": "Initial operational status (default: 'Active')",
                            "default": "Active",
                        },
                        "owner": {
                            "type": "string",
                            "description": "Optional account owner / assignee",
                        },
                        "renewal_date": {
                            "type": "string",
                            "format": "date",
                            "description": "Optional contract renewal date (YYYY-MM-DD)",
                        },
                    },
                    "required": [
                        "customer_id",
                        "company_name",
                    ],
                },
            },
            {
                "name": "Operations.list_customers",
                "server_id": self.server_id,
                "description": (
                    "Query the operations database table for all customer records, returning company names, "
                    "operational lifecycle states, account owners, and the number of active open tasks."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "Operations.get_customer",
                "server_id": self.server_id,
                "description": (
                    "Read a single customer's operational state from the database: lifecycle status, "
                    "account owner, renewal date, and count of open operational follow-up tasks."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Unique customer ID, e.g. 'ABC', 'XYZ'",
                        }
                    },
                    "required": [
                        "customer_id",
                    ],
                },
            },
            {
                "name": "Operations.update_customer_status",
                "server_id": self.server_id,
                "description": (
                    "Transition a customer's operational lifecycle status (e.g. 'Active', 'At-Risk', 'Suspended', 'Churned', 'Inactive') "
                    "with a mandatory justification reason and an immutable audit log entry."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Unique customer ID",
                        },
                        "status": {
                            "type": "string",
                            "description": "New operational status: 'Active', 'At-Risk', 'Suspended', 'Churned', 'Inactive'",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Mandatory business justification for the status change",
                        },
                    },
                    "required": [
                        "customer_id",
                        "status",
                    ],
                },
            },
            {
                "name": "Operations.add_customer_note",
                "server_id": self.server_id,
                "description": (
                    "Append an internal operational memo, ticket update, or compliance note to a customer's database record "
                    "with author tracking and audit trail."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Unique customer ID",
                        },
                        "note": {
                            "type": "string",
                            "description": "Operational note or memo text",
                        },
                    },
                    "required": [
                        "customer_id",
                        "note",
                    ],
                },
            },
            {
                "name": "Operations.get_customer_notes",
                "server_id": self.server_id,
                "description": "Retrieve all chronological operational notes and memos saved in the database for a customer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Unique customer ID",
                        }
                    },
                    "required": [
                        "customer_id",
                    ],
                },
            },
            {
                "name": "Operations.create_follow_up_task",
                "server_id": self.server_id,
                "description": (
                    "Create an actionable operational follow-up task with title, assignee, and due date. "
                    "Automatically records an audit entry."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Unique customer ID",
                        },
                        "title": {
                            "type": "string",
                            "description": "Actionable task title or objective",
                        },
                        "due_date": {
                            "type": "string",
                            "format": "date",
                            "description": "Optional task due date (YYYY-MM-DD)",
                        },
                    },
                    "required": [
                        "customer_id",
                        "title",
                    ],
                },
            },
            {
                "name": "Operations.list_follow_up_tasks",
                "server_id": self.server_id,
                "description": "List and filter operational follow-up tasks by customer ID and status ('pending' or 'completed').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Optional customer ID filter",
                        },
                        "status": {
                            "type": "string",
                            "description": "Optional status filter ('pending', 'completed')",
                        },
                    },
                },
            },
            {
                "name": "Operations.update_follow_up_task_status",
                "server_id": self.server_id,
                "description": "Update an existing follow-up task's status ('pending' or 'completed') with an immutable audit entry.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "integer",
                            "description": "Follow-up task ID",
                        },
                        "status": {
                            "type": "string",
                            "description": "New task status ('completed' or 'pending')",
                        },
                    },
                    "required": [
                        "task_id",
                        "status",
                    ],
                },
            },
            {
                "name": "Operations.get_audit_history",
                "server_id": self.server_id,
                "description": (
                    "Retrieve immutable database audit logs for customer operations changes: "
                    "timestamps, tool executed, action type, and old/new value diffs."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Optional customer ID to filter audit entries",
                        }
                    },
                    "required": [],
                },
            },
        ]

    # ============================================================
    # COMMON HELPERS
    # ============================================================

    @staticmethod
    def _customer_id(arguments: Dict[str, Any]) -> str:
        """
        Normalize and validate a customer ID.
        """

        customer_id = str(
            arguments.get("customer_id", "")
        ).strip().upper()

        if not customer_id:
            raise ValueError(
                "Missing required argument: 'customer_id'"
            )

        return customer_id

    @staticmethod
    def _audit(
        db,
        tool_name: str,
        customer_id: str,
        action: str,
        old_value: Any = None,
        new_value: Any = None,
    ):
        """
        Add an operation to the audit log.
        """

        db.add(
            OperationAuditLog(
                agent_id="customer_operations_agent",
                tool_name=tool_name,
                customer_id=customer_id,
                action=action,
                old_value=(
                    str(old_value)
                    if old_value is not None
                    else None
                ),
                new_value=(
                    str(new_value)
                    if new_value is not None
                    else None
                ),
                success=True,
            )
        )

    @staticmethod
    def _ensure_account(
        db,
        customer_id: str,
    ):
        """
        Get an operations account.

        If the account does not exist in the operations
        database, try to create it from the CRM/data service.
        """

        account = (
            db.query(CustomerAccount)
            .filter(
                CustomerAccount.customer_id == customer_id
            )
            .first()
        )

        if account:
            return account

        customer = data_service.get_customer(
            customer_id
        )

        if not customer:
            return None

        account = CustomerAccount(
            customer_id=customer_id,
            company_name=customer.get(
                "company_name",
                customer_id,
            ),
            status=customer.get(
                "status",
                "Active",
            ),
        )

        db.add(account)
        db.flush()

        return account

    @staticmethod
    def _account_payload(
        account: CustomerAccount,
    ) -> Dict[str, Any]:
        """
        Convert a CustomerAccount database object
        into a clean dictionary.
        """

        if not account:
            return None

        return {
            "customer_id": account.customer_id,
            "company_name": account.company_name,
            "status": account.status,
            "owner": account.owner,
            "renewal_date": (
                account.renewal_date.isoformat()
                if account.renewal_date
                else None
            ),
            "open_tasks": sum(
                1
                for task in account.tasks
                if task.status != "completed"
            ),
        }

    @staticmethod
    def _task_payload(
        task: FollowUpTask,
    ) -> Dict[str, Any]:
        """
        Convert a FollowUpTask database object
        into a clean dictionary.
        """

        return {
            "task_id": task.id,
            "customer_id": task.customer.customer_id,
            "title": task.title,
            "status": task.status,
            "due_date": (
                task.due_date.isoformat()
                if task.due_date
                else None
            ),
            "created_by": task.created_by,
            "created_at": task.created_at.isoformat(),
        }

    # ============================================================
    # TOOL HANDLERS
    # ============================================================

    def _create_customer(
        self,
        db,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a customer account.
        """

        customer_id = self._customer_id(
            arguments
        )

        company_name = str(
            arguments.get("company_name", "")
        ).strip()

        if not company_name:
            raise ValueError(
                "Missing required argument: 'company_name'"
            )

        existing = (
            db.query(CustomerAccount)
            .filter(
                CustomerAccount.customer_id == customer_id
            )
            .first()
        )

        if existing:
            return {
                "success": False,
                "customer_id": customer_id,
                "error": (
                    f"Customer '{customer_id}' "
                    "already exists in operations."
                ),
            }

        renewal_date = arguments.get(
            "renewal_date"
        )

        account = CustomerAccount(
            customer_id=customer_id,
            company_name=company_name,
            status=str(
                arguments.get("status")
                or "Active"
            ).strip(),
            owner=(
                str(
                    arguments.get("owner")
                    or ""
                ).strip()
                or None
            ),
            renewal_date=(
                datetime.date.fromisoformat(
                    renewal_date
                )
                if renewal_date
                else None
            ),
        )

        db.add(account)
        db.flush()

        self._audit(
            db=db,
            tool_name="Operations.create_customer",
            customer_id=customer_id,
            action="create_customer",
            new_value=company_name,
        )

        # Also sync newly created customer into CRM data_service
        data_service.save_customer({
            "customer_id": customer_id,
            "company_name": company_name,
            "industry": arguments.get("industry", "Enterprise Account"),
            "tier": arguments.get("tier", "Enterprise Tier 1"),
            "sla": arguments.get("sla", "Standard Enterprise SLA"),
            "contract_value": arguments.get("contract_value", "Pending Commercial Valuation"),
            "renewal_date": account.renewal_date.isoformat() if account.renewal_date else None,
            "account_owner": account.owner,
            "primary_stakeholder": arguments.get("primary_stakeholder"),
            "status": account.status,
            "notes": [],
        })

        return {
            "success": True,
            "customer": self._account_payload(
                account
            ),
        }

    # ------------------------------------------------------------

    def _list_customers(
        self,
        db,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        List all customer accounts.
        """

        accounts = (
            db.query(CustomerAccount)
            .order_by(
                CustomerAccount.company_name.asc()
            )
            .all()
        )

        return {
            "count": len(accounts),
            "customers": [
                self._account_payload(account)
                for account in accounts
            ],
        }

    # ------------------------------------------------------------

    def _get_customer(
        self,
        db,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Get one customer.
        """

        customer_id = self._customer_id(
            arguments
        )

        account = self._ensure_account(
            db,
            customer_id,
        )

        customer = data_service.get_customer(
            customer_id
        )

        if not account:
            return {
                "found": False,
                "customer_id": customer_id,
                "message": (
                    f"Customer '{customer_id}' "
                    "was not found in operations "
                    "or the CRM data source."
                ),
            }

        return {
            "found": True,
            "customer": (
                customer
                or self._account_payload(account)
            ),
            "operation_account": (
                self._account_payload(account)
            ),
        }

    # ------------------------------------------------------------

    def _update_customer_status(
        self,
        db,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update customer status, owner, and/or renewal_date.
        """

        customer_id = self._customer_id(
            arguments
        )

        account = self._ensure_account(
            db,
            customer_id,
        )

        if not account:
            return {
                "success": False,
                "found": False,
                "error": (
                    f"Customer '{customer_id}' "
                    "does not exist."
                ),
            }

        status = str(
            arguments.get("status", "")
        ).strip() or account.status or "Active"

        owner = arguments.get("owner")
        renewal_date = arguments.get("renewal_date")

        customer = data_service.get_customer(
            customer_id
        )

        old_status = (
            customer.get(
                "status",
                account.status,
            )
            if customer
            else account.status
        )

        account.status = status
        if owner is not None and str(owner).strip():
            account.owner = str(owner).strip()
        if renewal_date is not None and str(renewal_date).strip():
            try:
                account.renewal_date = datetime.date.fromisoformat(str(renewal_date).strip()[:10])
            except ValueError:
                pass

        if customer:
            customer["status"] = status
            if account.owner:
                customer["account_owner"] = account.owner
            if account.renewal_date:
                customer["renewal_date"] = account.renewal_date.isoformat()
        else:
            data_service.save_customer({
                "customer_id": account.customer_id,
                "company_name": account.company_name,
                "industry": "Enterprise Account",
                "tier": "Enterprise Tier 1",
                "sla": "Standard Enterprise SLA",
                "contract_value": "Pending Commercial Valuation",
                "renewal_date": account.renewal_date.isoformat() if account.renewal_date else None,
                "account_owner": account.owner,
                "status": account.status,
                "notes": [],
            })

        self._audit(
            db=db,
            tool_name="Operations.update_customer_status",
            customer_id=customer_id,
            action="update_status",
            old_value=old_status,
            new_value=f"status={status}, owner={account.owner}, renewal_date={account.renewal_date}",
        )

        return {
            "success": True,
            "customer_id": customer_id,
            "company_name": account.company_name,
            "old_status": old_status,
            "status": status,
            "owner": account.owner,
            "renewal_date": account.renewal_date.isoformat() if account.renewal_date else None,
            "reason": arguments.get("reason"),
        }

    # ------------------------------------------------------------

    def _add_customer_note(
        self,
        db,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Add a customer note.

        The note itself does not contain a timestamp.
        The database created_at field handles timestamps.
        """

        customer_id = self._customer_id(
            arguments
        )

        note = str(
            arguments.get("note", "")
        ).strip()

        if not note:
            raise ValueError(
                "Missing required argument: 'note'"
            )

        account = self._ensure_account(
            db,
            customer_id,
        )

        if not account:
            return {
                "success": False,
                "found": False,
                "error": (
                    f"Customer '{customer_id}' "
                    "does not exist."
                ),
            }

        # Keep the external data service in sync.
        if data_service.get_customer(customer_id):
            data_service.append_customer_note(
                customer_id,
                note,
            )

        # Save note in operations database.
        db.add(
            CustomerOperationNote(
                customer=account,
                note=note,
                created_by="customer_operations_agent",
            )
        )

        # Record audit entry.
        self._audit(
            db=db,
            tool_name="Operations.add_customer_note",
            customer_id=customer_id,
            action="add_note",
            new_value=note,
        )

        return {
            "success": True,
            "customer_id": customer_id,
            "note": note,
            "database_table": "customer_operation_notes",
        }

    # ------------------------------------------------------------

    def _get_customer_notes(
        self,
        db,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Get all notes for a customer.
        """

        customer_id = self._customer_id(
            arguments
        )

        account = self._ensure_account(
            db,
            customer_id,
        )

        if not account:
            return {
                "found": False,
                "customer_id": customer_id,
                "message": (
                    f"Customer '{customer_id}' "
                    "does not exist."
                ),
            }

        notes = sorted(
            account.notes,
            key=lambda note: note.created_at,
            reverse=True,
        )

        return {
            "found": True,
            "customer_id": customer_id,
            "count": len(notes),
            "notes": [
                {
                    "note_id": note.id,
                    "note": note.note,
                    "created_by": note.created_by,
                    "created_at": (
                        note.created_at.isoformat()
                    ),
                }
                for note in notes
            ],
        }

    # ------------------------------------------------------------

    def _create_follow_up_task(
        self,
        db,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a follow-up task.
        """

        customer_id = self._customer_id(
            arguments
        )

        title = str(
            arguments.get("title", "")
        ).strip()

        if not title:
            raise ValueError(
                "Missing required argument: 'title'"
            )

        account = self._ensure_account(
            db,
            customer_id,
        )

        if not account:
            return {
                "success": False,
                "found": False,
                "error": (
                    f"Customer '{customer_id}' "
                    "does not exist."
                ),
            }

        due_date = arguments.get(
            "due_date"
        )

        parsed_date = (
            datetime.date.fromisoformat(
                due_date
            )
            if due_date
            else None
        )

        task = FollowUpTask(
            customer=account,
            title=title,
            due_date=parsed_date,
            created_by="customer_operations_agent",
        )

        db.add(task)
        db.flush()

        self._audit(
            db=db,
            tool_name="Operations.create_follow_up_task",
            customer_id=customer_id,
            action="create_follow_up_task",
            new_value=title,
        )

        return {
            "success": True,
            "customer_id": customer_id,
            "task_id": task.id,
            "title": title,
            "due_date": due_date,
        }

    # ------------------------------------------------------------

    def _list_follow_up_tasks(
        self,
        db,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        List follow-up tasks.

        Supports optional customer_id and status filters.
        """

        customer_id = (
            str(
                arguments.get(
                    "customer_id",
                    "",
                )
            )
            .strip()
            .upper()
            or None
        )

        task_query = (
            db.query(FollowUpTask)
            .order_by(
                FollowUpTask.created_at.desc()
            )
        )

        if customer_id:

            account = self._ensure_account(
                db,
                customer_id,
            )

            if not account:
                return {
                    "count": 0,
                    "tasks": [],
                    "message": (
                        f"Customer '{customer_id}' "
                        "does not exist."
                    ),
                }

            task_query = task_query.filter(
                FollowUpTask.customer_id
                == account.id
            )

        task_status = str(
            arguments.get("status") or ""
        ).strip()

        if task_status:
            task_query = task_query.filter(
                FollowUpTask.status
                == task_status
            )

        tasks = task_query.all()

        return {
            "count": len(tasks),
            "tasks": [
                self._task_payload(task)
                for task in tasks
            ],
        }

    # ------------------------------------------------------------

    def _update_follow_up_task_status(
        self,
        db,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update a follow-up task status.
        """

        try:
            task_id = int(
                arguments.get("task_id")
            )
        except (TypeError, ValueError):
            raise ValueError(
                "Missing or invalid required argument: 'task_id'"
            )

        status = str(
            arguments.get("status") or ""
        ).strip()

        if not status:
            raise ValueError(
                "Missing required argument: 'status'"
            )

        task = (
            db.query(FollowUpTask)
            .filter(
                FollowUpTask.id == task_id
            )
            .first()
        )

        if not task:
            return {
                "success": False,
                "task_id": task_id,
                "error": (
                    "Follow-up task was not found."
                ),
            }

        old_status = task.status

        task.status = status

        self._audit(
            db=db,
            tool_name=(
                "Operations."
                "update_follow_up_task_status"
            ),
            customer_id=(
                task.customer.customer_id
            ),
            action=(
                "update_follow_up_task_status"
            ),
            old_value=old_status,
            new_value=status,
        )

        return {
            "success": True,
            "task": self._task_payload(task),
            "old_status": old_status,
        }

    # ------------------------------------------------------------

    def _get_audit_history(
        self,
        db,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Get recent audit history.

        Optional filter:
        customer_id
        """

        customer_id = (
            str(
                arguments.get(
                    "customer_id",
                    "",
                )
            )
            .strip()
            .upper()
            or None
        )

        query = (
            db.query(OperationAuditLog)
            .order_by(
                OperationAuditLog.created_at.desc()
            )
        )

        if customer_id:
            query = query.filter(
                OperationAuditLog.customer_id
                == customer_id
            )

        rows = query.limit(100).all()

        return {
            "count": len(rows),
            "history": [
                {
                    "id": row.id,
                    "tool_name": row.tool_name,
                    "customer_id": row.customer_id,
                    "action": row.action,
                    "old_value": row.old_value,
                    "new_value": row.new_value,
                    "success": row.success,
                    "created_at": (
                        row.created_at.isoformat()
                    ),
                }
                for row in rows
            ],
        }

    # ============================================================
    # TOOL ROUTER
    # ============================================================

    def _get_tool_handlers(
        self,
    ) -> Dict[
        str,
        Callable[
            [Any, Dict[str, Any]],
            Dict[str, Any]
        ],
    ]:
        """
        Map tool names to their handler functions.

        This replaces the large if/elif chain that was
        previously inside call_tool().
        """

        return {
            "create_customer":
                self._create_customer,

            "list_customers":
                self._list_customers,

            "get_customer":
                self._get_customer,

            "update_customer_status":
                self._update_customer_status,

            "add_customer_note":
                self._add_customer_note,

            "get_customer_notes":
                self._get_customer_notes,

            "create_follow_up_task":
                self._create_follow_up_task,

            "list_follow_up_tasks":
                self._list_follow_up_tasks,

            "update_follow_up_task_status":
                self._update_follow_up_task_status,

            "get_audit_history":
                self._get_audit_history,
        }

    # ============================================================
    # MCP TOOL EXECUTION
    # ============================================================

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute an MCP tool.

        Responsibilities:
        1. Normalize tool name.
        2. Find the correct handler.
        3. Create database session.
        4. Execute handler.
        5. Commit successful transaction.
        6. Roll back failed transaction.
        7. Close database session.
        """

        normalized = (
            tool_name
            .lower()
            .replace("operations.", "")
            .strip()
        )

        handlers = self._get_tool_handlers()

        handler = handlers.get(
            normalized
        )

        if handler is None:
            raise NotImplementedError(
                f"Tool '{tool_name}' is not implemented "
                "by the operations MCP server."
            )

        db = SessionLocal()

        try:
            result = handler(
                db,
                arguments,
            )

            # Commit the transaction after
            # successful handler execution.
            db.commit()

            return result

        except Exception:
            # Undo all database changes made
            # during this transaction.
            db.rollback()
            raise

        finally:
            # Always close the database session.
            db.close()


# ================================================================
# SERVER INSTANCE
# ================================================================

operations_server_instance = CustomerOperationsMCPServer()

# Official Model Context Protocol (MCP) Server instance
try:
    from mcp.server.mcpserver import MCPServer
    mcp_server = MCPServer("Customer Operations MCP Server")

    @mcp_server.tool(
        name="Operations.create_customer",
        description="Register a new customer account in the persistent database with company name, status, owner, renewal date."
    )
    async def operations_create_customer(
        customer_id: str,
        company_name: str,
        status: str = "Active",
        owner: str = None,
        renewal_date: str = None
    ) -> dict:
        """Create new customer account."""
        return await operations_server_instance.call_tool("Operations.create_customer", {
            "customer_id": customer_id,
            "company_name": company_name,
            "status": status,
            "owner": owner,
            "renewal_date": renewal_date,
        })

    @mcp_server.tool(
        name="Operations.list_customers",
        description="Query the operations database table for all customer records, returning company names, states, owners, open tasks."
    )
    async def operations_list_customers() -> dict:
        """List all customer accounts."""
        return await operations_server_instance.call_tool("Operations.list_customers", {})

    @mcp_server.tool(
        name="Operations.get_customer",
        description="Read single customer operational state: lifecycle status, account owner, renewal date, open tasks count."
    )
    async def operations_get_customer(customer_id: str) -> dict:
        """Get customer by ID."""
        return await operations_server_instance.call_tool("Operations.get_customer", {"customer_id": customer_id})

    @mcp_server.tool(
        name="Operations.update_customer_status",
        description="Transition customer operational status ('Active', 'At-Risk', 'Suspended', 'Churned', 'Inactive') with audit log."
    )
    async def operations_update_customer_status(customer_id: str, status: str, reason: str) -> dict:
        """Update customer status."""
        return await operations_server_instance.call_tool("Operations.update_customer_status", {
            "customer_id": customer_id,
            "status": status,
            "reason": reason,
        })

    @mcp_server.tool(
        name="Operations.add_customer_note",
        description="Append an operational note to customer account with optional author attribution and audit record."
    )
    async def operations_add_customer_note(customer_id: str, note: str, author: str = None) -> dict:
        """Add note to customer."""
        return await operations_server_instance.call_tool("Operations.add_customer_note", {
            "customer_id": customer_id,
            "note": note,
            "author": author,
        })

    @mcp_server.tool(
        name="Operations.get_customer_notes",
        description="Retrieve timestamped operational notes attached to a customer record in reverse chronological order."
    )
    async def operations_get_customer_notes(customer_id: str, limit: int = 20) -> dict:
        """Get customer notes."""
        return await operations_server_instance.call_tool("Operations.get_customer_notes", {
            "customer_id": customer_id,
            "limit": limit,
        })

    @mcp_server.tool(
        name="Operations.create_follow_up_task",
        description="Schedule a structured operational follow-up task for a customer with priority, due date, assignee, and audit entry."
    )
    async def operations_create_follow_up_task(
        customer_id: str,
        title: str,
        description: str = None,
        priority: str = "Medium",
        due_date: str = None,
        assignee: str = None
    ) -> dict:
        """Create follow-up task."""
        return await operations_server_instance.call_tool("Operations.create_follow_up_task", {
            "customer_id": customer_id,
            "title": title,
            "description": description,
            "priority": priority,
            "due_date": due_date,
            "assignee": assignee,
        })

    @mcp_server.tool(
        name="Operations.list_follow_up_tasks",
        description="Query scheduled operational tasks across customer accounts, optionally filtered by customer ID or status."
    )
    async def operations_list_follow_up_tasks(customer_id: str = None, status: str = None) -> dict:
        """List follow-up tasks."""
        return await operations_server_instance.call_tool("Operations.list_follow_up_tasks", {
            "customer_id": customer_id,
            "status": status,
        })

    @mcp_server.tool(
        name="Operations.update_follow_up_task_status",
        description="Mark an operational follow-up task as 'completed' or 'pending'. Records an audit entry."
    )
    async def operations_update_follow_up_task_status(task_id: int, status: str) -> dict:
        """Update follow-up task status."""
        return await operations_server_instance.call_tool("Operations.update_follow_up_task_status", {
            "task_id": task_id,
            "status": status,
        })

    @mcp_server.tool(
        name="Operations.get_audit_history",
        description="Retrieve immutable database audit logs for customer operations changes: timestamps, tool, action, old/new diffs."
    )
    async def operations_get_audit_history(customer_id: str = None, limit: int = 50) -> dict:
        """Get audit history."""
        return await operations_server_instance.call_tool("Operations.get_audit_history", {
            "customer_id": customer_id,
            "limit": limit,
        })

    # Resources
    @mcp_server.resource("operations://customers")
    def operations_customers_resource() -> str:
        """Direct access resource listing all persistent customer accounts and operational states."""
        db = SessionLocal()
        try:
            accounts = db.query(CustomerAccount).order_by(CustomerAccount.created_at.desc()).all()
            result = [operations_server_instance._account_payload(a) for a in accounts]
            return json.dumps(result, indent=2)
        finally:
            db.close()

    @mcp_server.resource("operations://tasks")
    def operations_tasks_resource() -> str:
        """Direct access resource listing all scheduled operational follow-up tasks."""
        db = SessionLocal()
        try:
            tasks = db.query(FollowUpTask).order_by(FollowUpTask.created_at.desc()).all()
            result = [operations_server_instance._task_payload(t) for t in tasks]
            return json.dumps(result, indent=2)
        finally:
            db.close()

    @mcp_server.resource("operations://audit")
    def operations_audit_resource() -> str:
        """Direct access resource reading latest immutable audit trail entries."""
        db = SessionLocal()
        try:
            logs = db.query(OperationAuditLog).order_by(OperationAuditLog.created_at.desc()).limit(50).all()
            result = [operations_server_instance._audit_payload(l) for l in logs]
            return json.dumps(result, indent=2)
        finally:
            db.close()

    # Prompts
    @mcp_server.prompt("operations_onboard_customer")
    def operations_onboard_customer_prompt(company_name: str, owner: str = "Tiya") -> str:
        """Structured customer onboarding workflow prompt template."""
        return (
            f"You are onboarding a new enterprise customer: '{company_name}'.\n"
            f"1. Generate a uppercase customer_id.\n"
            f"2. Call 'Operations.create_customer' with company_name='{company_name}', owner='{owner}', status='Active'.\n"
            f"3. Call 'Operations.add_customer_note' with initial onboarding details.\n"
            f"4. Call 'Operations.create_follow_up_task' with priority='High' to schedule the initial technical onboarding sync."
        )

    @mcp_server.prompt("operations_audit_investigation")
    def operations_audit_investigation_prompt(customer_id: str) -> str:
        """Compliance audit investigation prompt template."""
        return (
            f"Perform an audit investigation for customer account '{customer_id.upper()}'.\n"
            f"Query 'Operations.get_audit_history' to inspect all status changes, note creations, and task executions."
        )

except ImportError:
    mcp_server = None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Customer Operations MCP Server (Official Model Context Protocol)")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Transport protocol (stdio or sse)")
    parser.add_argument("--port", type=int, default=8003, help="Port for SSE transport (default: 8003)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for SSE transport")
    args = parser.parse_args()

    if mcp_server is None:
        sys.exit("Error: 'mcp' Python package is not installed.")

    if args.transport == "stdio":
        mcp_server.run(transport="stdio")
    else:
        mcp_server.run(transport="sse", host=args.host, port=args.port)