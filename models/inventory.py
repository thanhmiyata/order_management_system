from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum
import uuid

class InventoryStatus(str, Enum):
    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    DISCONTINUED = "DISCONTINUED"

class InventoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str
    name: str
    quantity: int
    reserved: int = 0
    status: InventoryStatus = InventoryStatus.IN_STOCK
    last_updated: datetime = Field(default_factory=datetime.now)
    
    def available_quantity(self) -> int:
        return self.quantity - self.reserved
    
    def to_dict(self):
        return self.model_dump()

class InventoryUpdate(BaseModel):
    product_id: str
    quantity_change: int  # Positive for increase, negative for decrease
    order_id: Optional[str] = None
    reason: Optional[str] = None
    
    def to_dict(self):
        return self.model_dump() 