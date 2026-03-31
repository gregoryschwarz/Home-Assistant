# Phase 2: Conversation Bridge - Research

**Researched:** 2026-03-30
**Domain:** Home Assistant service calls, regex-based NLU, entity name resolution, config entry options, HA test harness
**Confidence:** HIGH (conversation entity API verified in Phase 1; service call patterns from HA source and official docs; testing patterns from HA docs and community)

---

## Summary

Phase 2 wires the already-working `HaAiConversationAgent` echo stub to actual HA entity control. The `_async_handle_message` method signature, `ConversationResult` construction, and `ChatLog` patterns are all verified from Phase 1 — no re-investigation needed. The remaining unknowns are the four technical areas the plans must address: service call mechanics (`hass.services.async_call`), French+English regex intent matching, entity name resolution from natural language, and the domain whitelist stored in config entry options.

The HA service registry API is straightforward: `await hass.services.async_call(domain, service, service_data, blocking=True)` where `service_data` must include `"entity_id"` as a string. The two exceptions that matter are `ServiceNotFound` (the domain/service combination doesn't exist) and `HomeAssistantError` (execution failed). Callers must catch both and return a natural language error response — not let the exception propagate to HA's conversation layer.

For entity name resolution, the approach is a two-step cascade: (1) try exact slug match from user text to `entity_id` suffix (e.g., "salon" -> `light.salon`), (2) search entity registry `name`, `original_name`, and `aliases` fields for case-insensitive substring match. No external fuzzy-matching library is needed or recommended — Python's `re` module and `str.casefold()` are sufficient for the MVP regex patterns.

**Primary recommendation:** Build `IntentRouter` as a pure Python class with compiled regex patterns per intent type; build `EntityContextBuilder` with domain-whitelist filtering reading from `entry.options`; use `pytest_homeassistant_custom_component.common.mock_service` (or a manual `async_mock_service`) to capture service calls in tests.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `re` (stdlib) | built-in | Regex intent matching | No external NLU library needed for MVP with 10-15 regex patterns. `re.IGNORECASE + re.UNICODE` handles French accents correctly. |
| `homeassistant.core.ServiceRegistry` | HA 2026.3.4 (installed) | Execute entity control commands | The standard HA API for all service calls inside custom components. |
| `homeassistant.helpers.entity_registry` | HA 2026.3.4 (installed) | Resolve entity names from text | Provides `RegistryEntry.name`, `original_name`, `aliases` for fuzzy matching. |
| `homeassistant.exceptions` | HA 2026.3.4 (installed) | Exception handling | `ServiceNotFound`, `HomeAssistantError`, `ServiceValidationError` for error messaging. |
| `homeassistant.config_entries.OptionsFlow` | HA 2026.3.4 (installed) | Domain whitelist in options UI | Standard options flow pattern for runtime-configurable settings without re-setup. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `voluptuous` | HA built-in | Options schema validation | Define `OPTIONS_SCHEMA` for whitelist domains in OptionsFlowHandler. |
| `pytest_homeassistant_custom_component` | 0.13.320 (installed) | HA test harness | Already in use from Phase 1. `hass` fixture + `async_setup_component` pattern established. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python `re` (stdlib) | `hassil` (HA's own intent library) | `hassil` is HA's built-in sentence matcher; overkill for Phase 2's 10-15 patterns, adds dependency; revisit for Phase 3 if pattern set grows beyond 30 rules |
| `homeassistant.helpers.entity_registry` | `hass.states.async_all()` with name filter | Entity registry has `aliases` field; states only expose current state values — registry is richer for name resolution |
| Manual exception catch | `hass.services.has_service()` pre-check | Pre-check is a TOCTOU race — service could unregister between check and call; catch the exception instead |

---

## Architecture Patterns

### Recommended Project Structure for Phase 2

```
custom_components/ha_ai_agent/
├── __init__.py              # existing — no changes
├── conversation.py          # MODIFIED: wire _async_handle_message -> IntentRouter
├── intent_router.py         # NEW: IntentRouter with compiled regex patterns
├── entity_context.py        # NEW: EntityContextBuilder with domain whitelist
├── const.py                 # MODIFIED: add CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS
└── config_flow.py           # MODIFIED: add OptionsFlowHandler for domain whitelist

tests/
├── test_conversation.py     # existing — add end-to-end message routing tests
├── test_intent_router.py    # NEW: unit tests for regex matching + service calls
└── test_entity_context.py   # NEW: unit tests for entity filtering/resolution
```

### Pattern 1: hass.services.async_call — The Correct Signature

**What:** Call a HA service to control an entity. The recommended pattern for Phase 2 is `service_data` containing `entity_id` (the legacy but universally supported form). The `target=` keyword parameter also works in HA 2023.x+ but adds a dict wrapper that is unnecessary for single-entity calls.

**Key parameters:**
- `domain` (str): `"light"`, `"switch"`, `"climate"`, `"media_player"`
- `service` (str): `"turn_on"`, `"turn_off"`, `"set_temperature"`, `"media_play_pause"`
- `service_data` (dict): `{"entity_id": "light.salon"}` — entity_id goes here
- `blocking` (bool): use `True` in Phase 2 to get synchronous confirmation; if the service raises, you want to catch it before building the ConversationResult

**Example (verified pattern from HA community + source):**
```python
# Source: homeassistant/core.py ServiceRegistry.async_call
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound

async def _execute_service(
    self,
    domain: str,
    service: str,
    entity_id: str,
    additional_data: dict | None = None,
) -> None:
    service_data = {"entity_id": entity_id}
    if additional_data:
        service_data.update(additional_data)
    await self.hass.services.async_call(
        domain=domain,
        service=service,
        service_data=service_data,
        blocking=True,
    )
```

**Exception handling — mandatory pattern:**
```python
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound

try:
    await self.hass.services.async_call(
        domain, service, {"entity_id": entity_id}, blocking=True
    )
    return f"D'accord, j'ai {action_label} {entity_label}."
except ServiceNotFound:
    return f"Service {domain}.{service} introuvable. Vérifiez que l'intégration est activée."
except HomeAssistantError as err:
    return f"Impossible d'exécuter la commande: {err}"
```

**Confidence:** HIGH — `ServiceNotFound` from `homeassistant.exceptions` confirmed by HA source; `blocking=True` pattern confirmed by multiple community references and HA docs.

---

### Pattern 2: Regex Intent Matching — French + English

**What:** Compile patterns at class-init time (not per-request). Use `re.IGNORECASE | re.UNICODE`. French accented characters (`é`, `è`, `ê`, `ô`, `â`) are matched correctly with `re.UNICODE` on Python 3.12+.

**Intent taxonomy for Phase 2 (covers NLU-01, NLU-02):**

| Intent | French patterns | English patterns | HA service |
|--------|----------------|-----------------|------------|
| TURN_ON | `allume[rz]?`, `active[rz]?`, `mets?.*en marche`, `ouvre[rz]?` (volets) | `turn\s+on`, `switch\s+on`, `enable`, `open` (covers) | `{domain}.turn_on` |
| TURN_OFF | `éteins?`, `étein[dt]`, `désactive[rz]?`, `ferme[rz]?` | `turn\s+off`, `switch\s+off`, `disable`, `close` | `{domain}.turn_off` |
| SET_TEMP | `règle[rz]?.*température`, `mets?.*degrés?`, `chauffe[rz]?.*à` | `set.*temperature`, `set.*degrees?`, `heat.*to` | `climate.set_temperature` |
| MEDIA_PLAY | `mets?.*en pause`, `lance[rz]?`, `joue[rz]?`, `reprends?` | `play`, `pause`, `resume` | `media_player.media_play_pause` |

**Example compiled patterns (authoritative pattern for IntentRouter):**
```python
import re
from dataclasses import dataclass

@dataclass
class IntentPattern:
    intent: str
    pattern: re.Pattern
    service_domain: str    # extracted from match or entity domain
    service_name: str

INTENT_PATTERNS: list[IntentPattern] = [
    IntentPattern(
        intent="TURN_ON",
        pattern=re.compile(
            r"(?:allume[rz]?|active[rz]?|mets?\s+en\s+marche|turn\s+on|switch\s+on)\s+(?:la\s+|le\s+|les\s+|l['']\s*)?(?P<entity>.+)",
            re.IGNORECASE | re.UNICODE,
        ),
        service_domain="",      # resolved at runtime from entity domain
        service_name="turn_on",
    ),
    IntentPattern(
        intent="TURN_OFF",
        pattern=re.compile(
            r"(?:ét(?:eins?|einds?)|étein[dt]|désactive[rz]?|turn\s+off|switch\s+off)\s+(?:la\s+|le\s+|les\s+|l['']\s*)?(?P<entity>.+)",
            re.IGNORECASE | re.UNICODE,
        ),
        service_domain="",
        service_name="turn_off",
    ),
    IntentPattern(
        intent="SET_TEMP",
        pattern=re.compile(
            r"(?:règle[rz]?.*?|mets?.*?|chauffe[rz]?.*?|set.*?temperature.*?|heat.*?to\s+)(?P<temp>\d+(?:\.\d+)?)\s*(?:degrés?|°[cCfF]?|degrees?)?",
            re.IGNORECASE | re.UNICODE,
        ),
        service_domain="climate",
        service_name="set_temperature",
    ),
]
```

**Key insight on French articles:** Strip leading French articles (`la`, `le`, `les`, `l'`, `l'`) from the captured entity text before lookup. The regex above handles this inline with `(?:la\s+|le\s+|les\s+|l['']\s*)?` — use a compiled article-stripping helper as a second pass for robustness.

**Confidence:** HIGH for regex approach viability. MEDIUM for specific pattern correctness — test against French accented input, especially `éteins`, `éteinds`, and `l'` vs `l'` (curly vs straight apostrophe). Both forms appear in voice-transcribed text.

---

### Pattern 3: Entity Name Resolution

**What:** Convert natural language entity reference ("lumière du salon", "la lumière du salon", "salon light") to a HA `entity_id` string like `light.salon`.

**Three-pass resolution cascade (order matters for accuracy):**

1. **Direct slug match:** Normalize user text to lowercase, replace spaces with underscores, remove French articles (`du`, `de la`, `des`, `de`, `la`, `le`, `les`, `l'`). Check if `{domain}.{normalized_text}` exists in `hass.states`.
   - "lumière du salon" -> strip articles -> "lumière salon" -> normalize -> "lumiere_salon" -> try `light.lumiere_salon`
   - "salon" -> try `light.salon` (simple cases)

2. **Entity registry name match:** Iterate `entity_registry.entities.values()`, filter to allowed domains, compare `casefold()` of entry `.name` and `.original_name` against the normalized user text (substring or full match).

3. **Alias match:** Same iteration but check `entry.aliases` (a `set[str]` or `frozenset[str]`). Aliases are the user-defined voice names set in HA entity customization.

**Entity registry access pattern (verified from Phase 1 test code):**
```python
from homeassistant.helpers import entity_registry as er

registry = er.async_get(hass)   # synchronous, in-memory — safe on event loop
# registry.entities: dict[str, RegistryEntry]
# RegistryEntry fields: entity_id, name, original_name, aliases, domain, platform
```

**Implementation example:**
```python
import re
import unicodedata

FRENCH_ARTICLES = re.compile(
    r"\b(?:du|de\s+la|de\s+l['']\s*|des|de|la|le|les|l['']\s*)\b",
    re.IGNORECASE | re.UNICODE,
)

def _normalize(text: str) -> str:
    """Normalize to ASCII slug: strip accents, articles, lowercase, spaces -> underscores."""
    # Remove accents
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Strip French articles
    text = FRENCH_ARTICLES.sub("", text).strip()
    return re.sub(r"\s+", "_", text.strip().lower())

def resolve_entity(hass, user_entity_text: str, allowed_domains: list[str]) -> str | None:
    """Return entity_id or None."""
    normalized = _normalize(user_entity_text)
    # Pass 1: direct slug
    for domain in allowed_domains:
        candidate = f"{domain}.{normalized}"
        if hass.states.get(candidate):
            return candidate
    # Pass 2 + 3: registry name and alias search
    registry = er.async_get(hass)
    for entry in registry.entities.values():
        if entry.domain not in allowed_domains:
            continue
        for name_candidate in [entry.name, entry.original_name, *(entry.aliases or [])]:
            if name_candidate and normalized in _normalize(name_candidate):
                return entry.entity_id
    return None
```

**Confidence:** MEDIUM-HIGH. The registry API (`er.async_get`, `RegistryEntry.aliases`) is verified from Phase 1 test code and HA source docs. The slug-normalization approach is the recommended pattern in HA community for custom components. Unicode accent stripping with `unicodedata.NFKD` is a well-established Python pattern.

**Pitfall:** `entry.aliases` is a `set[str]` in HA 2024.x+; it may be `None` or `frozenset` depending on HA version — always guard with `*(entry.aliases or [])`.

---

### Pattern 4: Domain Whitelist via Config Entry Options

**What:** Store the list of controllable HA domains (`["light", "switch", "climate", "media_player"]` by default) in `entry.options`, not `entry.data`. Options are user-editable after initial setup via `OptionsFlow`.

**Reading options in setup and runtime:**
```python
# In __init__.py async_setup_entry — read at setup time
from .const import CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS

allowed_domains = entry.options.get(CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS)
```

**Important:** `entry.options` is initially empty (`{}`) until the user opens the options UI. Always use `.get(key, default)` — never assume options are populated.

**OptionsFlowHandler pattern (from official HA docs, verified 2026-03-30):**
```python
# config_flow.py — add to HaAiAgentConfigFlow class
from homeassistant.config_entries import OptionsFlow
import voluptuous as vol

class HaAiAgentOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_ALLOWED_DOMAINS,
                    default=current.get(CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS),
                ): vol.All(list, [str]),
            }),
        )

# Register in HaAiAgentConfigFlow:
@staticmethod
@callback
def async_get_options_flow(config_entry: ConfigEntry) -> HaAiAgentOptionsFlow:
    return HaAiAgentOptionsFlow()
```

**Const additions needed:**
```python
# const.py additions
CONF_ALLOWED_DOMAINS = "allowed_domains"
DEFAULT_ALLOWED_DOMAINS: list[str] = ["light", "switch", "climate", "media_player"]
```

**Confidence:** HIGH — `entry.options`, `OptionsFlow`, `async_get_options_flow` pattern from official HA developer docs (verified 2026-03-30). `entry.options.get(key, default)` pattern is stable across HA 2024.x+.

---

### Pattern 5: Testing Service Calls in the HA Test Harness

**What:** Verify that `IntentRouter._async_handle_message` triggers the correct `hass.services.async_call` call for a given text input. The HA test harness provides two approaches.

**Approach A — `mock_service` utility (recommended):**
`pytest_homeassistant_custom_component` exposes `mock_service` (sometimes spelled `async_mock_service` in newer harness versions). It captures service calls without executing them.

```python
from pytest_homeassistant_custom_component.common import mock_service
# OR for newer harness versions:
from homeassistant.core import HomeAssistant

async def test_turn_on_light(hass: HomeAssistant, mock_config_entry) -> None:
    # Register a mock light entity first
    hass.states.async_set("light.salon", "off", {"friendly_name": "Lumière salon"})

    # Capture all calls to light.turn_on
    calls = mock_service(hass, "light", "turn_on")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the agent entity and call _async_handle_message directly
    # (or invoke via hass.services.async_call("conversation", "process", ...))
    ...
    assert len(calls) == 1
    assert calls[0].data["entity_id"] == "light.salon"
```

**Approach B — State assertion (if mock_service unavailable):**
Register a mock light platform via `async_setup_component(hass, "light", {...})` or use `hass.states.async_set("light.salon", "off")` to seed state, call the service for real, then assert the state changed:
```python
hass.states.async_set("light.salon", "off")
# ... call router ...
await hass.async_block_till_done()
state = hass.states.get("light.salon")
assert state.state == "on"
```

**Approach C — Direct router unit tests (recommended for IntentRouter unit tests):**
Mock `hass.services.async_call` directly on the `hass` mock to capture calls without any HA platform setup:
```python
from unittest.mock import AsyncMock, patch

async def test_intent_router_turn_on(hass, mock_config_entry) -> None:
    hass.states.async_set("light.salon", "off")
    hass.services.async_call = AsyncMock(return_value=None)

    router = IntentRouter(hass, allowed_domains=["light", "switch"])
    result = await router.async_route("allume la lumière du salon", "fr")

    hass.services.async_call.assert_awaited_once_with(
        "light", "turn_on", {"entity_id": "light.salon"}, blocking=True
    )
    assert "salon" in result.lower()
```

**Confidence:** MEDIUM-HIGH — `mock_service` utility confirmed present in `pytest_homeassistant_custom_component`; `AsyncMock` pattern for direct unit tests is standard Python. The exact import path for `mock_service` should be verified at test run time (check `pytest_homeassistant_custom_component.common`).

---

### Pattern 6: Wiring IntentRouter in conversation.py

**What:** Replace the echo stub body in `_async_handle_message` with a call to `IntentRouter`. The `IntentRouter` instance is stored in `hass.data[DOMAIN][entry_id]` at setup time.

```python
# conversation.py — Phase 2 body for _async_handle_message
async def _async_handle_message(
    self,
    user_input: ConversationInput,
    chat_log: ChatLog,
) -> ConversationResult:
    router: IntentRouter = self.hass.data[DOMAIN][self._entry.entry_id]["router"]
    response_text = await router.async_route(
        text=user_input.text,
        language=user_input.language,
    )
    chat_log.async_add_assistant_content_without_tools(
        AssistantContent(agent_id=self.entity_id, content=response_text)
    )
    intent_response = conversation_intent.IntentResponse(language=user_input.language)
    intent_response.async_set_speech(response_text)
    return ConversationResult(
        response=intent_response,
        conversation_id=user_input.conversation_id,
    )
```

**__init__.py changes — create IntentRouter at setup, store in hass.data:**
```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    allowed_domains = entry.options.get(CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS)
    router = IntentRouter(hass, allowed_domains=allowed_domains)
    entity_context = EntityContextBuilder(hass, allowed_domains=allowed_domains)
    hass.data[DOMAIN][entry.entry_id] = {
        "entry": entry,
        "router": router,
        "entity_context": entity_context,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```

**Confidence:** HIGH — this extends the verified Phase 1 `hass.data[DOMAIN][entry.entry_id]` storage pattern. `IntentRouter` is a plain Python class with no HA lifecycle concerns; it only needs `hass` for entity state reads and service calls.

---

### Anti-Patterns to Avoid

- **Importing `AbstractConversationAgent`:** Deprecated since HA 2024.6. `conversation.py` already uses `ConversationEntity` — do not import or subclass `AbstractConversationAgent` anywhere in Phase 2 code.

- **Putting entity_id in `target=` instead of `service_data`:** The `target=` parameter (a dict with `entity_id`, `device_id`, `area_id` keys) works but requires a different dict structure. Use `service_data={"entity_id": entity_id}` for simplicity and maximum compatibility across HA versions.

- **Using `blocking=False` for Phase 2:** With `blocking=False`, `async_call` returns immediately and you cannot catch service errors. Phase 2 must return meaningful error messages — use `blocking=True`.

- **Resolving entity names only from `hass.states`:** `hass.states` provides the current runtime state but not entity aliases. Use `entity_registry.entities` for name/alias resolution.

- **Failing to strip French articles before entity lookup:** "la lumière du salon" will never match `light.lumiere_du_salon` without stripping `la`, `du`. The normalization step is required.

- **Compiling regex patterns inside `async_route()`:** Compile at class init in `__init__`. Recompiling on every message is wasteful; `re.compile` returns a cached object but the dict lookup still happens per call.

- **Not handling unicode apostrophes:** Voice-transcribed French text often produces `l'` (Unicode RIGHT SINGLE QUOTATION MARK U+2019) instead of `l'` (ASCII). Regex patterns must match both: `l[''\\u2019]`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy entity name matching | Custom Levenshtein or n-gram matcher | Registry name + alias lookup + slug normalization | HA entity registry `aliases` field is the correct first-party mechanism; users can add aliases in the UI for exactly this purpose |
| Intent classification | ML model or embedding-based classifier | `re.compile` patterns | 10-15 patterns cover the Phase 2 scope; regex is zero-latency, zero-cost, 100% offline |
| Service call retry logic | Custom exponential backoff | Catch `HomeAssistantError` and return user error | Phase 2 is local-only; services don't fail transiently — a failure means the entity/service is genuinely unavailable |
| Options persistence | Custom JSON file | `entry.options` via `OptionsFlow` | HA manages persistence, migration, and UI for options automatically |
| Language detection | langdetect library | `user_input.language` field from `ConversationInput` | HA passes the detected language in every `ConversationInput`; use it to select French vs English patterns |

**Key insight:** Phase 2 complexity is intentionally low — no LLM, no async I/O beyond the service call. The value is in correctness (right entity, right service, right error message), not sophistication.

---

## Common Pitfalls

### Pitfall 1: ServiceNotFound vs HomeAssistantError Distinction

**What goes wrong:** Catching only `ServiceNotFound` and letting `HomeAssistantError` propagate. This causes an unhandled exception trace in HA logs and a broken conversation response.

**Why it happens:** Developers assume `ServiceNotFound` covers all failure cases. But `HomeAssistantError` is raised when the service exists but execution fails (e.g., the light is unreachable, the climate entity is in error state).

**How to avoid:** Always catch both in `IntentRouter._execute_service`. Return a French user-friendly string from each handler. Log at WARNING level with `_LOGGER.warning("Service call failed: %s", err)`.

**Warning signs:** Python tracebacks with `HomeAssistantError` in HA logs when giving valid commands to entities that are temporarily unavailable.

---

### Pitfall 2: Unicode Apostrophes in French Voice Text

**What goes wrong:** Voice STT transcribes "l'éclairage" as `l\u2019éclairage` (curly apostrophe) while regex pattern uses `l'` (ASCII). No match.

**Why it happens:** macOS, iOS, and some STT engines auto-correct straight apostrophes to curly. HA's `ConversationInput.text` passes through whatever the STT produced.

**How to avoid:** In French article-stripping regex, always include both: `l['\u2019]`. In entity name normalization, normalize all apostrophes to ASCII before comparison with `text.replace('\u2019', "'")`.

**Warning signs:** "allume l'éclairage" fails but "allume l'éclairage" (straight apostrophe) succeeds in tests.

---

### Pitfall 3: Options Not Present on First Load

**What goes wrong:** `entry.options["allowed_domains"]` raises `KeyError` on a freshly-installed integration because options are empty until the user visits the options flow.

**Why it happens:** `ConfigEntry.options` is an empty `MappingProxyType({})` by default. Direct dict access crashes.

**How to avoid:** Always use `entry.options.get(CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS)`. Document this in constants: `DEFAULT_ALLOWED_DOMAINS = ["light", "switch", "climate", "media_player"]`.

**Warning signs:** `KeyError` on `async_setup_entry` during first-time component setup.

---

### Pitfall 4: Regex Pattern Captures Too Much After Entity Name

**What goes wrong:** Pattern `r"allume\s+(?P<entity>.+)"` applied to "allume la lumière du salon s'il te plaît" captures "la lumière du salon s'il te plaît". The trailing politeness phrase is included in the entity lookup, causing no match.

**Why it happens:** `.+` is greedy and captures everything to end of string.

**How to avoid:** Add common French/English suffixes as trim anchors. After capturing the entity group, apply a post-processing strip to remove: `"s'il te plaît"`, `"please"`, `"maintenant"`, `"now"`, `"tout de suite"`. Simple `re.sub(POLITE_SUFFIXES_PATTERN, "", text).strip()` before entity lookup.

**Warning signs:** Entity lookup fails on polite commands but succeeds on bare commands.

---

### Pitfall 5: Domain Whitelist Not Applied to Entity Lookup

**What goes wrong:** `resolve_entity` iterates all HA registry entries, including domains not in the whitelist. A command like "allume le bureau" could match `person.bureau` or `automation.bureau` before finding `light.bureau`.

**Why it happens:** Forgetting to filter by `allowed_domains` in `EntityContextBuilder.resolve_entity`.

**How to avoid:** Filter `entry.domain not in allowed_domains: continue` as the first check in the resolution loop. SEC-03 requires this.

**Warning signs:** Service call fails with unexpected domain (e.g., `person.turn_on`) in HA logs.

---

## Code Examples

### ConversationInput field access (verified Phase 1)

```python
# Source: tests/test_conversation.py (Phase 1 verified)
async def _async_handle_message(
    self,
    user_input: ConversationInput,
    chat_log: ChatLog,
) -> ConversationResult:
    text = user_input.text          # str: the raw user utterance
    language = user_input.language  # str: "fr", "en", etc.
    conv_id = user_input.conversation_id  # str | None: multi-turn tracking
```

### hass.services.async_call with error handling (authoritative pattern)

```python
# Source: homeassistant.exceptions module + community-verified pattern
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
import logging

_LOGGER = logging.getLogger(__name__)

async def _call_service(hass, domain: str, service: str, entity_id: str, extra_data: dict | None = None) -> str:
    """Call a HA service and return a natural-language result string."""
    service_data: dict = {"entity_id": entity_id}
    if extra_data:
        service_data.update(extra_data)
    try:
        await hass.services.async_call(domain, service, service_data, blocking=True)
        return f"Fait."  # Phase 2: simple confirmation; Phase 3 Claude can elaborate
    except ServiceNotFound:
        _LOGGER.warning("Service %s.%s not found for entity %s", domain, service, entity_id)
        return f"Le service {domain}.{service} n'est pas disponible."
    except HomeAssistantError as err:
        _LOGGER.warning("Service call failed: %s", err)
        return f"Impossible d'exécuter cette action : {err}"
```

### Entity registry name lookup (verified from Phase 1 test source)

```python
# Source: tests/test_conversation.py (Phase 1 — er.async_get pattern confirmed)
from homeassistant.helpers import entity_registry as er

registry = er.async_get(hass)  # synchronous, in-memory

# Iterate entries filtered by domain
for entry in registry.entities.values():
    if entry.domain == "light":
        print(entry.entity_id, entry.name, entry.original_name, entry.aliases)
```

### Mock service calls in tests

```python
# Source: pytest_homeassistant_custom_component.common (standard HA test pattern)
from pytest_homeassistant_custom_component.common import mock_service

async def test_router_calls_light_turn_on(hass, mock_config_entry) -> None:
    # Seed entity state so resolution works
    hass.states.async_set("light.salon", "off", {"friendly_name": "Lumière salon"})
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    calls = mock_service(hass, "light", "turn_on")
    # ... invoke router with "allume la lumière du salon" ...
    assert len(calls) == 1
    assert calls[0].data["entity_id"] == "light.salon"
```

### OptionsFlowHandler registration (from official HA docs 2026-03-30)

```python
# Source: https://developers.home-assistant.io/docs/config_entries_options_flow_handler/
from homeassistant.core import callback

class HaAiAgentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    # ... existing code ...

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HaAiAgentOptionsFlow:
        """Create the options flow."""
        return HaAiAgentOptionsFlow()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `AbstractConversationAgent` + `async_set_agent` + `async_process` | `ConversationEntity` + `PLATFORMS=["conversation"]` + `_async_handle_message(user_input, chat_log)` | HA 2024.6 | Phase 1 already uses the correct new API; no change needed |
| `entity_id` in `service_data` | `target={"entity_id": ...}` in `async_call` | HA 2023.x (optional, not mandatory) | Both forms work; use `service_data` form for simplicity |
| French NLU via Snips/Rhasspy | Built-in `hassil` sentence templates | HA 2023.x | Phase 2 uses regex (simpler for MVP); `hassil` available as upgrade path |
| No options flow | `OptionsFlow` for runtime settings | HA 2021.x+ | Standard pattern; use from Phase 2 for domain whitelist (SEC-03) |

**Deprecated/outdated:**
- `AbstractConversationAgent`: removed or deprecated in HA 2024.6+; never use
- `hass.services.call()` (sync): only valid in python_script context; always use `hass.services.async_call()` in custom components

---

## Open Questions

1. **`mock_service` exact import path in pytest_homeassistant_custom_component 0.13.320**
   - What we know: The utility exists and is a standard HA testing tool
   - What's unclear: Whether it's at `pytest_homeassistant_custom_component.common.mock_service` or another path in 0.13.320
   - Recommendation: Wave 0 of the test plan should run a quick import check; fallback is `AsyncMock` on `hass.services.async_call` directly

2. **`entry.aliases` type in HA 2026.3.4**
   - What we know: Documented as `set[str]` in recent HA source; may be `frozenset` or `None` on entries with no aliases set
   - What's unclear: Whether it's guaranteed non-None or can be `None`
   - Recommendation: Always guard with `*(entry.aliases or [])` — the `or []` fallback costs nothing

3. **Climate `set_temperature` service_data fields**
   - What we know: `set_temperature` requires `temperature` (float) in service_data, not just `entity_id`
   - What's unclear: Whether HA 2026.x added hvac_mode as required; whether `set_temperature` works without an HVAC mode
   - Recommendation: Phase 2 implementation should extract numeric temperature from regex and pass `{"entity_id": ..., "temperature": float(temp_match)}`. Test against a mock climate entity.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | runtime | Yes | 3.14 (Windows) | — |
| homeassistant | HA test harness | Yes | 2026.3.4 | — |
| pytest-homeassistant-custom-component | tests | Yes | 0.13.320 | — |
| pytest-asyncio | tests | Yes | 1.3.0 | — |
| ruff | linting | Yes | 0.15.8 | — |

All dependencies confirmed from Phase 1 installation. No new runtime dependencies needed for Phase 2 (regex is stdlib; entity registry and service registry are HA built-ins).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio 1.3.0 + pytest-homeassistant-custom-component 0.13.320 |
| Config file | `pyproject.toml` — `asyncio_mode = "auto"`, `testpaths = ["tests"]`, `addopts = "-x -q"` |
| Quick run command | `python -m pytest tests/test_intent_router.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| NLU-01 | "allume la lumiere du salon" turns on `light.salon` | integration | `python -m pytest tests/test_intent_router.py::test_turn_on_french -x` | Wave 0 |
| NLU-01 | "turn on the bedroom light" turns on `light.bedroom` | integration | `python -m pytest tests/test_intent_router.py::test_turn_on_english -x` | Wave 0 |
| NLU-01 | "éteins la lumière" turns off entity | integration | `python -m pytest tests/test_intent_router.py::test_turn_off_french -x` | Wave 0 |
| NLU-02 | Turn-on/off resolved without any Claude API call | unit | `python -m pytest tests/test_intent_router.py::test_no_llm_call -x` | Wave 0 |
| NLU-04 | Agent returns confirmation message after action | integration | `python -m pytest tests/test_intent_router.py::test_confirmation_response -x` | Wave 0 |
| NLU-05 | Entity not found -> clear error message | unit | `python -m pytest tests/test_intent_router.py::test_entity_not_found -x` | Wave 0 |
| NLU-05 | Service unavailable -> clear error message | unit | `python -m pytest tests/test_intent_router.py::test_service_not_found -x` | Wave 0 |
| SEC-03 | Whitelist blocks non-allowed domains | unit | `python -m pytest tests/test_entity_context.py::test_domain_whitelist -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_intent_router.py tests/test_entity_context.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green (all 14 existing Phase 1 tests + new Phase 2 tests) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_intent_router.py` — covers NLU-01, NLU-02, NLU-04, NLU-05
- [ ] `tests/test_entity_context.py` — covers SEC-03 domain whitelist filtering

*(Existing test infrastructure: `tests/conftest.py` with `mock_config_entry`, `hass_config_dir`, `hass_with_homeassistant` fixtures is fully reusable — no conftest changes needed)*

---

## Sources

### Primary (HIGH confidence)
- Phase 1 verified HA 2026.3.4 imports — `conversation.py`, `tests/test_conversation.py` in this repo
- Phase 1 `01-03-SUMMARY.md` — verified `_async_handle_message(user_input, chat_log)` signature, `AssistantContent`, `ChatLog` imports
- `homeassistant.helpers.entity_registry` — `er.async_get(hass)` pattern confirmed from Phase 1 test code
- HA Developer Docs (Options Flow) — https://developers.home-assistant.io/docs/config_entries_options_flow_handler/ — `OptionsFlow`, `async_get_options_flow`, `config_entry.options` patterns
- HA Developer Docs (Action Exceptions) — https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-exceptions/ — `ServiceValidationError`, `HomeAssistantError` guidance
- HA conversation entity docs — https://developers.home-assistant.io/docs/core/entity/conversation/ — `ConversationInput` field list

### Secondary (MEDIUM confidence)
- WebSearch: `ServiceNotFound` exception from `homeassistant.exceptions` — confirmed by multiple HA GitHub issues and community references
- WebSearch: `hass.services.async_call` with `service_data={"entity_id": ...}` and `blocking=True` — confirmed by multiple Python Script and custom component references
- `entity_registry.entities` field names (`name`, `original_name`, `aliases`) — confirmed from DeepWiki HA core entity registry documentation

### Tertiary (LOW confidence — verify at implementation)
- `mock_service` import path in `pytest_homeassistant_custom_component 0.13.320` — single-source, needs runtime verification
- `entry.aliases` nullability in HA 2026.3.4 — needs `*(entry.aliases or [])` guard regardless

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are HA built-ins already installed from Phase 1
- Architecture: HIGH — conversation entity API verified Phase 1; service call pattern confirmed from HA source and docs
- Regex patterns: MEDIUM — French patterns verified for correctness at design level; accent/apostrophe edge cases require integration testing
- Entity resolution: MEDIUM-HIGH — registry API confirmed; normalization logic is new, needs tests
- Options flow: HIGH — official HA docs pattern, unchanged since HA 2021.x

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (HA 2026.3.4 is the pinned test version; patterns stable)

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NLU-01 | User can send text command ("allume la lumière du salon") and the entity is controlled | Pattern 1 (hass.services.async_call) + Pattern 3 (entity name resolution) |
| NLU-02 | Simple/frequent commands processed locally (regex/rules) without Claude API call | Pattern 2 (regex intent matching) — IntentRouter decides locally, no async I/O to external API |
| NLU-04 | Agent replies with natural language confirmation after each action | Pattern 6 (conversation.py wiring) — response_text from router flows to IntentResponse.async_set_speech |
| NLU-05 | Agent handles errors (entity not found, service unavailable) with clear message | Pattern 1 exception handling — ServiceNotFound + HomeAssistantError both return user-facing strings |
| SEC-03 | Configurable whitelist of controllable domains (light, switch, climate, media_player) | Pattern 4 (entry.options) + Pattern 3 (domain filter in entity lookup) + EntityContextBuilder |
</phase_requirements>
