# Phase 3: Claude LLM Integration - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Ajouter Claude API comme fallback NLU lorsque l'IntentRouter local ne trouve pas de correspondance regex. Cette phase câble ClaudeClient (AsyncAnthropic), le schéma tool_use pour les actions HA, le filtrage des entités envoyées à l'API, et la dégradation gracieuse en cas d'échec. La Phase 2 (règles locales) reste prioritaire — Claude n'est appelé que si aucune règle ne correspond. La voix (Phase 4) et l'apprentissage (Phase 5) sont hors scope.

</domain>

<decisions>
## Implementation Decisions

### Déclenchement du fallback LLM
- **D-01:** `IntentRouter.async_route` retourne `None` (sentinel) quand aucun regex ne correspond — remplace le retour direct de `"Je n'ai pas compris la commande."` (ligne 96 actuelle).
- **D-02:** `conversation.py` détecte `None` et appelle `ClaudeClient.async_complete()`. Cela garde ClaudeClient hors de IntentRouter (séparation des responsabilités).
- **D-03:** Si Claude retourne une action exécutée avec succès, retourner la confirmation française. Si Claude ne peut pas résoudre non plus, retourner `"Je n'ai pas compris la commande."`.

### ClaudeClient
- **D-04:** Wrapper async autour de `AsyncAnthropic` avec système de retry : 1 tentative automatique avec backoff exponentiel (1 s), puis abandon.
- **D-05:** Modèle : `claude-sonnet-4-6` (défini dans `const.py` comme `DEFAULT_MODEL`).
- **D-06:** La clé API est lue depuis `entry.data[CONF_API_KEY]` (déjà stockée en Phase 1).
- **D-07:** Timeout de 10 secondes par requête pour ne pas bloquer l'interface HA.

### Historique de conversation
- **D-08:** Fenêtre glissante de **10 tours** (5 échanges user/assistant) en mémoire dans `ClaudeClient`, rattachée à `entry_id`. Non persistée entre redémarrages HA — acceptable pour v1.
- **D-09:** L'historique est réinitialisé si le composant est rechargé (unload/reload).

### Schéma tool_use
- **D-10:** Un seul tool déclaré : `execute_ha_service`. Paramètres : `domain` (str), `service` (str), `entity_id` (str), `service_data` (dict, optionnel).
- **D-11:** Validation stricte : si Claude retourne un `tool_use` avec `domain` non présent dans `CONF_ALLOWED_DOMAINS`, rejeter et retourner une erreur française sans exécuter.
- **D-12:** Si Claude retourne du texte libre sans tool_use, retourner ce texte directement comme réponse (cas : question, ambiguïté non résoluble en action).

### Filtrage des entités (SEC-01)
- **D-13:** Seules les entités des domaines `CONF_ALLOWED_DOMAINS` sont envoyées à Claude. Plafond de 50 entités max.
- **D-14:** Pour chaque entité, envoyer : `entity_id`, `friendly_name` (depuis `entity_registry`), `state` actuel. Pas d'attributs supplémentaires.
- **D-15:** Si plus de 50 entités dans les domaines autorisés, tronquer en priorisant les entités dont le `friendly_name` partage des tokens avec le texte de la commande (même logique que `EntityContextBuilder` Phase 2).

### System prompt
- **D-16:** Prompt système en français, persona "assistant domotique Home Assistant". Include : liste des domaines autorisés, format de réponse attendu (tool_use ou texte), instruction de ne jamais inventer un `entity_id` absent de la liste fournie.
- **D-17:** Le system prompt est une constante dans `const.py` (pas de configuration utilisateur en v1).

### Dégradation gracieuse
- **D-18:** Si l'API Claude est injoignable après retry : retourner `"Service Claude indisponible, veuillez réessayer."` — pas d'exception non gérée.
- **D-19:** Si la clé API est absente ou invalide (401) : retourner `"Clé API Claude invalide. Vérifiez la configuration."` — logguer en `WARNING`.
- **D-20:** Les erreurs API sont loguées via `_LOGGER` (même pattern que intent_router.py) mais jamais remontées à l'utilisateur en stack trace.

### Claude's Discretion
- Implémentation interne du retry (asyncio.sleep vs tenacity)
- Structure exacte du system prompt (wording, longueur)
- Format de troncature des entités au-delà de 50

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase existant (à lire obligatoirement)
- `custom_components/ha_ai_agent/intent_router.py` — Point exact du fallback (ligne ~96), pattern `async_route`, pattern de dispatch, structure des retours string
- `custom_components/ha_ai_agent/conversation.py` — Appel de `async_route`, construction de `ConversationResult`, point d'injection du fallback LLM
- `custom_components/ha_ai_agent/__init__.py` — Pattern `hass.data[DOMAIN][entry_id]`, où ajouter `ClaudeClient` au setup
- `custom_components/ha_ai_agent/entity_context.py` — `EntityContextBuilder`, méthode `resolve_entity` et pattern de récupération des entités depuis `entity_registry`
- `custom_components/ha_ai_agent/const.py` — `CONF_API_KEY`, `CONF_ALLOWED_DOMAINS`, `DEFAULT_ALLOWED_DOMAINS` — à étendre avec `DEFAULT_MODEL`, `CONF_MAX_HISTORY`
- `custom_components/ha_ai_agent/config_flow.py` — Pattern OptionsFlow existant (Phase 2), où ajouter la validation de clé API si besoin

### Requirements
- `.planning/REQUIREMENTS.md` — NLU-03 (commandes ambiguës → Claude + entités filtrées), SEC-01 (pas d'état complet HA vers API), SEC-02 (habitudes locales uniquement)

### No external specs
Les patterns Anthropic SDK (AsyncAnthropic, tool_use) seront recherchés par le researcher via la documentation officielle. Aucun ADR ou spec externe dans ce projet pour l'instant.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `EntityContextBuilder` (`entity_context.py`) — Contient déjà la logique de récupération des entités depuis `entity_registry`. Pour la Phase 3, une nouvelle méthode `list_entities_for_llm(text: str, limit: int = 50) -> list[dict]` doit être ajoutée (retourne entity_id + friendly_name + state).
- Pattern `hass.data[DOMAIN][entry_id]` (`__init__.py:20`) — Ajouter `"claude_client": ClaudeClient(...)` ici au setup.
- `_LOGGER = logging.getLogger(__name__)` — Pattern de logging présent dans tous les fichiers, à reproduire dans `claude_client.py`.

### Established Patterns
- Tous les retours d'erreur sont des strings françaises (jamais d'exceptions remontées à l'UI) — pattern NLU-05, à respecter dans ClaudeClient.
- Tests unitaires avec `unittest.mock.AsyncMock` pour `hass` et `hass.services` (voir `tests/test_intent_router.py`).
- `from __future__ import annotations` en tête de chaque fichier Python.

### Integration Points
- `conversation.py:83` → `router.async_route(text, language)` → détecter `None` → appeler `claude_client.async_complete(text, entities)`
- `__init__.py:async_setup_entry` → instancier `ClaudeClient(hass, entry)` et stocker dans `hass.data`
- `entity_context.py` → ajouter méthode `list_entities_for_llm` sans casser `resolve_entity` existant

</code_context>

<specifics>
## Specific Ideas

- Le modèle par défaut est `claude-sonnet-4-6` — déjà mentionné dans PROJECT.md.
- La clé API est déjà collectée en Phase 1 via config_flow — pas de nouvel écran de config pour Phase 3 (sauf validation de la clé si absente).

</specifics>

<deferred>
## Deferred Ideas

- Persistance de l'historique entre redémarrages HA — différé Phase 5 (stockage SQLite)
- Configuration utilisateur du modèle Claude (mini vs sonnet) — différé v2
- Validation de la clé API au moment du setup (appel test) — différé v2, trop de complexité pour v1
- Multi-actions dans un seul tour (ex: "allume X et baisse Y") — différé, complexité du schéma tool_use hors scope v1

</deferred>

---

*Phase: 03-claude-llm-integration*
*Context gathered: 2026-04-01 (auto — user selected "go")*
