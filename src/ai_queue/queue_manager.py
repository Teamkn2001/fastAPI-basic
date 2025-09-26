import asyncio
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict, deque
import logging

from .models import AIRequest, AIRequestResponse, AIRequestStatus, QueueStats

logger = logging.getLogger(__name__)

class AIQueueManager:
    def __init__(self, max_queue_size: int = 100, max_concurrent: int = 5):
        self.max_queue_size = max_queue_size
        self.max_concurrent = max_concurrent
        
        # Queue storage by priority
        self.queues = {
            "high": deque(),
            "normal": deque(), 
            "low": deque()
        }
        
        # Currently processing requests
        self.processing: Dict[str, dict] = {}
        
        # Completed requests (keep for 5 minutes)
        self.completed: Dict[str, AIRequestStatus] = {}
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "completed_requests": 0,
            "failed_requests": 0,
            "processing_times": deque(maxlen=100)  # Keep last 100 times
        }
        
        # Start background worker
        self._worker_task = None
        self.start_worker()
    
    def start_worker(self):
        """Start the background worker if not already running"""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())
    
    async def add_request(self, ai_request: AIRequest) -> AIRequestResponse:
        """Add a request to the appropriate queue"""
        
        # Check if queue is full
        total_queued = sum(len(queue) for queue in self.queues.values())
        if total_queued >= self.max_queue_size:
            return AIRequestResponse(
                request_id="",
                status="failed",
                message="Queue is full. System is overloaded. Please try again later.",
                created_at=datetime.now()
            )
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Create request data
        request_data = {
            "id": request_id,
            "request": ai_request,
            "created_at": datetime.now(),
            "status": "queued"
        }
        
        # Add to appropriate queue
        self.queues[ai_request.priority].append(request_data)
        self.stats["total_requests"] += 1
        
        # Calculate queue position
        queue_position = self._calculate_queue_position(request_id, ai_request.priority)
        estimated_wait = self._estimate_wait_time(queue_position)
        
        return AIRequestResponse(
            request_id=request_id,
            status="queued",
            message="Request added to queue successfully",
            queue_position=queue_position,
            estimated_wait_time=estimated_wait,
            created_at=datetime.now()
        )
    
    def get_request_status(self, request_id: str) -> Optional[AIRequestStatus]:
        """Get the current status of a request"""
        
        # Check if completed
        if request_id in self.completed:
            return self.completed[request_id]
        
        # Check if processing
        if request_id in self.processing:
            data = self.processing[request_id]
            progress = min(100, int((time.time() - data["started_at"]) / 10 * 100))  # Mock progress
            
            return AIRequestStatus(
                request_id=request_id,
                status="processing",
                progress=progress,
                created_at=data["created_at"]
            )
        
        # Check if in queue
        for priority, queue in self.queues.items():
            for i, item in enumerate(queue):
                if item["id"] == request_id:
                    position = self._calculate_queue_position(request_id, priority)
                    return AIRequestStatus(
                        request_id=request_id,
                        status="queued",
                        created_at=item["created_at"]
                    )
        
        return None
    
    def get_queue_stats(self) -> QueueStats:
        """Get current queue statistics"""
        total_queued = sum(len(queue) for queue in self.queues.values())
        total_processing = len(self.processing)
        
        # Calculate average processing time
        avg_time = 0.0
        if self.stats["processing_times"]:
            avg_time = sum(self.stats["processing_times"]) / len(self.stats["processing_times"])
        
        # Determine health status
        if total_queued > self.max_queue_size * 0.8:
            health = "overloaded"
        elif total_queued > self.max_queue_size * 0.5:
            health = "busy"
        else:
            health = "healthy"
        
        return QueueStats(
            total_queued=total_queued,
            total_processing=total_processing,
            total_completed=self.stats["completed_requests"],
            total_failed=self.stats["failed_requests"],
            avg_processing_time=avg_time,
            queue_health=health
        )
    
    def _calculate_queue_position(self, request_id: str, priority: str) -> int:
        """Calculate position in queue considering priority"""
        position = 1
        
        # Count high priority items first
        if priority in ["normal", "low"]:
            position += len(self.queues["high"])
        
        # Count normal priority items
        if priority == "low":
            position += len(self.queues["normal"])
        
        # Count items before this one in same priority
        for item in self.queues[priority]:
            if item["id"] == request_id:
                break
            position += 1
        
        return position
    
    def _estimate_wait_time(self, queue_position: int) -> int:
        """Estimate wait time based on queue position and avg processing time"""
        avg_time = 10  # Default 10 seconds
        if self.stats["processing_times"]:
            avg_time = sum(self.stats["processing_times"]) / len(self.stats["processing_times"])
        
        # Consider concurrent processing
        concurrent_factor = max(1, self.max_concurrent)
        estimated_seconds = (queue_position * avg_time) / concurrent_factor
        
        return int(estimated_seconds)
    
    async def _worker(self):
        """Background worker to process queued requests"""
        while True:
            try:
                # Process requests if we have capacity
                if len(self.processing) < self.max_concurrent:
                    request_data = self._get_next_request()
                    
                    if request_data:
                        # Start processing
                        asyncio.create_task(self._process_request(request_data))
                
                # Clean up old completed requests (older than 5 minutes)
                self._cleanup_completed()
                
                # Wait a bit before next iteration
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(5)
    
    def _get_next_request(self) -> Optional[dict]:
        """Get the next request to process (priority order)"""
        for priority in ["high", "normal", "low"]:
            if self.queues[priority]:
                return self.queues[priority].popleft()
        return None
    
    async def _process_request(self, request_data: dict):
        """Simulate processing an AI request"""
        request_id = request_data["id"]
        
        try:
            # Add to processing
            self.processing[request_id] = {
                "data": request_data,
                "started_at": time.time(),
                "created_at": request_data["created_at"]
            }
            
            # Simulate AI processing time (3-15 seconds)
            import random
            processing_time = random.uniform(3, 15)
            await asyncio.sleep(processing_time)
            
            # Simulate success/failure (90% success rate)
            success = random.random() > 0.1
            
            if success:
                result = f"AI processed: '{request_data['request'].prompt}' - Mock result generated successfully!"
                status = AIRequestStatus(
                    request_id=request_id,
                    status="completed",
                    result=result,
                    processing_time=processing_time,
                    created_at=request_data["created_at"],
                    completed_at=datetime.now()
                )
                self.stats["completed_requests"] += 1
            else:
                status = AIRequestStatus(
                    request_id=request_id,
                    status="failed",
                    error="Mock AI service error occurred",
                    processing_time=processing_time,
                    created_at=request_data["created_at"],
                    completed_at=datetime.now()
                )
                self.stats["failed_requests"] += 1
            
            # Store result
            self.completed[request_id] = status
            self.stats["processing_times"].append(processing_time)
            
        except Exception as e:
            logger.error(f"Error processing request {request_id}: {e}")
            status = AIRequestStatus(
                request_id=request_id,
                status="failed",
                error=str(e),
                created_at=request_data["created_at"],
                completed_at=datetime.now()
            )
            self.completed[request_id] = status
            self.stats["failed_requests"] += 1
        
        finally:
            # Remove from processing
            self.processing.pop(request_id, None)
    
    def _cleanup_completed(self):
        """Remove completed requests older than 5 minutes"""
        cutoff = datetime.now() - timedelta(minutes=5)
        to_remove = [
            req_id for req_id, status in self.completed.items()
            if status.completed_at and status.completed_at < cutoff
        ]
        
        for req_id in to_remove:
            del self.completed[req_id]

# Global instance
queue_manager = AIQueueManager()