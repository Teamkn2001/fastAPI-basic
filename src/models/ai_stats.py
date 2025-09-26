# src/models/ai_stats.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, BigInteger
from sqlalchemy.sql import func
import sys
import os

# Add src to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Try to import Base from your existing database setup
try:
    from database import Base
    print("✅ Imported Base from database")
except ImportError:
    try:
        from src.database import Base
        print("✅ Imported Base from src.database")
    except ImportError:
        try:
            from ..database import Base
            print("✅ Imported Base with relative import")
        except ImportError:
            print("⚠️ Could not import Base, creating fallback")
            from sqlalchemy.ext.declarative import declarative_base
            Base = declarative_base()

class AIStatsSummary(Base):
    """Summary table for overall AI usage statistics"""
    __tablename__ = "ai_stats_summary"

    id = Column(Integer, primary_key=True, index=True)
    total_requests = Column(BigInteger, default=0, nullable=False)
    successful_requests = Column(BigInteger, default=0, nullable=False)
    failed_requests = Column(BigInteger, default=0, nullable=False)
    total_tokens_used = Column(BigInteger, default=0, nullable=False)
    total_response_time = Column(Float, default=0.0, nullable=False)  # Sum of all response times
    first_started = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_cleanup = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<AIStats {self.total_requests} requests, {self.successful_requests} success>"


class AIRequestLog(Base):
    """Detailed log of individual AI requests"""
    __tablename__ = "ai_request_logs"

    id = Column(BigInteger, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    prompt_hash = Column(String(64), nullable=True, index=True)  # For deduplication tracking
    user_id = Column(String(100), nullable=True, index=True)  # Track user patterns
    success = Column(Boolean, nullable=False, index=True)
    response_time = Column(Float, nullable=False)  # In seconds
    tokens_used = Column(Integer, default=0, nullable=False)
    source = Column(String(50), default='azure_ai', nullable=False, index=True)  # azure_ai, fallback, deduplication
    priority = Column(String(20), default='normal', nullable=True)  # instant, fast, normal
    error_message = Column(Text, nullable=True)
    model_used = Column(String(100), nullable=True)  # gpt-4o-mini, etc.

    def __repr__(self):
        status = "✅" if self.success else "❌"
        return f"<AIRequest {status} {self.response_time:.2f}s {self.tokens_used}t>"


class AISystemMetrics(Base):
    """System performance metrics (hourly aggregates for analytics)"""
    __tablename__ = "ai_system_metrics"

    id = Column(BigInteger, primary_key=True, index=True)
    hour_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    requests_count = Column(Integer, default=0, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    avg_response_time = Column(Float, default=0.0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    peak_concurrent = Column(Integer, default=0, nullable=False)
    unique_users = Column(Integer, default=0, nullable=False)

    def __repr__(self):
        success_rate = (self.success_count / self.requests_count * 100) if self.requests_count > 0 else 0
        return f"<Metrics {self.hour_timestamp.strftime('%Y-%m-%d %H:00')} - {self.requests_count} req, {success_rate:.1f}% success>"