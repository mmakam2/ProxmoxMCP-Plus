"""OAuth utilities for the HTTP API."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence

from ..config.models import APISettings, OAuthClient


@dataclass
class TokenDetails:
    """Runtime details for an issued OAuth token."""

    token: str
    client_id: str
    expires_at: datetime
    scopes: Sequence[str]

    @property
    def expired(self) -> bool:
        """Return True if the token is expired."""

        return datetime.now(timezone.utc) >= self.expires_at


class OAuthManager:
    """In-memory OAuth token manager used by the HTTP API."""

    def __init__(self, settings: Optional[APISettings] = None):
        self.settings = settings or APISettings()
        self._clients: Dict[str, OAuthClient] = {
            client.client_id: client for client in self.settings.oauth_clients
        }
        self._tokens: Dict[str, TokenDetails] = {}

    @property
    def token_ttl(self) -> int:
        """Return the configured token TTL in seconds."""

        return int(self.settings.access_token_ttl_seconds)

    @property
    def is_configured(self) -> bool:
        """Whether at least one OAuth client has been configured."""

        return bool(self._clients)

    def authenticate(self, client_id: str, client_secret: str) -> Optional[OAuthClient]:
        """Validate client credentials and return the client definition."""

        client = self._clients.get(client_id)
        if not client:
            return None
        if not secrets.compare_digest(client.client_secret, client_secret):
            return None
        return client

    def issue_token(self, client: OAuthClient, scopes: Optional[Iterable[str]] = None) -> TokenDetails:
        """Create a new access token for the provided client."""

        requested_scopes: List[str] = list(scopes or client.scopes or [])
        token_value = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.token_ttl)
        token = TokenDetails(
            token=token_value,
            client_id=client.client_id,
            expires_at=expires_at,
            scopes=requested_scopes,
        )
        self._tokens[token_value] = token
        return token

    def validate_token(self, token_value: str, required_scopes: Optional[Iterable[str]] = None) -> TokenDetails:
        """Validate and return the token details."""

        self._purge_expired_tokens()
        token = self._tokens.get(token_value)
        if not token or token.expired:
            if token and token.expired:
                self._tokens.pop(token_value, None)
            raise ValueError("Invalid or expired token")

        if required_scopes:
            token_scopes = set(token.scopes)
            missing = [scope for scope in required_scopes if scope not in token_scopes]
            if missing:
                raise PermissionError("Token does not include required scopes")

        return token

    def _purge_expired_tokens(self) -> None:
        """Remove expired tokens from memory."""

        expired_tokens = [value for value, token in self._tokens.items() if token.expired]
        for value in expired_tokens:
            self._tokens.pop(value, None)
