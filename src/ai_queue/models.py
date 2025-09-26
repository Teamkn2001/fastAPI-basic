from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
import uuid

class AIRequest(BaseModel):
    prompt: str
    priority: Literal["high", "normal", "low"] = "normal"
    user_id: Optional[str] = None
    timeout: Optional[int] = 30  # seconds

class AIRequestResponse(BaseModel):
    request_id: str
    status: Literal["queued", "processing", "completed", "failed", "timeout"]
    message: str
    queue_position: Optional[int] = None
    estimated_wait_time: Optional[int] = None  # seconds
    created_at: datetime
    
class AIRequestStatus(BaseModel):
    request_id: str
    status: Literal["queued", "processing", "completed", "failed", "timeout"]
    progress: Optional[int] = None  # 0-100
    result: Optional[str] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None  # seconds
    created_at: datetime
    completed_at: Optional[datetime] = None

class QueueStats(BaseModel):
    total_queued: int
    total_processing: int
    total_completed: int
    total_failed: int
    avg_processing_time: float
    queue_health: Literal["healthy", "busy", "overloaded"]