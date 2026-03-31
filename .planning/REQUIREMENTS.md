# Requirements: HA Autonomous Agent

**Defined:** 2026-03-30
**Core Value:** Contrôler et automatiser sa maison en langage naturel sans configuration technique, avec un agent qui s'améliore au fil du temps.

## v1 Requirements

### Intégration Home Assistant

- [x] **HA-01**: Le composant s'installe via le dossier `custom_components/ha_ai_agent/` et apparaît dans l'interface HA
- [x] **HA-02**: L'utilisateur peut configurer la clé API Claude via le config flow HA (UI)
- [x] **HA-03**: Le composant peut être rechargé sans redémarrer Home Assistant
- [x] **HA-04**: Le composant s'enregistre comme agent de conversation sélectionnable dans les Voice Assistants HA

### Contrôle par langage naturel

- [ ] **NLU-01**: L'utilisateur peut envoyer une commande texte (ex: "allume la lumière du salon") et l'entité correspondante est contrôlée
- [ ] **NLU-02**: Les commandes simples/fréquentes sont traitées localement (regex/règles) sans appel API Claude
- [ ] **NLU-03**: Les commandes ambiguës ou complexes sont envoyées à Claude avec la liste filtrée des entités HA pertinentes
- [ ] **NLU-04**: L'agent répond avec une confirmation en langage naturel après chaque action
- [ ] **NLU-05**: L'agent gère les erreurs (entité introuvable, service indisponible) avec un message clair

### Interface voix

- [ ] **VOICE-01**: Les commandes vocales via le pipeline `assist_pipeline` de HA sont traitées par le composant
- [ ] **VOICE-02**: La réponse textuelle de l'agent est transmise au moteur TTS de HA pour lecture audio

### Apprentissage des habitudes

- [ ] **HABIT-01**: Le composant écoute les changements d'état HA et stocke les événements en base SQLite locale
- [ ] **HABIT-02**: Les données collectées contiennent : entité, action, heure, jour de semaine, contexte (présence, météo si disponible)
- [ ] **HABIT-03**: Le moteur de patterns détecte les habitudes récurrentes (ex: "allume la cuisine tous les matins à 7h")
- [ ] **HABIT-04**: Les habitudes détectées enrichissent le contexte envoyé à Claude pour des réponses plus pertinentes

### Sécurité et vie privée

- [ ] **SEC-01**: Seule la liste filtrée des entités pertinentes (pas l'état complet de tout HA) est envoyée à l'API Claude
- [ ] **SEC-02**: Les données d'habitudes restent exclusivement en local (pas de cloud sync)
- [ ] **SEC-03**: Une whitelist de domaines contrôlables est configurable (light, switch, climate, media_player par défaut)

## v2 Requirements

### Décisions autonomes

- **AUTO-01**: L'agent agit de façon proactive sans commande (ex: ferme les volets à la tombée de la nuit)
- **AUTO-02**: L'utilisateur peut activer/désactiver les actions autonomes par domaine d'entité
- **AUTO-03**: L'agent explique pourquoi il a effectué une action autonome

### Suggestions et feedback

- **SUGG-01**: L'agent propose des automations basées sur les habitudes détectées
- **SUGG-02**: L'utilisateur peut accepter, refuser ou modifier une suggestion
- **SUGG-03**: Les suggestions refusées ne sont plus proposées

### Multi-utilisateurs

- **MULTI-01**: Les habitudes sont associées à la personne détectée (présence HA)
- **MULTI-02**: Les suggestions sont personnalisées par personne

## Out of Scope

| Feature | Raison |
|---------|--------|
| Support multi-LLM (GPT, Ollama) | Complexité d'abstraction prématurée — Claude uniquement pour v1 |
| Add-on HA séparé | Custom component donne accès direct aux entités, pas de bridge REST/WS nécessaire |
| Cloud sync des habitudes | Régression vie privée sans bénéfice MVP |
| Interface web dédiée | L'interface native HA suffit (chat + voice assistants) |
| Orchestration multi-agents LLM | Sur-ingénierie pour le périmètre v1 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| HA-01 | Phase 1 | Complete |
| HA-02 | Phase 1 | Complete |
| HA-03 | Phase 1 | Complete |
| HA-04 | Phase 1 | Complete |
| NLU-01 | Phase 2 | Pending |
| NLU-02 | Phase 2 | Pending |
| NLU-03 | Phase 3 | Pending |
| NLU-04 | Phase 2 | Pending |
| NLU-05 | Phase 2 | Pending |
| VOICE-01 | Phase 4 | Pending |
| VOICE-02 | Phase 4 | Pending |
| HABIT-01 | Phase 5 | Pending |
| HABIT-02 | Phase 5 | Pending |
| HABIT-03 | Phase 5 | Pending |
| HABIT-04 | Phase 6 | Pending |
| SEC-01 | Phase 3 | Pending |
| SEC-02 | Phase 5 | Pending |
| SEC-03 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 — traceability confirmed against ROADMAP.md (6 phases)*
