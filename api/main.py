from fastapi import FastAPI, HTTPException, BackgroundTasks
from temporalio.client import Client, WorkflowFailureError, WorkflowHandle
from temporalio import workflow
from temporalio.common import RetryPolicy
import os
from dotenv import load_dotenv
from typing import Dict
import uuid
import asyncio
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Assuming models are defined in ../models/order.py relative to this file
# Adjust the import path if your structure differs
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.order import Order, OrderStatus, OrderItem # Import models
# from workflows.order_workflow import OrderWorkflow # Import cũ
from workflows.order_workflow import OrderApprovalWorkflow # Import workflow mới
from api.inventory import router as inventory_router
from api.payments import router as payments_router
from api.shipping import router as shipping_router

load_dotenv() # Load environment variables from .env file

app = FastAPI()

# Include routers
app.include_router(inventory_router, prefix="/inventory", tags=["inventory"])
app.include_router(payments_router, prefix="/payments", tags=["payments"])
app.include_router(shipping_router, prefix="/shipping", tags=["shipping"])

# Temporal client initialization
temporal_client: Client | None = None

@app.on_event("startup")
async def startup_event():
    global temporal_client
    host = os.getenv("TEMPORAL_HOST", "localhost")
    port = os.getenv("TEMPORAL_PORT", "7233")
    namespace = "default"  # Use default namespace
    try:
        temporal_client = await Client.connect(f"{host}:{port}", namespace=namespace)
        print(f"Connected to Temporal server at {host}:{port} in namespace '{namespace}'")
    except Exception as e:
        print(f"Failed to connect to Temporal: {e}")
        temporal_client = None

@app.on_event("shutdown")
async def shutdown_event():
    # Không cần gọi close() vì Client không có phương thức này
    pass


def calculate_total_amount(items: list[OrderItem]) -> float:
    return sum(item.quantity * item.price for item in items)

# --- Helper Function to Get Workflow Handle ---
async def get_workflow_handle(order_id: str) -> WorkflowHandle:
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal service unavailable")
    workflow_id = f"order-{order_id}"
    
    # Add retry mechanism
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            # Get workflow handle with namespace
            handle = temporal_client.get_workflow_handle(
                workflow_id=workflow_id
            )
            
            # Test if workflow exists by describing it
            try:
                desc = await temporal_client.describe_workflow(workflow_id)
                if not desc:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    raise HTTPException(status_code=404, detail=f"Order workflow {workflow_id} not found.")
                
                # Get workflow handle with run_id
                handle = temporal_client.get_workflow_handle(
                    workflow_id=workflow_id,
                    run_id=desc.workflow_execution.run_id
                )
                return handle
                
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                logger.error(f"Failed to describe workflow: {e}")
                raise HTTPException(status_code=404, detail=f"Order workflow {workflow_id} not found: {e}")
                
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            logger.error(f"Failed to get workflow handle: {e}")
            raise HTTPException(status_code=404, detail=f"Order workflow {workflow_id} not found: {e}")
    
    raise HTTPException(status_code=404, detail=f"Order workflow {workflow_id} not found after {max_retries} attempts")

# --- API Endpoints ---

@app.post("/orders", status_code=202) # 202 Accepted: Request received, processing started
async def create_order(order_data: Dict):
    """Creates a new order and starts the OrderApprovalWorkflow."""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal service unavailable")

    # Basic validation (enhance as needed)
    if "customer_id" not in order_data or "items" not in order_data:
         raise HTTPException(status_code=400, detail="Missing customer_id or items")

    try:
        order_items = [OrderItem(**item) for item in order_data["items"]]
        total_amount = calculate_total_amount(order_items)
    except Exception as e: # Catch potential Pydantic validation errors
        raise HTTPException(status_code=400, detail=f"Invalid item data: {e}")

    order_id = str(uuid.uuid4())
    order_input = Order(
        id=order_id,
        customer_id=order_data["customer_id"],
        items=order_items,
        total_amount=total_amount,
        # status will be set by the workflow initially
    )

    try:
        # Start the workflow using temporal_client
        await temporal_client.start_workflow(
            OrderApprovalWorkflow.run,
            order_input.model_dump(),
            id=f"order-{order_id}",
            task_queue="order-task-queue"
        )
        return {"order_id": order_id, "message": "Order creation initiated (Approval Workflow)."}
    except Exception as e:
        # Log the error for debugging
        print(f"Error starting workflow for order {order_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate order creation workflow")


@app.get("/orders/{order_id}/status")
async def get_order_status(order_id: str):
    """Gets the current status of an order workflow."""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal service unavailable")
    
    workflow_id = f"order-{order_id}"
    try:
        # Get workflow handle directly with namespace
        handle = temporal_client.get_workflow_handle(
            workflow_id
        )
        
        # Try to get status from workflow state
        try:
            status = await handle.query("get_status")
            return {"status": status}
        except Exception as e:
            # If query fails, return a generic status
            return {"status": "UNKNOWN", "error": str(e)}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get order status: {e}")

@app.post("/orders/{order_id}/approve", status_code=202)
async def approve_order(order_id: str):
    """Sends an approval signal to the order workflow."""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal service unavailable")
    
    workflow_id = f"order-{order_id}"
    try:
        # Get workflow handle directly with namespace
        handle = temporal_client.get_workflow_handle(
            workflow_id
        )
        
        # Send approval signal
        await handle.signal("provide_decision", "approved")
        return {"message": "Approval signal sent"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send approval signal: {e}")

@app.post("/orders/{order_id}/reject", status_code=202)
async def reject_order(order_id: str):
    """Sends a rejection signal to the order workflow."""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal service unavailable")
    
    workflow_id = f"order-{order_id}"
    try:
        # Get workflow handle directly with namespace
        handle = temporal_client.get_workflow_handle(
            workflow_id
        )
        
        # Send rejection signal
        await handle.signal("provide_decision", "rejected")
        return {"message": "Rejection signal sent"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send rejection signal: {e}")

@app.post("/orders/{order_id}/cancel", status_code=202)
async def cancel_order(order_id: str):
    """Sends a cancellation signal to the order workflow."""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal service unavailable")
    
    workflow_id = f"order-{order_id}"
    try:
        # Get workflow handle directly with namespace
        handle = temporal_client.get_workflow_handle(
            workflow_id
        )
        
        # Send cancellation signal
        await handle.signal("cancel_order")
        return {"message": "Cancellation signal sent"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send cancellation signal: {e}")

# Add other endpoints as needed (e.g., get order details, list orders)

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "localhost")
    port = int(os.getenv("API_PORT", 8000))
    # Use reload=True for development convenience
    uvicorn.run("api.main:app", host=host, port=port, reload=True)
