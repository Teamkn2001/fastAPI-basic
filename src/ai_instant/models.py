from pydantic import BaseModel
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime

class InstantAIRequest(BaseModel):
    prompt: str
    priority: Literal["instant", "fast", "normal"] = "normal"
    user_id: Optional[str] = None
    max_response_time: Optional[int] = None  # seconds
    
class InstantResponse(BaseModel):
    success: bool
    result: str
    response_time: float
    source: Literal["azure_ai", "deduplication", "fallback", "error", "batch_error"]
    metadata: Dict[str, Any] = {}
    timestamp: datetime = datetime.now()

class BatchRequest(BaseModel):
    requests: List[InstantAIRequest]
    batch_id: Optional[str] = None

class BatchResponse(BaseModel):
    success: bool
    batch_id: str
    total_requests: int
    results: List[InstantResponse]
    total_processing_time: float
    avg_time_per_request: float
    optimizations_applied: List[str] = []