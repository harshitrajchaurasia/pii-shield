"""
Resource Monitor - Cross-Platform System Resource Monitoring.

Provides CPU, memory, and system monitoring for auto-scaling decisions.
Works on Windows, Linux, macOS, and cloud environments (GCP, AWS, Azure).

Features:
- OS-agnostic resource monitoring
- Container-aware (Docker, Kubernetes)
- Cloud platform detection (GCP, AWS, Azure)
- Scaling profile recommendations
- Adaptive worker pool management

Usage:
    from shared.resource_monitor import ResourceMonitor, get_platform_info
    
    # Get platform information
    info = get_platform_info()
    print(f"OS: {info.os_type}, Cloud: {info.cloud_provider}")
    
    # Create monitor and get scaling recommendations
    monitor = ResourceMonitor()
    profile = monitor.get_scaling_profile(row_count=50000)
    print(f"Recommended workers: {profile.num_workers}")

Version: 1.0.0
"""

import os
import sys
import time
import logging
import platform
import multiprocessing as mp
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple, List, Callable
from enum import Enum
from functools import lru_cache

logger = logging.getLogger(__name__)

# Platform Detection
class OSType(Enum):
    """Operating system types."""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


class CloudProvider(Enum):
    """Cloud platform providers."""
    GCP = "gcp"
    AWS = "aws"
    AZURE = "azure"
    LOCAL = "local"
    UNKNOWN = "unknown"


class ContainerRuntime(Enum):
    """Container runtime environments."""
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    CLOUD_RUN = "cloud_run"
    NONE = "none"


@dataclass
class PlatformInfo:
    """Platform and environment information."""
    os_type: OSType
    os_version: str
    python_version: str
    cpu_count: int
    cpu_count_logical: int
    total_memory_gb: float
    cloud_provider: CloudProvider
    container_runtime: ContainerRuntime
    is_container: bool
    is_cloud: bool
    
    # Container/Cloud specific
    container_memory_limit_gb: Optional[float] = None
    container_cpu_limit: Optional[float] = None
    instance_type: Optional[str] = None
    region: Optional[str] = None


@lru_cache(maxsize=1)
def get_platform_info() -> PlatformInfo:
    """
    Detect platform, OS, cloud provider, and container runtime.
    Results are cached for performance.
    """
    # Detect OS
    system = platform.system().lower()
    if system == "windows":
        os_type = OSType.WINDOWS
    elif system == "linux":
        os_type = OSType.LINUX
    elif system == "darwin":
        os_type = OSType.MACOS
    else:
        os_type = OSType.UNKNOWN
    
    os_version = platform.version()
    python_version = platform.python_version()
    
    # CPU counts
    cpu_count = mp.cpu_count()
    cpu_count_logical = os.cpu_count() or cpu_count
    
    # Memory detection (cross-platform)
    total_memory_gb = _get_total_memory_gb()
    
    # Container detection
    is_container, container_runtime = _detect_container()
    
    # Cloud detection
    cloud_provider = _detect_cloud_provider()
    is_cloud = cloud_provider not in (CloudProvider.LOCAL, CloudProvider.UNKNOWN)
    
    # Container limits
    container_memory_limit_gb = None
    container_cpu_limit = None
    if is_container:
        container_memory_limit_gb = _get_container_memory_limit_gb()
        container_cpu_limit = _get_container_cpu_limit()
    
    # Cloud instance info
    instance_type = None
    region = None
    if is_cloud:
        instance_type, region = _get_cloud_instance_info(cloud_provider)
    
    return PlatformInfo(
        os_type=os_type,
        os_version=os_version,
        python_version=python_version,
        cpu_count=cpu_count,
        cpu_count_logical=cpu_count_logical,
        total_memory_gb=total_memory_gb,
        cloud_provider=cloud_provider,
        container_runtime=container_runtime,
        is_container=is_container,
        is_cloud=is_cloud,
        container_memory_limit_gb=container_memory_limit_gb,
        container_cpu_limit=container_cpu_limit,
        instance_type=instance_type,
        region=region,
    )


def _get_total_memory_gb() -> float:
    """Get total system memory in GB."""
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        pass
    
    # Fallback for Linux
    if os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb / (1024 ** 2)
        except Exception:
            pass
    
    # Windows fallback
    if platform.system().lower() == "windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            c_ulonglong = ctypes.c_ulonglong
            
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", c_ulonglong),
                    ("ullAvailPhys", c_ulonglong),
                    ("ullTotalPageFile", c_ulonglong),
                    ("ullAvailPageFile", c_ulonglong),
                    ("ullTotalVirtual", c_ulonglong),
                    ("ullAvailVirtual", c_ulonglong),
                    ("ullAvailExtendedVirtual", c_ulonglong),
                ]
            
            memoryStatus = MEMORYSTATUSEX()
            memoryStatus.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(memoryStatus))
            return memoryStatus.ullTotalPhys / (1024 ** 3)
        except Exception:
            pass
    
    return 8.0  # Default assumption


def _detect_container() -> Tuple[bool, ContainerRuntime]:
    """Detect if running in a container and which runtime."""
    # Check for Kubernetes
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return True, ContainerRuntime.KUBERNETES
    
    # Check for Cloud Run
    if os.environ.get("K_SERVICE") or os.environ.get("CLOUD_RUN_JOB"):
        return True, ContainerRuntime.CLOUD_RUN
    
    # Check for Docker via cgroup
    if os.path.exists("/.dockerenv"):
        return True, ContainerRuntime.DOCKER
    
    # Check cgroup for container
    try:
        with open("/proc/1/cgroup", "r") as f:
            content = f.read()
            if "docker" in content or "kubepods" in content or "containerd" in content:
                return True, ContainerRuntime.DOCKER
    except Exception:
        pass
    
    return False, ContainerRuntime.NONE


def _detect_cloud_provider() -> CloudProvider:
    """Detect cloud provider from environment/metadata."""
    # GCP Detection
    if os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT"):
        return CloudProvider.GCP
    if os.environ.get("K_SERVICE"):  # Cloud Run
        return CloudProvider.GCP
    
    # AWS Detection
    if os.environ.get("AWS_REGION") or os.environ.get("AWS_EXECUTION_ENV"):
        return CloudProvider.AWS
    
    # Azure Detection
    if os.environ.get("WEBSITE_SITE_NAME") or os.environ.get("AZURE_FUNCTIONS_ENVIRONMENT"):
        return CloudProvider.AZURE
    
    # Try metadata endpoints (only on Linux to avoid hanging)
    if platform.system().lower() == "linux":
        # GCP metadata
        try:
            import urllib.request
            req = urllib.request.Request(
                "http://metadata.google.internal/computeMetadata/v1/project/project-id",
                headers={"Metadata-Flavor": "Google"}
            )
            urllib.request.urlopen(req, timeout=0.5)
            return CloudProvider.GCP
        except Exception:
            pass
        
        # AWS metadata
        try:
            import urllib.request
            urllib.request.urlopen("http://169.254.169.254/latest/meta-data/", timeout=0.5)
            return CloudProvider.AWS
        except Exception:
            pass
    
    return CloudProvider.LOCAL


def _get_container_memory_limit_gb() -> Optional[float]:
    """Get container memory limit from cgroups."""
    # cgroups v2
    cgroup_v2_path = "/sys/fs/cgroup/memory.max"
    if os.path.exists(cgroup_v2_path):
        try:
            with open(cgroup_v2_path) as f:
                value = f.read().strip()
                if value != "max":
                    return int(value) / (1024 ** 3)
        except Exception:
            pass
    
    # cgroups v1
    cgroup_v1_path = "/sys/fs/cgroup/memory/memory.limit_in_bytes"
    if os.path.exists(cgroup_v1_path):
        try:
            with open(cgroup_v1_path) as f:
                value = int(f.read().strip())
                # Check if it's the "unlimited" value
                if value < 9223372036854771712:  # Less than max int64
                    return value / (1024 ** 3)
        except Exception:
            pass
    
    return None


def _get_container_cpu_limit() -> Optional[float]:
    """Get container CPU limit from cgroups."""
    # cgroups v2
    cgroup_v2_path = "/sys/fs/cgroup/cpu.max"
    if os.path.exists(cgroup_v2_path):
        try:
            with open(cgroup_v2_path) as f:
                parts = f.read().strip().split()
                if parts[0] != "max":
                    quota = int(parts[0])
                    period = int(parts[1])
                    return quota / period
        except Exception:
            pass
    
    # cgroups v1
    quota_path = "/sys/fs/cgroup/cpu/cpu.cfs_quota_us"
    period_path = "/sys/fs/cgroup/cpu/cpu.cfs_period_us"
    if os.path.exists(quota_path) and os.path.exists(period_path):
        try:
            with open(quota_path) as f:
                quota = int(f.read().strip())
            with open(period_path) as f:
                period = int(f.read().strip())
            if quota > 0:
                return quota / period
        except Exception:
            pass
    
    return None


def _get_cloud_instance_info(provider: CloudProvider) -> Tuple[Optional[str], Optional[str]]:
    """Get cloud instance type and region."""
    instance_type = None
    region = None
    
    if provider == CloudProvider.GCP:
        # Try environment variables first
        region = os.environ.get("GOOGLE_CLOUD_REGION") or os.environ.get("CLOUD_RUN_REGION")
        # Machine type from metadata would require HTTP call
    
    elif provider == CloudProvider.AWS:
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        instance_type = os.environ.get("AWS_EXECUTION_ENV")
    
    elif provider == CloudProvider.AZURE:
        region = os.environ.get("REGION_NAME")
    
    return instance_type, region


# Scaling Profiles
@dataclass
class ScalingProfile:
    """Scaling profile for different workload sizes."""
    name: str
    min_rows: int
    max_rows: int
    num_workers: int
    chunk_size: int
    enable_streaming: bool = False
    memory_per_worker_mb: int = 256
    description: str = ""


@dataclass
class ScalingConfig:
    """Configuration for auto-scaling behavior."""
    # CPU thresholds
    cpu_scale_up_threshold: float = 50.0    # Scale up if CPU < this
    cpu_scale_down_threshold: float = 85.0   # Scale down if CPU > this
    
    # Memory thresholds
    memory_scale_down_threshold: float = 80.0  # Scale down if memory > this
    memory_warning_threshold: float = 90.0      # Log warning if memory > this
    
    # Worker limits
    min_workers: int = 1
    max_workers: int = field(default_factory=lambda: mp.cpu_count())
    
    # File-based scaling thresholds
    small_file_threshold: int = 1000
    medium_file_threshold: int = 10000
    large_file_threshold: int = 50000
    xlarge_file_threshold: int = 100000
    
    # Chunk sizes
    small_chunk_size: int = 500
    medium_chunk_size: int = 1000
    large_chunk_size: int = 2000
    xlarge_chunk_size: int = 5000
    
    # Monitoring
    check_interval_seconds: float = 5.0
    scale_cooldown_seconds: float = 30.0


# Resource Monitor
class ResourceMonitor:
    """
    Cross-platform resource monitor for auto-scaling decisions.
    
    Features:
    - Real-time CPU/Memory monitoring
    - Scaling profile recommendations
    - Container-aware resource limits
    - Cloud platform integration
    """
    
    def __init__(self, config: Optional[ScalingConfig] = None):
        """Initialize resource monitor with optional config."""
        self.config = config or ScalingConfig()
        self.platform = get_platform_info()
        self._psutil_available = self._check_psutil()
        self._last_scale_time = 0.0
        self._current_workers = self.config.min_workers
        
        # Adjust max workers based on container limits
        if self.platform.container_cpu_limit:
            self.config.max_workers = min(
                self.config.max_workers,
                max(1, int(self.platform.container_cpu_limit))
            )
        
        logger.info(f"ResourceMonitor initialized: {self.platform.os_type.value}, "
                   f"CPUs: {self.platform.cpu_count}, "
                   f"Memory: {self.platform.total_memory_gb:.1f}GB, "
                   f"Container: {self.platform.is_container}, "
                   f"Cloud: {self.platform.cloud_provider.value}")
    
    def _check_psutil(self) -> bool:
        """Check if psutil is available."""
        try:
            import psutil
            return True
        except ImportError:
            logger.warning("psutil not available - resource monitoring will be limited")
            return False
    
    def get_cpu_percent(self, interval: float = 1.0) -> float:
        """Get current CPU usage percentage (cross-platform)."""
        if self._psutil_available:
            import psutil
            return psutil.cpu_percent(interval=interval)
        
        # Linux fallback using /proc/stat
        if self.platform.os_type == OSType.LINUX:
            return self._get_cpu_percent_linux()
        
        # Windows fallback using WMI (slow, use sparingly)
        if self.platform.os_type == OSType.WINDOWS:
            return self._get_cpu_percent_windows()
        
        return 50.0  # Default assumption
    
    def _get_cpu_percent_linux(self) -> float:
        """Get CPU usage on Linux using /proc/stat."""
        try:
            with open("/proc/stat") as f:
                line = f.readline()
                parts = line.split()
                if parts[0] == "cpu":
                    user = int(parts[1])
                    nice = int(parts[2])
                    system = int(parts[3])
                    idle = int(parts[4])
                    iowait = int(parts[5]) if len(parts) > 5 else 0
                    
                    total = user + nice + system + idle + iowait
                    busy = user + nice + system
                    return (busy / total) * 100 if total > 0 else 0.0
        except Exception:
            pass
        return 50.0
    
    def _get_cpu_percent_windows(self) -> float:
        """Get CPU usage on Windows (basic fallback)."""
        # This is expensive without psutil, return default
        return 50.0
    
    def get_memory_percent(self) -> float:
        """Get current memory usage percentage (cross-platform)."""
        if self._psutil_available:
            import psutil
            return psutil.virtual_memory().percent
        
        # Linux fallback
        if self.platform.os_type == OSType.LINUX:
            return self._get_memory_percent_linux()
        
        return 50.0  # Default assumption
    
    def _get_memory_percent_linux(self) -> float:
        """Get memory usage on Linux using /proc/meminfo."""
        try:
            meminfo = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        meminfo[parts[0].rstrip(":")] = int(parts[1])
            
            total = meminfo.get("MemTotal", 1)
            available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
            used = total - available
            return (used / total) * 100
        except Exception:
            pass
        return 50.0
    
    def get_available_memory_gb(self) -> float:
        """Get available memory in GB."""
        if self._psutil_available:
            import psutil
            return psutil.virtual_memory().available / (1024 ** 3)
        
        # Use container limit if available
        if self.platform.container_memory_limit_gb:
            # Estimate available as 70% of limit
            return self.platform.container_memory_limit_gb * 0.7
        
        # Estimate from total
        return self.platform.total_memory_gb * 0.5
    
    def get_effective_cpu_count(self) -> int:
        """Get effective CPU count considering container limits."""
        if self.platform.container_cpu_limit:
            return max(1, int(self.platform.container_cpu_limit))
        return self.platform.cpu_count
    
    def get_scaling_profile(self, row_count: int) -> ScalingProfile:
        """
        Get recommended scaling profile based on file size and resources.
        
        This implements Level 1: File-Based Scaling.
        """
        effective_cpus = self.get_effective_cpu_count()
        available_memory = self.get_available_memory_gb()
        
        # Memory constraint check
        memory_per_worker = 0.25  # 256MB per worker estimate
        max_workers_by_memory = max(1, int(available_memory / memory_per_worker))
        
        # Determine profile based on row count
        if row_count < self.config.small_file_threshold:
            # Small files: single-threaded is faster (no process overhead)
            return ScalingProfile(
                name="single",
                min_rows=0,
                max_rows=self.config.small_file_threshold,
                num_workers=1,
                chunk_size=self.config.small_chunk_size,
                enable_streaming=False,
                description="Single-threaded for small files"
            )
        
        elif row_count < self.config.medium_file_threshold:
            # Medium files: half the CPUs
            workers = max(1, min(effective_cpus // 2, max_workers_by_memory))
            return ScalingProfile(
                name="medium",
                min_rows=self.config.small_file_threshold,
                max_rows=self.config.medium_file_threshold,
                num_workers=workers,
                chunk_size=self.config.medium_chunk_size,
                enable_streaming=False,
                description=f"Medium files: {workers} workers"
            )
        
        elif row_count < self.config.large_file_threshold:
            # Large files: 3/4 of CPUs
            workers = max(1, min(int(effective_cpus * 0.75), max_workers_by_memory))
            return ScalingProfile(
                name="large",
                min_rows=self.config.medium_file_threshold,
                max_rows=self.config.large_file_threshold,
                num_workers=workers,
                chunk_size=self.config.large_chunk_size,
                enable_streaming=False,
                description=f"Large files: {workers} workers"
            )
        
        elif row_count < self.config.xlarge_file_threshold:
            # XLarge files: all CPUs
            workers = max(1, min(effective_cpus, max_workers_by_memory))
            return ScalingProfile(
                name="xlarge",
                min_rows=self.config.large_file_threshold,
                max_rows=self.config.xlarge_file_threshold,
                num_workers=workers,
                chunk_size=self.config.xlarge_chunk_size,
                enable_streaming=False,
                description=f"XLarge files: {workers} workers"
            )
        
        else:
            # Huge files: streaming mode with all CPUs
            workers = max(1, min(effective_cpus, max_workers_by_memory))
            return ScalingProfile(
                name="streaming",
                min_rows=self.config.xlarge_file_threshold,
                max_rows=float('inf'),
                num_workers=workers,
                chunk_size=self.config.xlarge_chunk_size,
                enable_streaming=True,
                description=f"Streaming mode: {workers} workers"
            )
    
    def get_recommended_workers(self, current_workers: int) -> int:
        """
        Get recommended worker count based on current resource usage.
        
        This implements Level 2: Resource-Aware Scaling.
        """
        # Check cooldown
        now = time.time()
        if now - self._last_scale_time < self.config.scale_cooldown_seconds:
            return current_workers
        
        cpu_percent = self.get_cpu_percent(interval=0.5)
        memory_percent = self.get_memory_percent()
        
        recommended = current_workers
        
        # Scale down conditions (priority)
        if memory_percent > self.config.memory_scale_down_threshold:
            recommended = max(self.config.min_workers, current_workers - 1)
            logger.warning(f"Memory pressure ({memory_percent:.1f}%), scaling down to {recommended} workers")
        
        elif cpu_percent > self.config.cpu_scale_down_threshold:
            recommended = max(self.config.min_workers, current_workers - 1)
            logger.info(f"CPU high ({cpu_percent:.1f}%), scaling down to {recommended} workers")
        
        # Scale up conditions
        elif cpu_percent < self.config.cpu_scale_up_threshold and memory_percent < 60:
            recommended = min(self.config.max_workers, current_workers + 1)
            logger.info(f"Resources available (CPU: {cpu_percent:.1f}%), scaling up to {recommended} workers")
        
        if recommended != current_workers:
            self._last_scale_time = now
        
        return recommended
    
    def should_use_multiprocessing(self, row_count: int) -> bool:
        """Determine if multiprocessing should be used."""
        profile = self.get_scaling_profile(row_count)
        return profile.num_workers > 1
    
    def get_resource_summary(self) -> Dict[str, Any]:
        """Get a summary of current resource status."""
        return {
            "platform": {
                "os": self.platform.os_type.value,
                "cloud": self.platform.cloud_provider.value,
                "container": self.platform.container_runtime.value,
            },
            "cpu": {
                "count": self.platform.cpu_count,
                "effective": self.get_effective_cpu_count(),
                "usage_percent": self.get_cpu_percent(interval=0.1),
            },
            "memory": {
                "total_gb": round(self.platform.total_memory_gb, 2),
                "available_gb": round(self.get_available_memory_gb(), 2),
                "usage_percent": self.get_memory_percent(),
                "container_limit_gb": self.platform.container_memory_limit_gb,
            },
            "scaling": {
                "max_workers": self.config.max_workers,
                "psutil_available": self._psutil_available,
            }
        }


# Adaptive Worker Pool (Level 2)
class AdaptiveWorkerPool:
    """
    A worker pool that adapts to system resources during processing.
    
    Use this for long-running batch jobs where dynamic scaling is beneficial.
    """
    
    def __init__(self, 
                 monitor: Optional[ResourceMonitor] = None,
                 initial_workers: Optional[int] = None):
        """Initialize adaptive pool."""
        self.monitor = monitor or ResourceMonitor()
        self._initial_workers = initial_workers or self.monitor.get_effective_cpu_count() - 1
        self._current_workers = max(1, self._initial_workers)
        self._pool = None
        self._is_running = False
    
    def get_optimal_workers(self, row_count: int) -> int:
        """Get optimal worker count based on file size and resources."""
        profile = self.monitor.get_scaling_profile(row_count)
        return profile.num_workers
    
    def get_optimal_chunk_size(self, row_count: int) -> int:
        """Get optimal chunk size based on file size."""
        profile = self.monitor.get_scaling_profile(row_count)
        return profile.chunk_size
    
    def create_pool(self, num_workers: int, initializer: Callable = None, 
                    initargs: tuple = ()) -> mp.Pool:
        """Create a multiprocessing pool with the specified workers."""
        self._current_workers = num_workers
        self._pool = mp.Pool(
            processes=num_workers,
            initializer=initializer,
            initargs=initargs
        )
        self._is_running = True
        return self._pool
    
    def close(self):
        """Close the pool."""
        if self._pool:
            self._pool.close()
            self._pool.join()
            self._is_running = False
            self._pool = None


# Utility Functions
def get_multiprocessing_method() -> str:
    """Get the appropriate multiprocessing start method for the current OS."""
    platform_info = get_platform_info()
    
    if platform_info.os_type == OSType.WINDOWS:
        return "spawn"  # Windows only supports spawn
    elif platform_info.os_type == OSType.MACOS:
        return "spawn"  # macOS default changed to spawn in Python 3.8+
    else:
        return "fork"  # Linux defaults to fork (faster)


def configure_multiprocessing():
    """Configure multiprocessing for the current platform."""
    method = get_multiprocessing_method()
    try:
        mp.set_start_method(method, force=False)
        logger.debug(f"Multiprocessing start method set to: {method}")
    except RuntimeError:
        # Already set
        pass


def estimate_memory_for_rows(row_count: int, avg_text_length: int = 500) -> float:
    """
    Estimate memory required for processing in GB.
    
    Args:
        row_count: Number of rows to process
        avg_text_length: Average text length per row
        
    Returns:
        Estimated memory in GB
    """
    # Rough estimate: each row needs ~2x text length (original + cleaned)
    # Plus overhead for regex patterns, DataFrame, etc.
    bytes_per_row = avg_text_length * 2 * 1.5  # 1.5x for overhead
    total_bytes = row_count * bytes_per_row
    return total_bytes / (1024 ** 3)


def can_process_in_memory(row_count: int, avg_text_length: int = 500) -> bool:
    """Check if the data can be processed in memory."""
    monitor = ResourceMonitor()
    estimated_memory = estimate_memory_for_rows(row_count, avg_text_length)
    available = monitor.get_available_memory_gb()
    
    # Leave 20% buffer
    return estimated_memory < (available * 0.8)


# Module Initialization - Auto-configure multiprocessing on import
configure_multiprocessing()
