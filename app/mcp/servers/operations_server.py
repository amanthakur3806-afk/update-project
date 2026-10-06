"""Customer Operations MCP server.

Provides persistent customer account, note, follow-up task, and audit tools.
Every write is committed as one database transaction and recorded in the
operation audit log.
"""
import datetime
from typing import Any, Dict, List

from app.database import SessionLocal
from app.models.customer_operations import (
    CustomerAccount, CustomerOperationNote, FollowUpTask, OperationAuditLog,
)
from app.services.data_service import data_service


class CustomerOperationsMCPServer:
    def __init__(self, server_id: str = "operations_mcp"):
        self.server_id = server_id

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "Operations.create_customer",
                "server_id": self.server_id,
                "description": "Create a persistent operations customer account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string", "description": "Unique customer ID"},
                        "company_name": {"type": "string", "description": "Customer company name"},
                        "status": {"type": "string", "description": "Initial status", "default": "Active"},
                        "owner": {"type": "string", "description": "Optional account owner"},
                        "renewal_date": {"type": "string", "format": "date", "description": "Optional renewal date"},
                    },
                    "required": ["customer_id", "company_name"],
                },
            },
            {
                "name": "Operations.list_customers",
                "server_id": self.server_id,
                "description": "List persistent operations customer accounts.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "Operations.get_customer",
                "server_id": self.server_id,
                "description": "Read one customer account and its open task count.",
                "parameters": {
                    "type": "object",
                    "properties": {"customer_id": {"type": "string"}},
                    "required": ["customer_id"],
                },
            },
            {
                "name": "Operations.update_customer_status",
                "server_id": self.server_id,
                "description": "Update customer status and add an audit entry.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "status": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["customer_id", "status"],
                },
            },
            {
                "name": "Operations.add_customer_note",
                "server_id": self.server_id,
                "description": "Add a persistent customer note and audit entry.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "note": {"type": "string"},
                    },
                    "required": ["customer_id", "note"],
                },
            },
            {
                "name": "Operations.get_customer_notes",
                "server_id": self.server_id,
                "description": "List notes saved for one customer.",
                "parameters": {
                    "type": "object",
                    "properties": {"customer_id": {"type": "string", "description": "Unique customer ID"}},
                    "required": ["customer_id"],
                },
            },
            {
                "name": "Operations.create_follow_up_task",
                "server_id": self.server_id,
                "description": "Create a persistent follow-up task and audit entry.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "title": {"type": "string"},
                        "due_date": {"type": "string", "format": "date"},
                    },
                    "required": ["customer_id", "title"],
                },
            },
            {
                "name": "Operations.list_follow_up_tasks",
                "server_id": self.server_id,
                "description": "List follow-up tasks, optionally for one customer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string", "description": "Optional customer ID"},
                        "status": {"type": "string", "description": "Optional task status filter"},
                    },
                },
            },
            {
                "name": "Operations.update_follow_up_task_status",
                "server_id": self.server_id,
                "description": "Change a follow-up task status and add an audit entry.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer", "description": "Follow-up task ID"},
                        "status": {"type": "string", "description": "New task status"},
                    },
                    "required": ["task_id", "status"],
                },
            },
            {
                "name": "Operations.get_audit_history",
                "server_id": self.server_id,
                "description": "List recent customer operations audit entries.",
                "parameters": {
                    "type": "object",
                    "properties": {"customer_id": {"type": "string"}},
                    "required": [],
                },
            },
        ]

    @staticmethod
    def _customer_id(arguments: Dict[str, Any]) -> str:
        customer_id = str(arguments.get("customer_id", "")).strip().upper()
        if not customer_id:
            raise ValueError("Missing required argument: 'customer_id'")
        return customer_id

    @staticmethod
    def _audit(db, tool_name, customer_id, action, old_value=None, new_value=None):
        db.add(OperationAuditLog(
            agent_id="customer_operations_agent", tool_name=tool_name,
            customer_id=customer_id, action=action,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            success=True,
        ))

    @staticmethod
    def _ensure_account(db, customer_id: str):
        account = db.query(CustomerAccount).filter(CustomerAccount.customer_id == customer_id).first()
        if account:
            return account
        customer = data_service.get_customer(customer_id)
        if not customer:
            return None
        account = CustomerAccount(
            customer_id=customer_id,
            company_name=customer.get("company_name", customer_id),
            status=customer.get("status", "Active"),
        )
        db.add(account)
        db.flush()
        return account

    @staticmethod
    def _account_payload(account: CustomerAccount) -> Dict[str, Any]:
        if not CustomerAccount:
            return None
        return {
            "customer_id": account.customer_id,
            "company_name": account.company_name,
            "status": account.status,
            "owner": account.owner,
            "renewal_date": account.renewal_date.isoformat() if account.renewal_date else None,
            "open_tasks": sum(1 for task in account.tasks if task.status != "completed"),
        }

    @staticmethod
    def _task_payload(task: FollowUpTask) -> Dict[str, Any]:
        return {
            "task_id": task.id,
            "customer_id": task.customer.customer_id,
            "title": task.title,
            "status": task.status,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "created_by": task.created_by,
            "created_at": task.created_at.isoformat(),
        }

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        normalized = tool_name.lower().replace("operations.", "").strip()
        customer_id = str(arguments.get("customer_id", "")).strip().upper() if arguments.get("customer_id") else None
        db = SessionLocal()
        try:
            if normalized == "create_customer":
                customer_id = self._customer_id(arguments)
                company_name = str(arguments.get("company_name", "")).strip()
                if not company_name:
                    raise ValueError("Missing required argument: 'company_name'")
                if db.query(CustomerAccount).filter(CustomerAccount.customer_id == customer_id).first():
                    return {"success": False, "customer_id": customer_id,
                            "error": f"Customer '{customer_id}' already exists in operations."}
                renewal_date = arguments.get("renewal_date")
                account = CustomerAccount(
                    customer_id=customer_id,
                    company_name=company_name,
                    status=str(arguments.get("status") or "Active").strip(),
                    owner=str(arguments.get("owner") or "").strip() or None,
                    renewal_date=datetime.date.fromisoformat(renewal_date) if renewal_date else None,
                )
                db.add(account)
                db.flush()
                self._audit(db, tool_name, customer_id, "create_customer", new_value=company_name)
                db.commit()
                return {"success": True, "customer": self._account_payload(account)}

            if normalized == "list_customers":
                accounts = db.query(CustomerAccount).order_by(CustomerAccount.company_name.asc()).all()
                return {"count": len(accounts), "customers": [self._account_payload(account) for account in accounts]}

            if normalized == "get_customer":
                customer_id = self._customer_id(arguments)
                account = self._ensure_account(db, customer_id)
                customer = data_service.get_customer(customer_id)
                if not account:
                    return {"found": False, "customer_id": customer_id,
                            "message": f"Customer '{customer_id}' was not found in operations or the CRM data source."}
                db.commit()
                return {"found": True, "customer": customer or self._account_payload(account),
                        "operation_account": self._account_payload(account)}

            if normalized == "update_customer_status":
                customer_id = self._customer_id(arguments)
                status = str(arguments.get("status", "")).strip()
                if not status:
                    raise ValueError("Missing required argument: 'status'")
                account = self._ensure_account(db, customer_id)
                if not account:
                    return {"success": False, "found": False, "error": f"Customer '{customer_id}' does not exist."}
                customer = data_service.get_customer(customer_id)
                old_status = customer.get("status", account.status) if customer else account.status
                if customer:
                    customer["status"] = status
                account.status = status
                self._audit(db, tool_name, customer_id, "update_status", old_status, status)
                db.commit()
                return {"success": True, "customer_id": customer_id, "old_status": old_status,
                        "status": status, "reason": arguments.get("reason")}

            if normalized == "add_customer_note":
                customer_id = self._customer_id(arguments)
                note = str(arguments.get("note", "")).strip()
                if not note:
                    raise ValueError("Missing required argument: 'note'")
                account = self._ensure_account(db, customer_id)
                if not account:
                    return {"success": False, "found": False, "error": f"Customer '{customer_id}' does not exist."}
                if data_service.get_customer(customer_id):
                    data_service.append_customer_note(customer_id)
                db.add(CustomerOperationNote(
                    customer=account,
                    note=note,
                    created_by="customer_operations_agent",
                ))
                self._audit(db, tool_name, customer_id, "add_note")
                db.commit()
                return {"success": True, "customer_id": customer_id, "note": timestamped,
                        "database_table": "customer_operation_notes"}

            if normalized == "get_customer_notes":
                customer_id = self._customer_id(arguments)
                account = self._ensure_account(db, customer_id)
                if not account:
                    return {"found": False, "customer_id": customer_id,
                            "message": f"Customer '{customer_id}' does not exist."}
                notes = sorted(account.notes, key=lambda note: note.created_at, reverse=True)
                return {"found": True, "customer_id": customer_id, "count": len(notes), "notes": [
                    {"note_id": note.id, "note": note.note, "created_by": note.created_by,
                     "created_at": note.created_at.isoformat()} for note in notes
                ]}

            if normalized == "create_follow_up_task":
                customer_id = self._customer_id(arguments)
                title = str(arguments.get("title", "")).strip()
                if not title:
                    raise ValueError("Missing required argument: 'title'")
                account = self._ensure_account(db, customer_id)
                if not account:
                    return {"success": False, "found": False, "error": f"Customer '{customer_id}' does not exist."}
                due_date = arguments.get("due_date")
                parsed_date = datetime.date.fromisoformat(due_date) if due_date else None
                task = FollowUpTask(customer=account, title=title, due_date=parsed_date,
                                    created_by="customer_operations_agent")
                db.add(task)
                db.flush()
                self._audit(db, tool_name, customer_id, "create_follow_up_task", new_value=title)
                db.commit()
                return {"success": True, "customer_id": customer_id, "task_id": task.id,
                        "title": title, "due_date": due_date}

            if normalized == "list_follow_up_tasks":
                task_query = db.query(FollowUpTask).order_by(FollowUpTask.created_at.desc())
                if customer_id:
                    account = self._ensure_account(db, customer_id)
                    if not account:
                        return {"count": 0, "tasks": [], "message": f"Customer '{customer_id}' does not exist."}
                    task_query = task_query.filter(FollowUpTask.customer_id == account.id)
                task_status = str(arguments.get("status") or "").strip()
                if task_status:
                    task_query = task_query.filter(FollowUpTask.status == task_status)
                tasks = task_query.all()
                return {"count": len(tasks), "tasks": [self._task_payload(task) for task in tasks]}

            if normalized == "update_follow_up_task_status":
                try:
                    task_id = int(arguments.get("task_id"))
                except (TypeError, ValueError):
                    raise ValueError("Missing or invalid required argument: 'task_id'")
                status = str(arguments.get("status") or "").strip()
                if not status:
                    raise ValueError("Missing required argument: 'status'")
                task = db.query(FollowUpTask).filter(FollowUpTask.id == task_id).first()
                if not task:
                    return {"success": False, "task_id": task_id, "error": "Follow-up task was not found."}
                old_status = task.status
                task.status = status
                self._audit(db, tool_name, task.customer.customer_id, "update_follow_up_task_status",
                            old_status, status)
                db.commit()
                return {"success": True, "task": self._task_payload(task), "old_status": old_status}

            if normalized == "get_audit_history":
                query = db.query(OperationAuditLog).order_by(OperationAuditLog.created_at.desc())
                if customer_id:
                    query = query.filter(OperationAuditLog.customer_id == customer_id)
                rows = query.limit(100).all()
                return {"count": len(rows), "history": [
                    {"id": row.id, "tool_name": row.tool_name, "customer_id": row.customer_id,
                     "action": row.action, "old_value": row.old_value, "new_value": row.new_value,
                     "success": row.success, "created_at": row.created_at.isoformat()} for row in rows]}

            raise NotImplementedError(f"Tool '{tool_name}' is not implemented by the operations MCP server.")
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


operations_server_instance = CustomerOperationsMCPServer()
