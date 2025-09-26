# Create this as src/ai_instant/azure_ai_service.py
# This is the actual Azure AI service implementation

import asyncio
import aiohttp
import json
import time
import os
from typing import Dict, List
from datetime import datetime

class AzureAIService:
    """Production-ready Azure AI service for instant responses"""
    
    def __init__(self):
        # Azure Configuration
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY") 
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-35-turbo")
        self.api_version = "2024-02-01"
        
        if not self.endpoint or not self.api_key:
            raise ValueError("Azure OpenAI credentials not found in environment variables")
        
        # Connection optimization for high throughput
        self.connector = aiohttp.TCPConnector(
            limit=50,           # Max connections
            limit_per_host=25,  # Per Azure endpoint
            keepalive_timeout=30,
            use_dns_cache=True
        )
        
        # Timeouts for different priority levels
        self.timeouts = {
            "instant": aiohttp.ClientTimeout(total=2),
            "fast": aiohttp.ClientTimeout(total=5), 
            "normal": aiohttp.ClientTimeout(total=10)
        }
        
        # Usage tracking
        self.usage_stats = {
            "requests": 0,
            "successful": 0,
            "failed": 0,
            "total_tokens": 0,
            "total_cost": 0.0  # Approximate
        }
    
    async def process_prompt(self, prompt: str, max_response_time: float = 3.0, priority: str = "normal") -> Dict:
        """
        Process a single prompt with Azure OpenAI
        Optimized for instant response system
        """
        start_time = time.time()
        self.usage_stats["requests"] += 1
        
        try:
            # Choose optimal settings based on priority
            if priority == "instant":
                max_tokens = 100
                temperature = 0.3  # More focused for speed
                timeout = self.timeouts["instant"]
            elif priority == "fast":
                max_tokens = 250
                temperature = 0.5
                timeout = self.timeouts["fast"]
            else:
                max_tokens = 500
                temperature = 0.7
                timeout = self.timeouts["normal"]
            
            # Prepare the request
            url = f"{self.endpoint}openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"
            
            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key
            }
            
            # Optimized payload for instant responses
            payload = {
                "messages": [
                    {
                        "role": "system",
                        "content": self._get_system_prompt(priority)
                    },
                    {
                        "role": "user",
                        "content": self._optimize_user_prompt(prompt, priority)
                    }
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.9,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "stream": False  # No streaming for instant responses
            }
            
            # Make the Azure API call
            async with aiohttp.ClientSession(connector=self.connector, timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    
                    processing_time = time.time() - start_time
                    
                    # Check if response is too slow
                    if processing_time > max_response_time:
                        return {
                            "success": False,
                            "error": "timeout_exceeded",
                            "processing_time": processing_time,
                            "message": f"Azure response took {processing_time:.2f}s, exceeded {max_response_time}s limit"
                        }
                    
                    # Handle Azure API errors
                    if response.status != 200:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": "azure_api_error",
                            "processing_time": processing_time,
                            "message": f"Azure API error {response.status}: {error_text}"
                        }
                    
                    # Parse successful response
                    data = await response.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    tokens_used = data["usage"]["total_tokens"]
                    
                    # Update statistics
                    self.usage_stats["successful"] += 1
                    self.usage_stats["total_tokens"] += tokens_used
                    self.usage_stats["total_cost"] += self._estimate_cost(tokens_used)
                    
                    return {
                        "success": True,
                        "result": content,
                        "processing_time": processing_time,
                        "tokens_used": tokens_used,
                        "model": self.deployment
                    }
        
        except asyncio.TimeoutError:
            processing_time = time.time() - start_time
            self.usage_stats["failed"] += 1
            return {
                "success": False,
                "error": "timeout",
                "processing_time": processing_time,
                "message": "Azure AI request timed out"
            }
        
        except Exception as e:
            processing_time = time.time() - start_time
            self.usage_stats["failed"] += 1
            return {
                "success": False,
                "error": "exception",
                "processing_time": processing_time,
                "message": f"Azure AI error: {str(e)}"
            }
    
    def _get_system_prompt(self, priority: str) -> str:
        """Get optimized system prompt based on priority"""
        if priority == "instant":
            return "You are a helpful assistant. Provide very brief, direct answers. Be concise and to the point. Maximum 1-2 sentences."
        elif priority == "fast":
            return "You are a helpful assistant. Provide clear, concise responses. Be direct but informative."
        else:
            return "You are a helpful assistant. Provide comprehensive, accurate, and helpful responses."
    
    def _optimize_user_prompt(self, prompt: str, priority: str) -> str:
        """Optimize user prompt for faster processing"""
        if priority == "instant" and len(prompt) > 100:
            return f"Brief answer to: {prompt[:100]}..."
        elif priority == "fast" and len(prompt) > 300:
            return f"Concise response to: {prompt[:300]}..."
        else:
            return prompt
    
    def _estimate_cost(self, tokens: int) -> float:
        """Estimate cost based on tokens (rough approximation)"""
        # Rough pricing for GPT-3.5-turbo (adjust based on your actual pricing)
        cost_per_1k_tokens = 0.002
        return (tokens / 1000) * cost_per_1k_tokens
    
    async def process_batch(self, prompts: List[str], max_concurrent: int = 10) -> List[Dict]:
        """Process multiple prompts concurrently with rate limiting"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_single(prompt):
            async with semaphore:
                return await self.process_prompt(prompt, priority="normal")
        
        tasks = [process_single(prompt) for prompt in prompts]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_stats(self) -> Dict:
        """Get usage statistics"""
        total = self.usage_stats["requests"]
        success_rate = (self.usage_stats["successful"] / total * 100) if total > 0 else 0
        
        return {
            "total_requests": total,
            "successful_requests": self.usage_stats["successful"],
            "failed_requests": self.usage_stats["failed"],
            "success_rate": f"{success_rate:.1f}%",
            "total_tokens_used": self.usage_stats["total_tokens"],
            "estimated_total_cost": f"${self.usage_stats['total_cost']:.4f}",
            "deployment": self.deployment,
            "endpoint_configured": bool(self.endpoint)
        }
    
    async def health_check(self) -> Dict:
        """Test Azure AI connectivity"""
        try:
            result = await self.process_prompt(
                "Say 'healthy' if you're working properly",
                max_response_time=5.0,
                priority="normal"
            )
            
            return {
                "status": "healthy" if result["success"] else "unhealthy",
                "response_time": result["processing_time"],
                "azure_response": result.get("result", result.get("message")),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

# Global instance
azure_ai_service = AzureAIService()