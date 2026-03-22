"""
Autoscaler - Multi-Level Auto-Scaling for PI Remover.

Combines all scaling levels:
- Level 1: File-based worker scaling (in resource_monitor.py)
- Level 2: Runtime resource-aware scaling (in resource_monitor.py)
- Level 3: Queue-based service scaling (this module)
- Level 4: Cloud cost-aware scaling (this module)

Works on Windows, Linux, and Cloud environments (GCP, AWS, Azure).

Usage:
    from shared.autoscaler import Autoscaler, ScalingConfig
    
    # Create autoscaler
    config = ScalingConfig.from_yaml('config/scaling.yaml')
    scaler = Autoscaler(config)
    
    # Get scaling decision
    decision = await scaler.get_scaling_decision()
    print(f"Action: {decision.action}, Workers: {decision.target_workers}")

Version: 1.0.0
"""

import os
import sys
import json
import time
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable, Awaitable
from enum import Enum

logger = logging.getLogger(__name__)

# Import dependencies
try:
    from .resource_monitor import (
        ResourceMonitor, 
        get_platform_info, 
        ScalingConfig as ResourceScalingConfig,
        CloudProvider,
        OSType
    )
    RESOURCE_MONITOR_AVAILABLE = True
except ImportError:
    RESOURCE_MONITOR_AVAILABLE = False
    ResourceMonitor = None

try:
    from .job_queue import JobQueue, QueueMetrics, get_scaling_recommendation
    JOB_QUEUE_AVAILABLE = True
except ImportError:
    JOB_QUEUE_AVAILABLE = False


# Scaling Configuration
class ScalingStrategy(Enum):
    """Scaling strategy types."""
    CONSERVATIVE = "conservative"  # Scale slowly, prefer stability
    BALANCED = "balanced"          # Default behavior
    AGGRESSIVE = "aggressive"      # Scale quickly, optimize for performance


@dataclass
class CloudConfig:
    """Cloud-specific configuration."""
    provider: str = "local"  # gcp, aws, azure, local
    project_id: Optional[str] = None
    region: Optional[str] = None
    
    # Instance configuration
    min_instances: int = 1
    max_instances: int = 10
    target_cpu_utilization: float = 70.0
    
    # Cost controls
    monthly_budget: float = 500.0  # USD
    alert_threshold: float = 80.0  # % of budget
    stop_threshold: float = 100.0  # % - stop scaling
    
    # Scheduling
    enable_scheduling: bool = False
    peak_hours_start: str = "09:00"
    peak_hours_end: str = "18:00"
    peak_max_instances: int = 10
    off_peak_max_instances: int = 2
    timezone: str = "UTC"


@dataclass
class AutoscalerConfig:
    """Complete autoscaler configuration."""
    # General
    enabled: bool = True
    strategy: ScalingStrategy = ScalingStrategy.BALANCED
    
    # Worker limits
    min_workers: int = 1
    max_workers: int = field(default_factory=lambda: min(os.cpu_count() or 4, 32))
    
    # Thresholds
    scale_up_threshold: int = 10   # Queue depth to trigger scale up
    scale_down_threshold: int = 2  # Queue depth to trigger scale down
    cooldown_seconds: int = 60     # Wait between scaling actions
    
    # Level 2: Resource monitoring
    enable_resource_monitoring: bool = True
    cpu_scale_down_threshold: float = 85.0
    memory_scale_down_threshold: float = 80.0
    
    # Level 3: Queue-based
    enable_queue_scaling: bool = True
    queue_check_interval: int = 10  # seconds
    
    # Level 4: Cloud
    cloud: CloudConfig = field(default_factory=CloudConfig)
    
    @classmethod
    def from_yaml(cls, config_path: str) -> 'AutoscalerConfig':
        """Load configuration from YAML file."""
        try:
            import yaml
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)
            
            # Parse cloud config if present
            cloud_data = data.pop('cloud', {})
            cloud_config = CloudConfig(**cloud_data) if cloud_data else CloudConfig()
            
            # Parse strategy
            strategy_str = data.pop('strategy', 'balanced')
            strategy = ScalingStrategy(strategy_str)
            
            return cls(strategy=strategy, cloud=cloud_config, **data)
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
            return cls()
    
    @classmethod
    def from_env(cls) -> 'AutoscalerConfig':
        """Load configuration from environment variables."""
        return cls(
            enabled=os.environ.get("AUTOSCALER_ENABLED", "true").lower() == "true",
            min_workers=int(os.environ.get("AUTOSCALER_MIN_WORKERS", "1")),
            max_workers=int(os.environ.get("AUTOSCALER_MAX_WORKERS", str(os.cpu_count() or 4))),
            scale_up_threshold=int(os.environ.get("AUTOSCALER_SCALE_UP_THRESHOLD", "10")),
            scale_down_threshold=int(os.environ.get("AUTOSCALER_SCALE_DOWN_THRESHOLD", "2")),
            cooldown_seconds=int(os.environ.get("AUTOSCALER_COOLDOWN_SECONDS", "60")),
            cloud=CloudConfig(
                provider=os.environ.get("CLOUD_PROVIDER", "local"),
                project_id=os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("AWS_PROJECT"),
                region=os.environ.get("CLOUD_REGION"),
                monthly_budget=float(os.environ.get("AUTOSCALER_MONTHLY_BUDGET", "500")),
            )
        )


# Scaling Decision
class ScalingAction(Enum):
    """Scaling action types."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    HOLD = "hold"
    EMERGENCY_SCALE_DOWN = "emergency_scale_down"


@dataclass
class ScalingDecision:
    """Result of scaling evaluation."""
    action: ScalingAction
    current_workers: int
    target_workers: int
    reason: str
    level: str  # Which scaling level triggered this
    urgency: str  # immediate, soon, optional
    
    # Metrics that influenced decision
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamp
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action": self.action.value,
            "current_workers": self.current_workers,
            "target_workers": self.target_workers,
            "reason": self.reason,
            "level": self.level,
            "urgency": self.urgency,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
        }


# Autoscaler
class Autoscaler:
    """
    Multi-level autoscaler for PI Remover.
    
    Combines:
    - Level 1: File-based scaling (handled in process_csv)
    - Level 2: Resource monitoring (CPU/Memory)
    - Level 3: Queue-based scaling
    - Level 4: Cloud cost-aware scaling
    """
    
    def __init__(self, config: Optional[AutoscalerConfig] = None):
        """Initialize autoscaler."""
        self.config = config or AutoscalerConfig.from_env()
        self._current_workers = self.config.min_workers
        self._last_scale_time = 0.0
        self._resource_monitor = None
        self._queue = None
        self._running = False
        
        # Initialize resource monitor if available
        if RESOURCE_MONITOR_AVAILABLE and self.config.enable_resource_monitoring:
            self._resource_monitor = ResourceMonitor()
            logger.info("Resource monitoring enabled")
        
        logger.info(f"Autoscaler initialized: strategy={self.config.strategy.value}, "
                   f"workers={self.config.min_workers}-{self.config.max_workers}")
    
    async def initialize(self, queue: Optional[Any] = None):
        """Initialize with optional job queue."""
        if queue:
            self._queue = queue
        elif JOB_QUEUE_AVAILABLE and self.config.enable_queue_scaling:
            self._queue = await JobQueue.create()
        
        logger.info("Autoscaler initialized")
    
    @property
    def current_workers(self) -> int:
        """Get current worker count."""
        return self._current_workers
    
    @current_workers.setter
    def current_workers(self, value: int):
        """Set current worker count."""
        self._current_workers = max(self.config.min_workers, 
                                    min(self.config.max_workers, value))
    
    def _is_in_cooldown(self) -> bool:
        """Check if we're in cooldown period."""
        return time.time() - self._last_scale_time < self.config.cooldown_seconds
    
    def _is_peak_hours(self) -> bool:
        """Check if current time is within peak hours."""
        if not self.config.cloud.enable_scheduling:
            return True
        
        try:
            from datetime import timezone
            import pytz
            
            tz = pytz.timezone(self.config.cloud.timezone)
            now = datetime.now(tz)
            
            peak_start = datetime.strptime(self.config.cloud.peak_hours_start, "%H:%M").time()
            peak_end = datetime.strptime(self.config.cloud.peak_hours_end, "%H:%M").time()
            
            return peak_start <= now.time() <= peak_end
        except Exception:
            return True  # Default to peak hours if timezone handling fails
    
    def _get_max_workers_for_time(self) -> int:
        """Get max workers based on time of day."""
        if self._is_peak_hours():
            return min(self.config.max_workers, self.config.cloud.peak_max_instances)
        else:
            return min(self.config.max_workers, self.config.cloud.off_peak_max_instances)
    
    async def _check_resource_pressure(self) -> Optional[ScalingDecision]:
        """Level 2: Check resource pressure and recommend scaling."""
        if not self._resource_monitor:
            return None
        
        cpu_percent = self._resource_monitor.get_cpu_percent(interval=0.5)
        memory_percent = self._resource_monitor.get_memory_percent()
        
        # Emergency: Memory critical
        if memory_percent > 90:
            return ScalingDecision(
                action=ScalingAction.EMERGENCY_SCALE_DOWN,
                current_workers=self._current_workers,
                target_workers=max(self.config.min_workers, self._current_workers - 2),
                reason=f"Critical memory pressure: {memory_percent:.1f}%",
                level="resource",
                urgency="immediate",
                metrics={"cpu_percent": cpu_percent, "memory_percent": memory_percent}
            )
        
        # High resource usage -> scale down
        if (cpu_percent > self.config.cpu_scale_down_threshold or 
            memory_percent > self.config.memory_scale_down_threshold):
            return ScalingDecision(
                action=ScalingAction.SCALE_DOWN,
                current_workers=self._current_workers,
                target_workers=max(self.config.min_workers, self._current_workers - 1),
                reason=f"Resource pressure: CPU={cpu_percent:.1f}%, MEM={memory_percent:.1f}%",
                level="resource",
                urgency="soon",
                metrics={"cpu_percent": cpu_percent, "memory_percent": memory_percent}
            )
        
        # Low usage -> can scale up if needed
        if cpu_percent < 50 and memory_percent < 60:
            # Return None to allow other levels to decide
            return None
        
        return None
    
    async def _check_queue_pressure(self) -> Optional[ScalingDecision]:
        """Level 3: Check queue pressure and recommend scaling."""
        if not self._queue:
            return None
        
        try:
            metrics = await self._queue.get_metrics()
        except Exception as e:
            logger.warning(f"Failed to get queue metrics: {e}")
            return None
        
        # Get recommendation from job_queue module
        if JOB_QUEUE_AVAILABLE:
            rec = get_scaling_recommendation(
                metrics,
                self._current_workers,
                self.config.min_workers,
                self._get_max_workers_for_time()
            )
            
            if rec.action == "scale_up":
                return ScalingDecision(
                    action=ScalingAction.SCALE_UP,
                    current_workers=self._current_workers,
                    target_workers=rec.recommended_workers,
                    reason=rec.reason,
                    level="queue",
                    urgency=rec.urgency,
                    metrics={
                        "pending_count": metrics.pending_count,
                        "queue_depth": metrics.queue_depth,
                        "avg_wait_time": metrics.avg_wait_time_seconds,
                    }
                )
            elif rec.action == "scale_down":
                return ScalingDecision(
                    action=ScalingAction.SCALE_DOWN,
                    current_workers=self._current_workers,
                    target_workers=rec.recommended_workers,
                    reason=rec.reason,
                    level="queue",
                    urgency=rec.urgency,
                    metrics={
                        "pending_count": metrics.pending_count,
                        "queue_depth": metrics.queue_depth,
                    }
                )
        
        return None
    
    async def _check_cost_constraints(self) -> Optional[ScalingDecision]:
        """Level 4: Check cost constraints."""
        # TODO: Integrate with cloud billing APIs
        # For now, just apply scheduling constraints
        
        max_workers = self._get_max_workers_for_time()
        
        if self._current_workers > max_workers:
            return ScalingDecision(
                action=ScalingAction.SCALE_DOWN,
                current_workers=self._current_workers,
                target_workers=max_workers,
                reason=f"Off-peak hours: max workers = {max_workers}",
                level="cost",
                urgency="soon",
                metrics={"max_workers": max_workers, "is_peak": self._is_peak_hours()}
            )
        
        return None
    
    async def get_scaling_decision(self) -> ScalingDecision:
        """
        Get scaling decision by evaluating all levels.
        
        Priority order:
        1. Resource pressure (Level 2) - safety first
        2. Cost constraints (Level 4) - budget enforcement
        3. Queue pressure (Level 3) - performance optimization
        """
        # Check cooldown
        if self._is_in_cooldown():
            return ScalingDecision(
                action=ScalingAction.HOLD,
                current_workers=self._current_workers,
                target_workers=self._current_workers,
                reason=f"In cooldown period ({self.config.cooldown_seconds}s)",
                level="cooldown",
                urgency="optional"
            )
        
        # Level 2: Resource pressure (highest priority for safety)
        resource_decision = await self._check_resource_pressure()
        if resource_decision and resource_decision.action in (
            ScalingAction.EMERGENCY_SCALE_DOWN, 
            ScalingAction.SCALE_DOWN
        ):
            return resource_decision
        
        # Level 4: Cost constraints
        cost_decision = await self._check_cost_constraints()
        if cost_decision and cost_decision.action == ScalingAction.SCALE_DOWN:
            return cost_decision
        
        # Level 3: Queue pressure
        queue_decision = await self._check_queue_pressure()
        if queue_decision:
            # Validate against resource availability
            if queue_decision.action == ScalingAction.SCALE_UP:
                # Check if resources allow scaling up
                if resource_decision is None:  # Resources OK
                    return queue_decision
            else:
                return queue_decision
        
        # Default: hold steady
        return ScalingDecision(
            action=ScalingAction.HOLD,
            current_workers=self._current_workers,
            target_workers=self._current_workers,
            reason="All metrics within acceptable range",
            level="none",
            urgency="optional"
        )
    
    async def apply_scaling_decision(self, decision: ScalingDecision) -> bool:
        """
        Apply a scaling decision.
        
        Returns True if scaling was applied, False if held.
        """
        if decision.action == ScalingAction.HOLD:
            return False
        
        old_workers = self._current_workers
        self._current_workers = decision.target_workers
        self._last_scale_time = time.time()
        
        logger.info(f"Scaling applied: {old_workers} -> {self._current_workers} workers "
                   f"({decision.action.value}, level={decision.level})")
        
        return True
    
    async def run_autoscaling_loop(self, 
                                    callback: Optional[Callable[[ScalingDecision], Awaitable[None]]] = None,
                                    interval: int = 10):
        """
        Run continuous autoscaling loop.
        
        Args:
            callback: Async function to call when scaling decision is made
            interval: Check interval in seconds
        """
        self._running = True
        logger.info(f"Starting autoscaling loop (interval={interval}s)")
        
        while self._running:
            try:
                decision = await self.get_scaling_decision()
                
                if decision.action != ScalingAction.HOLD:
                    await self.apply_scaling_decision(decision)
                    
                    if callback:
                        await callback(decision)
                
            except Exception as e:
                logger.error(f"Autoscaling error: {e}")
            
            await asyncio.sleep(interval)
    
    def stop(self):
        """Stop autoscaling loop."""
        self._running = False
        logger.info("Autoscaling stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current autoscaler status."""
        status = {
            "enabled": self.config.enabled,
            "strategy": self.config.strategy.value,
            "current_workers": self._current_workers,
            "min_workers": self.config.min_workers,
            "max_workers": self.config.max_workers,
            "in_cooldown": self._is_in_cooldown(),
            "is_peak_hours": self._is_peak_hours(),
        }
        
        if self._resource_monitor:
            status["resources"] = {
                "cpu_percent": self._resource_monitor.get_cpu_percent(interval=0.1),
                "memory_percent": self._resource_monitor.get_memory_percent(),
            }
        
        return status


# Convenience Functions
async def create_autoscaler(config_path: Optional[str] = None) -> Autoscaler:
    """Create and initialize autoscaler."""
    if config_path and os.path.exists(config_path):
        config = AutoscalerConfig.from_yaml(config_path)
    else:
        config = AutoscalerConfig.from_env()
    
    scaler = Autoscaler(config)
    await scaler.initialize()
    return scaler
