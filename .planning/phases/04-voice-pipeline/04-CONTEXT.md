# Phase 4: Voice Pipeline - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Configurer le pipeline vocal HA end-to-end : installation des add-ons Wyoming Whisper (STT) et Piper (TTS), configuration d'un pipeline Assist dans l'UI HA sélectionnant `conversation.ha_ai_agent` comme backend, activation du wake word openWakeWord, et validation par unit test + smoke test WebSocket.

**Zéro nouveau code Python dans le composant** — `HaAiConversationAgent` est déjà un backend pipeline-compatible. Cette phase est de la configuration et de la validation.

</domain>

<decisions>
## Implementation Decisions

### Type d'installation HA
- **D-01:** L'utilisateur tourne HA OS. Installer Wyoming Whisper et Wyoming Piper via le **store d'add-ons HA** (pas de Docker manuel). Pas de configuration réseau mDNS spéciale requise.

### Wake word
- **D-02:** Activer le wake word **openWakeWord** dans le pipeline. Mot de déclenchement : `alexa` (modèle pré-entraîné disponible dans openWakeWord — **usage non commercial uniquement**, à documenter dans le plan).
- **D-03:** Installer l'add-on openWakeWord depuis le store HA, sélectionner le modèle `alexa` dans la configuration du pipeline.

### Voix TTS française
- **D-04:** Voix Piper : `fr_FR-siwis-medium` (voix féminine naturelle, latence faible, la plus utilisée dans la communauté HA pour le français). À sélectionner explicitement dans la config du pipeline pour éviter le Pitfall 3 de la recherche.

### Configuration du pipeline
- **D-05:** Pipeline configuré exclusivement via l'UI HA (Settings > Voice Assistants). Aucune configuration YAML ou programmatique — les pipelines sont de la configuration utilisateur, pas de l'état du composant (anti-pattern documenté dans la recherche).
- **D-06:** Paramètres du pipeline :
  - `conversation_engine = "conversation.ha_ai_agent"` (entity_id complet avec le point — Pitfall 1 à éviter)
  - `conversation_language = "fr"`
  - `language = "fr"`
  - `stt_engine = "stt.faster_whisper"`
  - `stt_language = "fr"`
  - `tts_engine = "tts.piper"`
  - `tts_language = "fr"`
  - `tts_voice = "fr_FR-siwis-medium"`
  - `wake_word_entity = "wake_word.openWakeWord"`
  - `wake_word_id = "alexa"`

### Stratégie de validation
- **D-07:** Validation en deux niveaux :
  1. **Unit test automatisé** : `async_get_agent_info(hass, "conversation.ha_ai_agent")` retourne un objet non-null avec `id == "conversation.ha_ai_agent"`. Reproductible en CI.
  2. **Smoke test WebSocket** : appel `assist_pipeline/run` avec `start_stage: "intent"` et un texte de commande (`"allume le salon"`). Valide le pipeline end-to-end manuellement.

### Claude's Discretion
- Nom du pipeline dans l'UI HA (ex: "Mon assistant HA" — cosmétique)
- Choix du satellite physique si applicable (hors scope du plan)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase existant
- `custom_components/ha_ai_agent/conversation.py` — `_attr_name = "HA AI Agent"` (→ entity_id stable), `supported_languages = ["fr", "en"]`, `_async_handle_message` déjà compatible pipeline
- `custom_components/ha_ai_agent/manifest.json` — `"after_dependencies": ["assist_pipeline"]` déjà présent (aucune modification requise)

### Research Phase 4
- `.planning/phases/04-voice-pipeline/04-RESEARCH.md` — Architecture complète du pipeline, pitfalls 1-5, exemples de code de validation, paramètres du dataclass Pipeline vérifiés sur HA 2026.3.4

### Requirements
- `.planning/REQUIREMENTS.md` — VOICE-01 (commandes vocales via assist_pipeline), VOICE-02 (réponse TTS via moteur HA)

### No external specs
Aucun ADR ou spec externe — toutes les décisions sont capturées dans ce CONTEXT.md et dans 04-RESEARCH.md.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `HaAiConversationAgent` (`conversation.py`) — Déjà enregistré comme `ConversationEntity`, déjà compatible pipeline. Aucune modification requise pour Phase 4.
- `manifest.json` — `after_dependencies: ["assist_pipeline"]` déjà déclaré en Phase 1.

### Established Patterns
- `supported_languages = ["fr", "en"]` retourne les deux langues — le pipeline configuré en FR trouvera l'agent sans problème de filtrage.
- `_attr_name = "HA AI Agent"` est une constante → `entity_id = "conversation.ha_ai_agent"` est stable.

### Integration Points
- Aucun nouveau point d'intégration code. Le pipeline HA appelle `conversation.async_get_agent(hass, "conversation.ha_ai_agent")` → trouve `HaAiConversationAgent` → appelle `_async_handle_message` → chaîne IntentRouter/ClaudeClient existante.

</code_context>

<specifics>
## Specific Ideas

- Wake word choisi : `alexa` — modèle openWakeWord disponible, usage non commercial uniquement.
- Voix TTS : `fr_FR-siwis-medium` — explicitement nommée pour éviter le Pitfall 3 (mauvaise voix par défaut).
- Le plan doit documenter la note "usage non commercial" pour alexa.

</specifics>

<deferred>
## Deferred Ideas

- Configuration d'un satellite physique (ex: M5Stack ATOM Echo) — hors scope Phase 4, Phase 5+
- Ajout d'un wake word personnalisé (modèle entraîné) — hors scope v1

</deferred>

---

*Phase: 04-voice-pipeline*
*Context gathered: 2026-04-04*
