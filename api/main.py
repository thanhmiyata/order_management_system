from fastapi import FastAPI, HTTPException, BackgroundTasks
from temporalio.client import Client, WorkflowFailureError
from temporalio.common import RetryPolicy
import os
from dotenv import load_dotenv
from typing import Dict
import uuid

# Assuming models are defined in ../models/order.py relative to this file
# Adjust the import path if your structure differs
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.order import Order, OrderStatus, OrderItem # Import models
# from workflows.order_workflow import OrderWorkflow # Import cũ
from workflows.order_workflow import OrderApprovalWorkflow # Import workflow mới

load_dotenv() # Load environment variables from .env file

app = FastAPI()

# Temporal client initialization (consider moving to a dependency injection pattern for larger apps)
temporal_client: Client | None = None

@app.on_event("startup")
async def startup_event():
    global temporal_client
    host = os.getenv("TEMPORAL_HOST", "localhost")
    port = os.getenv("TEMPORAL_PORT", "7233")
    try:
        temporal_client = await Client.connect(f"{host}:{port}")
        print(f"Connected to Temporal server at {host}:{port}")
    except Exception as e:
        print(f"Failed to connect to Temporal: {e}")
        # Decide how to handle connection failure - maybe raise an exception or retry
        temporal_client = None # Ensure client is None if connection fails


@app.on_event("shutdown")
async def shutdown_event():
    if temporal_client:
        await temporal_client.close()
        print("Temporal client disconnected.")


def calculate_total_amount(items: list[OrderItem]) -> float:
    return sum(item.quantity * item.price for item in items)

# --- Helper Function to Get Workflow Handle ---
async def get_workflow_handle(order_id: str) -> workflow.WorkflowHandle:
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal service unavailable")
    workflow_id = f"order-{order_id}"
    handle = await temporal_client.get_workflow_handle_for(OrderApprovalWorkflow.run, workflow_id=workflow_id)
    if not handle:
        raise HTTPException(status_code=404, detail=f"Order workflow {workflow_id} not found.")
    return handle

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
        # Start the workflow
        await temporal_client.start_workflow(
            OrderApprovalWorkflow.run, # Use the new workflow run method
            order_input.model_dump(), # Pass order data as argument
            id=f"order-{order_id}",
            task_queue="order-task-queue", # Needs to match the worker's task queue
        )
        return {"order_id": order_id, "message": "Order creation initiated (Approval Workflow)."}
    except Exception as e:
        # Log the error for debugging
        print(f"Error starting workflow for order {order_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate order creation workflow")


@app.get("/orders/{order_id}/status")
async def get_order_status(order_id: str):
    """Queries the workflow for the current status of an order."""
    try:
        handle = await get_workflow_handle(order_id)
        # Execute a query method named 'get_status'
        status = await handle.query(OrderApprovalWorkflow.get_status) # Use new workflow query
        return {"order_id": order_id, "status": status}

    except HTTPException as http_exc: # Re-raise known HTTP exceptions
        raise http_exc
    except Exception as e:
        print(f"Error querying workflow order-{order_id}: {e}")
        # Check if the error message indicates a failed workflow task state, which can happen transiently
        # or if the workflow failed permanently.
        if "Workflow Task in failed state" in str(e):
            raise HTTPException(status_code=503, detail="Workflow task failed. Status may be unavailable temporarily or workflow has failed.")
        raise HTTPException(status_code=500, detail="Failed to get order status")

@app.post("/orders/{order_id}/approve", status_code=202)
async def approve_order(order_id: str):
    """Sends an 'approved' signal to the order workflow."""
    try:
        handle = await get_workflow_handle(order_id)
        await handle.signal(OrderApprovalWorkflow.provide_decision, "approved") # Use new signal
        return {"order_id": order_id, "message": "Approval signal sent."}
    except HTTPException as http_exc:
        raise http_exc
    except WorkflowFailureError as e:
         print(f"Workflow failure during approval signal for order-{order_id}: {e}")
         raise HTTPException(status_code=400, detail=f"Failed to approve order: {e.cause}")
    except Exception as e:
        print(f"Error sending approval signal for workflow order-{order_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send approval signal")

@app.post("/orders/{order_id}/reject", status_code=202)
async def reject_order(order_id: str):
    """Sends a 'rejected' signal to the order workflow."""
    try:
        handle = await get_workflow_handle(order_id)
        await handle.signal(OrderApprovalWorkflow.provide_decision, "rejected") # Use new signal
        return {"order_id": order_id, "message": "Rejection signal sent."}
    except HTTPException as http_exc:
        raise http_exc
    except WorkflowFailureError as e:
         print(f"Workflow failure during rejection signal for order-{order_id}: {e}")
         raise HTTPException(status_code=400, detail=f"Failed to reject order: {e.cause}")
    except Exception as e:
        print(f"Error sending rejection signal for workflow order-{order_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send rejection signal")


@app.post("/orders/{order_id}/cancel", status_code=202)
async def cancel_order(order_id: str):
    """Sends a signal to the workflow to cancel the order."""
    try:
        handle = await get_workflow_handle(order_id)
        # Send a signal named 'cancel_order'
        await handle.signal(OrderApprovalWorkflow.cancel_order) # Use new workflow cancel signal
        return {"order_id": order_id, "message": "Order cancellation requested."}
    except HTTPException as http_exc:
        raise http_exc
    except WorkflowFailureError as e:
         # Handle cases where cancellation might fail (e.g., workflow already completed/failed)
         print(f"Workflow failure during cancellation signal for order-{order_id}: {e}")
         raise HTTPException(status_code=400, detail=f"Failed to cancel order: {e.cause}")
    except Exception as e:
        print(f"Error signalling cancellation for workflow order-{order_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to request order cancellation")

# Add other endpoints as needed (e.g., get order details, list orders)

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "localhost")
    port = int(os.getenv("API_PORT", 8000))
    # Use reload=True for development convenience
    uvicorn.run("api.main:app", host=host, port=port, reload=True)
