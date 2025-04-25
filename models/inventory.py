from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
import uuid

class InventoryStatus(str, Enum):
    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    DISCONTINUED = "DISCONTINUED"
    PENDING = "PENDING"
    RESERVED = "RESERVED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class InventoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str
    name: str
    quantity: int
    reserved: int = 0
    status: InventoryStatus = InventoryStatus.IN_STOCK
    last_updated: datetime = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def available_quantity(self) -> int:
        return self.quantity - self.reserved
    
    def to_dict(self):
        return self.model_dump()

class InventoryUpdate(BaseModel):
    product_id: str
    quantity_change: int  # Positive for increase, negative for decrease
    order_id: Optional[str] = None
    reason: Optional[str] = None
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def to_dict(self) -> Dict:
        return {
            "product_id": self.product_id,
            "quantity_change": self.quantity_change,
            "order_id": self.order_id
        }

class InventoryCheckItem(BaseModel):
    product_id: str
    quantity: int

class InventoryCheckRequest(BaseModel):
    items: List[InventoryCheckItem]

class InventoryUpdateItem(BaseModel):
    product_id: str
    quantity: int

class InventoryUpdateRequest(BaseModel):
    order_id: str
    items: List[InventoryUpdateItem]

class InventoryResponse(BaseModel):
    order_id: str
    status: str
    details: Optional[Dict] = None
    message: Optional[str] = None 