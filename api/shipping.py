from fastapi import APIRouter, HTTPException
from typing import Dict
import uuid

router = APIRouter()

# Mock shipping data
shippings = {}

@router.post("")
async def create_shipping(shipping_data: Dict):
    shipping_id = str(uuid.uuid4())
    shippings[shipping_id] = {
        "id": shipping_id,
        "order_id": shipping_data["order_id"],
        "status": shipping_data["status"],
        "address": shipping_data["address"],
        "tracking_number": shipping_data.get("tracking_number", "")
    }
    return {"id": shipping_id, "message": "Shipping created"}

@router.put("/{order_id}")
async def update_shipping(order_id: str, shipping_data: Dict):
    shipping = next((s for s in shippings.values() if s["order_id"] == order_id), None)
    if not shipping:
        raise HTTPException(status_code=404, detail="Shipping not found")
    
    shipping.update({
        "status": shipping_data["status"],
        "tracking_number": shipping_data.get("tracking_number", "")
    })
    return {"message": "Shipping updated"}

@router.get("/order/{order_id}")
async def get_shipping_by_order(order_id: str):
    shipping = next((s for s in shippings.values() if s["order_id"] == order_id), None)
    if not shipping:
        raise HTTPException(status_code=404, detail="Shipping not found")
    return shipping 