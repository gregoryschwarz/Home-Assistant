"""Constants for the HA Autonomous AI Agent integration."""
DOMAIN = "ha_ai_agent"
CONF_API_KEY = "api_key"
DEFAULT_MODEL = "claude-sonnet-4-6"

CONF_ALLOWED_DOMAINS = "allowed_domains"
DEFAULT_ALLOWED_DOMAINS: list[str] = ["light", "switch", "climate", "media_player"]

MAX_HISTORY_TURNS = 10

DB_FILENAME = "ha_ai_agent_habits.db"
HABIT_TTL_DAYS = 90
HABIT_EVENT_CAP = 10_000

SYSTEM_PROMPT = (
    "Tu es un assistant domotique Home Assistant. "
    "Tu reponds toujours en francais. "
    "Tu controles les appareils de la maison via le tool execute_ha_service. "
    "Domaines autorises : {allowed_domains}. "
    "Utilise UNIQUEMENT les entity_id presents dans la liste d'entites fournie par l'utilisateur. "
    "Ne jamais inventer un entity_id absent de cette liste. "
    "Si l'entite demandee n'existe pas dans la liste, reponds en texte libre sans appeler le tool. "
    "Si la commande est ambigue, demande une clarification en texte libre."
)

EXECUTE_HA_SERVICE_TOOL = {
    "name": "execute_ha_service",
    "description": (
        "Appelle un service Home Assistant pour controler une entite. "
        "Utilise ce tool uniquement quand la commande de l'utilisateur demande une action "
        "sur une entite domotique (lumiere, interrupteur, thermostat, lecteur media). "
        "Ne jamais inventer un entity_id absent de la liste fournie. "
        "Si l'entite demandee n'existe pas dans la liste, reponds en texte libre sans appeler ce tool."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domaine HA de l'entite (ex: light, switch, climate, media_player).",
            },
            "service": {
                "type": "string",
                "description": "Service HA a appeler (ex: turn_on, turn_off, set_temperature).",
            },
            "entity_id": {
                "type": "string",
                "description": "L'identifiant exact de l'entite tel que fourni dans la liste.",
            },
            "service_data": {
                "type": "object",
                "description": "Parametres additionnels du service. Omettre si non necessaire.",
            },
        },
        "required": ["domain", "service", "entity_id"],
    },
}
