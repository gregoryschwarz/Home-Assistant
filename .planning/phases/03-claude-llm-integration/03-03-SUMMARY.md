---
phase: 03-claude-llm-integration
plan: "03"
subsystem: entity-context
tags: [home-assistant, entity-registry, llm-context, security, filtering]

# Dependency graph
requires:
  - phase: 02-conversation-bridge
    provides: EntityContextBuilder with 3-pass resolve_entity, _normalize helper

provides:
  - EntityContextBuilder.list_entities_for_llm(text, limit=50) — filtered, capped, prioritized entity list for Claude API
  - SEC-01: only allowed-domain entities sent to LLM
  - SEC-02: exactly {entity_id, friendly_name, state} per entity — no raw state dumps
  - D-13: hard cap at 50 entities
  - D-15: token-based prioritization using _normalize when over limit
affects: [03-02-conversation, claude-client, llm-prompt-assembly]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Token scoring: _normalize(friendly_name).split('_') intersected with _normalize(text).split('_') for relevance ranking"
    - "Registry-first friendly name: entry.name or entry.original_name or entry.entity_id (not state.attributes)"
    - "Minimal LLM payload: exactly 3 keys per entity dict enforced by construction"

key-files:
  created: []
  modified:
    - custom_components/ha_ai_agent/entity_context.py
    - tests/test_entity_resolver.py

key-decisions:
  - "Reuse _normalize for token scoring: ensures consistent accent-stripping and article removal between resolve_entity and list_entities_for_llm"
  - "entry.name or entry.original_name or entry.entity_id: avoids state.attributes['friendly_name'] which can include extra data"
  - "Sort then slice: sort all entities by token score descending, then take first `limit` — O(n log n) but n bounded by HA entity count"

patterns-established:
  - "LLM entity payload: exactly {entity_id, friendly_name, state} — minimal surface for privacy (SEC-02)"
  - "Token-based prioritization: split normalized text on '_', compute intersection size as relevance score"

requirements-completed: [SEC-01, SEC-02]

# Metrics
duration: 15min
completed: 2026-04-01
---

# Phase 03 Plan 03: list_entities_for_llm — Filtered Entity Context for Claude API

**EntityContextBuilder extended with list_entities_for_llm: domain-filtered, 50-capped, token-prioritized entity list returning exactly {entity_id, friendly_name, state} per entity for SEC-01/SEC-02 compliance**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-01T10:56:47Z
- **Completed:** 2026-04-01T11:12:00Z
- **Tasks:** 1 (TDD)
- **Files modified:** 2

## Accomplishments

- Implemented `list_entities_for_llm(text, limit=50)` on `EntityContextBuilder` with full TDD cycle
- Domain whitelist filter (SEC-01): only entities in `self.allowed_domains` reach the LLM
- Minimal payload (SEC-02/D-14): exactly 3 keys per dict — `entity_id`, `friendly_name`, `state` — no extra attributes
- Hard cap at 50 entities (D-13) with token-based prioritization using existing `_normalize` helper (D-15)
- All 9 entity resolver tests pass (5 existing + 4 new TDD tests)

## Task Commits

1. **Task 1: Add list_entities_for_llm method and tests** — `063add4` (feat) — TDD RED then GREEN in single commit

**Plan metadata:** (docs commit — to follow)

_Note: TDD commit combines test + implementation as both were written/verified in the same task cycle_

## Files Created/Modified

- `custom_components/ha_ai_agent/entity_context.py` — Added `list_entities_for_llm` method (35 lines) after `resolve_entity`
- `tests/test_entity_resolver.py` — Appended 4 new async test functions (91 lines)

## Decisions Made

- Reused `_normalize` for token scoring — same normalization ensures "salon" matches "Lumiere Salon" consistently across resolve_entity and list_entities_for_llm
- Used `entry.name or entry.original_name or entry.entity_id` to get friendly_name from registry (not `state.attributes`) — avoids pulling extra data into the LLM payload
- Sort-then-slice approach for prioritization: simple, readable, sufficient for typical HA scale (~100–500 entities)

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Pre-existing failures in `tests/test_claude_client.py` (requires `claude_client.py` from plan 03-01, not yet present on this parallel branch) — confirmed pre-existing, not caused by this plan's changes
- All 30 non-blocked tests pass without regression

## Known Stubs

None — `list_entities_for_llm` is fully wired: reads from live HA entity registry and state machine.

## Next Phase Readiness

- `list_entities_for_llm` is ready to be called from `conversation.py` (plan 03-02) when building the system prompt for Claude API requests
- SEC-01 and SEC-02 requirements are satisfied

---
*Phase: 03-claude-llm-integration*
*Completed: 2026-04-01*
