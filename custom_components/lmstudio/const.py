DOMAIN = "lmstudio"

CONF_URL = "url"
CONF_MODEL = "model"
CONF_PROMPT = "system_prompt"   # key stored in entry.data
CONF_IDLE_TIMEOUT = "idle_timeout"

DEFAULT_IDLE_TIMEOUT = 5
DEFAULT_PROMPT = "You are a helpful smart home assistant."

# OpenAI-compatible tool definitions sent to the LLM
HA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "turn_on",
            "description": "Turn on a Home Assistant entity",
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
            "description": "Turn off a Home Assistant entity",
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
            "description": "Call any Home Assistant service",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Service domain, e.g. light"},
                    "service": {"type": "string", "description": "Service name, e.g. turn_on"},
                    "data": {"type": "object", "description": "Service data payload"},
                },
                "required": ["domain", "service"],
            },
        },
    },
]