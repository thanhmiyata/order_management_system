from fastapi import APIRouter, HTTPException, status
from typing import Dict, List, Optional
from pydantic import BaseModel
import uuid
import sys
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Adjust the import path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from temporalio.client import Client
from workflows.inventory_workflow import InventoryWorkflow
from models.inventory import (
    InventoryStatus,
    InventoryCheckRequest,
    InventoryUpdateRequest,
    InventoryResponse,
    InventoryUpdate,
    InventoryCheckItem,
    InventoryUpdateItem
)

load_dotenv()  # Load environment variables

router = APIRouter()

class ErrorResponse(BaseModel):
    detail: str

@router.post("/check", response_model=Dict[str, bool], responses={
    400: {"model": ErrorResponse, "description": "Invalid request"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def check_inventory(request: InventoryCheckRequest):
    try:
        logger.debug(f"Received inventory check request: {request.dict()}")
        client = await get_temporal_client()
        workflow_id = f"inventory_check_{uuid.uuid4()}"
        
        # Convert request items to InventoryUpdate objects
        inventory_updates = [
            InventoryUpdate(
                product_id=item.product_id,
                quantity_change=item.quantity,  # Use positive quantity for check
                order_id=workflow_id
            ).to_dict()
            for item in request.items
        ]
        logger.debug(f"Converted inventory updates: {inventory_updates}")
        
        # Start a workflow to check inventory
        logger.debug(f"Starting workflow with ID: {workflow_id}")
        handle = await client.start_workflow(
            InventoryWorkflow.run,
            args=[workflow_id, inventory_updates],  # Pass arguments as a list
            id=workflow_id,
            task_queue="inventory-task-queue"
        )
        
        # Wait for the workflow to complete
        logger.debug("Waiting for workflow result")
        result = await handle.result()
        logger.debug(f"Workflow result: {result}")
        
        if result["status"] == "FAILED":
            logger.error(f"Inventory check failed: {result.get('reason')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("reason", "Inventory check failed")
            )
            
        return {"available": result["status"] == "COMPLETED"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking inventory: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check inventory"
        )

@router.post("/update", response_model=InventoryResponse, responses={
    400: {"model": ErrorResponse, "description": "Invalid request"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def update_inventory(request: InventoryUpdateRequest):
    try:
        logger.debug(f"Received inventory update request: {request.dict()}")
        client = await get_temporal_client()
        
        # Convert request items to InventoryUpdate objects and add order_id
        inventory_updates = []
        for item in request.items:
            update = InventoryUpdate(
                product_id=item.product_id,
                quantity_change=item.quantity,
                order_id=request.order_id  # Add order_id to each update
            )
            inventory_updates.append(update.to_dict())
            
        logger.debug(f"Converted inventory updates: {inventory_updates}")
        
        # Generate workflow ID based on order_id
        workflow_id = f"inventory_{request.order_id}"
        logger.debug(f"Starting new workflow with ID: {workflow_id}")
        
        try:
            # Start workflow with correct parameters
            handle = await client.start_workflow(
                InventoryWorkflow.run,
                args=[workflow_id, inventory_updates],  # Pass workflow_id and inventory_updates
                id=workflow_id,
                task_queue="inventory-task-queue"
            )
            
            # Return immediate response
            return InventoryResponse(
                order_id=request.order_id,
                status="PENDING",
                details={"workflow_id": workflow_id},
                message="Inventory update workflow started, waiting for approval"
            )
            
        except Exception as e:
            logger.error(f"Error in workflow execution: {str(e)}")
            if "already started" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A workflow for this update is already in progress"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to execute inventory workflow: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating inventory: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update inventory: {str(e)}"
        )

@router.get("/status/{order_id}", response_model=InventoryResponse, responses={
    404: {"model": ErrorResponse, "description": "Inventory workflow not found"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def get_inventory_status(order_id: str):
    try:
        logger.debug(f"Getting inventory status for order: {order_id}")
        client = await get_temporal_client()
        workflow_id = f"inventory_{order_id}"
        
        try:
            handle = client.get_workflow_handle(workflow_id)
            status = await handle.query(InventoryWorkflow.get_status)
            details = await handle.query(InventoryWorkflow.get_reservation_details)
            logger.debug(f"Retrieved status: {status}, details: {details}")
            
            return InventoryResponse(
                order_id=order_id,
                status=status,
                details=details,
                message="Inventory status retrieved successfully"
            )
        except Exception as e:
            if "workflow not found" in str(e).lower():
                logger.error(f"Workflow not found: {workflow_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Inventory workflow not found"
                )
            raise
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting inventory status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve inventory status"
        )

@router.post("/{order_id}/approve", response_model=InventoryResponse, responses={
    404: {"model": ErrorResponse, "description": "Inventory workflow not found"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def approve_inventory_update(order_id: str):
    """Phê duyệt cập nhật tồn kho cho một đơn hàng"""
    try:
        logger.debug(f"Approving inventory update for order: {order_id}")
        client = await get_temporal_client()
        workflow_id = f"inventory_{order_id}"
        
        try:
            # Lấy handle của workflow
            handle = client.get_workflow_handle(workflow_id)
            
            # Kiểm tra trạng thái hiện tại
            current_status = await handle.query(InventoryWorkflow.get_status)
            if current_status in ["COMPLETED", "FAILED", "CANCELLED"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot approve inventory update in {current_status} state"
                )
            
            # Gửi signal commit
            await handle.signal(InventoryWorkflow.commit)
            logger.debug(f"Sent commit signal to workflow {workflow_id}")
            
            # Đợi workflow hoàn thành
            result = await handle.result()
            logger.debug(f"Workflow completed with result: {result}")
            
            return InventoryResponse(
                order_id=order_id,
                status=result["status"],
                details=result.get("details"),
                message="Inventory update approved and completed"
            )
            
        except Exception as e:
            if "workflow not found" in str(e).lower():
                logger.error(f"Workflow not found: {workflow_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Inventory update workflow not found"
                )
            raise
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving inventory update: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve inventory update: {str(e)}"
        )

@router.post("/{order_id}/cancel", response_model=InventoryResponse, responses={
    404: {"model": ErrorResponse, "description": "Inventory workflow not found"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def cancel_inventory_update(order_id: str):
    """Hủy cập nhật tồn kho cho một đơn hàng"""
    try:
        logger.debug(f"Cancelling inventory update for order: {order_id}")
        client = await get_temporal_client()
        workflow_id = f"inventory_{order_id}"
        
        try:
            # Lấy handle của workflow
            handle = client.get_workflow_handle(workflow_id)
            
            # Kiểm tra trạng thái hiện tại
            current_status = await handle.query(InventoryWorkflow.get_status)
            if current_status in ["COMPLETED", "FAILED", "CANCELLED"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot cancel inventory update in {current_status} state"
                )
            
            # Gửi signal cancel
            await handle.signal(InventoryWorkflow.cancel)
            logger.debug(f"Sent cancel signal to workflow {workflow_id}")
            
            # Đợi workflow hoàn thành
            result = await handle.result()
            logger.debug(f"Workflow completed with result: {result}")
            
            return InventoryResponse(
                order_id=order_id,
                status=result["status"],
                details=result.get("details"),
                message="Inventory update cancelled"
            )
            
        except Exception as e:
            if "workflow not found" in str(e).lower():
                logger.error(f"Workflow not found: {workflow_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Inventory update workflow not found"
                )
            raise
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling inventory update: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel inventory update: {str(e)}"
        )

async def get_temporal_client() -> Client:
    """Get or create Temporal client"""
    host = os.getenv("TEMPORAL_HOST", "localhost")
    port = os.getenv("TEMPORAL_PORT", "7233")
    
    try:
        logger.debug(f"Connecting to Temporal server at {host}:{port}")
        client = await Client.connect(f"{host}:{port}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Temporal server: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to workflow service"
        ) 