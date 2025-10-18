"""Tests for the HTTP API extensions."""

import json
from typing import List
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from proxmox_mcp.config.models import (
    APISettings,
    AuthConfig,
    Config,
    LoggingConfig,
    OAuthClient,
    ProxmoxConfig,
)
from proxmox_mcp.server import ProxmoxMCPServer


@pytest.fixture
def api_config() -> Config:
    """Return a configuration object with OAuth clients configured."""

    return Config(
        proxmox=ProxmoxConfig(host="test.proxmox.local", port=8006, verify_ssl=False, service="PVE"),
        auth=AuthConfig(user="user@pve", token_name="token", token_value="value"),
        logging=LoggingConfig(level="DEBUG"),
        api=APISettings(
            oauth_clients=[OAuthClient(client_id="web", client_secret="secret", scopes=["cluster:read"])],
            access_token_ttl_seconds=3600,
            cluster_event_interval_seconds=0.01,
        ),
    )


@pytest.fixture
def mock_proxmox_api() -> Mock:
    """Fixture returning a configured Proxmox API mock."""

    api_mock = Mock()
    api_mock.version.get.return_value = {"version": "test"}

    cluster_status = Mock()
    cluster_status.get.return_value = [
        {"type": "cluster", "name": "prod", "quorate": True},
        {"type": "node", "name": "node1"},
        {"type": "node", "name": "node2"},
    ]
    cluster_mock = Mock()
    cluster_mock.status = cluster_status
    api_mock.cluster = cluster_mock
    return api_mock


@pytest.fixture
def api_server(api_config: Config, mock_proxmox_api: Mock) -> ProxmoxMCPServer:
    """Instantiate a ProxmoxMCPServer with HTTP API enabled."""

    with patch("proxmox_mcp.server.load_config", return_value=api_config), patch(
        "proxmox_mcp.core.proxmox.ProxmoxAPI", return_value=mock_proxmox_api
    ):
        return ProxmoxMCPServer(config_path="dummy")


def test_token_endpoint_returns_access_token(api_server: ProxmoxMCPServer):
    """OAuth token endpoint should issue access tokens for valid clients."""

    client = TestClient(api_server.get_api_app())
    response = client.post(
        "/auth/token",
        data={"username": "web", "password": "secret"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["expires_in"] == api_server.oauth_manager.token_ttl


def test_token_endpoint_rejects_invalid_credentials(api_server: ProxmoxMCPServer):
    """OAuth token endpoint should reject invalid client credentials."""

    client = TestClient(api_server.get_api_app())
    response = client.post(
        "/auth/token",
        data={"username": "web", "password": "wrong"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 401


def test_cluster_sse_stream(api_server: ProxmoxMCPServer, mock_proxmox_api: Mock):
    """Cluster SSE endpoint should stream cluster updates when authorized."""

    client = TestClient(api_server.get_api_app())
    token_response = client.post(
        "/auth/token",
        data={"username": "web", "password": "secret"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    access_token = token_response.json()["access_token"]

    # SSE endpoint requires authorization
    unauthorized = client.get("/events/cluster")
    assert unauthorized.status_code == 401

    with client.stream("GET", "/events/cluster", headers={"Authorization": f"Bearer {access_token}"}) as stream:
        lines: List[str] = []
        for line in stream.iter_lines():
            if line:
                lines.append(line)
                break

    assert lines
    assert lines[0].startswith("data: ")
    data = json.loads(lines[0].replace("data: ", ""))
    assert data["nodes"] == 2
    assert data["quorum"] is True
