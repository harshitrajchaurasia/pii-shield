"""
YAML Configuration Loader for PI Remover Services.

Loads configuration from YAML files with support for:
- Multiple config files with merging
- Default values
- Command-line argument overrides
- Config file path specification via --config argument

Usage:
    # In your service:
    from shared.config_loader import get_config
    
    config = get_config('api_service')  # Loads config/api_service.yaml
    port = config.get('service.port', 8080)
    
    # Or with custom path:
    config = get_config(config_path='./my_config.yaml')

Version: 2.9.0
"""

import os
import sys
import yaml
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List, Union
from functools import lru_cache

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    YAML configuration loader with hierarchical key access and merging.
    
    Features:
    - Load from multiple YAML files with merging
    - Dot notation access (config.get('service.port'))
    - Default values
    - Deep merge of nested dictionaries
    - Command-line argument overrides
    """
    
    def __init__(self, config_data: Optional[Dict[str, Any]] = None):
        """Initialize with optional pre-loaded config data."""
        self._config: Dict[str, Any] = config_data or {}
    
    @classmethod
    def from_yaml(cls, *file_paths: Union[str, Path]) -> 'ConfigLoader':
        """
        Load configuration from one or more YAML files.
        Later files override earlier ones (deep merge).
        
        Args:
            *file_paths: One or more paths to YAML config files
            
        Returns:
            ConfigLoader instance with merged configuration
        """
        merged_config: Dict[str, Any] = {}
        
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"Config file not found: {path}")
                continue
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f) or {}
                    merged_config = cls._deep_merge(merged_config, file_config)
                    logger.info(f"Loaded config from: {path}")
            except yaml.YAMLError as e:
                logger.error(f"Error parsing YAML file {path}: {e}")
                raise
            except Exception as e:
                logger.error(f"Error loading config file {path}: {e}")
                raise
        
        return cls(merged_config)
    
    @classmethod
    def from_args(cls, service_name: str, args: Optional[List[str]] = None) -> 'ConfigLoader':
        """
        Load configuration based on command-line arguments.
        
        Supports:
        - --config <path>: Custom config file path
        - --port <port>: Override service port
        - --host <host>: Override service host
        - --environment <env>: Override environment (development/production)
        
        Args:
            service_name: Default service name (e.g., 'api_service')
            args: Command-line arguments (defaults to sys.argv[1:])
            
        Returns:
            ConfigLoader instance
        """
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--config', type=str, help='Path to config file')
        parser.add_argument('--port', type=int, help='Service port')
        parser.add_argument('--host', type=str, help='Service host')
        parser.add_argument('--environment', type=str, choices=['development', 'production'])
        
        # Parse known args only (allows other args to pass through)
        known_args, _ = parser.parse_known_args(args)
        
        # Determine config file path
        if known_args.config:
            config_path = Path(known_args.config).resolve()
            # Security: restrict config paths to allowed directories
            allowed_roots = cls._get_allowed_config_roots()
            if not any(cls._is_safe_path(config_path, root) for root in allowed_roots):
                logger.error(
                    f"Config path '{config_path}' is outside allowed directories. "
                    f"Allowed roots: {allowed_roots}"
                )
                raise ValueError(f"Config path not in allowed directories: {config_path}")
        else:
            # Look for config in standard locations
            config_path = cls._find_config_file(service_name)
        
        # Load base config
        loader = cls.from_yaml(config_path) if config_path else cls()
        
        # Apply command-line overrides
        if known_args.port:
            loader.set('service.port', known_args.port)
        if known_args.host:
            loader.set('service.host', known_args.host)
        if known_args.environment:
            loader.set('service.environment', known_args.environment)
        
        return loader

    @staticmethod
    def _is_safe_path(path: Path, allowed_root: Path) -> bool:
        """Check if a resolved path is within an allowed root directory."""
        try:
            path.resolve().relative_to(allowed_root.resolve())
            return True
        except ValueError:
            return False

    @staticmethod
    def _get_allowed_config_roots() -> List[Path]:
        """Return list of directories where config files are allowed."""
        # Project root (cwd) and its config subdirectory
        cwd = Path.cwd()
        roots = [cwd, cwd / 'config']
        # Also allow the package's own config directory
        pkg_root = Path(__file__).resolve().parent.parent
        roots.append(pkg_root / 'config')
        roots.append(pkg_root)
        return roots
    
    @staticmethod
    def _find_config_file(service_name: str) -> Optional[Path]:
        """Find config file in standard locations."""
        # Standard locations to search
        search_paths = [
            Path(f'config/{service_name}.yaml'),
            Path(f'../config/{service_name}.yaml'),
            Path(f'../../config/{service_name}.yaml'),
            Path(__file__).parent.parent / 'config' / f'{service_name}.yaml',
        ]
        
        for path in search_paths:
            if path.exists():
                return path.resolve()
        
        return None
    
    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries. Override values take precedence.
        
        Args:
            base: Base dictionary
            override: Dictionary with override values
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigLoader._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'service.port' or 'security.jwt_expiry_minutes')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'service.port')
            value: Value to set
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get an entire configuration section.
        
        Args:
            section: Section name (e.g., 'security')
            
        Returns:
            Dictionary containing the section or empty dict
        """
        return self.get(section, {})
    
    def require(self, key: str) -> Any:
        """
        Get a required configuration value. Raises error if not found.
        
        Args:
            key: Configuration key
            
        Returns:
            Configuration value
            
        Raises:
            ValueError: If key is not found
        """
        value = self.get(key)
        if value is None:
            raise ValueError(f"Required configuration key not found: {key}")
        return value
    
    def to_dict(self) -> Dict[str, Any]:
        """Return the entire configuration as a dictionary."""
        return self._config.copy()
    
    def __repr__(self) -> str:
        return f"ConfigLoader({list(self._config.keys())})"


# Global config cache
_config_cache: Dict[str, ConfigLoader] = {}


def get_config(
    service_name: Optional[str] = None,
    config_path: Optional[str] = None,
    reload: bool = False
) -> ConfigLoader:
    """
    Get or load configuration for a service.
    
    Args:
        service_name: Service name (e.g., 'api_service', 'web_service')
        config_path: Optional explicit path to config file
        reload: Force reload of configuration
        
    Returns:
        ConfigLoader instance
    """
    cache_key = config_path or service_name or 'default'
    
    if not reload and cache_key in _config_cache:
        return _config_cache[cache_key]
    
    if config_path:
        loader = ConfigLoader.from_yaml(config_path)
    elif service_name:
        loader = ConfigLoader.from_args(service_name)
    else:
        loader = ConfigLoader()
    
    _config_cache[cache_key] = loader
    return loader


def load_clients_config(config_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Load client credentials from clients.yaml.
    
    Args:
        config_path: Optional path to clients.yaml
        
    Returns:
        Dictionary of client configurations
    """
    if config_path:
        path = Path(config_path)
    else:
        # Search standard locations
        search_paths = [
            Path('config/clients.yaml'),
            Path('../config/clients.yaml'),
            Path(__file__).parent.parent / 'config' / 'clients.yaml',
        ]
        path = None
        for p in search_paths:
            if p.exists():
                path = p
                break
    
    if not path or not path.exists():
        logger.warning("clients.yaml not found, using default credentials")
        return {}
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
            return data.get('clients', {})
    except Exception as e:
        logger.error(f"Error loading clients config: {e}")
        return {}
