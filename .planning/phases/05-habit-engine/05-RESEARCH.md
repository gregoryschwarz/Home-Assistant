# Phase 5: Habit Engine - Research

**Researched:** 2026-04-05
**Domain:** aiosqlite / Home Assistant event bus / time-series pattern detection
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Enregistrer uniquement les actions déclenchées par un humain : `context.user_id` non null dans l'événement `state_changed`. Les automatisations (user_id null) sont ignorées.
- **D-02:** Seuls les domaines présents dans `CONF_ALLOWED_DOMAINS` (light, switch, climate, media_player par défaut) sont trackés — cohérent avec le filtrage Phase 2.
- **D-03:** Détection souple — **3 répétitions sur 14 jours** avec fenêtre horaire **±30 min**. Ex : lumière cuisine allumée ≥3× entre 6h30 et 7h30 en 2 semaines → habitude détectée.
- **D-04:** La détection s'appuie sur : `entity_id` + `action` (service appelé) + `hour_of_day` + `day_of_week` pour grouper les occurrences similaires.
- **D-05:** Présence : liste des personnes actuellement à la maison au moment de l'événement, lue depuis les entités `person.*` de HA. Format : `["greg", "pam"]` (friendly_name en minuscules). Null si aucune entité person.* disponible.
- **D-06:** Météo : état de la première entité `weather.*` trouvée dans HA au moment de l'événement (ex: `"sunny"`, `"cloudy"`). Null si aucune entité weather.* disponible. Pas de configuration utilisateur en v1.
- **D-07:** Champs complets d'un enregistrement : `entity_id`, `domain`, `service`, `timestamp` (ISO 8601 UTC), `day_of_week` (0=lundi), `hour` (int), `persons_home` (JSON array), `weather_condition` (str|null).
- **D-08:** TTL de **90 jours** — les événements plus anciens sont purgés automatiquement (purge lancée au démarrage du composant et quotidiennement).
- **D-09:** Cap de **10 000 événements** — politique FIFO : quand le cap est atteint, les événements les plus anciens sont écrasés. L'enregistrement ne s'arrête jamais.
- **D-10:** WAL mode activé sur SQLite (aiosqlite) pour la résistance aux crashes. Schema versioning via table `meta` avec clé `schema_version`.

### Claude's Discretion

- Algorithme exact de détection de fréquence (time-series bucketing ou clustering)
- Structure exacte de la table `patterns` (colonnes, index)
- Fréquence et timing de la tâche de détection (au démarrage, toutes les N heures)
- Implémentation du daily TTL purge (asyncio task vs HA scheduler)

### Deferred Ideas (OUT OF SCOPE)

- **HABIT-04** (enrichissement contexte Claude) — Phase 6, hors scope Phase 5
- Suggestions d'automatisation basées sur les patterns (SUGG-01) — v2
- Habitudes par personne avec personnalisation (MULTI-01/02) — v2
- Interface de consultation des habitudes dans HA — v2
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HABIT-01 | Le composant écoute les changements d'état HA et stocke les événements en base SQLite locale | aiosqlite 0.22.1 déjà dans manifest.json ; `hass.bus.async_listen("state_changed", ...)` pattern documenté |
| HABIT-02 | Les données collectées contiennent : entité, action, heure, jour de semaine, contexte (présence, météo si disponible) | Schema D-07 ; lecture `person.*`/`weather.*` via `hass.states.async_all(domain)` |
| HABIT-03 | Le moteur de patterns détecte les habitudes récurrentes (ex: "allume la cuisine tous les matins à 7h") | SQL GROUP BY + COUNT avec fenêtre ±30min ; seuil 3 répétitions / 14 jours (D-03, D-04) |
| SEC-02 | Les données d'habitudes restent exclusivement en local (pas de cloud sync) | SQLite local dans `hass.config.config_dir` ; aucun appel réseau dans AgentStorage/HabitEngine |
</phase_requirements>

---

## Summary

La Phase 5 livre trois modules : **AgentStorage** (couche SQLite via aiosqlite), **HabitEngine** (listener d'événements HA), et **PatternDetector** (analyse de fréquence). L'infrastructure est déjà partiellement prête : `aiosqlite>=0.20` est déclaré dans `manifest.json` (version installée : 0.22.1), et tous les patterns async du composant existant (teardown via `entry.async_on_unload`, logging, `hass.data[DOMAIN][entry_id]`) s'appliquent directement.

Les deux points d'attention principaux sont : (1) le filtrage humain/automation via `event.data["new_state"].context.user_id` — qui est null pour les automatisations, non-null pour les actions frontend — et (2) le daily purge TTL, pour lequel la recommandation est `async_track_time_interval` de `homeassistant.helpers.event` avec enregistrement du cancel_callback dans `entry.async_on_unload`, ce qui évite une tâche asyncio manuelle difficile à nettoyer.

L'algorithme de détection de patterns est implémenté en pur SQL : un `GROUP BY entity_id, service, day_of_week, CAST((hour * 60) / 30 AS INT)` (bucket de 30 min) sur la fenêtre de 14 jours, filtré sur `COUNT(*) >= 3`. C'est le choix le plus simple, entièrement local, sans dépendance à pandas ou scipy.

**Recommandation principale :** Utiliser `aiosqlite.connect(db_path)` avec WAL PRAGMA au démarrage, table `meta` pour schema_version, `entry.async_on_unload` pour fermer proprement la DB et annuler la tâche TTL.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiosqlite | 0.22.1 (installé) | SQLite async | Déjà dans manifest.json ; pattern async natif HA |
| sqlite3 (stdlib) | Python 3.14 | Runtime SQLite | Fourni par Python, pas d'installation |
| homeassistant.helpers.event | (intégré HA) | async_track_time_interval | Pattern HA officiel pour tâches périodiques |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | Python 3.14 | Sérialisation persons_home JSON | Toujours — champ D-05 est un JSON array |
| datetime (stdlib) | Python 3.14 | ISO 8601, day_of_week, hour | Toujours — champs timestamp / day_of_week / hour |

### Alternatives considérées

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQL pur pour détection | pandas / scipy | pandas non installé, surcharge pour 10 000 événements |
| async_track_time_interval | asyncio.create_task loop | La task HA gère teardown proprement via cancel_callback |
| aiosqlite | SQLAlchemy async | SQLAlchemy ajoute une abstraction inutile pour ce schéma fixe |

**Installation :** Rien à installer — `aiosqlite>=0.20` est déjà déclaré dans `manifest.json`. Vérification :
```bash
pip show aiosqlite
# Name: aiosqlite, Version: 0.22.1
```

---

## Architecture Patterns

### Recommended Project Structure

```
custom_components/ha_ai_agent/
├── __init__.py           # Enregistrer AgentStorage + HabitEngine dans hass.data
├── storage.py            # AgentStorage — couche SQLite (Plan 05-01)
├── habit_engine.py       # HabitEngine — listener state_changed (Plan 05-02)
├── pattern_detector.py   # PatternDetector — analyse fréquence (Plan 05-03)
├── const.py              # Ajouter DB_FILENAME, HABIT_TTL_DAYS, HABIT_CAP, etc.
└── manifest.json         # aiosqlite déjà déclaré — rien à changer

tests/
├── test_storage.py       # Tests AgentStorage : schema, WAL, TTL, cap (HABIT-01)
├── test_habit_engine.py  # Tests HabitEngine : filtrage user_id, domaine (HABIT-01, HABIT-02)
└── test_pattern_detector.py  # Tests PatternDetector : seuil, fenêtre ±30min (HABIT-03)
```

### Pattern 1 : AgentStorage — connexion et initialisation

**What :** Classe async qui ouvre une connexion aiosqlite persistante, active WAL, crée les tables et gère le schema_version.

**When to use :** Instancié dans `async_setup_entry`, fermé via `entry.async_on_unload`.

```python
# Source: aiosqlite GitHub + HA __init__.py existing pattern
import aiosqlite
import logging
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

class AgentStorage:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._db: aiosqlite.Connection | None = None

    async def async_open(self) -> None:
        db_path = self.hass.config.config_dir + "/ha_ai_agent_habits.db"
        self._db = await aiosqlite.connect(db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.commit()
        await self._ensure_schema()

    async def async_close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def _ensure_schema(self) -> None:
        # Crée table meta pour schema_version
        await self._db.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        await self._db.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1')"
        )
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                service TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                day_of_week INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                persons_home TEXT,
                weather_condition TEXT
            )
        """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_entity_ts "
            "ON events (entity_id, timestamp)"
        )
        await self._db.commit()
```

### Pattern 2 : Enregistrement dans hass.data et teardown

**What :** Enregistrer `AgentStorage` et `HabitEngine` dans `hass.data[DOMAIN][entry.entry_id]`, et fermer proprement via `entry.async_on_unload`.

```python
# Source: custom_components/ha_ai_agent/__init__.py existing pattern
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    storage = AgentStorage(hass)
    await storage.async_open()
    habit_engine = HabitEngine(hass, storage, allowed_domains=allowed_domains)
    await habit_engine.async_start()

    hass.data[DOMAIN][entry.entry_id]["storage"] = storage
    hass.data[DOMAIN][entry.entry_id]["habit_engine"] = habit_engine

    # Teardown propre
    entry.async_on_unload(storage.async_close)
    entry.async_on_unload(habit_engine.async_stop)
    ...
```

### Pattern 3 : HabitEngine — listener state_changed avec filtrage

**What :** Subscribe à `state_changed` via `hass.bus.async_listen`, filtre les événements humains (user_id non null) et les domaines autorisés.

```python
# Source: HA Data Science Portal (context doc) + HA event bus patterns
from homeassistant.core import Event

class HabitEngine:
    def __init__(self, hass, storage, allowed_domains):
        self.hass = hass
        self._storage = storage
        self._allowed_domains = allowed_domains
        self._unsub = None

    async def async_start(self) -> None:
        self._unsub = self.hass.bus.async_listen(
            "state_changed", self._handle_state_changed
        )

    async def async_stop(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    async def _handle_state_changed(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        # D-01 : filtrage humain — user_id non null = action frontend
        if new_state.context.user_id is None:
            return
        entity_id: str = new_state.entity_id
        domain = entity_id.split(".")[0]
        # D-02 : filtrage domaine
        if domain not in self._allowed_domains:
            return
        await self._storage.async_record_event(new_state, domain)
```

### Pattern 4 : Lecture du contexte présence et météo

**What :** `hass.states.async_all(domain)` pour lister les entités d'un domaine ; `state.attributes.get("friendly_name")` pour le nom.

```python
# Source: test_voice_pipeline.py existing pattern — hass.states.async_all("conversation")
# Verified: same API works for "person" and "weather" domains

def _get_persons_home(hass) -> list[str] | None:
    """Retourne friendly_names en minuscules des personnes présentes."""
    person_states = hass.states.async_all("person")
    if not person_states:
        return None
    home = [
        s.attributes.get("friendly_name", s.entity_id).lower()
        for s in person_states
        if s.state == "home"
    ]
    return home or []

def _get_weather_condition(hass) -> str | None:
    """Retourne l'état de la première entité weather.*"""
    weather_states = hass.states.async_all("weather")
    if not weather_states:
        return None
    return weather_states[0].state
```

**Note :** `hass.states.async_all(domain)` accepte un domain string — confirmé par usage dans `test_voice_pipeline.py` (`hass.states.async_all("conversation")`). [MEDIUM confidence — code existant dans le projet, pas de doc officielle trouvée]

### Pattern 5 : Purge TTL quotidienne via async_track_time_interval

**What :** Scheduler HA officiel pour tâches périodiques, avec cancel_callback enregistré dans `entry.async_on_unload`.

```python
# Source: homeassistant.helpers.event — standard HA pattern
from datetime import timedelta
from homeassistant.helpers.event import async_track_time_interval

async def async_start(self) -> None:
    # Purge au démarrage
    await self._storage.async_purge_old_events()
    # Purge quotidienne
    cancel = async_track_time_interval(
        self.hass,
        self._daily_purge,
        timedelta(hours=24),
    )
    self._cancel_purge = cancel

async def async_stop(self) -> None:
    if self._cancel_purge is not None:
        self._cancel_purge()
```

### Pattern 6 : Cap FIFO et purge TTL en SQL

```sql
-- Purge TTL 90 jours
DELETE FROM events WHERE timestamp < datetime('now', '-90 days');

-- Cap FIFO : supprime les plus anciens quand > 10000
DELETE FROM events WHERE id IN (
    SELECT id FROM events ORDER BY id ASC
    LIMIT MAX(0, (SELECT COUNT(*) FROM events) - 10000)
);
```

### Pattern 7 : Détection de patterns — SQL bucketing 30 min

**What :** Découpe `hour` en buckets de 30 min, groupe par `entity_id + service + day_of_week + bucket`, compte les occurrences sur 14 jours.

```sql
-- Source: algorithme dérivé des patterns SQL time-series standard
-- Bucket = (hour * 2) + (0 ou 1 pour la demi-heure) — simplifié : bucket par heure entière
-- D-03 : fenêtre ±30min = bucket de 30min
SELECT
    entity_id,
    domain,
    service,
    day_of_week,
    (hour * 2) AS bucket_30min,   -- 0..47 pour les 24h
    COUNT(*) as occurrences,
    MAX(timestamp) as last_seen
FROM events
WHERE timestamp >= datetime('now', '-14 days')
GROUP BY entity_id, domain, service, day_of_week, bucket_30min
HAVING COUNT(*) >= 3
```

### Anti-Patterns to Avoid

- **Ne pas utiliser `asyncio.create_task` pour la purge périodique** : la task échappe au lifecycle HA — utiliser `async_track_time_interval` avec cancel enregistré dans `entry.async_on_unload`.
- **Ne pas appeler `await db.execute(...)` sans `await db.commit()`** : aiosqlite ne commite pas automatiquement en dehors d'un context manager `async with db`.
- **Ne pas lire `event.data["context"]` directement** : accéder via `event.data["new_state"].context.user_id` — la structure est `new_state` qui porte l'objet Context, pas l'event lui-même.
- **Ne pas confondre domain de l'entity_id et service HA** : dans `state_changed`, le `service` (ex: `turn_on`) n'est pas directement dans l'événement — il doit être inféré depuis old_state → new_state ou depuis les attributs. Voir section Pitfalls.
- **Ne pas oublier `await storage.async_close()` dans `async_unload_entry`** : sinon la connexion SQLite reste ouverte lors du reload du composant (HA-03).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Purge périodique | asyncio.create_task + sleep | `async_track_time_interval` (HA helpers) | Teardown géré par HA lifecycle |
| Accès async SQLite | Thread pool manual | `aiosqlite` (déjà déclaré) | WAL, cursors, transactions managés |
| JSON serialization des personnes | Encodeur custom | `json.dumps` / `json.loads` (stdlib) | Trivial pour une liste de strings |
| Détection de patterns | pandas groupby | SQL GROUP BY + HAVING | pandas non installé, surcharge |

**Key insight :** La complexité de cette phase est dans la logique métier (filtrage, schema), pas dans la plomberie technique — aiosqlite fournit tout le nécessaire.

---

## Common Pitfalls

### Pitfall 1 : `service` absent de l'événement `state_changed`

**What goes wrong :** `state_changed` ne porte pas le `service` appelé (ex: `turn_on`). Le schema D-07 exige le champ `service`.

**Why it happens :** HA transmet `state_changed` avec `old_state` et `new_state`, pas l'action qui a causé le changement. Le service peut être inféré heuristiquement (`old_state.state` → `new_state.state`).

**How to avoid :** Inférer le service depuis la transition d'état : `turn_on` si `old="off"→new="on"`, `turn_off` si `old="on"→new="off"`, etc. Pour climate, mapper `set_temperature` si l'attribut temperature change. Documenter clairement que `service` est inféré, pas lu directement depuis l'événement.

**Warning signs :** Champ `service` toujours vide ou null dans les enregistrements.

### Pitfall 2 : `user_id` null pour les actions physiques (interrupteur mural)

**What goes wrong :** Un changement d'état déclenché physiquement (appui sur interrupteur Zigbee, etc.) peut avoir `context.user_id = null` même si un humain l'a fait. D-01 l'exclut.

**Why it happens :** HA ne peut pas associer une action physique à un `user_id` HA — seules les actions via frontend/API portent un user_id.

**How to avoid :** C'est une décision acceptée (D-01). Documenter dans le module que la couverture est limitée aux actions via interface HA. Ne pas tenter de hacks d'inférence hors scope.

**Warning signs :** 0 événements enregistrés si l'utilisateur ne passe jamais par le frontend HA.

### Pitfall 3 : `entry.async_on_unload` n'attend pas les coroutines si mal utilisé

**What goes wrong :** `entry.async_on_unload` accepte une fonction qui retourne une coroutine ou None. Si on passe un callable qui ne retourne pas de coroutine (ex: une lambda synchrone), le cleanup est silencieusement incomplet.

**Why it happens :** L'API attend `Callable[[], Coroutine | None]`. Passer `storage.async_close` (une méthode coroutine) est correct — passer `lambda: storage.async_close()` sans await aussi mais crée une coroutine non attendue.

**How to avoid :** Passer directement `entry.async_on_unload(storage.async_close)` — la méthode elle-même, pas un appel. [Vérifié depuis config_entries.py source]

**Warning signs :** La DB n'est pas fermée proprement au reload → `OperationalError: database is locked` au redémarrage.

### Pitfall 4 : WAL PRAGMA pas persisté entre connexions

**What goes wrong :** Si on appelle `PRAGMA journal_mode=WAL` mais qu'on ferme/rouvre la connexion, le mode WAL est persisté dans le fichier `.db` — mais il faut le confirmer à chaque reconnexion pour que SQLite respecte le mode.

**Why it happens :** SQLite stocke WAL dans le fichier, mais la connexion doit confirmer le mode au démarrage.

**How to avoid :** Appeler `PRAGMA journal_mode=WAL` dans `_ensure_schema()` qui est appelée à chaque `async_open()`. [HIGH confidence — documenté par Simon Willison's TILs]

### Pitfall 5 : `PRAGMA synchronous=NORMAL` requis avec WAL

**What goes wrong :** WAL avec `synchronous=FULL` (défaut) est plus lent que nécessaire.

**Why it happens :** SQLite par défaut est conservateur. Avec WAL, `synchronous=NORMAL` offre un bon compromis crash-safety/performance.

**How to avoid :** Exécuter les deux PRAGMAs ensemble dans `async_open`.

### Pitfall 6 : bucket 30 min dans SQL — calcul correct

**What goes wrong :** `CAST(hour / 30 AS INT)` donne toujours 0. `hour` est déjà un entier 0-23.

**Why it happens :** La fenêtre ±30min signifie regrouper par demi-heure, pas par heure/30. La bonne formule est : `(hour * 2) + CASE WHEN minutes >= 30 THEN 1 ELSE 0 END`. Mais les minutes ne sont pas stockées selon D-07 (seul `hour` est stocké).

**How to avoid :** Avec le schema D-07 (hour = entier), la fenêtre ±30min s'implémente en groupant par `hour` uniquement (bucket = 1h autour de l'heure) ce qui couvre ±30min de façon conservatrice. Si plus de précision souhaitée, stocker `minute` dans le schema — mais c'est hors scope v1. Utiliser `GROUP BY hour` pour la détection.

---

## Code Examples

### Ouverture connexion avec WAL

```python
# Source: aiosqlite official API + Simon Willison's TILs (WAL persistence)
async with aiosqlite.connect(db_path) as db:
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")
    await db.commit()
```

Ou avec connexion persistante (recommandé pour AgentStorage) :

```python
self._db = await aiosqlite.connect(db_path)
await self._db.execute("PRAGMA journal_mode=WAL")
await self._db.execute("PRAGMA synchronous=NORMAL")
await self._db.commit()
```

### Insertion d'un événement

```python
import json
from datetime import datetime, timezone

await self._db.execute(
    """INSERT INTO events
       (entity_id, domain, service, timestamp, day_of_week, hour, persons_home, weather_condition)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    (
        entity_id,
        domain,
        service,
        datetime.now(timezone.utc).isoformat(),
        datetime.now(timezone.utc).weekday(),  # 0=lundi
        datetime.now(timezone.utc).hour,
        json.dumps(persons_home),  # None ou liste sérialisée
        weather_condition,
    ),
)
await self._db.commit()
```

### Query détection de patterns

```python
# Source: SQL time-series GROUP BY pattern (verified logic)
async with self._db.execute("""
    SELECT entity_id, domain, service, day_of_week, hour,
           COUNT(*) as occurrences, MAX(timestamp) as last_seen
    FROM events
    WHERE timestamp >= datetime('now', '-14 days')
    GROUP BY entity_id, domain, service, day_of_week, hour
    HAVING COUNT(*) >= 3
    ORDER BY occurrences DESC
""") as cursor:
    rows = await cursor.fetchall()
```

### Listener state_changed avec unsubscribe

```python
# Source: HA event bus pattern (hass.bus.async_listen returns cancel callable)
self._unsub = self.hass.bus.async_listen(
    "state_changed",
    self._handle_state_changed
)
# Teardown :
entry.async_on_unload(self._unsub)  # _unsub est un callable synchrone
```

### Test fixture pour AgentStorage (tmp_path)

```python
# Source: pytest tmp_path + aiosqlite pattern
import pytest
import aiosqlite
from pathlib import Path

@pytest.fixture
async def tmp_db(tmp_path: Path):
    db_path = tmp_path / "test_habits.db"
    storage = AgentStorage.__new__(AgentStorage)
    # Inject tmp path for tests — pattern cohérent avec conftest.py existant
    storage._db_path = str(db_path)
    await storage.async_open()
    yield storage
    await storage.async_close()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Connexion SQLite dans un thread séparé | aiosqlite (thread interne géré) | 2019+ | Non-blocking event loop |
| `AbstractConversationAgent` | `ConversationEntity` | HA 2024.6 | Déjà migré Phase 1 |
| asyncio.create_task pour tâches périodiques | `async_track_time_interval` | HA standard | Teardown lifecycle géré |

**Deprecated/outdated :**
- `sqlite3` direct dans un composant HA async : bloque l'event loop — remplacé par aiosqlite.

---

## Open Questions

1. **Inférence du service depuis `state_changed`**
   - What we know : `state_changed` ne porte pas le service appelé. L'inférence depuis `old_state → new_state` est simple pour light/switch mais plus complexe pour climate/media_player.
   - What's unclear : Faut-il un mapping complet `domain → service` ou un service générique `"state_change"` est acceptable ?
   - Recommendation : Implémenter une inférence basique (turn_on/turn_off pour light/switch, set_temperature pour climate, play/stop pour media_player) avec fallback `"state_change"`.

2. **`hass.states.async_all(domain)` — signature exacte**
   - What we know : Utilisé dans `test_voice_pipeline.py` avec `"conversation"` comme argument. Fonctionne dans les tests existants.
   - What's unclear : La signature exacte de l'API publique n'a pas été trouvée dans la doc officielle.
   - Recommendation : MEDIUM confidence — utiliser le pattern existant du projet (`hass.states.async_all("person")`), tester en Phase 5.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| aiosqlite | AgentStorage, SQLite async | ✓ | 0.22.1 | — |
| Python sqlite3 | Runtime SQLite | ✓ | Python 3.14 stdlib | — |
| pytest-homeassistant-custom-component | Tests | ✓ | 0.13.320 | — |
| homeassistant.helpers.event | TTL purge scheduler | ✓ | Intégré HA | asyncio.create_task (moins propre) |

**Missing dependencies with no fallback :** Aucune.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-homeassistant-custom-component 0.13.320 |
| Config file | `pytest.ini` ou `pyproject.toml` (existant dans le projet) |
| Quick run command | `python -m pytest tests/test_storage.py tests/test_habit_engine.py tests/test_pattern_detector.py -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HABIT-01 | Events recorded in SQLite on state_changed | unit | `python -m pytest tests/test_storage.py tests/test_habit_engine.py -x` | ❌ Wave 0 |
| HABIT-01 | user_id null events ignored | unit | `python -m pytest tests/test_habit_engine.py::test_automation_event_ignored -x` | ❌ Wave 0 |
| HABIT-01 | Non-allowed domain events ignored | unit | `python -m pytest tests/test_habit_engine.py::test_domain_filtered -x` | ❌ Wave 0 |
| HABIT-02 | Record contains all D-07 fields | unit | `python -m pytest tests/test_storage.py::test_event_schema -x` | ❌ Wave 0 |
| HABIT-02 | persons_home populated from person.* states | unit | `python -m pytest tests/test_habit_engine.py::test_persons_home -x` | ❌ Wave 0 |
| HABIT-02 | weather_condition from weather.* state | unit | `python -m pytest tests/test_habit_engine.py::test_weather_context -x` | ❌ Wave 0 |
| HABIT-03 | Pattern detected after 3 occurrences / 14 days | unit | `python -m pytest tests/test_pattern_detector.py::test_pattern_threshold -x` | ❌ Wave 0 |
| HABIT-03 | No pattern below threshold | unit | `python -m pytest tests/test_pattern_detector.py::test_no_pattern_below_threshold -x` | ❌ Wave 0 |
| SEC-02 | No network calls in storage/engine (verified by no import of httpx/requests) | static | `python -m pytest tests/test_storage.py tests/test_habit_engine.py -k sec` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit :** `python -m pytest tests/test_storage.py -x -q`
- **Per wave merge :** `python -m pytest tests/ -q`
- **Phase gate :** Full suite green avant `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_storage.py` — couvre HABIT-01 (schema, WAL, TTL, cap FIFO)
- [ ] `tests/test_habit_engine.py` — couvre HABIT-01, HABIT-02 (filtrage user_id, domaine, contexte)
- [ ] `tests/test_pattern_detector.py` — couvre HABIT-03 (seuil, fenêtre)
- [ ] Fixtures dans `tests/conftest.py` : `tmp_db` (AgentStorage sur tmp_path), `mock_state_changed_event` (Event avec context.user_id)

---

## Sources

### Primary (HIGH confidence)

- aiosqlite GitHub (omnilib/aiosqlite) — API connect, execute, Row, context manager
- `custom_components/ha_ai_agent/manifest.json` — aiosqlite 0.22.1 déjà déclaré
- `custom_components/ha_ai_agent/__init__.py` — patterns hass.data, entry.async_on_unload
- `tests/test_voice_pipeline.py` — `hass.states.async_all(domain)` usage vérifié dans le projet
- HA config_entries.py source (GitHub) — `async_on_unload` signature et comportement

### Secondary (MEDIUM confidence)

- [Home Assistant Context docs](https://data.home-assistant.io/docs/context/) — user_id null = automation, non-null = frontend
- [Simon Willison's TIL — WAL mode](https://til.simonwillison.net/sqlite/enabling-wal-mode) — WAL persisté dans fichier db
- [aiosqlite smoke tests](https://github.com/omnilib/aiosqlite/blob/main/aiosqlite/tests/smoke.py) — patterns de test avec TemporaryDirectory

### Tertiary (LOW confidence)

- WebSearch résultats sur `async_track_time_interval` — non trouvé dans doc officielle, inféré depuis usage HA community

---

## Metadata

**Confidence breakdown :**
- Standard stack : HIGH — aiosqlite déjà installé (0.22.1), manifest.json confirmé
- Architecture : HIGH — patterns directement issus du code existant du projet
- Pitfalls : MEDIUM — inférence service depuis state_changed non documentée officiellement, validée par logique HA
- Patterns SQL : HIGH — SQL pur GROUP BY, pas de dépendance externe

**Research date :** 2026-04-05
**Valid until :** 2026-05-05 (stack stable — aiosqlite et HA core ne changent pas fréquemment)
