"""
Data Management Endpoints
=========================
APIs to inspect, import, and delete CRM and Analytics datasets dynamically.
Enables evaluators to verify:
  - Zero Silent Fallbacks: deleting customer ABC immediately causes CRM.get_customer to report not found.
  - Adding new customers without touching Python source code.
  - Reloading demo fixtures.
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.data_service import data_service

router = APIRouter(prefix="/data", tags=["Data Management"])


class CustomerCreate(BaseModel):
    customer_id: str
    company_name: str
    tier: str
    industry: str
    status: str = "Active"
    account_executive: str
    technical_contact: str
    contract_value: str
    contract_start: str
    contract_renewal: str
    sla_tier: str
    sla_response_time: str
    notes: List[str] = []


class MetricsUpdate(BaseModel):
    arr: int
    monthly_recurring_revenue: int
    churn_risk_score: float
    nps_score: int
    active_users: int
    api_calls_last_30d: int
    error_rate_percentage: float
    open_tickets_count: int
    average_ticket_resolution_hours: float
    sla_compliance_rate: str
    health_status: str


# --- CRM Endpoints ---

@router.get("/crm/customers", summary="List all active CRM customers")
def list_customers():
    return data_service.list_customers()


@router.get("/crm/customers/{customer_id}", summary="Get customer by ID")
def get_customer(customer_id: str):
    cust = data_service.get_customer(customer_id)
    if not cust:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found in CRM data source."
        )
    return cust


@router.post("/crm/customers", status_code=status.HTTP_201_CREATED, summary="Add or update a CRM customer")
def create_or_update_customer(customer: CustomerCreate):
    cid = data_service.save_customer(customer.model_dump())
    return {"success": True, "customer_id": cid, "message": "Customer record saved."}


@router.delete("/crm/customers/{customer_id}", summary="Delete a CRM customer (Test Zero Silent Fallback)")
def delete_customer(customer_id: str):
    existed = data_service.delete_customer(customer_id)
    if not existed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' does not exist in CRM."
        )
    return {"success": True, "customer_id": customer_id, "message": "Customer deleted from CRM data source."}


# --- Analytics Endpoints ---

@router.get("/analytics/metrics", summary="List all customer metrics")
def list_metrics():
    return data_service.list_all_metrics()


@router.get("/analytics/metrics/{customer_id}", summary="Get metrics for a customer")
def get_metrics(customer_id: str):
    m = data_service.get_metrics(customer_id)
    if not m:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analytics metrics found for customer '{customer_id}'."
        )
    return m


@router.post("/analytics/metrics/{customer_id}", summary="Update metrics for a customer")
def update_metrics(customer_id: str, payload: MetricsUpdate):
    data_service.save_metrics(customer_id, payload.model_dump())
    return {"success": True, "customer_id": customer_id.upper(), "message": "Metrics updated."}


@router.delete("/analytics/metrics/{customer_id}", summary="Delete metrics for customer (Test Zero Silent Fallback)")
def delete_metrics(customer_id: str):
    existed = data_service.delete_metrics(customer_id)
    if not existed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No metrics for customer '{customer_id}'."
        )
    return {"success": True, "customer_id": customer_id, "message": "Customer metrics deleted from analytics store."}


# --- Demo Lifecycle Endpoints ---

@router.post("/demo/reload", summary="Reload external demo fixtures from demo_data/")
def reload_demo_data():
    counts = data_service.load_demo_data()
    return {"success": True, "status": "reloaded", "records_loaded": counts}


@router.post("/demo/clear", summary="Clear all business data (simulate fresh install / empty state)")
def clear_all_data():
    data_service.clear_all()
    return {"success": True, "status": "cleared", "message": "All CRM and Analytics records cleared."}
