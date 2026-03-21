"""
Singleton spaCy Model Manager for PI Remover.

Provides thread-safe, singleton management of spaCy models to:
- Prevent duplicate model loading (~500MB per model)
- Share model instances across PIRemover instances
- Support lazy loading and preloading
- Track model load times for metrics

Usage:
    from pi_remover.model_manager import SpacyModelManager
    
    # Get a model (lazy loads if needed)
    nlp = SpacyModelManager.get_model("en_core_web_lg")
    
    # Check if model is available
    if SpacyModelManager.is_model_available("en_core_web_lg"):
        nlp = SpacyModelManager.get_model("en_core_web_lg")
    
    # Preload models at startup
    SpacyModelManager.preload_models(["en_core_web_sm", "en_core_web_lg"])
    
    # Get load times for metrics
    load_times = SpacyModelManager.get_load_times()
"""

import time
import logging
import threading
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================================
# Check spaCy availability
# ============================================================================

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    spacy = None
    SPACY_AVAILABLE = False
    logger.info("spaCy not installed - NER features will be disabled")


# ============================================================================
# Model Info
# ============================================================================

@dataclass
class ModelInfo:
    """Information about a loaded spaCy model."""
    name: str
    nlp: Any  # spacy.Language
    load_time_seconds: float
    loaded_at: float  # timestamp
    disabled_pipes: List[str] = field(default_factory=list)
    
    @property
    def memory_estimate_mb(self) -> float:
        """Rough memory estimate based on model size."""
        # These are approximate sizes
        model_sizes = {
            "en_core_web_sm": 12,
            "en_core_web_md": 50,
            "en_core_web_lg": 560,
            "en_core_web_trf": 500,
        }
        return model_sizes.get(self.name, 100)


# ============================================================================
# Singleton Model Manager
# ============================================================================

class SpacyModelManager:
    """
    Thread-safe singleton manager for spaCy models.
    
    Ensures only one instance of each spaCy model is loaded,
    shared across all PIRemover instances.
    """
    
    # Class-level state (singleton pattern)
    _lock = threading.Lock()
    _models: Dict[str, ModelInfo] = {}
    _failed_models: Set[str] = set()  # Models that failed to load
    _initialized = False
    
    # Default pipes to disable for PI removal (speed optimization)
    DEFAULT_DISABLED_PIPES = ["parser", "lemmatizer", "attribute_ruler"]
    
    # Allowed models whitelist
    ALLOWED_MODELS = {"en_core_web_sm", "en_core_web_md", "en_core_web_lg", "en_core_web_trf"}
    
    @classmethod
    def _initialize(cls):
        """Initialize the manager (called once)."""
        if cls._initialized:
            return
        
        with cls._lock:
            if cls._initialized:
                return
            
            cls._initialized = True
            logger.debug("SpacyModelManager initialized")
    
    @classmethod
    def is_available(cls) -> bool:
        """Check if spaCy is available."""
        return SPACY_AVAILABLE
    
    @classmethod
    def is_model_available(cls, model_name: str) -> bool:
        """
        Check if a specific model is installed.
        
        Does not load the model - just checks if it can be loaded.
        """
        if not SPACY_AVAILABLE:
            return False
        
        # Check if already loaded
        if model_name in cls._models:
            return True
        
        # Check if already failed
        if model_name in cls._failed_models:
            return False
        
        # Check if model package is installed
        try:
            import importlib.util
            model_pkg = model_name.replace("-", "_")
            spec = importlib.util.find_spec(model_pkg)
            return spec is not None
        except Exception:
            return False
    
    @classmethod
    def get_available_models(cls) -> List[str]:
        """Get list of installed/available models."""
        available = []
        for model in cls.ALLOWED_MODELS:
            if cls.is_model_available(model):
                available.append(model)
        return available
    
    @classmethod
    def get_model(
        cls, 
        model_name: str, 
        disable_pipes: Optional[List[str]] = None
    ) -> Optional[Any]:
        """
        Get a spaCy model, loading it if necessary.
        
        Thread-safe - only one thread will load a model at a time.
        
        Args:
            model_name: Name of the spaCy model (e.g., "en_core_web_lg")
            disable_pipes: Pipeline components to disable (default: parser, lemmatizer)
            
        Returns:
            spacy.Language object, or None if loading failed
        """
        cls._initialize()
        
        if not SPACY_AVAILABLE:
            logger.debug("spaCy not available, returning None")
            return None
        
        # Validate model name
        if model_name not in cls.ALLOWED_MODELS:
            logger.warning(f"Model '{model_name}' not in allowed list: {cls.ALLOWED_MODELS}")
            return None
        
        # Check if already loaded
        if model_name in cls._models:
            return cls._models[model_name].nlp
        
        # Check if previously failed
        if model_name in cls._failed_models:
            logger.debug(f"Model '{model_name}' previously failed to load")
            return None
        
        # Load with lock (thread-safe)
        with cls._lock:
            # Double-check after acquiring lock
            if model_name in cls._models:
                return cls._models[model_name].nlp
            
            if model_name in cls._failed_models:
                return None
            
            # Load the model
            return cls._load_model(model_name, disable_pipes)
    
    @classmethod
    def _load_model(
        cls, 
        model_name: str, 
        disable_pipes: Optional[List[str]] = None
    ) -> Optional[Any]:
        """
        Internal method to load a model (must be called with lock held).
        """
        if disable_pipes is None:
            disable_pipes = cls.DEFAULT_DISABLED_PIPES
        
        start_time = time.time()
        
        try:
            logger.info(f"Loading spaCy model: {model_name}")
            nlp = spacy.load(model_name)
            
            # Disable unnecessary pipeline components for speed
            actually_disabled = []
            for pipe in disable_pipes:
                if pipe in nlp.pipe_names:
                    try:
                        nlp.disable_pipe(pipe)
                        actually_disabled.append(pipe)
                    except Exception as e:
                        logger.debug(f"Could not disable pipe '{pipe}': {e}")
            
            load_time = time.time() - start_time
            
            # Store model info
            model_info = ModelInfo(
                name=model_name,
                nlp=nlp,
                load_time_seconds=load_time,
                loaded_at=time.time(),
                disabled_pipes=actually_disabled,
            )
            cls._models[model_name] = model_info
            
            logger.info(
                f"Loaded spaCy model '{model_name}' in {load_time:.2f}s "
                f"(disabled: {actually_disabled})"
            )
            
            return nlp
            
        except OSError as e:
            cls._failed_models.add(model_name)
            logger.warning(
                f"spaCy model '{model_name}' not found. "
                f"Install with: python -m spacy download {model_name}"
            )
            return None
            
        except Exception as e:
            cls._failed_models.add(model_name)
            logger.error(f"Failed to load spaCy model '{model_name}': {e}")
            return None
    
    @classmethod
    def preload_models(cls, model_names: List[str]) -> Dict[str, bool]:
        """
        Preload multiple models at startup.
        
        Useful for warming up models before serving requests.
        
        Args:
            model_names: List of model names to preload
            
        Returns:
            Dict mapping model names to load success status
        """
        results = {}
        for model_name in model_names:
            nlp = cls.get_model(model_name)
            results[model_name] = nlp is not None
        return results
    
    @classmethod
    def unload_model(cls, model_name: str) -> bool:
        """
        Unload a model to free memory.
        
        Args:
            model_name: Name of model to unload
            
        Returns:
            True if model was unloaded, False if not found
        """
        with cls._lock:
            if model_name in cls._models:
                del cls._models[model_name]
                logger.info(f"Unloaded spaCy model: {model_name}")
                return True
            return False
    
    @classmethod
    def unload_all(cls):
        """Unload all models."""
        with cls._lock:
            model_names = list(cls._models.keys())
            cls._models.clear()
            cls._failed_models.clear()
            logger.info(f"Unloaded all spaCy models: {model_names}")
    
    @classmethod
    def get_loaded_models(cls) -> List[str]:
        """Get list of currently loaded model names."""
        return list(cls._models.keys())
    
    @classmethod
    def get_model_info(cls, model_name: str) -> Optional[ModelInfo]:
        """Get info about a loaded model."""
        return cls._models.get(model_name)
    
    @classmethod
    def get_load_times(cls) -> Dict[str, float]:
        """Get load times for all loaded models (for metrics)."""
        return {
            name: info.load_time_seconds 
            for name, info in cls._models.items()
        }
    
    @classmethod
    def get_total_memory_estimate_mb(cls) -> float:
        """Estimate total memory used by loaded models."""
        return sum(info.memory_estimate_mb for info in cls._models.values())
    
    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Get manager statistics for health checks."""
        return {
            "spacy_available": SPACY_AVAILABLE,
            "loaded_models": cls.get_loaded_models(),
            "failed_models": list(cls._failed_models),
            "available_models": cls.get_available_models(),
            "total_memory_mb": cls.get_total_memory_estimate_mb(),
            "load_times": cls.get_load_times(),
        }


# ============================================================================
# Convenience Function
# ============================================================================

def get_spacy_model(model_name: str = "en_core_web_lg") -> Optional[Any]:
    """
    Convenience function to get a spaCy model.
    
    Usage:
        nlp = get_spacy_model("en_core_web_lg")
        if nlp:
            doc = nlp(text)
    """
    return SpacyModelManager.get_model(model_name)


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "SpacyModelManager",
    "ModelInfo",
    "get_spacy_model",
    "SPACY_AVAILABLE",
]
