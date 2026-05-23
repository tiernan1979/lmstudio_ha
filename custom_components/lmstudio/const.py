"""Constants for the LM Studio integration."""

DOMAIN = "lmstudio"
CONF_URL = "url"
CONF_API_KEY = "api_key"
CONF_MODEL = "model"
CONF_PROMPT = "system_prompt"
CONF_IDLE_TIMEOUT = "idle_timeout"
CONF_USE_TOOLS = "use_tools"
CONF_THINKING = "thinking"

DEFAULT_PROMPT = "You are a helpful smart home assistant."
DEFAULT_IDLE_TIMEOUT = 300
DEFAULT_USE_TOOLS = True
DEFAULT_THINKING = False

PLATFORMS = ["select"]

HA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_state",
            "description": "Get the current state of a Home Assistant entity",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Comma-separated list of entity IDs",
                    }
                },
                "required": ["entity_id"],
            },
        },
    },
]
