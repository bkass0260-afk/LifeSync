from pydantic import BaseModel
from typing import Optional

class Receipt(BaseModel):
    merchant_name: str
    total_amount: float
    date: str
    category: Optional[str] = None
from pydantic import BaseModel
from typing import Optional

class Receipt(BaseModel):
    merchant_name: str
    total_amount: float
    date: str
    category: Optional[str] = None
