# src/ai_instant/instant_manager.py - Complete version with MySQL persistence
import asyncio
import aiohttp
import time
import uuid
import os
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
import sys

load_dotenv()

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from .persistent_stats import mysql_stats
except ImportError:
    try:
        from ai_instant.persistent_stats import mysql_stats
    except ImportError:
        print("⚠️ Could not import mysql_stats, creating fallback")
        # Create a dummy mysql_stats for fallback
        class DummyStatsManager:
            def log_request(self, **kwargs):
                print(f"📊 Request logged: {kwargs}")
            def get_stats(self):
                return {"error": "MySQL stats not available", "total_requests": 0}
        mysql_stats = DummyStatsManager()

class InstantAIManager:
    def __init__(self, max_concurrent: int = 20):
        self.max_concurrent = max_concurrent
        
        # Azure OpenAI Configuration
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
        self.api_version = "2024-02-01"
        
        if not self.azure_endpoint or not self.azure_api_key:
            raise ValueError("Missing Azure credentials!")
        
        self.azure_endpoint = self._clean_endpoint(self.azure_endpoint)
        
        # Processing tracking (in-memory, reset on restart)
        self.active_processing: Dict[str, dict] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}
        
        # MySQL stats manager
        self.persistent_stats = mysql_stats
        
        # In-memory stats (for quick access, gets updated from MySQL)
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens_used": 0,
            "avg_response_times": []
        }
        
        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        
        print("🚀 InstantAIManager initialized with MySQL persistence")
    
    def _clean_endpoint(self, endpoint: str) -> str:
        """Clean and validate the Azure endpoint URL"""
        if not endpoint:
            raise ValueError("Azure endpoint is empty")
        
        endpoint = endpoint.rstrip('/')
        
        if not endpoint.startswith('https://'):
            if endpoint.startswith('http://'):
                endpoint = endpoint.replace('http://', 'https://')
            else:
                endpoint = f"https://{endpoint}"
        
        # Extract base URL if full API URL was provided
        if '/openai/deployments/' in endpoint:
            base_url = endpoint.split('/openai/deployments/')[0]
            endpoint = base_url
        
        # Validate Azure endpoint format (both old and new formats)
        valid_patterns = [
            '.openai.azure.com',
            '.cognitiveservices.azure.com'
        ]
        
        is_valid = any(pattern in endpoint for pattern in valid_patterns)
        
        if not is_valid:
            raise ValueError(f"Invalid Azure endpoint format: {endpoint}")
        
        return endpoint
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session (thread-safe)"""
        async with self._session_lock:
            if self._session is None or self._session.closed:
                connector = aiohttp.TCPConnector(
                    limit=50,
                    limit_per_host=25,
                    keepalive_timeout=30,
                    enable_cleanup_closed=True
                )
                
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=aiohttp.ClientTimeout(total=30)
                )
            
            return self._session
    
    async def get_instant_response(self, request) -> dict:
        """Main method: Process request with Azure AI (with MySQL persistence)"""
        start_time = time.time()
        
        # Update in-memory counter
        self.stats["total_requests"] += 1
        
        try:
            # Strategy 1: Check deduplication
            request_hash = hash(f"{request.prompt}:{getattr(request, 'user_id', 'anonymous')}")
            
            if request_hash in self.pending_requests:
                try:
                    existing_result = await self.pending_requests[request_hash]
                    response_time = time.time() - start_time
                    
                    # Log to MySQL
                    self.persistent_stats.log_request(
                        prompt_hash=str(request_hash),
                        success=True,
                        response_time=response_time,
                        tokens_used=0,
                        source="deduplication",
                        priority=getattr(request, 'priority', 'normal'),
                        user_id=getattr(request, 'user_id', None)
                    )
                    
                    return {
                        "success": True,
                        "result": existing_result,
                        "response_time": response_time,
                        "source": "deduplication",
                        "metadata": {"deduplicated": True},
                        "timestamp": datetime.now().isoformat()
                    }
                except Exception:
                    pass
            
            # Strategy 2: Process with Azure AI
            if len(self.active_processing) < self.max_concurrent:
                return await self._process_with_azure(request, start_time, request_hash)
            
            # Strategy 3: Graceful fallback
            return self._graceful_fallback(request, start_time, request_hash)
            
        except Exception as e:
            response_time = time.time() - start_time
            self.stats["failed_requests"] += 1
            
            # Log error to MySQL
            self.persistent_stats.log_request(
                prompt_hash=str(hash(request.prompt)),
                success=False,
                response_time=response_time,
                tokens_used=0,
                source="error",
                priority=getattr(request, 'priority', 'normal'),
                user_id=getattr(request, 'user_id', None),
                error_message=str(e)
            )
            
            return {
                "success": False,
                "result": f"Error processing request: {str(e)}",
                "response_time": response_time,
                "source": "error",
                "metadata": {"error": str(e)},
                "timestamp": datetime.now().isoformat()
            }
    
    async def _process_with_azure(self, request, start_time: float, request_hash: int) -> dict:
        """Process request with Azure OpenAI using persistent session"""
        processing_id = str(uuid.uuid4())
        
        try:
            # Add to active processing
            self.active_processing[processing_id] = {
                "request": request,
                "start_time": start_time
            }
            
            # Create future for deduplication
            future = asyncio.Future()
            self.pending_requests[request_hash] = future
            
            # Call Azure OpenAI with persistent session
            azure_result = await self._call_azure_openai(request)
            
            processing_time = time.time() - start_time
            
            # Success - update in-memory stats
            self.stats["successful_requests"] += 1
            self.stats["total_tokens_used"] += azure_result.get("tokens_used", 0)
            self._update_response_time_stats(processing_time)
            
            # Log to MySQL
            self.persistent_stats.log_request(
                prompt_hash=str(request_hash),
                success=True,
                response_time=processing_time,
                tokens_used=azure_result.get("tokens_used", 0),
                source="azure_ai",
                priority=getattr(request, 'priority', 'normal'),
                user_id=getattr(request, 'user_id', None),
                model_used=azure_result.get("model", self.azure_deployment)
            )
            
            # Set result for deduplication
            if not future.done():
                future.set_result(azure_result["content"])
            
            return {
                "success": True,
                "result": azure_result["content"],
                "response_time": processing_time,
                "source": "azure_ai",
                "metadata": {
                    "processing_id": processing_id,
                    "tokens_used": azure_result.get("tokens_used", 0),
                    "model": azure_result.get("model", self.azure_deployment)
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.stats["failed_requests"] += 1
            
            # Log error to MySQL
            self.persistent_stats.log_request(
                prompt_hash=str(request_hash),
                success=False,
                response_time=processing_time,
                tokens_used=0,
                source="azure_ai",
                priority=getattr(request, 'priority', 'normal'),
                user_id=getattr(request, 'user_id', None),
                error_message=str(e)
            )
            
            # Set error for deduplication
            if 'future' in locals() and not future.done():
                future.set_exception(e)
            raise e
            
        finally:
            # Cleanup
            self.active_processing.pop(processing_id, None)
            self.pending_requests.pop(request_hash, None)
    
    def _graceful_fallback(self, request, start_time: float, request_hash: int) -> dict:
        """Provide graceful fallback when Azure is unavailable or at capacity"""
        
        response_time = time.time() - start_time
        current_load = len(self.active_processing)
        load_percentage = (current_load / self.max_concurrent) * 100
        
        if load_percentage >= 100:
            message = f"System is at full capacity ({current_load}/{self.max_concurrent} slots used). Please try again in a moment."
            fallback_reason = "capacity_full"
        else:
            message = "Unable to process request quickly. Please try again or use a simpler prompt."
            fallback_reason = "processing_timeout"
        
        # Log fallback to MySQL
        self.persistent_stats.log_request(
            prompt_hash=str(request_hash),
            success=False,
            response_time=response_time,
            tokens_used=0,
            source="fallback",
            priority=getattr(request, 'priority', 'normal'),
            user_id=getattr(request, 'user_id', None),
            error_message=f"Fallback: {fallback_reason}"
        )
        
        return {
            "success": False,
            "result": message,
            "response_time": response_time,
            "source": "fallback",
            "metadata": {
                "fallback_reason": fallback_reason,
                "current_load": f"{current_load}/{self.max_concurrent}",
                "load_percentage": f"{load_percentage:.1f}%",
                "suggestion": "Try again in 30-60 seconds"
            },
            "timestamp": datetime.now().isoformat()
        }
    
    async def _call_azure_openai(self, request) -> Dict:
        """Make actual call to Azure OpenAI API with persistent session"""
        
        # Build the complete URL
        url = f"{self.azure_endpoint}/openai/deployments/{self.azure_deployment}/chat/completions?api-version={self.api_version}"
        
        headers = {
            "Content-Type": "application/json",
            "api-key": self.azure_api_key
        }
        
        # Optimize payload based on priority
        priority = getattr(request, 'priority', 'normal')
        if priority == "instant":
            max_tokens = 150
            temperature = 0.3
            timeout_seconds = 8
        elif priority == "fast":
            max_tokens = 300
            temperature = 0.5
            timeout_seconds = 15
        else:
            max_tokens = 500
            temperature = 0.7
            timeout_seconds = 25
        
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant. Provide clear, accurate responses."
                },
                {
                    "role": "user",
                    "content": request.prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9
        }
        
        try:
            # Get the persistent session
            session = await self._get_session()
            
            # Make the request with specific timeout
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
            
            async with session.post(url, headers=headers, json=payload, timeout=timeout) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Azure API error {response.status}: {error_text}")
                
                data = await response.json()
                
                return {
                    "content": data["choices"][0]["message"]["content"].strip(),
                    "tokens_used": data["usage"]["total_tokens"],
                    "model": data.get("model", self.azure_deployment)
                }
        
        except asyncio.TimeoutError:
            raise Exception("Request timed out")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(f"API call failed: {str(e)}")
    
    def _update_response_time_stats(self, response_time: float):
        """Update response time statistics (in-memory)"""
        self.stats["avg_response_times"].append(response_time)
        
        # Keep only last 100 response times in memory
        if len(self.stats["avg_response_times"]) > 100:
            self.stats["avg_response_times"].pop(0)
    
    def get_stats(self) -> Dict:
        """Get comprehensive statistics from MySQL"""
        # Get MySQL stats (persistent, comprehensive)
        mysql_stats_data = self.persistent_stats.get_stats()
        
        # Add current in-memory info
        mysql_stats_data.update({
            "active_processing": len(self.active_processing),
            "max_concurrent": self.max_concurrent,
            "azure_deployment": self.azure_deployment,
            "session_status": "active" if (self._session and not self._session.closed) else "inactive"
        })
        
        return mysql_stats_data
    
    async def health_check(self) -> Dict:
        """Check Azure AI connectivity"""
        try:
            # Create a simple test request object
            class TestRequest:
                def __init__(self):
                    self.prompt = "Say 'Health check OK' if you're working"
                    self.priority = "fast"
                    self.user_id = "health_check"
            
            test_request = TestRequest()
            result = await self.get_instant_response(test_request)
            
            return {
                "status": "healthy" if result["success"] else "unhealthy",
                "azure_response": result["result"],
                "response_time": f"{result['response_time']:.2f}s",
                "timestamp": datetime.now().isoformat(),
                "mysql_logged": True
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def process_batch_requests(self, requests: List) -> List[Dict]:
        """Process multiple requests concurrently"""
        
        if len(requests) > 50:
            error_response = {
                "success": False,
                "result": "Batch too large. Maximum 50 requests per batch.",
                "response_time": 0.001,
                "source": "error",
                "metadata": {"error": "batch_size_exceeded"},
                "timestamp": datetime.now().isoformat()
            }
            return [error_response] * len(requests)
        
        # Process all requests concurrently
        tasks = [asyncio.create_task(self.get_instant_response(req)) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "result": f"Error processing request: {str(result)}",
                    "response_time": 0.001,
                    "source": "error",
                    "metadata": {"error": str(result), "request_index": i},
                    "timestamp": datetime.now().isoformat()
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def close(self):
        """Clean shutdown - close the session"""
        print("🔄 Shutting down InstantAIManager...")
        
        async with self._session_lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
        
        print("✅ InstantAIManager shutdown complete")
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - clean up"""
        await self.close()

# Global instance
instant_manager = InstantAIManager()