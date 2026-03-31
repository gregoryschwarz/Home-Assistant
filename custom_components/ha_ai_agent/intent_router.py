"""IntentRouter — local rule engine for NLU-02 (zero-latency commands) and NLU-05 (clear errors).

Compiles FR+EN regex patterns at module load time to route TURN_ON / TURN_OFF /
SET_TEMP / MEDIA_PLAY intents to hass.services.async_call without any LLM call.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled regex patterns (FR + EN, UNICODE, IGNORECASE)
# l['\u2019] handles both ASCII apostrophe and curly apostrophe (U+2019).
# ---------------------------------------------------------------------------

# TURN_ON: French + English
TURN_ON_RE = re.compile(
    r"(?:allume[rz]?|active[rz]?|mets?\s+en\s+marche|turn\s+on|switch\s+on|enable|open)\s+"
    r"(?:la\s+|le\s+|les\s+|l['\u2019]\s*)?(?P<entity>.+)",
    re.IGNORECASE | re.UNICODE,
)

# TURN_OFF: French + English
TURN_OFF_RE = re.compile(
    r"(?:\u00e9t(?:eins?|einds?)|\u00e9tein[dt]|d\u00e9sactive[rz]?|turn\s+off|switch\s+off|disable|close)\s+"
    r"(?:la\s+|le\s+|les\s+|l['\u2019]\s*)?(?P<entity>.+)",
    re.IGNORECASE | re.UNICODE,
)

# SET_TEMP: captures temperature value; entity text comes before the temperature.
# r[eè]gle handles both accented (règle) and unaccented (regle) input.
# [àa] handles à (with accent) and a (without).
SET_TEMP_RE = re.compile(
    r"(?:r[e\u00e8]gle[rz]?|mets?|chauffe[rz]?|set\s+(?:the\s+)?temperature|heat\s+to)\s+"
    r"(?:la\s+|le\s+|les\s+|l['\u2019]\s*)?(?P<entity>.*?)\s+[\u00e0a]?\s*(?P<temp>\d+(?:\.\d+)?)\s*"
    r"(?:degr[\u00e9e]s?|\u00b0[cCfF]?|degrees?)?",
    re.IGNORECASE | re.UNICODE,
)

# MEDIA_PLAY_PAUSE: French + English
MEDIA_RE = re.compile(
    r"(?:mets?\s+en\s+pause|lance[rz]?|joue[rz]?|reprends?|play|pause|resume)\s+"
    r"(?:la\s+|le\s+|les\s+|l['\u2019]\s*)?(?P<entity>.+)",
    re.IGNORECASE | re.UNICODE,
)


# ---------------------------------------------------------------------------
# IntentRouter
# ---------------------------------------------------------------------------


class IntentRouter:
    """Routes natural language text to HA intents via compiled regex patterns.

    No LLM call — zero latency for common commands (NLU-02).
    All errors returned as French strings — never re-raised (NLU-05).
    """

    def __init__(self, hass: HomeAssistant, allowed_domains: list[str]) -> None:
        self.hass = hass
        self.allowed_domains = allowed_domains

    async def async_route(self, text: str, language: str) -> str:
        """Match text against compiled patterns, resolve entity, call service.

        Returns a natural language French response string.
        """
        # Normalize curly apostrophe U+2019 -> ASCII apostrophe before matching
        text_normalized = text.replace("\u2019", "'")

        match = TURN_ON_RE.match(text_normalized)
        if match:
            return await self._dispatch(match.group("entity"), "turn_on", None)

        match = TURN_OFF_RE.match(text_normalized)
        if match:
            return await self._dispatch(match.group("entity"), "turn_off", None)

        match = SET_TEMP_RE.match(text_normalized)
        if match:
            extra = {"temperature": float(match.group("temp"))}
            entity_text = match.group("entity").strip() or "thermostat"
            return await self._dispatch(entity_text, "set_temperature", extra)

        match = MEDIA_RE.match(text_normalized)
        if match:
            return await self._dispatch(match.group("entity"), "media_play_pause", None)

        return "Je n'ai pas compris la commande."

    async def _dispatch(
        self,
        entity_text: str,
        service_name: str,
        extra_data: dict | None,
    ) -> str:
        """Resolve entity_id then call hass.services.async_call."""
        # Lazy import avoids circular dependency; entity_context stub available from plan 02-01
        from .entity_context import EntityContextBuilder
        from .const import DOMAIN

        # Retrieve shared EntityContextBuilder from hass.data if available (production path),
        # otherwise construct a local instance (unit-test path).
        ec: EntityContextBuilder | None = None
        for entry_data in self.hass.data.get(DOMAIN, {}).values():
            if isinstance(entry_data, dict) and "entity_context" in entry_data:
                ec = entry_data["entity_context"]
                break
        if ec is None:
            ec = EntityContextBuilder(self.hass, self.allowed_domains)

        entity_id = ec.resolve_entity(entity_text.strip())
        if entity_id is None:
            return f"Entite introuvable : {entity_text.strip()}."

        domain = entity_id.split(".")[0]
        service_data: dict = {"entity_id": entity_id}
        if extra_data:
            service_data.update(extra_data)

        try:
            await self.hass.services.async_call(
                domain=domain,
                service=service_name,
                service_data=service_data,
                blocking=True,
            )
        except ServiceNotFound:
            _LOGGER.warning("Service %s.%s not found", domain, service_name)
            return (
                f"Service {domain}.{service_name} introuvable. "
                "Verifiez que l'integration est active."
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Service call failed: %s", err)
            return f"Impossible d'executer la commande : {err}"

        action_label = {
            "turn_on": "allume",
            "turn_off": "eteint",
            "set_temperature": "regle",
            "media_play_pause": "controle",
        }.get(service_name, service_name)
        return f"D'accord, j'ai {action_label} {entity_text.strip()}."
