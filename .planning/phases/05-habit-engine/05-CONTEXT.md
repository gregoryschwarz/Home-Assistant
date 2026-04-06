# Phase 5: Habit Engine - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Observer et persister les changements d'état Home Assistant dans une base SQLite locale crash-safe, puis détecter les routines récurrentes. Cette phase livre : l'infrastructure de stockage (AgentStorage), le collecteur d'événements (HabitEngine), et le détecteur de patterns. La consommation des patterns par Claude (enrichissement du contexte) est Phase 6 (HABIT-04).

</domain>

<decisions>
## Implementation Decisions

### Filtrage des événements
- **D-01:** Enregistrer uniquement les actions déclenchées par un humain : `context.user_id` non null dans l'événement `state_changed`. Les automatisations (user_id null) sont ignorées.
- **D-02:** Seuls les domaines présents dans `CONF_ALLOWED_DOMAINS` (light, switch, climate, media_player par défaut) sont trackés — cohérent avec le filtrage Phase 2.

### Seuil de détection de pattern
- **D-03:** Détection souple — **3 répétitions sur 14 jours** avec fenêtre horaire **±30 min**. Ex : lumière cuisine allumée ≥3× entre 6h30 et 7h30 en 2 semaines → habitude détectée.
- **D-04:** La détection s'appuie sur : `entity_id` + `action` (service appelé) + `hour_of_day` + `day_of_week` pour grouper les occurrences similaires.

### Contexte enregistré (HABIT-02)
- **D-05:** Présence : liste des personnes actuellement à la maison au moment de l'événement, lue depuis les entités `person.*` de HA. Format : `["greg", "pam"]` (friendly_name en minuscules). Null si aucune entité person.* disponible.
- **D-06:** Météo : état de la première entité `weather.*` trouvée dans HA au moment de l'événement (ex: `"sunny"`, `"cloudy"`). Null si aucune entité weather.* disponible. Pas de configuration utilisateur en v1.
- **D-07:** Champs complets d'un enregistrement : `entity_id`, `domain`, `service`, `timestamp` (ISO 8601 UTC), `day_of_week` (0=lundi), `hour` (int), `persons_home` (JSON array), `weather_condition` (str|null).

### Rétention et cap
- **D-08:** TTL de **90 jours** — les événements plus anciens sont purgés automatiquement (purge lancée au démarrage du composant et quotidiennement).
- **D-09:** Cap de **10 000 événements** — politique FIFO : quand le cap est atteint, les événements les plus anciens sont écrasés. L'enregistrement ne s'arrête jamais.
- **D-10:** WAL mode activé sur SQLite (aiosqlite) pour la résistance aux crashes. Schema versioning via table `meta` avec clé `schema_version`.

### Claude's Discretion
- Algorithme exact de détection de fréquence (time-series bucketing ou clustering)
- Structure exacte de la table `patterns` (colonnes, index)
- Fréquence et timing de la tâche de détection (au démarrage, toutes les N heures)
- Implémentation du daily TTL purge (asyncio task vs HA scheduler)

</decisions>

<specifics>
## Specific Ideas

- Aucune référence externe spécifique — l'utilisateur fait confiance aux choix techniques pour l'implémentation SQLite/aiosqlite.
- Priorité vie privée : les données ne quittent jamais le device (SEC-02 verrouillé).

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase existant (à lire obligatoirement)
- `custom_components/ha_ai_agent/__init__.py` — Pattern `hass.data[DOMAIN][entry_id]`, setup/teardown du composant, où enregistrer HabitEngine et AgentStorage
- `custom_components/ha_ai_agent/const.py` — `CONF_ALLOWED_DOMAINS`, `DEFAULT_ALLOWED_DOMAINS`, `DOMAIN` — HabitEngine filtre sur ces domaines
- `custom_components/ha_ai_agent/conversation.py` — Pattern ConversationEntity existant, référence pour les patterns HA async
- `custom_components/ha_ai_agent/manifest.json` — Dépendances déclarées, où ajouter `aiosqlite` si nécessaire

### Requirements
- `.planning/REQUIREMENTS.md` — HABIT-01 (écoute state_changed + stockage SQLite), HABIT-02 (champs de l'enregistrement), HABIT-03 (détection patterns récurrents), SEC-02 (données locales uniquement)

### Roadmap
- `.planning/ROADMAP.md` — Phase 5 plans (05-01 AgentStorage, 05-02 HabitEngine, 05-03 Pattern detection) pour vérifier l'alignement des livrables

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `hass.data[DOMAIN][entry_id]` pattern (`__init__.py`) — AgentStorage et HabitEngine s'enregistrent au même endroit pour être accessibles depuis conversation.py (Phase 6)
- `CONF_ALLOWED_DOMAINS` (`const.py`) — utilisé directement par HabitEngine pour filtrer les événements

### Established Patterns
- Async Python avec `asyncio` — tout le composant est async, aiosqlite suit le même pattern
- Logging via `_LOGGER = logging.getLogger(__name__)` — à reproduire dans les nouveaux modules
- Teardown via `entry.async_on_unload()` — AgentStorage doit fermer la connexion DB proprement

### Integration Points
- `hass.bus.async_listen("state_changed", ...)` — point d'entrée HabitEngine pour capturer les événements
- `hass.states.get("person.*")` + `hass.states.get("weather.*")` — lecture du contexte présence/météo
- `hass.config.config_dir` — répertoire de stockage pour le fichier SQLite (ex: `{config_dir}/ha_ai_agent_habits.db`)

</code_context>

<deferred>
## Deferred Ideas

- **HABIT-04** (enrichissement contexte Claude) — Phase 6, hors scope Phase 5
- Suggestions d'automatisation basées sur les patterns (SUGG-01) — v2
- Habitudes par personne avec personnalisation (MULTI-01/02) — v2
- Interface de consultation des habitudes dans HA — v2

</deferred>

---

*Phase: 05-habit-engine*
*Context gathered: 2026-04-05*
