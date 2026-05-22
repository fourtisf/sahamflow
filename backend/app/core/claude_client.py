from anthropic import Anthropic

from app.core.config import settings

_client: Anthropic | None = None


def get_claude() -> Anthropic:
    """Lazy singleton Anthropic client. Reads ANTHROPIC_API_KEY from settings/env."""
    global _client
    if _client is None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client
