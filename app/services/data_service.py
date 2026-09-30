"""
Data Service
============
Manages dynamic business data for CRM and Analytics.

Key Architecture Principles:
  1. Source code contains NO hardcoded business data.
  2. In Demo Mode, loads from external `demo_data/` JSON fixtures.
  3. In Real Mode, starts empty or loads from configured data paths.
  4. ZERO SILENT FALLBACKS: If a customer or metric is missing/deleted,
     returns explicit "not found" / "no data configured" instead of fabricating data.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.config import settings

logger = logging.getLogger("data_service")


class DataService:
    """
    Central repository for dynamic CRM customer records, analytics metrics,
    and customer chronological event timelines.
    """

    def __init__(self):
        self._customers: Dict[str, Dict[str, Any]] = {}
        self._metrics: Dict[str, Dict[str, Any]] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = {}
        self._demo_mode: bool = settings.DEMO_MODE

        # Auto-load demo data on init if Demo Mode is enabled
        if self._demo_mode:
            self.load_demo_data()

    @property
    def demo_mode(self) -> bool:
        return self._demo_mode

    def set_demo_mode(self, enabled: bool):
        """Toggle between Demo Mode and Real Mode."""
        self._demo_mode = enabled
        if enabled:
            if not self._customers:
                self.load_demo_data()
        else:
            # Real Mode must not retain records loaded from demo fixtures.
            self.clear_all()

    # ----------------------------------------------------------------------
    # External Demo Data Ingestion
    # ----------------------------------------------------------------------

    def load_demo_data(self) -> Dict[str, int]:
        """
        Load external demo fixtures from `demo_data/` into memory.
        Returns record counts.
        """
        demo_dir = settings.BASE_DIR / "demo_data"

        crm_file = demo_dir / "crm" / "customers.json"
        metrics_file = demo_dir / "analytics" / "metrics.json"
        history_file = demo_dir / "analytics" / "history.json"

        loaded_counts = {"customers": 0, "metrics": 0, "history": 0}

        if crm_file.exists():
            try:
                with open(crm_file, "r", encoding="utf-8") as f:
                    self._customers = json.load(f)
                    loaded_counts["customers"] = len(self._customers)
            except Exception as e:
                logger.error(f"Failed to load demo CRM data: {e}")

        if metrics_file.exists():
            try:
                with open(metrics_file, "r", encoding="utf-8") as f:
                    self._metrics = json.load(f)
                    loaded_counts["metrics"] = len(self._metrics)
            except Exception as e:
                logger.error(f"Failed to load demo Analytics metrics: {e}")

        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    self._history = json.load(f)
                    loaded_counts["history"] = sum(len(v) for v in self._history.values())
            except Exception as e:
                logger.error(f"Failed to load demo Analytics history: {e}")

        logger.info(f"DataService loaded demo fixtures: {loaded_counts}")
        return loaded_counts

    def clear_all(self):
        """Clear all loaded business data to simulate an empty fresh install."""
        self._customers.clear()
        self._metrics.clear()
        self._history.clear()
        logger.info("DataService cleared all records.")

    # ----------------------------------------------------------------------
    # CRM Operations
    # ----------------------------------------------------------------------

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Look up a customer record by ID. Returns None if not found."""
        if not customer_id:
            return None
        return self._customers.get(customer_id.strip().upper())

    def search_customers(self, query: str) -> List[Dict[str, Any]]:
        """Search customers by ID, company name, or industry."""
        if not query:
            return []
        q = query.lower().strip()
        matches = []
        for cust in self._customers.values():
            if (
                q in cust.get("customer_id", "").lower()
                or q in cust.get("company_name", "").lower()
                or q in cust.get("industry", "").lower()
            ):
                matches.append(cust)
        return matches

    def list_customers(self) -> List[Dict[str, Any]]:
        """List all loaded customer records."""
        return list(self._customers.values())

    def save_customer(self, customer: Dict[str, Any]) -> str:
        """Add or update a customer record."""
        cid = customer.get("customer_id", "").strip().upper()
        if not cid:
            raise ValueError("customer_id is required")
        self._customers[cid] = customer
        return cid

    def delete_customer(self, customer_id: str) -> bool:
        """Delete a customer record. Returns True if existed and deleted."""
        cid = customer_id.strip().upper()
        if cid in self._customers:
            del self._customers[cid]
            return True
        return False

    def append_customer_note(self, customer_id: str, note_entry: str) -> bool:
        """Append an operational note to customer notes list."""
        cid = customer_id.strip().upper()
        if cid in self._customers:
            if "notes" not in self._customers[cid]:
                self._customers[cid]["notes"] = []
            self._customers[cid]["notes"].append(note_entry)
            return True
        return False

    # ----------------------------------------------------------------------
    # Analytics Operations
    # ----------------------------------------------------------------------

    def get_metrics(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Look up metrics for a customer. Returns None if not found."""
        if not customer_id:
            return None
        return self._metrics.get(customer_id.strip().upper())

    def list_all_metrics(self) -> List[Dict[str, Any]]:
        """List all customer metrics."""
        return list(self._metrics.values())

    def save_metrics(self, customer_id: str, metrics: Dict[str, Any]):
        """Save or update metrics for a customer."""
        cid = customer_id.strip().upper()
        metrics["customer_id"] = cid
        self._metrics[cid] = metrics

    def delete_metrics(self, customer_id: str) -> bool:
        """Delete metrics for a customer."""
        cid = customer_id.strip().upper()
        if cid in self._metrics:
            del self._metrics[cid]
            return True
        return False

    def get_history(self, customer_id: str, months: int = 3) -> List[Dict[str, Any]]:
        """Get chronological event timeline for customer."""
        cid = customer_id.strip().upper()
        return self._history.get(cid, [])

    def append_history_event(self, customer_id: str, event: Dict[str, Any]):
        """Append an event to customer history."""
        cid = customer_id.strip().upper()
        if cid not in self._history:
            self._history[cid] = []
        self._history[cid].append(event)


# Global singleton instance
data_service = DataService()
