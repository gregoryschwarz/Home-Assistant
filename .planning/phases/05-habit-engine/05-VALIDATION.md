---
phase: 05
slug: habit-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-05
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-homeassistant-custom-component |
| **Config file** | `pytest.ini` (existant dans le projet) |
| **Quick run command** | `py -m pytest tests/test_storage.py tests/test_habit_engine.py tests/test_pattern_detector.py -x -q` |
| **Full suite command** | `py -m pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `py -m pytest tests/test_storage.py -x -q`
- **After every plan wave:** Run `py -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 0 | HABIT-01/02 | unit stubs | `py -m pytest tests/test_storage.py tests/test_habit_engine.py tests/test_pattern_detector.py -x -q` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | HABIT-01 | unit | `py -m pytest tests/test_storage.py -x -q` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | HABIT-01/02 | unit | `py -m pytest tests/test_habit_engine.py -x -q` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 2 | HABIT-03 | unit | `py -m pytest tests/test_pattern_detector.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_storage.py` — stubs pour HABIT-01 (schema, WAL mode, TTL purge, cap FIFO 10k)
- [ ] `tests/test_habit_engine.py` — stubs pour HABIT-01/02 (filtrage user_id, domaine, contexte présence/météo)
- [ ] `tests/test_pattern_detector.py` — stubs pour HABIT-03 (seuil 3×/14j, fenêtre ±30min)
- [ ] Fixtures dans `tests/conftest.py` : `tmp_db` (AgentStorage sur tmp_path), `mock_state_changed_event`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pas de données transmises hors device | SEC-02 | Vérification réseau live | Confirmer absence d'appels réseau dans logs HA pendant enregistrement d'événements |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
