DOMAIN = "lmstudio"

CONF_URL = "url"
CONF_MODEL = "model"
CONF_PROMPT = "system_prompt"
CONF_IDLE_TIMEOUT = "idle_timeout"

DEFAULT_IDLE_TIMEOUT = 5
DEFAULT_PROMPT = "You are a helpful smart home assistant."

HA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "turn_on",
            "description": "Turn on a Home Assistant entity such as a light, switch, or scene",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "The entity to turn on, e.g. light.kitchen",
                    }
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_off",
            "description": "Turn off a Home Assistant entity such as a light, switch, or scene",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "The entity to turn off, e.g. light.kitchen",
                    }
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_service",
            "description": "Call any Home Assistant service for advanced control",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Service domain, e.g. light, climate, media_player",
                    },
                    "service": {
                        "type": "string",
                        "description": "Service name, e.g. turn_on, set_temperature",
                    },
                    "data": {
                        "type": "object",
                        "description": "Optional service data payload",
                    },
                },
                "required": ["domain", "service"],
            },
        },
    },
]