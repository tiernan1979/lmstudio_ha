"""Constants for the LM Studio integration."""

DOMAIN = "lmstudio"
CONF_URL = "url"
CONF_API_KEY = "api_key"
CONF_MODEL = "model"
CONF_PROMPT = "prompt"
CONF_MAX_HISTORY = "max_history"
CONF_NUM_CTX = "num_ctx"
CONF_CONTEXT_LENGTH = "context_length"
CONF_FLASH_ATTENTION = "flash_attention"
CONF_IDLE_TIMEOUT = "idle_timeout"
CONF_LLM_HASS_API = "llm_hass_api"

DEFAULT_NAME = "LM Studio"
DEFAULT_CONVERSATION_NAME = "LM Studio Conversation"
DEFAULT_AI_TASK_NAME = "LM Studio AI Task"
DEFAULT_MAX_HISTORY = 20
DEFAULT_NUM_CTX = 4096
DEFAULT_CONTEXT_LENGTH = 4096
DEFAULT_FLASH_ATTENTION = False
DEFAULT_IDLE_TIMEOUT = 5
DEFAULT_TIMEOUT = 5.0

PLATFORMS = ["conversation", "ai_task"]
