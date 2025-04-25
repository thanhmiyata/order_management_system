from temporalio import workflow
from temporalio.client import Client
from fastapi import APIRouter, HTTPException, status
from models.order import OrderStatusResponse, OrderRequest
from workflows.order_workflow import OrderApprovalWorkflow
from utils.temporal import get_temporal_client

router = APIRouter()

@router.get("/{order_id}/status", response_model=OrderStatusResponse)
async def get_order_status(order_id: str):
    """Kiểm tra trạng thái đơn hàng"""
    try:
        # Lấy client Temporal
        client = await get_temporal_client()
        
        workflow_id = f"order-{order_id}"
        
        # Lấy handle của workflow
        handle = await client.get_workflow_handle(workflow_id)
        
        # Lấy trạng thái hiện tại
        status = await handle.query("get_status")
        
        return OrderStatusResponse(
            order_id=order_id,
            status=status
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order status: {str(e)}"
        ) 