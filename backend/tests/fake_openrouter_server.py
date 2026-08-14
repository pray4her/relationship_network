"""Compatibility wrapper; the Compose service imports fake_openrouter from the package."""

from relationship_network_api.fake_openrouter import app

__all__ = ["app"]
