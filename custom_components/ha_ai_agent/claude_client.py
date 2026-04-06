"""ClaudeClient — async wrapper around AsyncAnthropic for HA LLM fallback.

Implements D-04 (1 retry with 1s backoff), D-07 (10s timeout),
D-08 (sliding window history), D-11 (domain validation),
D-18/D-19 (French error strings), D-20 (no re-raised exceptions).

Phase 6 additions:
  - async_complete gains optional habits param (D-03/D-04/D-05 from Phase 6 CONTEXT)
  - Relevant habits injected as "Habitudes connues" block after entity list
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque

from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    AuthenticationError,
)
from homeassistant.core import HomeAssistant

from .const import DEFAULT_MODEL, EXECUTE_HA_SERVICE_TOOL, MAX_HISTORY_TURNS, SYSTEM_PROMPT

_LOGGER = logging.getLogger(__name__)


class ClaudeClient:
    """Async wrapper around AsyncAnthropic for Home Assistant LLM fallback.

    Usage:
        client = ClaudeClient(hass, api_key, allowed_domains)
        response = await client.async_complete(text, entities)
        await client.async_close()
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        allowed_domains: list[str],
    ) -> None:
        self.hass = hass
        self._allowed_domains = allowed_domains
        self._client = AsyncAnthropic(
            api_key=api_key,
            timeout=10.0,      # D-07: max 10s per request
            max_retries=0,     # D-04: manual retry loop, not SDK retry
        )
        self._history: deque = deque(maxlen=MAX_HISTORY_TURNS)  # D-08

    # French day names indexed by ISO weekday (0=Monday … 6=Sunday) matching
    # the day_of_week field stored in the patterns table (strftime('%w', ...) = 0 Sunday).
    # Phase 5 uses SQLite strftime('%w') which is 0=Sunday, 1=Monday … 6=Saturday.
    _DOW_NAMES: list[str] = [
        "dimanche",  # 0 — SQLite %w: Sunday
        "lundi",     # 1
        "mardi",     # 2
        "mercredi",  # 3
        "jeudi",     # 4
        "vendredi",  # 5
        "samedi",    # 6
    ]

    async def async_complete(
        self,
        text: str,
        entities: list[dict],
        habits: "list[dict] | None" = None,
    ) -> str | None:
        """Call Claude API with the user text, entity list, and optional habits.

        Args:
            text: User command text.
            entities: List of dicts with keys entity_id, friendly_name, state.
            habits: Optional list of pattern dicts (D-04). Each dict must have
                entity_id, service, day_of_week, hour, occurrences keys.
                If None or empty, no habits block is injected (D-02).

        Returns a French string (action confirmation, free text, or error).
        Never raises — all errors are converted to French strings (D-20).
        """
        # Build entity list for context (D-13/D-14)
        entity_list_str = "\n".join(
            f"- {e['entity_id']} ({e['friendly_name']}, etat: {e['state']})"
            for e in entities
        )
        if entity_list_str:
            user_content = f"{text}\n\nEntites disponibles:\n{entity_list_str}"
        else:
            user_content = text

        # Inject habits block if relevant habits provided (D-05 Phase 6)
        if habits:
            habit_lines = []
            for h in habits:
                dow = int(h.get("day_of_week", 0))
                day_name = self._DOW_NAMES[dow % 7]
                hour = int(h.get("hour", 0))
                occurrences = int(h.get("occurrences", 0))
                entity_id = h.get("entity_id", "")
                service = h.get("service", "")
                habit_lines.append(
                    f"- {entity_id} {service} le {day_name} a {hour}h"
                    f" ({occurrences} fois en 14 jours)"
                )
            habits_block = "Habitudes connues (contexte personnel) :\n" + "\n".join(habit_lines)
            user_content = f"{user_content}\n\n{habits_block}"

        self._history.append({"role": "user", "content": user_content})

        system = SYSTEM_PROMPT.format(
            allowed_domains=", ".join(self._allowed_domains)
        )

        response = None
        for attempt in range(2):
            try:
                response = await self._client.messages.create(
                    model=DEFAULT_MODEL,
                    max_tokens=512,
                    system=system,
                    tools=[EXECUTE_HA_SERVICE_TOOL],
                    messages=list(self._history),
                )
                break
            except AuthenticationError:
                _LOGGER.warning("Claude API key invalid (401)")
                self._history.pop()
                return "Cle API Claude invalide. Verifiez la configuration."
            except (APIConnectionError, APITimeoutError) as err:
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                _LOGGER.warning("Claude API unreachable after retry: %s", err)
                self._history.pop()
                return "Service Claude indisponible, veuillez reessayer."
            except APIStatusError as err:
                _LOGGER.warning("Claude API error %s: %s", err.status_code, err)
                self._history.pop()
                return "Service Claude indisponible, veuillez reessayer."

        if response is None:
            return "Service Claude indisponible, veuillez reessayer."

        return await self._handle_response(response, text)

    async def _handle_response(self, response, original_text: str) -> str | None:
        """Parse the Claude response and dispatch accordingly."""
        if response.stop_reason == "tool_use":
            tool_block = next(
                (b for b in response.content if b.type == "tool_use"), None
            )
            if tool_block is None:
                return None
            tool_input = tool_block.input
            # D-11: validate domain against allowed list
            if tool_input["domain"] not in self._allowed_domains:
                _LOGGER.warning(
                    "Claude attempted call to non-allowed domain '%s'",
                    tool_input["domain"],
                )
                return "Action refusee : domaine non autorise dans la configuration."
            result_text = await self._execute_service(tool_input, original_text)
            # Pitfall 1: store only text strings in history, not content blocks
            self._history.append({"role": "assistant", "content": result_text})
            return result_text

        if response.stop_reason == "end_turn":
            text_blocks = [b for b in response.content if b.type == "text"]
            reply = text_blocks[0].text if text_blocks else None
            if reply:
                self._history.append({"role": "assistant", "content": reply})
            return reply

        return None

    async def _execute_service(self, tool_input: dict, original_text: str) -> str:
        """Execute the HA service call from a validated tool_use block."""
        from homeassistant.exceptions import HomeAssistantError, ServiceNotFound

        domain = tool_input["domain"]
        service = tool_input["service"]
        entity_id = tool_input["entity_id"]
        service_data: dict = dict(tool_input.get("service_data") or {})
        service_data["entity_id"] = entity_id

        try:
            await self.hass.services.async_call(
                domain=domain,
                service=service,
                service_data=service_data,
                blocking=True,
            )
        except ServiceNotFound:
            return f"Service {domain}.{service} introuvable."
        except HomeAssistantError as err:
            return f"Impossible d'executer la commande : {err}"

        return f"D'accord, j'ai effectue l'action sur {entity_id}."

    async def async_close(self) -> None:
        """Close the underlying AsyncAnthropic HTTP client (D-09)."""
        await self._client.close()
