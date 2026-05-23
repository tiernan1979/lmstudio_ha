"""Constants for the LM Studio integration."""

DOMAIN = "lmstudio"
CONF_URL = "url"
CONF_API_KEY = "api_key"
CONF_MODEL = "model"
PLATFORMS = ["conversation", "select"]

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
