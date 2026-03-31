# HA Autonomous Agent

## What This Is

Un agent IA autonome intégré dans Home Assistant sous forme de custom component. Il comprend les commandes en langage naturel (texte et voix), apprend les habitudes des habitants au fil du temps, et prend des décisions automatiques en combinant des règles locales et le modèle Claude (Anthropic) pour les situations complexes.

## Core Value

Permettre de contrôler et d'automatiser sa maison en langage naturel sans configuration technique, avec un agent qui s'améliore au fil du temps.

## Requirements

### Validated

- [x] Commandes en langage naturel (texte) pour contrôler les entités Home Assistant via règles locales — Validé en Phase 2 (NLU-01, NLU-02, NLU-04, NLU-05)
- [x] Intégration comme custom component HA (dossier `custom_components/`) — Validé en Phase 1 (HA-01, HA-02, HA-03, HA-04)
- [x] Whitelist de domaines configurable via OptionsFlow HA — Validé en Phase 2 (SEC-03)

### Active

- [ ] Commandes vocales pour contrôler les entités Home Assistant (texte ✓ via Phase 2, voix — Phase 4)
- [ ] Apprentissage des habitudes : l'agent observe et mémorise les routines pour les suggérer ou les appliquer automatiquement
- [ ] Intégration comme custom component HA (dossier `custom_components/`)
- [ ] Utilisation de l'API Claude (Anthropic) pour l'interprétation des intentions complexes
- [ ] Combinaison règles locales + LLM : règles pour les cas simples/fréquents, Claude pour les situations ambiguës
- [ ] Interface vocale et textuelle dans Home Assistant

### Out of Scope

- Décisions autonomes sans commande (v1) — différé à v2, risque de comportement non souhaité sans phase d'apprentissage solide
- Explication des actions par l'IA (v1) — différé à v2 pour garder le scope v1 focalisé
- Support multi-LLM (GPT, Ollama) — choix fixé sur Claude pour v1, éviter la complexité d'abstraction prématurée

## Context

- **Écosystème** : Home Assistant (HASS) — Python, architecture event-driven, entités/états/services, WebSocket API
- **Custom component** : Python dans `custom_components/ha_ai_agent/`, déclaré via `manifest.json`, config via `config_entries`
- **LLM** : Claude API (Anthropic SDK Python) — `claude-sonnet-4-6` comme modèle par défaut
- **Voix** : Intégration avec le pipeline STT/TTS natif de HA (`assist_pipeline`) ou via `conversation` integration
- **Apprentissage** : Stockage local des patterns (SQLite ou fichier JSON dans le dossier config HA)

## Constraints

- **Tech stack** : Python 3.11+, Home Assistant Core 2024.x+
- **Intégration** : Doit respecter l'architecture custom_component de HA (pas d'add-on séparé)
- **API** : Clé API Claude requise — configurée via l'interface HA (config flow)
- **Vie privée** : Les données d'apprentissage restent locales, seules les requêtes LLM partent vers l'API Anthropic

## Key Decisions

| Décision | Rationale | Outcome |
|----------|-----------|---------|
| Custom component (pas add-on) | Intégration native, pas de conteneur séparé, accès direct aux entités HA | — Pending |
| Claude comme LLM unique (v1) | Évite la complexité d'abstraction, utilisateur déjà décidé | — Pending |
| Règles locales + LLM hybride | Performance pour les cas fréquents, intelligence pour les cas complexes | — Pending |
| Apprentissage stocké localement | Vie privée, pas de dépendance cloud pour les données utilisateur | — Pending |

## Evolution

Ce document évolue à chaque transition de phase et jalons de milestone.

**Après chaque phase :**
1. Requirements invalidés ? → Déplacer vers Out of Scope avec raison
2. Requirements validés ? → Déplacer vers Validated avec référence de phase
3. Nouveaux requirements ? → Ajouter dans Active
4. Décisions à journaliser ? → Ajouter dans Key Decisions
5. "What This Is" toujours exact ? → Mettre à jour si dérivé

**Après chaque milestone :**
1. Revue complète de toutes les sections
2. Core Value check — toujours la bonne priorité ?
3. Audit Out of Scope — raisons toujours valides ?
4. Mettre à jour Context avec l'état actuel

---
*Last updated: 2026-03-31 — Phase 2 complete (conversation bridge, local rules, entity resolution)*
