"""Config flow for HA Autonomous AI Agent (HA-02)."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_API_KEY, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class HaAiAgentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA AI Agent."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step — show API key form or create entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Prevent duplicate config entries (Pitfall 4 from research)
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            # Phase 1: store key as-is (no API validation yet)
            # Phase 3 will add: try minimal Anthropic API call, catch AuthenticationError,
            # set errors["base"] = "invalid_auth" and re-show form on failure
            return self.async_create_entry(
                title="HA AI Agent",
                data={CONF_API_KEY: user_input[CONF_API_KEY]},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
