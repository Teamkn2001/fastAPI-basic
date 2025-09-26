# src/ai_instant/persistent_stats.py
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
import sys
import os

# Add the src directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Try different import patterns for your project structure
try:
    # Try direct import (if running from src/ directory)
    from database import get_db, engine
    from models.ai_stats import AIStatsSummary, AIRequestLog, AISystemMetrics
    print("✅ Imported database models (direct import)")
except ImportError:
    try:
        # Try src.database import
        from src.database import get_db, engine
        from src.models.ai_stats import AIStatsSummary, AIRequestLog, AISystemMetrics
        print("✅ Imported database models (src import)")
    except ImportError:
        try:
            # Try relative import from current package
            from ...database import get_db, engine
            from ...models.ai_stats import AIStatsSummary, AIRequestLog, AISystemMetrics
            print("✅ Imported database models (relative import)")
        except ImportError:
            print("⚠️ Warning: Could not import database models. Creating fallback classes.")
            # Create dummy classes to prevent import errors
            class AIStatsSummary:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)
                    
            class AIRequestLog:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)
                        
            class AISystemMetrics:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)
                        
            def get_db():
                yield None
                
            engine = None

class MySQLStatsManager:
    def __init__(self, max_records: int = 100000, cleanup_days: int = 30):
        """
        MySQL-based stats manager with auto-cleanup
        
        Args:
            max_records: Maximum request records to keep (default: 100K)
            cleanup_days: Delete records older than X days (default: 30)
        """
        self.max_records = max_records
        self.cleanup_days = cleanup_days
        self.cleanup_counter = 0
        self.initialized = False
        
        # Try to initialize database
        try:
            self._ensure_tables()
            self._ensure_summary_record()
            self.initialized = True
            print(f"✅ MySQL Stats Manager initialized: {max_records:,} max records, {cleanup_days} days retention")
        except Exception as e:
            print(f"⚠️ MySQL Stats Manager initialization failed: {e}")
            print("📊 Stats will be logged to console instead")
    
    def _ensure_tables(self):
        """Create tables if they don't exist"""
        if not engine:
            raise Exception("Database engine not available")
            
        try:
            # Try different import paths for Base
            Base = None
            try:
                from models.ai_stats import Base
            except ImportError:
                try:
                    from src.models.ai_stats import Base
                except ImportError:
                    try:
                        from ...models.ai_stats import Base
                    except ImportError:
                        print("⚠️ Could not import Base class for table creation")
                        return
            
            if Base:
                Base.metadata.create_all(bind=engine)
                print("✅ MySQL AI stats tables ready")
        except Exception as e:
            print(f"⚠️ Error creating tables: {e}")
            raise
    
    def _ensure_summary_record(self):
        """Ensure we have a summary record"""
        if not self.initialized:
            return
            
        try:
            db = next(get_db())
            summary = db.query(AIStatsSummary).first()
            if not summary:
                summary = AIStatsSummary()
                db.add(summary)
                db.commit()
                print("📊 Created initial stats summary record")
        except Exception as e:
            print(f"⚠️ Error creating summary record: {e}")
        finally:
            if 'db' in locals():
                db.close()
    
    def log_request(self, prompt_hash: str, success: bool, response_time: float,
                   tokens_used: int = 0, source: str = "azure_ai", 
                   priority: str = "normal", user_id: str = None,
                   error_message: str = None, model_used: str = None):
        """Log individual request to MySQL"""
        
        if not self.initialized:
            # Fallback to console logging
            status = "✅" if success else "❌"
            print(f"{status} Request: {response_time:.2f}s, {tokens_used} tokens, {source}")
            return
        
        try:
            db = next(get_db())
            
            # Create request log
            request_log = AIRequestLog(
                prompt_hash=prompt_hash,
                user_id=user_id,
                success=success,
                response_time=response_time,
                tokens_used=tokens_used,
                source=source,
                priority=priority,
                error_message=error_message,
                model_used=model_used
            )
            db.add(request_log)
            
            # Update summary statistics
            summary = db.query(AIStatsSummary).first()
            if summary:
                summary.total_requests += 1
                summary.total_response_time += response_time
                
                if success:
                    summary.successful_requests += 1
                    summary.total_tokens_used += tokens_used
                else:
                    summary.failed_requests += 1
            
            db.commit()
            
            # Auto-cleanup check (every 1000 requests)
            self.cleanup_counter += 1
            if self.cleanup_counter >= 1000:
                self.cleanup_counter = 0
                self._auto_cleanup(db)
                
        except Exception as e:
            if 'db' in locals():
                db.rollback()
            print(f"⚠️ Error logging request: {e}")
        finally:
            if 'db' in locals():
                db.close()
    
    def get_stats(self) -> Dict:
        """Get comprehensive statistics from MySQL"""
        if not self.initialized:
            return {
                "error": "MySQL not initialized",
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "storage_type": "console_only"
            }
        
        try:
            db = next(get_db())
            
            # Get summary stats
            summary = db.query(AIStatsSummary).first()
            
            # Get recent response times (last 100 successful requests)
            recent_times = db.query(AIRequestLog.response_time)\
                           .filter(AIRequestLog.success == True)\
                           .order_by(desc(AIRequestLog.id))\
                           .limit(100).all()
            
            response_times = [rt[0] for rt in recent_times]
            
            # Get current record count
            total_records = db.query(func.count(AIRequestLog.id)).scalar()
            
            # Get today's stats - simplified query for compatibility
            today = datetime.now().date()
            today_total = db.query(func.count(AIRequestLog.id))\
                           .filter(func.date(AIRequestLog.timestamp) == today).scalar() or 0
            
            today_successful = db.query(func.count(AIRequestLog.id))\
                              .filter(func.date(AIRequestLog.timestamp) == today)\
                              .filter(AIRequestLog.success == True).scalar() or 0
            
            today_tokens = db.query(func.sum(AIRequestLog.tokens_used))\
                          .filter(func.date(AIRequestLog.timestamp) == today)\
                          .filter(AIRequestLog.success == True).scalar() or 0
            
            if summary:
                success_rate = (summary.successful_requests / summary.total_requests * 100) if summary.total_requests > 0 else 0
                avg_response_time = sum(response_times) / len(response_times) if response_times else 0
                
                return {
                    "total_requests": summary.total_requests,
                    "successful_requests": summary.successful_requests,
                    "failed_requests": summary.failed_requests,
                    "success_rate": f"{success_rate:.1f}%",
                    "total_tokens_used": summary.total_tokens_used,
                    "avg_response_time": f"{avg_response_time:.2f}s",
                    "first_started": summary.first_started.isoformat() if summary.first_started else None,
                    "last_updated": summary.last_updated.isoformat() if summary.last_updated else None,
                    # Today's stats
                    "today_requests": today_total,
                    "today_successful": today_successful,
                    "today_tokens": today_tokens,
                    # System info
                    "total_records_stored": total_records,
                    "storage_type": "mysql_database",
                    "retention_days": self.cleanup_days,
                    "max_records": self.max_records
                }
            
            return {"error": "No stats found in database"}
            
        except Exception as e:
            return {"error": f"Failed to get stats: {str(e)}"}
        finally:
            if 'db' in locals():
                db.close()
    
    def get_recent_requests(self, limit: int = 50) -> List[Dict]:
        """Get recent request history"""
        if not self.initialized:
            return [{"error": "MySQL not initialized"}]
        
        try:
            db = next(get_db())
            requests = db.query(AIRequestLog)\
                        .order_by(desc(AIRequestLog.timestamp))\
                        .limit(limit).all()
            
            return [{
                "id": req.id,
                "timestamp": req.timestamp.isoformat(),
                "success": req.success,
                "response_time": req.response_time,
                "tokens_used": req.tokens_used,
                "source": req.source,
                "priority": req.priority,
                "user_id": req.user_id,
                "error_message": req.error_message,
                "model_used": req.model_used
            } for req in requests]
            
        except Exception as e:
            return [{"error": f"Failed to get recent requests: {str(e)}"}]
        finally:
            if 'db' in locals():
                db.close()
    
    def get_analytics(self, days: int = 7) -> Dict:
        """Get analytics for the past X days"""
        if not self.initialized:
            return {"error": "MySQL not initialized"}
        
        try:
            db = next(get_db())
            cutoff = datetime.now() - timedelta(days=days)
            
            # Daily request counts - simplified queries for compatibility
            daily_stats = db.query(
                func.date(AIRequestLog.timestamp).label('date'),
                func.count(AIRequestLog.id).label('total'),
                func.avg(AIRequestLog.response_time).label('avg_time'),
                func.sum(AIRequestLog.tokens_used).label('tokens')
            ).filter(AIRequestLog.timestamp >= cutoff)\
             .group_by(func.date(AIRequestLog.timestamp))\
             .order_by(func.date(AIRequestLog.timestamp)).all()
            
            # Get successful counts separately for each date
            daily_breakdown = []
            for stat in daily_stats:
                successful_count = db.query(func.count(AIRequestLog.id))\
                                  .filter(func.date(AIRequestLog.timestamp) == stat.date)\
                                  .filter(AIRequestLog.success == True).scalar() or 0
                
                daily_breakdown.append({
                    "date": stat.date.isoformat(),
                    "total_requests": stat.total,
                    "successful_requests": successful_count,
                    "success_rate": f"{(successful_count / stat.total * 100):.1f}%" if stat.total > 0 else "0%",
                    "avg_response_time": f"{stat.avg_time:.2f}s" if stat.avg_time else "0s",
                    "total_tokens": stat.tokens or 0
                })
            
            # Source breakdown
            source_stats = db.query(
                AIRequestLog.source,
                func.count(AIRequestLog.id).label('count')
            ).filter(AIRequestLog.timestamp >= cutoff)\
             .group_by(AIRequestLog.source).all()
            
            return {
                "period_days": days,
                "daily_breakdown": daily_breakdown,
                "source_breakdown": [{
                    "source": stat.source,
                    "request_count": stat.count
                } for stat in source_stats]
            }
            
        except Exception as e:
            return {"error": f"Failed to get analytics: {str(e)}"}
        finally:
            if 'db' in locals():
                db.close()
    
    def _auto_cleanup(self, db: Session):
        """Auto-cleanup old records"""
        if not self.initialized:
            return
            
        try:
            # Strategy 1: Remove records older than cleanup_days
            cutoff_date = datetime.now() - timedelta(days=self.cleanup_days)
            old_records = db.query(AIRequestLog)\
                           .filter(AIRequestLog.timestamp < cutoff_date)\
                           .count()
            
            if old_records > 0:
                db.query(AIRequestLog)\
                  .filter(AIRequestLog.timestamp < cutoff_date)\
                  .delete(synchronize_session=False)
                print(f"🧹 Cleaned up {old_records} old records (>{self.cleanup_days} days)")
            
            # Strategy 2: Keep only max_records (remove oldest if exceeded)
            total_records = db.query(func.count(AIRequestLog.id)).scalar()
            if total_records > self.max_records:
                # Get the ID threshold (keep newest max_records)
                threshold_id = db.query(AIRequestLog.id)\
                                .order_by(desc(AIRequestLog.id))\
                                .offset(self.max_records)\
                                .limit(1).scalar()
                
                if threshold_id:
                    excess_count = db.query(AIRequestLog)\
                                    .filter(AIRequestLog.id < threshold_id)\
                                    .count()
                    
                    db.query(AIRequestLog)\
                      .filter(AIRequestLog.id < threshold_id)\
                      .delete(synchronize_session=False)
                    
                    print(f"🧹 Cleaned up {excess_count} excess records (keeping newest {self.max_records})")
            
            # Update cleanup timestamp
            summary = db.query(AIStatsSummary).first()
            if summary:
                summary.last_cleanup = datetime.now()
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            print(f"⚠️ Cleanup error: {e}")

# Global instance - this is what gets imported
mysql_stats = MySQLStatsManager(max_records=100000, cleanup_days=30)