"""Config flow for HA Autonomous AI Agent (HA-02)."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_API_KEY, CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS, DOMAIN

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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "HaAiAgentOptionsFlow":
        """Return the options flow handler for domain whitelist configuration (SEC-03)."""
        return HaAiAgentOptionsFlow()


class HaAiAgentOptionsFlow(OptionsFlow):
    """Options flow for domain whitelist configuration (SEC-03)."""

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle domain whitelist options form."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ALLOWED_DOMAINS,
                        default=current.get(CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS),
                    ): vol.All(list, [str]),
                }
            ),
        )
