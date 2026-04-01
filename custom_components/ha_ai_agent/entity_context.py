"""EntityContextBuilder — entity name resolution with 3-pass cascade."""
from __future__ import annotations

import re
import unicodedata
import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

FRENCH_ARTICLES = re.compile(
    r"\b(?:du|de\s+la|de\s+l['\u2019]\s*|des|de|la|le|les|l['\u2019]\s*)\b",
    re.IGNORECASE | re.UNICODE,
)


def _normalize(text: str) -> str:
    """Normalize to ASCII slug: curly apostrophe -> ASCII, strip accents, articles, lowercase."""
    text = text.replace("\u2019", "'")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = FRENCH_ARTICLES.sub(" ", text)
    text = re.sub(r"\s+", "_", text.strip().lower())
    return text.strip("_")


class EntityContextBuilder:
    """Resolve natural language entity names to HA entity_ids using 3-pass cascade."""

    def __init__(self, hass: HomeAssistant, allowed_domains: list[str]) -> None:
        self.hass = hass
        self.allowed_domains = allowed_domains

    def resolve_entity(self, user_entity_text: str) -> str | None:
        """Return entity_id or None using 3-pass cascade filtered to allowed_domains."""
        if not user_entity_text or not user_entity_text.strip():
            return None

        normalized = _normalize(user_entity_text)
        if not normalized:
            return None

        # Pass 1: Direct slug match against hass.states
        for domain in self.allowed_domains:
            candidate = f"{domain}.{normalized}"
            if self.hass.states.get(candidate) is not None:
                return candidate

        # Pass 2 + 3: Entity registry name, original_name, and alias match
        registry = er.async_get(self.hass)
        for entry in registry.entities.values():
            if entry.domain not in self.allowed_domains:
                continue
            candidates = [entry.name, entry.original_name]
            # Pass 3: aliases — guard against None and frozenset
            candidates.extend(entry.aliases or [])
            for name_candidate in candidates:
                if not name_candidate:
                    continue
                norm_candidate = _normalize(name_candidate)
                if normalized in norm_candidate or norm_candidate in normalized:
                    _LOGGER.debug(
                        "Resolved '%s' -> '%s' via registry match",
                        user_entity_text,
                        entry.entity_id,
                    )
                    return entry.entity_id

        _LOGGER.debug(
            "Could not resolve entity: '%s' (normalized: '%s')",
            user_entity_text,
            normalized,
        )
        return None

    def list_entities_for_llm(self, text: str, limit: int = 50) -> list[dict]:
        """Return filtered entity list for Claude API context (SEC-01, D-13/D-14/D-15).

        Returns list of {entity_id, friendly_name, state} dicts.
        Only entities in self.allowed_domains. Capped at `limit`.
        When over limit, prioritizes entities whose friendly_name shares tokens with text.
        """
        registry = er.async_get(self.hass)
        entities: list[dict] = []

        for entry in registry.entities.values():
            if entry.domain not in self.allowed_domains:
                continue
            state_obj = self.hass.states.get(entry.entity_id)
            entities.append({
                "entity_id": entry.entity_id,
                "friendly_name": entry.name or entry.original_name or entry.entity_id,
                "state": state_obj.state if state_obj else "unknown",
            })

        if len(entities) <= limit:
            return entities

        # D-15: prioritize entities whose friendly_name shares tokens with command text
        command_tokens = set(_normalize(text).split("_")) if text.strip() else set()

        def _score(entity: dict) -> int:
            name_tokens = set(_normalize(entity["friendly_name"]).split("_"))
            return len(name_tokens & command_tokens)

        entities.sort(key=_score, reverse=True)
        return entities[:limit]
