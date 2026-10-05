"""Customer Operations MCP server.

The tool contracts are available for discovery, but write behavior is
intentionally not implemented yet. Implement each handler only after adding
transaction handling, permission checks, confirmation, and audit logging.
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
                "name": "Operations.get_customer",
                "server_id": self.server_id,
                "description": "Read a customer account from the operations database.",
                "parameters": {
                    "type": "object",
                    "properties": {"customer_id": {"type": "string"}},
                    "required": ["customer_id"],
                },
            },
            {
                "name": "Operations.update_customer_status",
                "server_id": self.server_id,
                "description": "Future write: update customer status after confirmation.",
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
                "description": "Future write: add an auditable customer note after confirmation.",
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
                "name": "Operations.create_follow_up_task",
                "server_id": self.server_id,
                "description": "Future write: create a follow-up task after confirmation.",
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
                "name": "Operations.get_audit_history",
                "server_id": self.server_id,
                "description": "Future read: list changes made by operations agents.",
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
        customer = data_service.get_customer(customer_id)
        if not customer:
            return None
        if not account:
            account = CustomerAccount(
                customer_id=customer_id,
                company_name=customer.get("company_name", customer_id),
                status=customer.get("status", "Active"),
            )
            db.add(account)
            db.flush()
        return account

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        normalized = tool_name.lower().replace("operations.", "").strip()
        customer_id = str(arguments.get("customer_id", "")).strip().upper() if arguments.get("customer_id") else None
        db = SessionLocal()
        try:
            if normalized == "get_customer":
                customer_id = self._customer_id(arguments)
                customer = data_service.get_customer(customer_id)
                if not customer:
                    return {"found": False, "customer_id": customer_id,
                            "message": f"Customer '{customer_id}' was not found in the CRM data source."}
                account = self._ensure_account(db, customer_id)
                db.commit()
                return {"found": True, "customer": customer,
                        "operation_account": {"status": account.status, "open_tasks": len(account.tasks)}}

            if normalized == "update_customer_status":
                customer_id = self._customer_id(arguments)
                status = str(arguments.get("status", "")).strip()
                if not status:
                    raise ValueError("Missing required argument: 'status'")
                account = self._ensure_account(db, customer_id)
                if not account:
                    return {"success": False, "found": False, "error": f"Customer '{customer_id}' does not exist."}
                customer = data_service.get_customer(customer_id)
                old_status = customer.get("status", account.status)
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
                if not data_service.get_customer(customer_id):
                    return {"success": False, "found": False, "error": f"Customer '{customer_id}' does not exist."}
                timestamped = f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] {note}"
                data_service.append_customer_note(customer_id, timestamped)
                account = self._ensure_account(db, customer_id)
                db.add(CustomerOperationNote(
                    customer=account,
                    note=note,
                    created_by="customer_operations_agent",
                ))
                self._audit(db, tool_name, customer_id, "add_note", new_value=timestamped)
                db.commit()
                return {"success": True, "customer_id": customer_id, "note": timestamped,
                        "database_table": "customer_operation_notes"}

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
