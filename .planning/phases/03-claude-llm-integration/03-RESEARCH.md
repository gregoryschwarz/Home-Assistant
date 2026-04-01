# Phase 3: Claude LLM Integration - Research

**Researched:** 2026-04-01
**Domain:** Anthropic Python SDK (AsyncAnthropic), HA entity registry, tool_use schema
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** `IntentRouter.async_route` retourne `None` (sentinel) quand aucun regex ne correspond — remplace le retour direct de `"Je n'ai pas compris la commande."` (ligne 96 actuelle).
- **D-02:** `conversation.py` détecte `None` et appelle `ClaudeClient.async_complete()`. Cela garde ClaudeClient hors de IntentRouter (séparation des responsabilités).
- **D-03:** Si Claude retourne une action exécutée avec succès, retourner la confirmation française. Si Claude ne peut pas résoudre non plus, retourner `"Je n'ai pas compris la commande."`.
- **D-04:** Wrapper async autour de `AsyncAnthropic` avec système de retry : 1 tentative automatique avec backoff exponentiel (1 s), puis abandon.
- **D-05:** Modèle : `claude-sonnet-4-6` (défini dans `const.py` comme `DEFAULT_MODEL`).
- **D-06:** La clé API est lue depuis `entry.data[CONF_API_KEY]` (déjà stockée en Phase 1).
- **D-07:** Timeout de 10 secondes par requête pour ne pas bloquer l'interface HA.
- **D-08:** Fenêtre glissante de 10 tours (5 échanges user/assistant) en mémoire dans `ClaudeClient`, rattachée à `entry_id`. Non persistée entre redémarrages HA.
- **D-09:** L'historique est réinitialisé si le composant est rechargé (unload/reload).
- **D-10:** Un seul tool déclaré : `execute_ha_service`. Paramètres : `domain` (str), `service` (str), `entity_id` (str), `service_data` (dict, optionnel).
- **D-11:** Validation stricte : si Claude retourne un `tool_use` avec `domain` non présent dans `CONF_ALLOWED_DOMAINS`, rejeter et retourner une erreur française sans exécuter.
- **D-12:** Si Claude retourne du texte libre sans tool_use, retourner ce texte directement comme réponse.
- **D-13:** Seules les entités des domaines `CONF_ALLOWED_DOMAINS` sont envoyées à Claude. Plafond de 50 entités max.
- **D-14:** Pour chaque entité, envoyer : `entity_id`, `friendly_name` (depuis `entity_registry`), `state` actuel. Pas d'attributs supplémentaires.
- **D-15:** Si plus de 50 entités dans les domaines autorisés, tronquer en priorisant les entités dont le `friendly_name` partage des tokens avec le texte de la commande.
- **D-16:** Prompt système en français, persona "assistant domotique Home Assistant". Include : liste des domaines autorisés, format de réponse attendu (tool_use ou texte), instruction de ne jamais inventer un `entity_id` absent de la liste fournie.
- **D-17:** Le system prompt est une constante dans `const.py` (pas de configuration utilisateur en v1).
- **D-18:** Si l'API Claude est injoignable après retry : retourner `"Service Claude indisponible, veuillez réessayer."` — pas d'exception non gérée.
- **D-19:** Si la clé API est absente ou invalide (401) : retourner `"Clé API Claude invalide. Vérifiez la configuration."` — logguer en `WARNING`.
- **D-20:** Les erreurs API sont loguées via `_LOGGER` mais jamais remontées à l'utilisateur en stack trace.

### Claude's Discretion
- Implémentation interne du retry (asyncio.sleep vs tenacity)
- Structure exacte du system prompt (wording, longueur)
- Format de troncature des entités au-delà de 50

### Deferred Ideas (OUT OF SCOPE)
- Persistance de l'historique entre redémarrages HA — différé Phase 5
- Configuration utilisateur du modèle Claude (mini vs sonnet) — différé v2
- Validation de la clé API au moment du setup (appel test) — différé v2
- Multi-actions dans un seul tour — différé, complexité hors scope v1
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NLU-03 | Les commandes ambiguës ou complexes sont envoyées à Claude avec la liste filtrée des entités HA pertinentes | AsyncAnthropic messages API + entity_registry list pattern + tool_use schema |
| SEC-01 | Seule la liste filtrée des entités pertinentes (pas l'état complet de tout HA) est envoyée à l'API Claude | `list_entities_for_llm()` method on `EntityContextBuilder`, cap at 50, allowed_domains filter |
</phase_requirements>

---

## Summary

Phase 3 wires `AsyncAnthropic` as a fallback NLU layer when the local `IntentRouter` returns `None`. The integration spans three files: `claude_client.py` (new), `intent_router.py` (line 96 sentinel change), and `conversation.py` (line 83 fallback branch). The `EntityContextBuilder` gains a `list_entities_for_llm()` method that reuses the existing `entity_registry` access already present in `resolve_entity`. The `hass.data[DOMAIN][entry_id]` dict in `__init__.py` gains a `"claude_client"` key at setup.

The Anthropic Python SDK (v0.27–<1, per `manifest.json`) exposes `AsyncAnthropic` with constructor-level `timeout` and `max_retries`. Decision D-04 requires 1 retry with 1 s backoff: set `max_retries=0` on the client and implement the retry loop manually with `asyncio.sleep(1)` to give full control over the 10 s timeout (D-07). The tool_use schema for `execute_ha_service` follows the standard JSON Schema `object` pattern; the response parsing path must handle both `stop_reason == "tool_use"` and free-text (`stop_reason == "end_turn"`).

**Primary recommendation:** Implement `ClaudeClient` as a standalone class in `claude_client.py` with an `async_complete(text, entities)` coroutine; keep the retry/timeout logic inside that class; keep domain validation in `conversation.py` so it matches the config-entry's live `CONF_ALLOWED_DOMAINS`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.27,<1 (latest stable: ~0.87) | AsyncAnthropic client, tool_use, error types | Official Anthropic SDK; already declared in `manifest.json` |
| asyncio | stdlib | `asyncio.sleep` for retry backoff | No extra dependency needed for 1-retry logic |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| homeassistant.helpers.entity_registry | HA built-in | `er.async_get(hass)` to list entities with `friendly_name` | In `list_entities_for_llm()` |
| unittest.mock.AsyncMock | stdlib | Mocking `AsyncAnthropic.messages.create` in tests | Standard pattern in this project (see `test_intent_router.py`) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual retry with asyncio.sleep | tenacity library | tenacity is not in manifest.json; adds a dependency for a trivial 1-retry case; asyncio.sleep is simpler |
| Constructor-level `max_retries=0` | SDK built-in retries | SDK retries on 429/5xx only, not on `APITimeoutError` with our 10 s custom timeout; manual loop gives exact control |

**Installation:** Already declared in `manifest.json` — no new packages required for Phase 3.

---

## Architecture Patterns

### Recommended Project Structure (additions)
```
custom_components/ha_ai_agent/
├── claude_client.py      # NEW: ClaudeClient wrapper (plan 03-01)
├── const.py              # EXTEND: add SYSTEM_PROMPT, MAX_HISTORY_TURNS constants
├── intent_router.py      # MODIFY line 96: return None instead of string
├── conversation.py       # MODIFY line 83: add None-check + Claude fallback
└── entity_context.py     # EXTEND: add list_entities_for_llm() method

tests/
└── test_claude_client.py # NEW: Wave 0 scaffold
```

### Pattern 1: AsyncAnthropic Initialization with Timeout
**What:** Construct `AsyncAnthropic` with `api_key`, `timeout`, and `max_retries=0` at class init time. Reuse the single client instance for all calls.
**When to use:** In `ClaudeClient.__init__`.
```python
# Source: https://platform.claude.com/docs/en/api/sdks/python
from anthropic import AsyncAnthropic

self._client = AsyncAnthropic(
    api_key=api_key,
    timeout=10.0,    # D-07: 10 s timeout
    max_retries=0,   # D-04: manual retry, not SDK retry
)
```

### Pattern 2: messages.create with tool_use
**What:** Single API call with system prompt, conversation history, and `tools` parameter.
**When to use:** In `ClaudeClient.async_complete()`.
```python
# Source: https://platform.claude.com/docs/en/api/sdks/python
response = await self._client.messages.create(
    model=DEFAULT_MODEL,
    max_tokens=512,
    system=SYSTEM_PROMPT,
    tools=[EXECUTE_HA_SERVICE_TOOL],
    messages=self._history,  # sliding window
)
```

### Pattern 3: Manual 1-Retry with Exponential Backoff
**What:** Try once, catch `APIConnectionError` / `APITimeoutError`, sleep 1 s, retry once, then raise.
**When to use:** In `ClaudeClient.async_complete()` to implement D-04 without tenacity.
```python
# Source: D-04 decision + asyncio stdlib
import asyncio
from anthropic import APIConnectionError, APITimeoutError

for attempt in range(2):
    try:
        response = await self._client.messages.create(...)
        break
    except (APIConnectionError, APITimeoutError):
        if attempt == 0:
            await asyncio.sleep(1)
            continue
        raise
```

### Pattern 4: Response Parsing — tool_use vs text
**What:** After `messages.create`, check `response.stop_reason` to branch between tool call and free text.
**When to use:** After the API call in `async_complete()`.
```python
# Source: https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
if response.stop_reason == "tool_use":
    tool_block = next(
        b for b in response.content if b.type == "tool_use"
    )
    tool_input = tool_block.input  # dict: domain, service, entity_id, [service_data]
    # validate domain, call hass.services.async_call
elif response.stop_reason == "end_turn":
    text_block = next(b for b in response.content if b.type == "text")
    return text_block.text  # D-12: return free text directly
```

### Pattern 5: Conversation History Sliding Window
**What:** Maintain a `deque(maxlen=10)` of message dicts (`{"role": "user"|"assistant", "content": ...}`). Append user message before the call; append assistant response after.
**When to use:** In `ClaudeClient` to implement D-08 (10 turns = 5 user+assistant pairs).
```python
from collections import deque

self._history: deque = deque(maxlen=10)

# Before call:
self._history.append({"role": "user", "content": text})
# After successful call:
self._history.append({"role": "assistant", "content": response.content})

# Pass as list to API:
messages=list(self._history)
```

### Pattern 6: entity_registry List for LLM Context
**What:** Iterate `er.async_get(hass).entities`, filter by `allowed_domains`, collect `entity_id + friendly_name + state`.
**When to use:** In `EntityContextBuilder.list_entities_for_llm()` — reuses the registry access already in `resolve_entity`.
```python
# Source: entity_context.py existing code (Pass 2 pattern) + hass.states.get()
from homeassistant.helpers import entity_registry as er

registry = er.async_get(self.hass)
entities = []
for entry in registry.entities.values():
    if entry.domain not in self.allowed_domains:
        continue
    state_obj = self.hass.states.get(entry.entity_id)
    entities.append({
        "entity_id": entry.entity_id,
        "friendly_name": entry.name or entry.original_name or entry.entity_id,
        "state": state_obj.state if state_obj else "unknown",
    })
```

### Pattern 7: Priority Truncation at 50 Entities
**What:** Score entities by token overlap with command text, sort descending, take first 50.
**When to use:** When `len(entities) > 50` in `list_entities_for_llm`.
```python
# D-15: token overlap scoring (same logic as EntityContextBuilder._normalize)
def _score(entity: dict, command_tokens: set[str]) -> int:
    name_tokens = set(_normalize(entity["friendly_name"]).split("_"))
    return len(name_tokens & command_tokens)

command_tokens = set(_normalize(text).split("_"))
entities.sort(key=lambda e: _score(e, command_tokens), reverse=True)
entities = entities[:50]
```

### Pattern 8: Error Handling Map (D-18/D-19)
**What:** Catch specific Anthropic exception types and return French error strings.
```python
# Source: https://platform.claude.com/docs/en/api/sdks/python (error table)
from anthropic import AuthenticationError, APIConnectionError, APITimeoutError, APIStatusError

except AuthenticationError:
    _LOGGER.warning("Claude API key invalid (401)")
    return "Clé API Claude invalide. Vérifiez la configuration."
except (APIConnectionError, APITimeoutError):
    _LOGGER.warning("Claude API unreachable after retry: %s", err)
    return "Service Claude indisponible, veuillez réessayer."
except APIStatusError as err:
    _LOGGER.warning("Claude API error %s: %s", err.status_code, err)
    return "Service Claude indisponible, veuillez réessayer."
```

### Anti-Patterns to Avoid
- **Do not put `ClaudeClient` inside `IntentRouter`.** D-02 requires separation; `IntentRouter` stays pure regex, fallback is wired in `conversation.py`.
- **Do not use SDK built-in `max_retries`.** The SDK retries on 429/5xx but not on `APITimeoutError` with a custom 10 s timeout. Use `max_retries=0` and a manual loop.
- **Do not pass `hass.states.async_all()` attributes to the API.** Only `entity_id`, `friendly_name`, `state` per D-14.
- **Do not re-raise exceptions from `ClaudeClient.async_complete()`.** All errors return French strings per D-18/D-19/D-20.
- **Do not use `AbstractConversationAgent`.** Deprecated as of HA 2024.6 (comment in conversation.py line 6). The existing `ConversationEntity` base class is already correct.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async HTTP to Anthropic API | Custom httpx client | `AsyncAnthropic` from `anthropic` SDK | SDK handles auth headers, version headers, response parsing, error types |
| JSON Schema for tool inputs | Ad-hoc dict | Standard `input_schema` with `type: object, properties, required` | SDK validates schema at init; Claude enforces it |
| Entity name lookup | Re-implement | Existing `EntityContextBuilder.resolve_entity()` | Already handles 3-pass cascade and normalization |

**Key insight:** The `anthropic` SDK is already in `manifest.json` — Phase 3 only needs to instantiate it correctly.

---

## Exact Injection Points

### `intent_router.py` — line 96
**Current (to change):**
```python
return "Je n'ai pas compris la commande."
```
**Change to:**
```python
return None  # D-01: sentinel for LLM fallback
```
Also change return type annotation on `async_route` from `str` to `str | None`.

### `conversation.py` — line 83
**Current (to change):**
```python
router: IntentRouter = self.hass.data[DOMAIN][self._entry.entry_id]["router"]
response_text = await router.async_route(
    text=user_input.text,
    language=user_input.language,
)
```
**Change to (D-02):** Add None-check after `async_route`, fall through to `claude_client`:
```python
router: IntentRouter = self.hass.data[DOMAIN][self._entry.entry_id]["router"]
response_text = await router.async_route(
    text=user_input.text,
    language=user_input.language,
)
if response_text is None:
    claude_client = self.hass.data[DOMAIN][self._entry.entry_id]["claude_client"]
    entity_context = self.hass.data[DOMAIN][self._entry.entry_id]["entity_context"]
    entities = entity_context.list_entities_for_llm(user_input.text)
    response_text = await claude_client.async_complete(user_input.text, entities)
    if response_text is None:
        response_text = "Je n'ai pas compris la commande."
```

### `__init__.py` — `async_setup_entry` (line 14–26)
**Add after `entity_context = EntityContextBuilder(...)` (line 19):**
```python
from .claude_client import ClaudeClient
from .const import CONF_API_KEY
claude_client = ClaudeClient(
    hass=hass,
    api_key=entry.data[CONF_API_KEY],
    allowed_domains=allowed_domains,
)
hass.data[DOMAIN][entry.entry_id] = {
    "entry": entry,
    "router": router,
    "entity_context": entity_context,
    "claude_client": claude_client,   # D-06
}
```

### `const.py` — extend with new constants
```python
CONF_API_KEY = "api_key"
DEFAULT_MODEL = "claude-sonnet-4-6"    # already present — D-05
CONF_ALLOWED_DOMAINS = "allowed_domains"
DEFAULT_ALLOWED_DOMAINS: list[str] = ["light", "switch", "climate", "media_player"]
MAX_HISTORY_TURNS = 10                  # D-08: sliding window size
SYSTEM_PROMPT = (                       # D-16/D-17
    "Tu es un assistant domotique Home Assistant. ..."
)
```

### `entity_context.py` — add `list_entities_for_llm()` method
Add to `EntityContextBuilder` class after `resolve_entity` (after line 75). Does not modify `resolve_entity`.

---

## tool_use Schema Definition

The `execute_ha_service` tool definition to pass as `tools=[...]` in the messages.create call:

```python
# Source: https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools
EXECUTE_HA_SERVICE_TOOL = {
    "name": "execute_ha_service",
    "description": (
        "Appelle un service Home Assistant pour contrôler une entité. "
        "Utilise ce tool uniquement quand la commande de l'utilisateur demande une action "
        "sur une entité domotique (lumière, interrupteur, thermostat, lecteur média). "
        "Ne jamais inventer un entity_id absent de la liste fournie. "
        "Si l'entité demandée n'existe pas dans la liste, réponds en texte libre sans appeler ce tool."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domaine HA de l'entité (ex: light, switch, climate, media_player).",
            },
            "service": {
                "type": "string",
                "description": "Service HA à appeler (ex: turn_on, turn_off, set_temperature, media_play_pause).",
            },
            "entity_id": {
                "type": "string",
                "description": "L'identifiant exact de l'entité tel que fourni dans la liste des entités disponibles.",
            },
            "service_data": {
                "type": "object",
                "description": "Paramètres additionnels du service (ex: {'temperature': 21} pour climate.set_temperature). Omettre si non nécessaire.",
            },
        },
        "required": ["domain", "service", "entity_id"],
    },
}
```

**Validation at call time (D-11):**
```python
tool_input = tool_block.input
if tool_input["domain"] not in self._allowed_domains:
    _LOGGER.warning(
        "Claude attempted call to non-allowed domain '%s'", tool_input["domain"]
    )
    return "Action refusée : domaine non autorisé dans la configuration."
```

---

## Common Pitfalls

### Pitfall 1: History Deque Includes tool_use Content Blocks
**What goes wrong:** The Anthropic API requires that when an assistant message contains `tool_use` blocks, the next user message must contain matching `tool_result` blocks. Appending a raw `response.content` list (which may contain tool_use blocks) to history without also appending the tool_result will cause a 400 API error on the next turn.
**Why it happens:** `response.content` is a list of content blocks, not a plain string. Naively appending it creates an incomplete conversation turn.
**How to avoid:** After executing the tool, store the assistant turn (with tool_use) AND the user turn (with tool_result) together before the next call, OR store only the final text response in history (simpler for v1).
**For v1 simplest approach:** Store only text content in history — strip tool_use blocks:
```python
# After successful tool execution, store only the confirmation text
self._history.append({"role": "user", "content": user_text})
self._history.append({"role": "assistant", "content": confirmation_text})
```

### Pitfall 2: SDK Default `max_retries=2` Conflicts with D-04
**What goes wrong:** The SDK default is `max_retries=2` with backoff on 408/409/429/5xx. This ignores `APITimeoutError` from our custom 10 s timeout and may produce up to 3 total attempts (vs. D-04's 1 retry = 2 attempts).
**How to avoid:** Always set `max_retries=0` at `AsyncAnthropic(...)` constructor. Implement the 1-retry loop manually with `asyncio.sleep(1)`.

### Pitfall 3: SDK Default Timeout is 10 Minutes, Not 10 Seconds
**What goes wrong:** Without explicitly setting `timeout=10.0`, requests can block HA's event loop for up to 10 minutes on a slow or hanging API response.
**How to avoid:** Always pass `timeout=10.0` to `AsyncAnthropic(...)` constructor. D-07 is mandatory.

### Pitfall 4: `entry.data` vs `entry.options` for API Key
**What goes wrong:** The API key is stored in `entry.data[CONF_API_KEY]` (set in `config_flow.async_step_user`). `entry.options` holds only `CONF_ALLOWED_DOMAINS`. Using `entry.options.get(CONF_API_KEY)` always returns `None`.
**How to avoid:** Use `entry.data[CONF_API_KEY]` in `ClaudeClient.__init__`. The `__init__.py` already reads `CONF_ALLOWED_DOMAINS` from `entry.options` (line 17) — the API key is different.

### Pitfall 5: `friendly_name` from `entity_registry` vs `hass.states`
**What goes wrong:** `hass.states.get(entity_id).attributes["friendly_name"]` is set by the device firmware and may differ from the registry name the user configured in HA. The `EntityContextBuilder` already uses `entry.name or entry.original_name` from the registry — continue that pattern for `list_entities_for_llm()`.
**How to avoid:** Use `entry.name or entry.original_name or entry.entity_id` from the registry entry, not `state.attributes.get("friendly_name")`.

### Pitfall 6: `async_route` Return Type Change Breaks Tests
**What goes wrong:** Existing tests in `test_intent_router.py` assert `isinstance(result, str)` and `len(result) > 0`. After the D-01 change (return `None`), `test_unrecognized_command_returns_fallback` (line 117) will fail because the function now returns `None`.
**How to avoid:** Update `test_unrecognized_command_returns_fallback` to assert `result is None` instead. Document this test change in plan 03-01.

---

## Code Examples

### Full ClaudeClient skeleton
```python
# Source: official SDK docs + project patterns
from __future__ import annotations

import asyncio
import logging
from collections import deque

from anthropic import (
    AsyncAnthropic,
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    APIStatusError,
)
from homeassistant.core import HomeAssistant

from .const import DEFAULT_MODEL, MAX_HISTORY_TURNS, SYSTEM_PROMPT, EXECUTE_HA_SERVICE_TOOL

_LOGGER = logging.getLogger(__name__)


class ClaudeClient:
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
            timeout=10.0,
            max_retries=0,
        )
        self._history: deque = deque(maxlen=MAX_HISTORY_TURNS)

    async def async_complete(
        self, text: str, entities: list[dict]
    ) -> str | None:
        """Call Claude API with fallback. Returns French string or None."""
        entity_list_str = "\n".join(
            f"- {e['entity_id']} ({e['friendly_name']}, état: {e['state']})"
            for e in entities
        )
        user_content = f"{text}\n\nEntités disponibles:\n{entity_list_str}"
        self._history.append({"role": "user", "content": user_content})

        for attempt in range(2):
            try:
                response = await self._client.messages.create(
                    model=DEFAULT_MODEL,
                    max_tokens=512,
                    system=SYSTEM_PROMPT,
                    tools=[EXECUTE_HA_SERVICE_TOOL],
                    messages=list(self._history),
                )
                break
            except AuthenticationError:
                _LOGGER.warning("Claude API key invalid (401)")
                self._history.pop()
                return "Clé API Claude invalide. Vérifiez la configuration."
            except (APIConnectionError, APITimeoutError) as err:
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                _LOGGER.warning("Claude API unreachable after retry: %s", err)
                self._history.pop()
                return "Service Claude indisponible, veuillez réessayer."
            except APIStatusError as err:
                _LOGGER.warning("Claude API error %s: %s", err.status_code, err)
                self._history.pop()
                return "Service Claude indisponible, veuillez réessayer."

        return await self._handle_response(response, text)

    async def _handle_response(self, response, original_text: str) -> str:
        if response.stop_reason == "tool_use":
            tool_block = next(b for b in response.content if b.type == "tool_use")
            tool_input = tool_block.input
            if tool_input["domain"] not in self._allowed_domains:
                _LOGGER.warning(
                    "Claude attempted non-allowed domain '%s'", tool_input["domain"]
                )
                return "Action refusée : domaine non autorisé dans la configuration."
            # Execute the service call
            result_text = await self._execute_service(tool_input, original_text)
            self._history.append({"role": "assistant", "content": result_text})
            return result_text
        elif response.stop_reason == "end_turn":
            text_blocks = [b for b in response.content if b.type == "text"]
            reply = text_blocks[0].text if text_blocks else None
            if reply:
                self._history.append({"role": "assistant", "content": reply})
            return reply
        return None

    async def _execute_service(self, tool_input: dict, original_text: str) -> str:
        from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
        domain = tool_input["domain"]
        service = tool_input["service"]
        entity_id = tool_input["entity_id"]
        service_data = tool_input.get("service_data") or {}
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
            return f"Impossible d'exécuter la commande : {err}"
        return f"D'accord, j'ai effectué l'action sur {entity_id}."
```

### Mocking AsyncAnthropic in Tests
```python
# Source: test_intent_router.py pattern (AsyncMock) + Anthropic SDK response shape
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

_CLAUDE_PATCH = "custom_components.ha_ai_agent.claude_client.AsyncAnthropic"

async def test_claude_returns_tool_use(hass):
    mock_response = MagicMock()
    mock_response.stop_reason = "tool_use"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {"domain": "light", "service": "turn_on", "entity_id": "light.salon"}
    mock_response.content = [tool_block]

    with patch(_CLAUDE_PATCH) as MockAsyncAnthropic:
        instance = MockAsyncAnthropic.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)
        # ... test ClaudeClient with this mock
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `AbstractConversationAgent` | `ConversationEntity` | HA 2024.6 | `_async_handle_message(user_input, chat_log)` signature; already used in Phase 2 |
| Direct `anthropic.Anthropic` (sync) | `anthropic.AsyncAnthropic` | SDK v0.5+ | Required for HA event loop compatibility |

---

## Open Questions

1. **System prompt wording**
   - What we know: D-16 requires French, persona "assistant domotique HA", include allowed domains, no invented entity_ids.
   - What's unclear: Exact token length and format of the entity list within the system prompt vs. user message.
   - Recommendation: Include allowed domains in system prompt; include the entity list in the user message (not system) so it updates per call. System prompt is a constant.

2. **History deque with tool_use turns**
   - What we know: Storing raw `response.content` (list of content blocks) in history will cause API errors on the next turn if it contains unresolved tool_use blocks.
   - Recommendation: For v1, store only text strings in history (user text + confirmation text). See Pitfall 1. Defer full multi-turn tool-use conversation history to Phase 5.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| anthropic SDK | ClaudeClient | Declared in manifest.json | >=0.27,<1 | None — required |
| Python asyncio | Retry backoff | Always available in HA | stdlib | — |
| homeassistant.helpers.entity_registry | list_entities_for_llm | HA built-in | HA 2026.x | — |

All dependencies are available. No missing blocking dependencies.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (asyncio_mode = auto) |
| Config file | pyproject.toml (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/test_claude_client.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NLU-03 | Ambiguous command triggers Claude with filtered entities | unit | `pytest tests/test_claude_client.py::test_async_complete_tool_use -x` | Wave 0 |
| NLU-03 | Free-text response returned directly | unit | `pytest tests/test_claude_client.py::test_async_complete_free_text -x` | Wave 0 |
| NLU-03 | Fallback branch wired in conversation.py | integration | `pytest tests/test_conversation_bridge.py -x` | Wave 0 |
| SEC-01 | Only entities in allowed_domains sent to API | unit | `pytest tests/test_entity_resolver.py::test_list_entities_for_llm_filters_domains -x` | Wave 0 |
| SEC-01 | Entity list capped at 50 | unit | `pytest tests/test_entity_resolver.py::test_list_entities_for_llm_cap -x` | Wave 0 |
| D-11 | Non-allowed domain rejected without execution | unit | `pytest tests/test_claude_client.py::test_domain_validation_rejects -x` | Wave 0 |
| D-18 | API timeout returns French error string | unit | `pytest tests/test_claude_client.py::test_api_timeout_returns_error -x` | Wave 0 |
| D-19 | Invalid API key returns French error string | unit | `pytest tests/test_claude_client.py::test_auth_error_returns_error -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_claude_client.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_claude_client.py` — covers NLU-03, D-11, D-18, D-19 (new file)
- [ ] `tests/test_entity_resolver.py::test_list_entities_for_llm_*` — covers SEC-01 (new tests in existing file)
- [ ] `tests/test_conversation_bridge.py` — integration test for None-sentinel path in conversation.py

---

## Project Constraints (from CLAUDE.md)

CLAUDE.md currently states: "Projet vide — en cours d'initialisation via `/gsd:new-project`."

No actionable directives beyond the standard. All constraints come from CONTEXT.md decisions listed above.

Established project-wide conventions (from codebase inspection):
- `from __future__ import annotations` at top of every Python file
- `_LOGGER = logging.getLogger(__name__)` pattern in every module
- All error returns are French strings, never exceptions propagated to UI
- `AsyncMock` + `patch` from `unittest.mock` for all test doubles
- Type annotations on all public method signatures

---

## Sources

### Primary (HIGH confidence)
- https://platform.claude.com/docs/en/api/sdks/python — AsyncAnthropic, timeout, max_retries, error types, retry behavior
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools — tool schema format, input_schema, name constraints
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls — stop_reason, tool_use blocks, tool_result format
- Codebase direct read: `entity_context.py`, `intent_router.py`, `conversation.py`, `__init__.py`, `const.py`, `manifest.json`, `pyproject.toml`

### Secondary (MEDIUM confidence)
- https://deepwiki.com/anthropics/anthropic-sdk-python/4.2-synchronous-and-asynchronous-clients — AsyncAnthropic constructor parameters cross-verified with official docs

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified from manifest.json + official Anthropic SDK docs
- Architecture: HIGH — injection points from direct file + line number inspection
- tool_use schema: HIGH — from official Anthropic tool-use documentation
- Pitfalls: HIGH (Pitfall 1–4) / MEDIUM (Pitfall 5–6) — verified against codebase and SDK docs

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (stable SDK, HA entity_registry API stable)
