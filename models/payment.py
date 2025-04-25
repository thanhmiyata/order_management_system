from pydantic import BaseModel, Field, validator
from enum import Enum
from datetime import datetime
import uuid
from typing import Optional
from pydantic import ConfigDict

class PaymentMethod(str, Enum):
    CREDIT_CARD = "CREDIT_CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    CASH = "CASH"
    E_WALLET = "E_WALLET"

class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

class Payment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    amount: float
    method: PaymentMethod
    status: PaymentStatus = PaymentStatus.PENDING
    transaction_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    description: Optional[str] = None
    
    # Cho phép các kiểu bất kỳ, bao gồm datetime
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def to_dict(self):
        return self.model_dump()
        
    @validator("created_at", "updated_at", pre=True)
    def parse_datetime(cls, value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value 