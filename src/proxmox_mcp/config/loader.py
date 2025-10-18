"""
Configuration loading utilities for the Proxmox MCP server.

This module handles loading and validation of server configuration:
- JSON configuration file loading
- Environment variable handling
- Configuration validation using Pydantic models
- Error handling for invalid configurations

The module ensures that all required configuration is present
and valid before the server starts operation.
"""
import json
import os
from typing import Optional, Dict, Any, List

from .models import Config, OAuthClient

def _bool_from_env(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _load_env_clients(raw_value: Optional[str]) -> List[Dict[str, Any]]:
    if not raw_value:
        return []

    clients: List[Dict[str, Any]] = []
    for item in raw_value.split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.split(":")
        if len(parts) < 2:
            continue
        client_id, client_secret, *scope_parts = parts
        scopes: List[str] = []
        if scope_parts:
            scopes = [scope for scope in scope_parts[0].split("|") if scope]
        clients.append({
            "client_id": client_id,
            "client_secret": client_secret,
            "scopes": scopes,
        })
    return clients


def _load_config_from_env() -> Optional[Dict[str, Any]]:
    host = os.getenv("PROXMOX_HOST")
    user = os.getenv("PROXMOX_USER")
    token_name = os.getenv("PROXMOX_TOKEN_NAME")
    token_value = os.getenv("PROXMOX_TOKEN_VALUE")

    if not all([host, user, token_name, token_value]):
        return None

    proxmox_config: Dict[str, Any] = {
        "host": host,
        "port": int(os.getenv("PROXMOX_PORT", "8006")),
        "verify_ssl": _bool_from_env(os.getenv("PROXMOX_VERIFY_SSL"), True),
        "service": os.getenv("PROXMOX_SERVICE", "PVE"),
    }

    auth_config = {
        "user": user,
        "token_name": token_name,
        "token_value": token_value,
    }

    logging_config: Dict[str, Any] = {
        "level": os.getenv("LOG_LEVEL", "INFO"),
        "format": os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        "file": os.getenv("LOG_FILE"),
    }

    api_config: Dict[str, Any] = {
        "oauth_clients": _load_env_clients(os.getenv("API_OAUTH_CLIENTS")),
        "access_token_ttl_seconds": int(os.getenv("API_ACCESS_TOKEN_TTL", "3600")),
        "cluster_event_interval_seconds": float(os.getenv("API_CLUSTER_EVENT_INTERVAL", "5")),
    }

    return {
        "proxmox": proxmox_config,
        "auth": auth_config,
        "logging": logging_config,
        "api": api_config,
    }


def load_config(config_path: Optional[str] = None) -> Config:
    """Load and validate configuration from JSON file.

    Performs the following steps:
    1. Verifies config path is provided
    2. Loads JSON configuration file
    3. Validates required fields are present
    4. Converts to typed Config object using Pydantic
    
    Configuration must include:
    - Proxmox connection settings (host, port, etc.)
    - Authentication credentials (user, token)
    - Logging configuration
    
    Args:
        config_path: Path to the JSON configuration file
                    If not provided, raises ValueError

    Returns:
        Config object containing validated configuration:
        {
            "proxmox": {
                "host": "proxmox-host",
                "port": 8006,
                ...
            },
            "auth": {
                "user": "username",
                "token_name": "token-name",
                ...
            },
            "logging": {
                "level": "INFO",
                ...
            }
        }

    Raises:
        ValueError: If:
                 - Config path is not provided
                 - JSON is invalid
                 - Required fields are missing
                 - Field values are invalid
    """
    if not config_path:
        env_config = _load_config_from_env()
        if env_config:
            return Config(**env_config)
        raise ValueError("PROXMOX_MCP_CONFIG environment variable must be set")

    try:
        with open(config_path) as f:
            config_data = json.load(f)
            if not config_data.get('proxmox', {}).get('host'):
                raise ValueError("Proxmox host cannot be empty")
            if "api" in config_data and isinstance(config_data["api"], dict):
                raw_clients = config_data["api"].get("oauth_clients", [])
                config_data["api"]["oauth_clients"] = [OAuthClient(**client) if not isinstance(client, OAuthClient) else client for client in raw_clients]
            return Config(**config_data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load config: {e}")
