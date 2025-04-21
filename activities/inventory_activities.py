from temporalio import activity
from temporalio.exceptions import ApplicationError
import asyncio
import random
import sys
import os
from datetime import datetime

# Adjust the import path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.inventory import InventoryItem, InventoryUpdate, InventoryStatus

# Mô phỏng cơ sở dữ liệu kho hàng
_inventory_db = {
    "PROD-001": InventoryItem(
        id="INV-001",
        product_id="PROD-001",
        name="Laptop XPS 15",
        quantity=50,
        reserved=5
    ),
    "PROD-002": InventoryItem(
        id="INV-002",
        product_id="PROD-002",
        name="iPhone 15 Pro",
        quantity=100,
        reserved=10
    ),
    "PROD-003": InventoryItem(
        id="INV-003",
        product_id="PROD-003",
        name="Sony Headphones XM5",
        quantity=30,
        reserved=2
    ),
    "PROD-004": InventoryItem(
        id="INV-004",
        product_id="PROD-004",
        name="Samsung TV 65\"",
        quantity=12,
        reserved=2
    ),
    "PROD-005": InventoryItem(
        id="INV-005",
        product_id="PROD-005",
        name="Gaming Mouse",
        quantity=5,
        reserved=0
    )
}

async def _simulate_inventory_service(operation: str, product_id: str, duration_seconds: float = 1.0):
    """Mô phỏng gọi service kho hàng"""
    activity.logger.info(f"Connecting to inventory service for operation '{operation}' on product {product_id}")
    
    # Mô phỏng độ trễ mạng/xử lý
    await asyncio.sleep(duration_seconds)
    
    # Mô phỏng lỗi ngẫu nhiên (10% xác suất)
    if random.random() < 0.1:
        activity.logger.error(f"Inventory service error during {operation} for product {product_id}")
        return False
    
    activity.logger.info(f"Inventory service operation '{operation}' completed for product {product_id}")
    return True

@activity.defn
async def check_inventory(product_id: str, quantity: int) -> dict:
    """Kiểm tra xem sản phẩm có đủ số lượng trong kho không"""
    activity.logger.info(f"Checking inventory for product {product_id}, quantity {quantity}")
    
    # Mô phỏng thời gian kiểm tra
    await asyncio.sleep(0.5)
    
    # Kiểm tra sản phẩm có tồn tại không
    if product_id not in _inventory_db:
        activity.logger.error(f"Product {product_id} not found in inventory")
        raise ApplicationError(f"Product {product_id} not found", non_retryable=True)
    
    inventory_item = _inventory_db[product_id]
    available = inventory_item.quantity - inventory_item.reserved
    
    activity.logger.info(f"Product {product_id} has {available} available units (total: {inventory_item.quantity}, reserved: {inventory_item.reserved})")
    
    is_available = available >= quantity
    if not is_available:
        activity.logger.warning(f"Insufficient inventory for product {product_id}. Requested: {quantity}, Available: {available}")
    
    # Cập nhật trạng thái dựa trên số lượng hiện có
    status = inventory_item.status
    if inventory_item.quantity == 0:
        status = InventoryStatus.OUT_OF_STOCK
    elif inventory_item.quantity < 10:
        status = InventoryStatus.LOW_STOCK
    
    return {
        "product_id": product_id,
        "available": available,
        "is_available": is_available,
        "status": status,
        "checked_at": datetime.now().isoformat()
    }

@activity.defn
async def reserve_inventory(update: dict) -> dict:
    """Đặt trước hàng tồn kho cho một đơn hàng"""
    inventory_update = InventoryUpdate(**update)
    product_id = inventory_update.product_id
    quantity = abs(inventory_update.quantity_change)  # Đảm bảo giá trị dương
    
    activity.logger.info(f"Reserving {quantity} units of product {product_id} for order {inventory_update.order_id or 'N/A'}")
    
    # Kiểm tra sản phẩm có tồn tại không
    if product_id not in _inventory_db:
        activity.logger.error(f"Product {product_id} not found in inventory")
        raise ApplicationError(f"Product {product_id} not found", non_retryable=True)
    
    # Mô phỏng service call
    service_success = await _simulate_inventory_service("reserve", product_id, 1.5)
    if not service_success:
        activity.logger.error(f"Failed to connect to inventory service for product {product_id}")
        raise ValueError("Inventory service temporarily unavailable")
    
    # Kiểm tra và cập nhật inventory
    inventory_item = _inventory_db[product_id]
    available = inventory_item.quantity - inventory_item.reserved
    
    if available < quantity:
        activity.logger.error(f"Cannot reserve {quantity} units of product {product_id}. Only {available} available")
        raise ApplicationError(f"Insufficient inventory for product {product_id}", non_retryable=True)
    
    # Cập nhật dữ liệu đặt trước
    inventory_item.reserved += quantity
    inventory_item.last_updated = datetime.now()
    
    activity.logger.info(f"Successfully reserved {quantity} units of product {product_id}. New reserved count: {inventory_item.reserved}")
    
    return {
        "product_id": product_id,
        "quantity": quantity,
        "order_id": inventory_update.order_id,
        "status": "RESERVED",
        "reserved_at": datetime.now().isoformat()
    }

@activity.defn
async def update_inventory(update: dict) -> dict:
    """Cập nhật kho hàng (giảm hoặc tăng)"""
    inventory_update = InventoryUpdate(**update)
    product_id = inventory_update.product_id
    quantity_change = inventory_update.quantity_change
    
    activity.logger.info(f"Updating inventory for product {product_id} by {quantity_change} units for order {inventory_update.order_id or 'N/A'}")
    
    # Kiểm tra sản phẩm có tồn tại không
    if product_id not in _inventory_db:
        activity.logger.error(f"Product {product_id} not found in inventory")
        raise ApplicationError(f"Product {product_id} not found", non_retryable=True)
    
    # Mô phỏng service call
    service_success = await _simulate_inventory_service("update", product_id, 1.0)
    if not service_success:
        activity.logger.error(f"Failed to connect to inventory service for product {product_id}")
        raise ValueError("Inventory service temporarily unavailable")
    
    # Cập nhật inventory
    inventory_item = _inventory_db[product_id]
    
    # Nếu quantity_change âm (giảm kho) thì giảm cả reserved
    if quantity_change < 0:
        abs_change = abs(quantity_change)
        # Đảm bảo không vượt quá số lượng đã đặt trước
        if abs_change > inventory_item.reserved:
            activity.logger.warning(f"Attempting to reduce more than reserved for product {product_id}. Reserved: {inventory_item.reserved}, Change: {abs_change}")
            abs_change = inventory_item.reserved
        
        inventory_item.quantity += quantity_change  # Giảm vì quantity_change < 0
        inventory_item.reserved -= abs_change
        
        if inventory_item.quantity < 0:
            inventory_item.quantity = 0
            
    else:  # quantity_change > 0, tăng kho
        inventory_item.quantity += quantity_change
    
    # Cập nhật trạng thái
    if inventory_item.quantity == 0:
        inventory_item.status = InventoryStatus.OUT_OF_STOCK
    elif inventory_item.quantity < 10:
        inventory_item.status = InventoryStatus.LOW_STOCK
    else:
        inventory_item.status = InventoryStatus.IN_STOCK
    
    inventory_item.last_updated = datetime.now()
    
    activity.logger.info(f"Inventory updated for product {product_id}. New quantity: {inventory_item.quantity}, Reserved: {inventory_item.reserved}")
    
    return {
        "product_id": product_id,
        "quantity_change": quantity_change,
        "new_quantity": inventory_item.quantity,
        "new_reserved": inventory_item.reserved,
        "status": inventory_item.status,
        "updated_at": datetime.now().isoformat()
    }

@activity.defn
async def unreserve_inventory(update: dict) -> dict:
    """Hủy đặt trước hàng tồn kho"""
    inventory_update = InventoryUpdate(**update)
    product_id = inventory_update.product_id
    quantity = abs(inventory_update.quantity_change)  # Đảm bảo giá trị dương
    
    activity.logger.info(f"Unreserving {quantity} units of product {product_id} for order {inventory_update.order_id or 'N/A'}")
    
    # Kiểm tra sản phẩm có tồn tại không
    if product_id not in _inventory_db:
        activity.logger.error(f"Product {product_id} not found in inventory")
        raise ApplicationError(f"Product {product_id} not found", non_retryable=True)
    
    # Cập nhật inventory
    inventory_item = _inventory_db[product_id]
    
    # Đảm bảo không hủy đặt trước nhiều hơn số lượng đã đặt
    if quantity > inventory_item.reserved:
        activity.logger.warning(f"Attempting to unreserve more than reserved for product {product_id}. Reserved: {inventory_item.reserved}, Unreserve: {quantity}")
        quantity = inventory_item.reserved
    
    inventory_item.reserved -= quantity
    inventory_item.last_updated = datetime.now()
    
    activity.logger.info(f"Successfully unreserved {quantity} units of product {product_id}. New reserved count: {inventory_item.reserved}")
    
    return {
        "product_id": product_id,
        "quantity": quantity,
        "order_id": inventory_update.order_id,
        "status": "UNRESERVED",
        "unreserved_at": datetime.now().isoformat()
    }

# Tất cả các activities kho hàng
inventory_activities = [
    check_inventory,
    reserve_inventory,
    update_inventory,
    unreserve_inventory
] 