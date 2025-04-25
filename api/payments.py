from fastapi import APIRouter, HTTPException, status
from typing import Dict, Optional, List
from enum import Enum
import uuid
import sys
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
from decimal import Decimal
import asyncio

# Adjust the import path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from temporalio.client import Client
from workflows.payment_workflow import PaymentWorkflow
from models.payment import PaymentStatus, PaymentMethod

load_dotenv()  # Load environment variables

router = APIRouter()

# Initialize Temporal client
temporal_client: Client | None = None

# Remove startup event since we'll use the client from main.py
def get_temporal_client() -> Client:
    """Get the Temporal client from main app"""
    from api.main import temporal_client
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal service unavailable")
    return temporal_client

class PaymentCreate(BaseModel):
    order_id: str = Field(..., description="The ID of the order this payment is for")
    amount: Decimal = Field(..., gt=0, description="Payment amount, must be greater than 0")
    payment_method: PaymentMethod = Field(..., description="Payment method enum value")
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        return v

class PaymentResponse(BaseModel):
    id: str
    order_id: str
    amount: float
    method: str
    status: str
    created_at: str
    updated_at: str
    transaction_id: Optional[str]
    description: str

class ErrorResponse(BaseModel):
    detail: str

class PaymentAction(str, Enum):
    CANCEL = "cancel"
    REFUND = "refund"

class PaymentActionRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)

@router.post("", response_model=PaymentResponse, responses={
    400: {"model": ErrorResponse, "description": "Invalid request"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def create_payment(payment_data: PaymentCreate):
    try:
        client = get_temporal_client()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize payment service"
        )

    payment_id = str(uuid.uuid4())
    current_time = datetime.now().isoformat()
    
    payment = {
        "id": payment_id,
        "order_id": payment_data.order_id,
        "amount": float(payment_data.amount),
        "method": payment_data.payment_method.value,
        "status": PaymentStatus.PENDING.value,
        "created_at": current_time,
        "updated_at": current_time,
        "transaction_id": None,
        "description": "Payment initiated"
    }
    
    try:
        workflow_id = f"payment_{payment_id}"
        print(f"Starting payment workflow with ID: {workflow_id}")
        
        await client.start_workflow(
            PaymentWorkflow.run,
            payment,
            id=workflow_id,
            task_queue="payment-task-queue"
        )
        
        return PaymentResponse(**payment)
        
    except Exception as e:
        print(f"Error processing payment: {str(e)}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process payment"
        )

@router.get("/{payment_id}/status", response_model=Dict[str, str], responses={
    404: {"model": ErrorResponse, "description": "Payment not found"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def get_payment_status(payment_id: str):
    try:
        client = get_temporal_client()
        workflow_id = f"payment_{payment_id}"
        
        try:
            workflow = client.get_workflow_handle(workflow_id)
            payment_status = await workflow.query(PaymentWorkflow.getStatus)
            return {"status": payment_status}
        except Exception as e:
            if "workflow not found" in str(e).lower():
                raise HTTPException(
                    status_code=404,
                    detail="Payment not found"
                )
            print(f"Error getting payment status: {str(e)}", file=sys.stderr)
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve payment status"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting payment status: {str(e)}", file=sys.stderr)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve payment status"
        )

@router.get("/order/{order_id}", response_model=List[PaymentResponse], responses={
    404: {"model": ErrorResponse, "description": "No payments found for order"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def get_payment_by_order(order_id: str):
    client = get_temporal_client()
    
    try:
        # Try to find the payment workflow by searching for workflows with the order ID
        workflows = client.list_workflows(query=f"WorkflowId like 'payment-%' and order_id = '{order_id}'")
        async for workflow in workflows:
            handle = client.get_workflow_handle(workflow.workflow_id)
            details = await handle.query("getDetails")  # Use the exact query name we defined
            if details.get("order_id") == order_id:
                return details
        raise HTTPException(status_code=404, detail="Payment not found")
    except Exception as e:
        print(f"Error getting payment by order: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get payment: {str(e)}")

@router.post("/{payment_id}/{action}", response_model=PaymentResponse, responses={
    400: {"model": ErrorResponse, "description": "Invalid request"},
    404: {"model": ErrorResponse, "description": "Payment not found"},
    409: {"model": ErrorResponse, "description": "Invalid payment state for action"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def process_payment_action(
    payment_id: str,
    action: PaymentAction,
    action_data: PaymentActionRequest
):
    try:
        client = get_temporal_client()
        workflow_id = f"payment_{payment_id}"
        workflow = client.get_workflow_handle(workflow_id)
        
        # Check if workflow exists and get current status
        try:
            current_status = await workflow.query("getStatus")
        except Exception as e:
            if "workflow not found" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found"
                )
            raise
        
        # Validate payment state for the requested action
        if action == PaymentAction.CANCEL:
            if current_status != PaymentStatus.PENDING.value:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only pending payments can be cancelled"
                )
            signal_name = "cancelPayment"
        else:  # REFUND
            if current_status != PaymentStatus.COMPLETED.value:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only completed payments can be refunded"
                )
            signal_name = "refundPayment"
        
        # Send signal to workflow
        await workflow.signal(signal_name, action_data.reason)
        
        # Wait for a short time and get updated payment details
        await asyncio.sleep(1)
        payment_details = await workflow.query("getPaymentDetails")
        return PaymentResponse(**payment_details)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing payment {action}: {str(e)}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process payment {action}"
        )

@router.get("/{payment_id}", response_model=PaymentResponse, responses={
    404: {"model": ErrorResponse, "description": "Payment not found"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def get_payment_details(payment_id: str):
    try:
        client = get_temporal_client()
        workflow_id = f"payment_{payment_id}"
        
        try:
            workflow = client.get_workflow_handle(workflow_id)
            payment_details = await workflow.query(PaymentWorkflow.getPaymentDetails)
            return PaymentResponse(**payment_details)
        except Exception as e:
            if "workflow not found" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found"
                )
            raise
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting payment details: {str(e)}", file=sys.stderr)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve payment details"
        ) 