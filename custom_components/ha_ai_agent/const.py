"""Constants for the HA Autonomous AI Agent integration."""
DOMAIN = "ha_ai_agent"
CONF_API_KEY = "api_key"
DEFAULT_MODEL = "claude-sonnet-4-6"

CONF_ALLOWED_DOMAINS = "allowed_domains"
DEFAULT_ALLOWED_DOMAINS: list[str] = ["light", "switch", "climate", "media_player"]
