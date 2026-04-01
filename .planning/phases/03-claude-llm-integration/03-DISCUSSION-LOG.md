# Phase 3: Claude LLM Integration - Discussion Log

**Date:** 2026-04-01
**Mode:** Auto (user said "go" — no interactive Q&A)

## Areas Analyzed

Claude analyzed the codebase and derived decisions from:
- PROJECT.md (model choice, privacy constraints)
- REQUIREMENTS.md (NLU-03, SEC-01, SEC-02)
- Prior phase CONTEXT.md files (none for phases 1-2)
- Codebase scout: intent_router.py, conversation.py, __init__.py, entity_context.py

## Auto-Selected Decisions

| Area | Decision | Rationale |
|------|----------|-----------|
| Fallback trigger | `IntentRouter` returns `None` sentinel | Keeps Claude out of regex engine, clean separation |
| ClaudeClient | `AsyncAnthropic` wrapper, 1 retry + 10s timeout | Matches async HA patterns, avoids blocking UI |
| History | 10-turn in-memory window, not persisted | Sufficient for v1, no storage complexity |
| Tool use | Single `execute_ha_service` tool, strict domain validation | Simple, safe, matches phase scope |
| Entity filter | Allowed domains only, cap 50, send entity_id+name+state | Satisfies SEC-01, matches Phase 2 whitelist |
| Retry/degradation | French error strings, log WARNING, never surface stack trace | Consistent with NLU-05 pattern |

## Deferred
- History persistence, model config, API key validation test, multi-action — all v2
