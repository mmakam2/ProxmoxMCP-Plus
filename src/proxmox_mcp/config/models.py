"""
Configuration models for the Proxmox MCP server.

This module defines Pydantic models for configuration validation:
- Proxmox connection settings
- Authentication credentials
- Logging configuration
- Tool-specific parameter models

The models provide:
- Type validation
- Default values
- Field descriptions
- Required vs optional field handling
"""
from typing import Optional, Annotated, List
from pydantic import BaseModel, Field

class NodeStatus(BaseModel):
    """Model for node status query parameters.
    
    Validates and documents the required parameters for
    querying a specific node's status in the cluster.
    """
    node: Annotated[str, Field(description="Name/ID of node to query (e.g. 'pve1', 'proxmox-node2')")]

class VMCommand(BaseModel):
    """Model for VM command execution parameters.
    
    Validates and documents the required parameters for
    executing commands within a VM via QEMU guest agent.
    """
    node: Annotated[str, Field(description="Host node name (e.g. 'pve1', 'proxmox-node2')")]
    vmid: Annotated[str, Field(description="VM ID number (e.g. '100', '101')")]
    command: Annotated[str, Field(description="Shell command to run (e.g. 'uname -a', 'systemctl status nginx')")]

class ProxmoxConfig(BaseModel):
    """Model for Proxmox connection configuration.
    
    Defines the required and optional parameters for
    establishing a connection to the Proxmox API server.
    Provides sensible defaults for optional parameters.
    """
    host: str  # Required: Proxmox host address
    port: int = 8006  # Optional: API port (default: 8006)
    verify_ssl: bool = True  # Optional: SSL verification (default: True)
    service: str = "PVE"  # Optional: Service type (default: PVE)

class AuthConfig(BaseModel):
    """Model for Proxmox authentication configuration.
    
    Defines the required parameters for API authentication
    using token-based authentication. All fields are required
    to ensure secure API access.
    """
    user: str  # Required: Username (e.g., 'root@pam')
    token_name: str  # Required: API token name
    token_value: str  # Required: API token secret


class OAuthClient(BaseModel):
    """Model representing an OAuth client credential pair."""

    client_id: Annotated[str, Field(description="Public identifier for the OAuth client")]
    client_secret: Annotated[str, Field(description="Private secret used to authenticate the client")]
    scopes: Annotated[List[str], Field(default_factory=list, description="List of scopes granted to the client")]


class APISettings(BaseModel):
    """Model for HTTP API configuration."""

    oauth_clients: Annotated[List[OAuthClient], Field(default_factory=list, description="Configured OAuth clients for token issuance")]
    access_token_ttl_seconds: Annotated[int, Field(default=3600, ge=60, le=86400, description="Lifetime for issued access tokens in seconds")]
    cluster_event_interval_seconds: Annotated[float, Field(default=5.0, gt=0, description="Polling interval for SSE cluster updates in seconds")]

class LoggingConfig(BaseModel):
    """Model for logging configuration.
    
    Defines logging parameters with sensible defaults.
    Supports both file and console logging with
    customizable format and log levels.
    """
    level: str = "INFO"  # Optional: Log level (default: INFO)
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # Optional: Log format
    file: Optional[str] = None  # Optional: Log file path (default: None for console logging)

class Config(BaseModel):
    """Root configuration model.
    
    Combines all configuration models into a single validated
    configuration object. All sections are required to ensure
    proper server operation.
    """
    proxmox: ProxmoxConfig  # Required: Proxmox connection settings
    auth: AuthConfig  # Required: Authentication credentials
    logging: LoggingConfig  # Required: Logging configuration
    api: APISettings = Field(default_factory=APISettings)  # Optional: HTTP API settings
