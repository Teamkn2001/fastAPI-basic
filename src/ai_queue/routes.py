from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
import asyncio

from .models import AIRequest, AIRequestResponse, AIRequestStatus, QueueStats
from .queue_manager import queue_manager

router = APIRouter(prefix="/ai", tags=["AI Queue Management"])

@router.post("/process", response_model=AIRequestResponse)
async def submit_ai_request(ai_request: AIRequest):
    """
    Submit an AI processing request to the queue.
    
    This endpoint demonstrates handling overload gracefully:
    - Requests are queued instead of immediately processed
    - Users get queue position and estimated wait time
    - No errors thrown when system is busy
    """
    try:
        response = await queue_manager.add_request(ai_request)
        return response
    except Exception as e:
        # Even in error cases, we provide helpful information
        return AIRequestResponse(
            request_id="",
            status="failed",
            message=f"Unable to process request: {str(e)}",
            created_at=datetime.now()
        )

@router.get("/status/{request_id}", response_model=AIRequestStatus)
async def get_request_status(request_id: str):
    """
    Check the status of a submitted AI request.
    
    Returns current status including:
    - Queue position (if queued)
    - Processing progress (if processing) 
    - Results (if completed)
    - Error details (if failed)
    """
    status = queue_manager.get_request_status(request_id)
    
    if not status:
        raise HTTPException(
            status_code=404, 
            detail="Request not found. It may have expired (requests are kept for 5 minutes after completion)."
        )
    
    return status

@router.get("/queue/stats", response_model=QueueStats)
async def get_queue_statistics():
    """
    Get current queue statistics and system health.
    
    Useful for monitoring system load and making scaling decisions.
    """
    return queue_manager.get_queue_stats()

@router.get("/health")
async def health_check():
    """
    Health check endpoint for the AI queue system.
    """
    stats = queue_manager.get_queue_stats()
    
    return {
        "status": "healthy" if stats.queue_health != "overloaded" else "degraded",
        "queue_health": stats.queue_health,
        "active_requests": stats.total_processing,
        "queued_requests": stats.total_queued,
        "message": "AI queue system is operational"
    }

# Stress testing endpoints (for development/testing only)
@router.post("/test/flood")
async def flood_test(
    num_requests: int = 50, 
    priority: str = "normal",
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Stress test endpoint - floods the system with multiple requests.
    
    Use this to test how the system handles overload scenarios.
    DO NOT use in production!
    """
    if num_requests > 200:
        raise HTTPException(status_code=400, detail="Maximum 200 requests allowed for testing")
    
    results = []
    
    for i in range(num_requests):
        ai_request = AIRequest(
            prompt=f"Test request #{i+1} - stress testing the queue system",
            priority=priority,
            user_id=f"test_user_{i}"
        )
        
        response = await queue_manager.add_request(ai_request)
        results.append({
            "request_number": i+1,
            "request_id": response.request_id,
            "status": response.status,
            "queue_position": response.queue_position
        })
    
    return {
        "message": f"Submitted {num_requests} test requests",
        "results": results,
        "queue_stats": queue_manager.get_queue_stats()
    }

@router.delete("/test/clear")
async def clear_queue():
    """
    Clear all queues (for testing only).
    DO NOT use in production!
    """
    # Clear all queues
    for queue in queue_manager.queues.values():
        queue.clear()
    
    # Clear processing and completed
    queue_manager.processing.clear()
    queue_manager.completed.clear()
    
    return {
        "message": "All queues cleared",
        "queue_stats": queue_manager.get_queue_stats()
    }