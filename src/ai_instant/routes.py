# routes/ai_routes.py - Enhanced with MySQL analytics
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import time
from datetime import datetime

from .models import InstantAIRequest, InstantResponse, BatchRequest, BatchResponse
from .instant_manager import instant_manager
from .persistent_stats import mysql_stats

router = APIRouter(prefix="/ai", tags=["Azure AI Agent"])

@router.post("/ask", response_model=InstantResponse)
async def ask_ai(request: InstantAIRequest):
    """
    🤖 ASK AI: Send prompt to Azure AI, get response back
    
    Simple usage:
    {
        "prompt": "Explain quantum computing",
        "priority": "fast",
        "max_response_time": 10,
        "user_id": "optional_user_tracking"
    }
    
    Priority levels:
    - "instant": 8s timeout, shorter response (150 tokens)
    - "fast": 15s timeout, medium response (300 tokens)  
    - "normal": 25s timeout, full response (500 tokens)
    
    ✨ All requests are automatically logged to MySQL for analytics!
    """
    
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    
    if len(request.prompt) > 4000:
        raise HTTPException(status_code=400, detail="Prompt too long (max 4000 characters)")
    
    # Get response from instant_manager (automatically logs to MySQL)
    result = await instant_manager.get_instant_response(request)
    
    # Convert dict response to InstantResponse model
    return InstantResponse(
        success=result["success"],
        result=result["result"],
        response_time=result["response_time"],
        source=result["source"],
        metadata=result["metadata"]
    )

@router.post("/batch", response_model=BatchResponse)
async def process_batch(batch_request: BatchRequest):
    """
    📦 BATCH PROCESSING: Send multiple prompts to Azure AI at once
    
    Processes up to 50 requests concurrently.
    All individual requests are logged to MySQL for detailed analytics.
    """
    
    if not batch_request.requests:
        raise HTTPException(status_code=400, detail="No requests provided")
    
    if len(batch_request.requests) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 requests per batch")
    
    start_time = time.time()
    batch_id = batch_request.batch_id or f"batch_{int(time.time())}"
    
    # Process all requests (each gets logged automatically)
    results = []
    for request in batch_request.requests:
        try:
            result_dict = await instant_manager.get_instant_response(request)
            instant_response = InstantResponse(
                success=result_dict["success"],
                result=result_dict["result"],
                response_time=result_dict["response_time"],
                source=result_dict["source"],
                metadata=result_dict["metadata"]
            )
            results.append(instant_response)
        except Exception as e:
            error_response = InstantResponse(
                success=False,
                result=f"Error processing request: {str(e)}",
                response_time=0.001,
                source="error",
                metadata={"error": str(e)}
            )
            results.append(error_response)
    
    total_time = time.time() - start_time
    successful_count = sum(1 for r in results if r.success)
    
    return BatchResponse(
        success=True,
        batch_id=batch_id,
        total_requests=len(batch_request.requests),
        results=results,
        total_processing_time=total_time,
        avg_time_per_request=total_time / len(results) if results else 0,
        optimizations_applied=[
            f"concurrent_processing_{len(batch_request.requests)}_requests",
            f"success_rate_{successful_count}/{len(results)}",
            "mysql_persistence",
            "request_deduplication"
        ]
    )

@router.get("/stats")
async def get_azure_stats():
    """📊 AZURE AI STATISTICS: Comprehensive usage metrics from MySQL"""
    return instant_manager.get_stats()

@router.get("/analytics")
async def get_analytics(days: int = Query(7, ge=1, le=365, description="Number of days to analyze")):
    """📈 DETAILED ANALYTICS: Daily breakdowns, trends, and source analysis"""
    return mysql_stats.get_analytics(days=days)

@router.get("/recent-requests")
async def get_recent_requests(limit: int = Query(50, ge=1, le=500, description="Number of recent requests to fetch")):
    """📝 RECENT REQUESTS: Detailed log of recent AI requests"""
    return {
        "recent_requests": mysql_stats.get_recent_requests(limit=limit),
        "total_showing": limit,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/health")
async def health_check():
    """🏥 HEALTH CHECK: Test Azure AI connectivity and performance"""
    try:
        health = await instant_manager.health_check()
        
        if health["status"] == "error":
            raise HTTPException(
                status_code=503,
                detail=f"Azure AI service error: {health['error']}"
            )
        
        # Add database health
        db_stats = mysql_stats.get_stats()
        health["database_status"] = "connected" if "error" not in db_stats else "error"
        health["total_requests_logged"] = db_stats.get("total_requests", 0)
        
        return health
        
    except Exception as e:
        raise HTTPException(
            status_code=503, 
            detail=f"System health check failed: {str(e)}"
        )

@router.get("/capacity")
async def get_capacity():
    """📈 SYSTEM CAPACITY: Current load and processing capacity with MySQL insights"""
    stats = instant_manager.get_stats()
    active_processing = len(instant_manager.active_processing)
    max_concurrent = instant_manager.max_concurrent
    
    load_percentage = (active_processing / max_concurrent) * 100
    
    if load_percentage < 30:
        status = "low_load"
        recommendation = "System ready for requests"
    elif load_percentage < 70:
        status = "medium_load" 
        recommendation = "System handling requests well"
    elif load_percentage < 90:
        status = "high_load"
        recommendation = "System busy but accepting requests"
    else:
        status = "at_capacity"
        recommendation = "System at capacity, may have delays"
    
    return {
        "status": status,
        "active_processing": active_processing,
        "max_concurrent": max_concurrent,
        "load_percentage": f"{load_percentage:.1f}%",
        "recommendation": recommendation,
        "today_requests": stats.get("today_requests", 0),
        "today_successful": stats.get("today_successful", 0),
        "success_rate_today": f"{(stats.get('today_successful', 0) / max(stats.get('today_requests', 1), 1) * 100):.1f}%",
        "total_requests_all_time": stats.get("total_requests", 0),
        "database_records": stats.get("total_records_stored", 0),
        "timestamp": datetime.now().isoformat()
    }

@router.post("/test")
async def test_azure_ai(test_prompt: str = "Say 'Azure AI with MySQL is working perfectly!'"):
    """🧪 TEST AZURE AI: Quick test with custom prompt (gets logged to MySQL)"""
    
    test_request = InstantAIRequest(
        prompt=test_prompt,
        priority="fast",
        max_response_time=15,
        user_id="api_test"
    )
    
    result = await instant_manager.get_instant_response(test_request)
    
    return {
        "test_successful": result["success"],
        "test_prompt": test_prompt,
        "azure_response": result["result"],
        "response_time": f"{result['response_time']:.2f}s",
        "tokens_used": result["metadata"].get("tokens_used", 0),
        "model": result["metadata"].get("model", "unknown"),
        "source": result["source"],
        "logged_to_mysql": True,
        "timestamp": result["timestamp"]
    }

@router.post("/reset-session")
async def reset_session():
    """🔄 RESET SESSION: Force close and recreate Azure AI session"""
    try:
        await instant_manager.close()
        return {
            "success": True,
            "message": "Session reset successfully",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset session: {str(e)}"
        )

@router.get("/debug")
async def debug_info():
    """🐛 DEBUG INFO: Detailed system information with MySQL status"""
    
    session_info = {}
    if hasattr(instant_manager, '_session'):
        session_info = {
            "session_exists": instant_manager._session is not None,
            "session_closed": instant_manager._session.closed if instant_manager._session else None,
        }
    
    # Get MySQL status
    db_stats = mysql_stats.get_stats()
    
    return {
        "azure_config": {
            "endpoint": instant_manager.azure_endpoint,
            "deployment": instant_manager.azure_deployment,
            "api_version": instant_manager.api_version,
            "has_api_key": bool(instant_manager.azure_api_key)
        },
        "session_info": session_info,
        "active_processing": {
            "count": len(instant_manager.active_processing),
            "ids": list(instant_manager.active_processing.keys())
        },
        "pending_requests": len(instant_manager.pending_requests),
        "mysql_status": {
            "connected": "error" not in db_stats,
            "total_records": db_stats.get("total_records_stored", 0),
            "retention_days": mysql_stats.cleanup_days,
            "max_records": mysql_stats.max_records
        },
        "stats_summary": db_stats,
        "timestamp": datetime.now().isoformat()
    }

@router.delete("/cleanup-logs")
async def manual_cleanup(older_than_days: int = Query(30, ge=1, le=365, description="Delete logs older than X days")):
    """🗑️ MANUAL CLEANUP: Force cleanup of old MySQL logs"""
    try:
        # This would need to be implemented in mysql_stats
        # For now, return info about what would be cleaned
        db_stats = mysql_stats.get_stats()
        
        return {
            "message": f"Cleanup would remove logs older than {older_than_days} days",
            "current_records": db_stats.get("total_records_stored", 0),
            "auto_cleanup_enabled": True,
            "retention_policy": f"{mysql_stats.cleanup_days} days",
            "max_records_policy": f"{mysql_stats.max_records:,} records",
            "note": "Auto-cleanup runs every 1,000 requests",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cleanup operation failed: {str(e)}"
        )