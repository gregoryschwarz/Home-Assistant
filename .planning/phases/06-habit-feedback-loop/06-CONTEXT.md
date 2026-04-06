# Phase 6: Habit Feedback Loop - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Faire boucler les habitudes détectées (Phase 5) vers l'utilisateur de deux façons :
1. **Injection contextuelle** — les habitudes pertinentes enrichissent le prompt envoyé à Claude pour des réponses plus personnalisées
2. **Notifications proactives** — quand un nouveau pattern est détecté, une notification HA informe l'utilisateur et suggère une automatisation

Phase 6 ne crée pas de nouvelles habitudes (Phase 5), ne gère pas les suggestions acceptées/refusées (v2), et ne prend pas de décisions autonomes (v2).

</domain>

<decisions>
## Implementation Decisions

### Sélection des habitudes injectées (HABIT-04)
- **D-01:** Filtrage contextuel — lors d'une requête, injecter uniquement les habitudes dont l'`entity_id` est mentionné dans la commande utilisateur OU dont l'`hour` est dans la fenêtre `heure_actuelle ±2h`. Pas d'injection de toutes les habitudes à chaque appel.
- **D-02:** Si aucune habitude pertinente : ne rien injecter (pas de section habits dans le message).

### Format d'injection dans le message utilisateur
- **D-03:** Les habitudes filtrées sont ajoutées dynamiquement au contenu du message utilisateur dans `async_complete`, juste après la liste des entités. `SYSTEM_PROMPT` (const.py) n'est pas modifié.
- **D-04:** Signature étendue : `async_complete(text, entities, habits=None)` — paramètre `habits` optionnel de type `list[dict] | None`. Rétrocompatible avec tous les appelants existants.
- **D-05:** Format d'injection dans le message :
  ```
  Habitudes connues (contexte personnel) :
  - kitchen_light allumé le lundi à 7h (3 fois en 14 jours)
  - salon_thermostat ajusté à 19h le weekend (4 fois en 14 jours)
  ```
  Ajouté après la section "Entites disponibles:" si `habits` est non vide.

### Notifications HA (proactives)
- **D-06:** Anti-spam : un pattern ne génère qu'une notification par 24h maximum. Tracking de la date de dernière notification par `notification_id` en mémoire (pas de persistance entre redémarrages — acceptable v1).
- **D-07:** `notification_id` unique par pattern : `ha_ai_agent_habit_{entity_id}_{day_of_week}_{hour}` — la notification est remplacée (pas dupliquée) si le même pattern est re-détecté.
- **D-08:** Contenu de la notification :
  ```
  Habitude détectée : tu allumes {friendly_name} tous les {jour} à {heure}h ({N} fois en 14 jours).
  Créer une automatisation ?
  ```
  Via `hass.services.async_call("persistent_notification", "create", {...})`.
- **D-09:** Déclenchement : après chaque appel `async_detect_patterns()`, comparer les patterns retournés aux `notification_id` déjà envoyés dans les dernières 24h. Nouveaux patterns uniquement → notification.

### Claude's Discretion
- Logique exacte de matching "entité mentionnée dans la commande" (regex vs token matching)
- Format exact du jour de la semaine dans la notification (lundi/mardi vs 0/1)
- Emplacement du tracking anti-spam (attribut de PatternDetector ou module séparé)

</decisions>

<specifics>
## Specific Ideas

- Aucune référence externe — l'utilisateur fait confiance aux choix techniques pour l'implémentation.
- La notification doit rester informative et non intrusive — texte simple, pas de bouton cliquable (limitation HA persistent_notification).

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase existant (à lire obligatoirement)
- `custom_components/ha_ai_agent/claude_client.py` — `async_complete(text, entities)` à étendre avec `habits=None`, construction du `user_content`, `SYSTEM_PROMPT.format()`
- `custom_components/ha_ai_agent/const.py` — `SYSTEM_PROMPT` (ne pas modifier), imports existants
- `custom_components/ha_ai_agent/conversation.py` — point d'appel de `async_complete`, où récupérer `pattern_detector` depuis `hass.data` et passer les habits
- `custom_components/ha_ai_agent/__init__.py` — `hass.data[DOMAIN][entry_id]` dict (keys: router, entity_context, claude_client, storage, habit_engine, pattern_detector)
- `custom_components/ha_ai_agent/pattern_detector.py` — `async_detect_patterns()` (détecte + upsert), `async_get_patterns()` (lecture patterns table)

### Requirements
- `.planning/REQUIREMENTS.md` — HABIT-04 (habitudes enrichissent contexte Claude)

### Phase précédente
- `.planning/phases/05-habit-engine/05-CONTEXT.md` — D-04 (champs du pattern : entity_id, domain, service, day_of_week, hour, occurrences), D-07 (schema events)
- `.planning/phases/05-habit-engine/05-VERIFICATION.md` — API confirmée : `async_detect_patterns()`, `async_get_patterns()`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `hass.data[DOMAIN][entry_id]["pattern_detector"]` — PatternDetector déjà instancié et accessible depuis `conversation.py`
- `hass.services.async_call("persistent_notification", "create", {...})` — pattern HA standard pour les notifications

### Established Patterns
- `async_complete(text, entities)` dans `claude_client.py` — à étendre avec paramètre optionnel `habits=None`
- `hass.data[DOMAIN][self._entry.entry_id]["claude_client"]` — pattern d'accès aux services depuis `conversation.py` (lignes 90-91)

### Integration Points
- `conversation.py` `async_handle_text_input` → récupère `pattern_detector` → appelle `async_get_patterns()` → filtre par entité/heure → passe à `async_complete`
- `pattern_detector.py` `async_detect_patterns()` → après détection → vérifie anti-spam → appelle `hass.services.async_call("persistent_notification", "create", ...)` pour chaque nouveau pattern

</code_context>

<deferred>
## Deferred Ideas

- **SUGG-01/02/03** (accepter/refuser suggestions) — v2, hors scope Phase 6
- Boutons d'action dans les notifications — non supporté par `persistent_notification` en v1
- Persistance de l'anti-spam entre redémarrages — v2 (nécessiterait stockage supplémentaire)
- Personnalisation par personne (MULTI-01/02) — v2

</deferred>

---

*Phase: 06-habit-feedback-loop*
*Context gathered: 2026-04-05*
