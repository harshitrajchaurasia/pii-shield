"""
Job Queue - Redis-backed Job Queue with Priority Support.

Provides a distributed job queue for PI Remover API service with:
- Priority queues (urgent, normal, batch)
- Job lifecycle management
- Queue metrics and monitoring
- Auto-scaling support

Works on Windows, Linux, and Cloud environments.

Usage:
    from shared.job_queue import JobQueue, Job, JobPriority
    
    # Create queue
    queue = await JobQueue.create()
    
    # Enqueue job
    job = Job(job_type="redact", payload={"text": "..."})
    await queue.enqueue(job, priority=JobPriority.NORMAL)
    
    # Get metrics
    metrics = await queue.get_metrics()
    print(f"Pending: {metrics.pending_count}")

Version: 1.0.0
"""

import os
import sys
import json
import time
import uuid
import asyncio
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable, Awaitable
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    try:
        import aioredis
        REDIS_AVAILABLE = True
    except ImportError:
        REDIS_AVAILABLE = False
        logger.info("Redis not available - using in-memory queue")


# Job Definitions
class JobPriority(Enum):
    """Job priority levels."""
    URGENT = "urgent"    # Small, fast jobs (< 100 rows)
    NORMAL = "normal"    # Standard jobs (100-10000 rows)
    BATCH = "batch"      # Large batch jobs (> 10000 rows)


class JobStatus(Enum):
    """Job status states."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY = "retry"


@dataclass
class Job:
    """Represents a processing job."""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_type: str = "redact"
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.PENDING
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # Processing info
    worker_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    
    # Result
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['priority'] = self.priority.value
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """Create from dictionary."""
        data['priority'] = JobPriority(data.get('priority', 'normal'))
        data['status'] = JobStatus(data.get('status', 'pending'))
        return cls(**data)
    
    def estimate_priority(self) -> JobPriority:
        """Estimate priority based on payload size."""
        row_count = self.payload.get('row_count', 0)
        text_length = len(self.payload.get('text', ''))
        
        # Small text or few rows -> urgent
        if text_length < 1000 or row_count < 100:
            return JobPriority.URGENT
        # Large batch -> batch
        elif row_count > 10000:
            return JobPriority.BATCH
        else:
            return JobPriority.NORMAL


@dataclass
class QueueMetrics:
    """Queue metrics for monitoring and scaling decisions."""
    pending_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    
    # Per-priority metrics
    urgent_pending: int = 0
    normal_pending: int = 0
    batch_pending: int = 0
    
    # Performance metrics
    avg_wait_time_seconds: float = 0.0
    avg_processing_time_seconds: float = 0.0
    throughput_per_minute: float = 0.0
    
    # Resource metrics
    queue_depth: int = 0
    oldest_job_age_seconds: float = 0.0
    
    # Timestamps
    measured_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# In-Memory Queue (Fallback)
class InMemoryQueue:
    """Simple in-memory queue for single-instance deployments."""
    
    def __init__(self):
        self._queues: Dict[str, List[Job]] = {
            JobPriority.URGENT.value: [],
            JobPriority.NORMAL.value: [],
            JobPriority.BATCH.value: [],
        }
        self._jobs: Dict[str, Job] = {}
        self._processing: Dict[str, Job] = {}
        self._completed: List[Job] = []
        self._lock = asyncio.Lock()
    
    async def enqueue(self, job: Job, priority: Optional[JobPriority] = None) -> str:
        """Add job to queue."""
        async with self._lock:
            priority = priority or job.priority
            job.priority = priority
            self._queues[priority.value].append(job)
            self._jobs[job.job_id] = job
            logger.debug(f"Enqueued job {job.job_id} with priority {priority.value}")
            return job.job_id
    
    async def dequeue(self, worker_id: str) -> Optional[Job]:
        """Get next job from queue (priority order)."""
        async with self._lock:
            # Try urgent first, then normal, then batch
            for priority in [JobPriority.URGENT, JobPriority.NORMAL, JobPriority.BATCH]:
                queue = self._queues[priority.value]
                if queue:
                    job = queue.pop(0)
                    job.status = JobStatus.PROCESSING
                    job.started_at = datetime.utcnow().isoformat()
                    job.worker_id = worker_id
                    self._processing[job.job_id] = job
                    logger.debug(f"Dequeued job {job.job_id} for worker {worker_id}")
                    return job
            return None
    
    async def complete(self, job_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """Mark job as completed."""
        async with self._lock:
            job = self._processing.pop(job_id, None)
            if job:
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow().isoformat()
                job.result = result
                self._completed.append(job)
                logger.debug(f"Completed job {job_id}")
                return True
            return False
    
    async def fail(self, job_id: str, error: str) -> bool:
        """Mark job as failed."""
        async with self._lock:
            job = self._processing.pop(job_id, None)
            if job:
                job.retry_count += 1
                if job.retry_count < job.max_retries:
                    job.status = JobStatus.RETRY
                    self._queues[job.priority.value].insert(0, job)  # Retry at front
                else:
                    job.status = JobStatus.FAILED
                    job.error = error
                    job.completed_at = datetime.utcnow().isoformat()
                    self._completed.append(job)
                logger.warning(f"Failed job {job_id}: {error}")
                return True
            return False
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self._jobs.get(job_id) or self._processing.get(job_id)
    
    async def get_metrics(self) -> QueueMetrics:
        """Get queue metrics."""
        async with self._lock:
            pending_count = sum(len(q) for q in self._queues.values())
            processing_count = len(self._processing)
            
            # Calculate average times from completed jobs
            recent_completed = self._completed[-100:]  # Last 100 jobs
            wait_times = []
            processing_times = []
            
            for job in recent_completed:
                if job.started_at and job.created_at:
                    try:
                        created = datetime.fromisoformat(job.created_at)
                        started = datetime.fromisoformat(job.started_at)
                        wait_times.append((started - created).total_seconds())
                    except Exception:
                        pass
                
                if job.completed_at and job.started_at:
                    try:
                        started = datetime.fromisoformat(job.started_at)
                        completed = datetime.fromisoformat(job.completed_at)
                        processing_times.append((completed - started).total_seconds())
                    except Exception:
                        pass
            
            return QueueMetrics(
                pending_count=pending_count,
                processing_count=processing_count,
                completed_count=len(self._completed),
                failed_count=sum(1 for j in self._completed if j.status == JobStatus.FAILED),
                urgent_pending=len(self._queues[JobPriority.URGENT.value]),
                normal_pending=len(self._queues[JobPriority.NORMAL.value]),
                batch_pending=len(self._queues[JobPriority.BATCH.value]),
                avg_wait_time_seconds=sum(wait_times) / len(wait_times) if wait_times else 0,
                avg_processing_time_seconds=sum(processing_times) / len(processing_times) if processing_times else 0,
                queue_depth=pending_count + processing_count,
            )


# Redis Queue
class RedisQueue:
    """Redis-backed distributed queue."""
    
    # Queue key names
    QUEUE_PREFIX = "pi_remover:queue"
    JOB_PREFIX = "pi_remover:job"
    METRICS_KEY = "pi_remover:metrics"
    
    def __init__(self, redis_client):
        self._redis = redis_client
    
    @classmethod
    async def create(cls, 
                     host: str = "localhost",
                     port: int = 6379,
                     password: Optional[str] = None,
                     db: int = 0) -> 'RedisQueue':
        """Create Redis queue with connection."""
        redis_client = await aioredis.from_url(
            f"redis://{host}:{port}/{db}",
            password=password,
            decode_responses=True
        )
        return cls(redis_client)
    
    def _queue_key(self, priority: JobPriority) -> str:
        """Get queue key for priority."""
        return f"{self.QUEUE_PREFIX}:{priority.value}"
    
    def _job_key(self, job_id: str) -> str:
        """Get job key."""
        return f"{self.JOB_PREFIX}:{job_id}"
    
    async def enqueue(self, job: Job, priority: Optional[JobPriority] = None) -> str:
        """Add job to queue."""
        priority = priority or job.priority
        job.priority = priority
        
        # Store job data
        await self._redis.set(
            self._job_key(job.job_id),
            json.dumps(job.to_dict()),
            ex=86400  # 24 hour TTL
        )
        
        # Add to priority queue (sorted set with timestamp as score)
        score = time.time()
        await self._redis.zadd(
            self._queue_key(priority),
            {job.job_id: score}
        )
        
        logger.debug(f"Enqueued job {job.job_id} with priority {priority.value}")
        return job.job_id
    
    async def dequeue(self, worker_id: str) -> Optional[Job]:
        """Get next job from queue (priority order)."""
        # Try each priority level
        for priority in [JobPriority.URGENT, JobPriority.NORMAL, JobPriority.BATCH]:
            queue_key = self._queue_key(priority)
            
            # Pop from sorted set (oldest first)
            result = await self._redis.zpopmin(queue_key, 1)
            if result:
                job_id = result[0][0]
                
                # Get job data
                job_data = await self._redis.get(self._job_key(job_id))
                if job_data:
                    job = Job.from_dict(json.loads(job_data))
                    job.status = JobStatus.PROCESSING
                    job.started_at = datetime.utcnow().isoformat()
                    job.worker_id = worker_id
                    
                    # Update job in Redis
                    await self._redis.set(
                        self._job_key(job_id),
                        json.dumps(job.to_dict()),
                        ex=86400
                    )
                    
                    # Track processing jobs
                    await self._redis.sadd(f"{self.QUEUE_PREFIX}:processing", job_id)
                    
                    logger.debug(f"Dequeued job {job_id} for worker {worker_id}")
                    return job
        
        return None
    
    async def complete(self, job_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """Mark job as completed."""
        job_data = await self._redis.get(self._job_key(job_id))
        if job_data:
            job = Job.from_dict(json.loads(job_data))
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow().isoformat()
            job.result = result
            
            # Update job
            await self._redis.set(
                self._job_key(job_id),
                json.dumps(job.to_dict()),
                ex=3600  # 1 hour retention for completed
            )
            
            # Remove from processing set
            await self._redis.srem(f"{self.QUEUE_PREFIX}:processing", job_id)
            
            # Increment completed counter
            await self._redis.incr(f"{self.METRICS_KEY}:completed")
            
            logger.debug(f"Completed job {job_id}")
            return True
        return False
    
    async def fail(self, job_id: str, error: str) -> bool:
        """Mark job as failed."""
        job_data = await self._redis.get(self._job_key(job_id))
        if job_data:
            job = Job.from_dict(json.loads(job_data))
            job.retry_count += 1
            
            # Remove from processing
            await self._redis.srem(f"{self.QUEUE_PREFIX}:processing", job_id)
            
            if job.retry_count < job.max_retries:
                # Re-queue for retry
                job.status = JobStatus.RETRY
                await self._redis.set(
                    self._job_key(job_id),
                    json.dumps(job.to_dict()),
                    ex=86400
                )
                await self._redis.zadd(
                    self._queue_key(job.priority),
                    {job_id: time.time()}
                )
            else:
                # Mark as failed
                job.status = JobStatus.FAILED
                job.error = error
                job.completed_at = datetime.utcnow().isoformat()
                await self._redis.set(
                    self._job_key(job_id),
                    json.dumps(job.to_dict()),
                    ex=3600
                )
                await self._redis.incr(f"{self.METRICS_KEY}:failed")
            
            logger.warning(f"Failed job {job_id}: {error}")
            return True
        return False
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        job_data = await self._redis.get(self._job_key(job_id))
        if job_data:
            return Job.from_dict(json.loads(job_data))
        return None
    
    async def get_metrics(self) -> QueueMetrics:
        """Get queue metrics."""
        # Get queue lengths
        urgent_len = await self._redis.zcard(self._queue_key(JobPriority.URGENT))
        normal_len = await self._redis.zcard(self._queue_key(JobPriority.NORMAL))
        batch_len = await self._redis.zcard(self._queue_key(JobPriority.BATCH))
        processing_count = await self._redis.scard(f"{self.QUEUE_PREFIX}:processing")
        
        # Get counters
        completed_count = int(await self._redis.get(f"{self.METRICS_KEY}:completed") or 0)
        failed_count = int(await self._redis.get(f"{self.METRICS_KEY}:failed") or 0)
        
        # Get oldest job age
        oldest_age = 0.0
        for priority in [JobPriority.URGENT, JobPriority.NORMAL, JobPriority.BATCH]:
            oldest = await self._redis.zrange(self._queue_key(priority), 0, 0, withscores=True)
            if oldest:
                oldest_age = max(oldest_age, time.time() - oldest[0][1])
        
        return QueueMetrics(
            pending_count=urgent_len + normal_len + batch_len,
            processing_count=processing_count,
            completed_count=completed_count,
            failed_count=failed_count,
            urgent_pending=urgent_len,
            normal_pending=normal_len,
            batch_pending=batch_len,
            queue_depth=urgent_len + normal_len + batch_len + processing_count,
            oldest_job_age_seconds=oldest_age,
        )
    
    async def close(self):
        """Close Redis connection."""
        await self._redis.close()


# Job Queue Factory
class JobQueue:
    """Factory for creating job queues."""
    
    @classmethod
    async def create(cls,
                     redis_host: Optional[str] = None,
                     redis_port: int = 6379,
                     redis_password: Optional[str] = None,
                     redis_db: int = 0) -> 'InMemoryQueue | RedisQueue':
        """
        Create appropriate queue based on Redis availability.
        
        Args:
            redis_host: Redis host (None for in-memory)
            redis_port: Redis port
            redis_password: Redis password
            redis_db: Redis database number
            
        Returns:
            Queue instance (Redis or in-memory fallback)
        """
        # Check environment variables
        redis_host = redis_host or os.environ.get("REDIS_HOST")
        redis_password = redis_password or os.environ.get("REDIS_PASSWORD")
        
        if redis_host and REDIS_AVAILABLE:
            try:
                queue = await RedisQueue.create(
                    host=redis_host,
                    port=redis_port,
                    password=redis_password,
                    db=redis_db
                )
                logger.info(f"Using Redis queue at {redis_host}:{redis_port}")
                return queue
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}, using in-memory queue")
        
        logger.info("Using in-memory queue")
        return InMemoryQueue()


# Scaling Recommendations
@dataclass
class ScalingRecommendation:
    """Recommendation for worker scaling based on queue metrics."""
    current_workers: int
    recommended_workers: int
    action: str  # "scale_up", "scale_down", "hold"
    reason: str
    urgency: str  # "immediate", "soon", "optional"


def get_scaling_recommendation(metrics: QueueMetrics, 
                                current_workers: int,
                                min_workers: int = 1,
                                max_workers: int = 10) -> ScalingRecommendation:
    """
    Get scaling recommendation based on queue metrics.
    
    This implements Level 3: Queue-Based Scaling.
    """
    # Scale up conditions
    if metrics.urgent_pending > 5:
        new_workers = min(max_workers, current_workers + 2)
        return ScalingRecommendation(
            current_workers=current_workers,
            recommended_workers=new_workers,
            action="scale_up",
            reason=f"High urgent queue: {metrics.urgent_pending} pending",
            urgency="immediate"
        )
    
    if metrics.queue_depth > 20:
        new_workers = min(max_workers, current_workers + 1)
        return ScalingRecommendation(
            current_workers=current_workers,
            recommended_workers=new_workers,
            action="scale_up",
            reason=f"High queue depth: {metrics.queue_depth}",
            urgency="soon"
        )
    
    if metrics.avg_wait_time_seconds > 30:
        new_workers = min(max_workers, current_workers + 1)
        return ScalingRecommendation(
            current_workers=current_workers,
            recommended_workers=new_workers,
            action="scale_up",
            reason=f"High wait time: {metrics.avg_wait_time_seconds:.1f}s",
            urgency="soon"
        )
    
    # Scale down conditions
    if metrics.pending_count == 0 and metrics.processing_count == 0:
        new_workers = max(min_workers, current_workers - 1)
        return ScalingRecommendation(
            current_workers=current_workers,
            recommended_workers=new_workers,
            action="scale_down",
            reason="Queue empty, no processing jobs",
            urgency="optional"
        )
    
    if metrics.queue_depth < 3 and current_workers > min_workers:
        return ScalingRecommendation(
            current_workers=current_workers,
            recommended_workers=max(min_workers, current_workers - 1),
            action="scale_down",
            reason=f"Low queue depth: {metrics.queue_depth}",
            urgency="optional"
        )
    
    # Hold steady
    return ScalingRecommendation(
        current_workers=current_workers,
        recommended_workers=current_workers,
        action="hold",
        reason="Queue metrics within acceptable range",
        urgency="optional"
    )
