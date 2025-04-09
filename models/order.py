from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
import uuid

class OrderStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATION_PENDING = "VALIDATION_PENDING"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    AUTO_REJECTED = "AUTO_REJECTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

class OrderItem(BaseModel):
    product_id: str
    quantity: int
    price: float

class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str
    items: List[OrderItem]
    total_amount: float
    status: OrderStatus = OrderStatus.CREATED
    payment_id: Optional[str] = None
    shipping_id: Optional[str] = None
