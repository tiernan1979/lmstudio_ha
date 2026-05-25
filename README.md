# LM Studio for Home Assistant

Integrate local large language models from [LM Studio](https://lmstudio.ai/) with Home Assistant. Chat with your LLM through the Home Assistant UI, voice assistants, or any conversation client — and have it query states, control devices, and call services in your smart home.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Platform](https://img.shields.io/badge/platform-Home%20Assistant-orange)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **Conversation Agents** — Full integration with the Home Assistant conversation platform. Chat via UI, Assist, or any conversation client with real-time streaming responses.
- **AI Tasks** — Generate structured data from natural language prompts using the AI Task platform (JSON schema enforcement, attachments).
- **Smart Home Tool Calling** — The LLM can automatically query entity states, call services, and control devices through built-in function calling. Multi-turn tool loops are handled transparently.
- **Model Management** — Automatic on-demand loading/unloading of models with configurable idle timeout to conserve server RAM.
- **Multi-Agent Support** — Configure multiple conversation agents and AI tasks against a single LM Studio server, each with independent model, settings, and behavior.
- **Built-in Utility Tools** — Common tools like `get_current_time`, `get_current_date`, and `get_live_context` are available to the LLM without requiring Home Assistant API access.
- **MCP Support via LM Studio** — LM Studio natively supports the Model Context Protocol (MCP). Configure MCP servers inside LM Studio — the integration automatically passes MCP tools through to the LLM.

---

## Requirements

- Home Assistant 2025.x or later (requires `conversation` and `ai_task` platforms)
- [LM Studio](https://lmstudio.ai/) running locally or remotely with the local HTTP server enabled (`localhost:1234` by default)
- At least one model loaded or available in LM Studio
- (Optional) [MCP servers](https://github.com/modelcontextprotocol) configured in LM Studio for extended tool access

---

## Installation

### Via HACS (Recommended)

1. Open **HACS** → **Integrations** → **Three dots (...)** → **Custom repositories**
2. Enter this repository URL and select category **Integration**
3. Install **LM Studio**
4. Restart Home Assistant

### Manual Installation

Copy the `custom_components/lmstudio` directory into your Home Assistant config:

```
<config>/custom_components/lmstudio/
```

Then restart Home Assistant.

---

## Configuration

All configuration is done through the Home Assistant UI — no YAML required.

Navigate to **Settings** → **Devices & services** → **Add Integration** → search for **"LM Studio"**.

### Server Connection (Main Entry)

| Option    | Required | Description                        |
|-----------|----------|------------------------------------|
| `URL`     | Yes      | LM Studio server address (e.g. `http://localhost:1234`) |
| `API Key` | No       | Optional API key for authentication |

### Conversation Agent (Sub-Entry)

After connecting to the server, add conversation agents or AI tasks as sub-entries:

| Option             | Type     | Default         | Description                                                    |
|--------------------|----------|-----------------|----------------------------------------------------------------|
| `Name`             | string   | —               | Display name for the agent                                     |
| `Model`            | dropdown | —               | LLM model to use (populated from server)                       |
| `Context Length`   | integer  | Server default  | Max tokens per request                                         |
| `Flash Attention`  | boolean  | Disabled        | Enable for faster inference on compatible GPUs                 |
| `Idle Timeout`     | integer  | 5 minutes       | Minutes before model unloads. Set to `0` for indefinite        |
| `Streaming`        | boolean  | Enabled         | Stream tokens back in real-time                                |
| `Max History`      | integer  | Unlimited       | Max conversation exchanges kept in context                     |
| `System Prompt`    | text     | Empty           | Custom instructions for how the LLM should behave              |
| `HA API Access`    | selector | Off             | `None`, `Read` (query state), or `Control` (call services)     |

### AI Task (Sub-Entry)

Same options as conversation agent, excluding **System Prompt** and **HA API Access**.

---

## Usage

### Chatting with a Conversation Agent

Once configured, you can interact with your agent in several ways:

1. **Home Assistant UI** — Use the chat panel or Assist interface
2. **Voice Assistants** — Pipe through any voice assistant that uses the conversation platform
3. **Services** — Call `conversation.process` with the agent's entity ID

```yaml
service: conversation.process
data:
  text: "What's the temperature in the living room?"
target:
  entity_id: conversation.lmstudio_agent
```

### AI Tasks for Structured Output

AI tasks generate structured data from natural language prompts. Use them via the `ai_task.run` service or through automations:

```yaml
service: ai_task.generate_data
data:
  prompt: "Create a weekly meal plan based on these ingredients: chicken, rice, broccoli"
target:
  entity_id: ai_task.lmstudio_meal_planner
```

### Tool Calling (Function Calling)

When **HA API Access** is set to `Read` or `Control`, the LLM can automatically:

- Query current states of entities (`llm_get_hass_states`)
- Call Home Assistant services (`llm_call_hass_services`)
- Control devices like lights, switches, etc. (`llm_control_hass_devices`)

The integration handles multi-turn tool loops internally — if the model needs to call tools, it gets results back and can make further decisions until its task is complete.

### Built-in Utility Tools

The following tools are always available to the LLM — no Home Assistant API access needed:

| Tool | Description |
|------|-------------|
| `get_current_time` | Returns the current date, time, and timezone |
| `get_current_date` | Returns today's date |
| `get_live_context` | Searches all Home Assistant entities in a given domain (e.g., `light`, `switch`, `sensor`). Use this to discover entity IDs and friendly names before controlling devices. |

### Entity Resolution / Fuzzy Matching

When controlling devices (e.g., "turn on the study light"), the LLM must know the exact entity ID. Use `get_live_context(domain="light")` to list all lights with their friendly names. This allows the model to find entities even when the entity ID doesn't match the spoken name (e.g., `light.study_desk` vs "study light").

---

## Architecture

```
Config Entry (LM Studio server URL + API key)
    |
    +-- Shared Runtime: {client, model_manager}
    |
    +-- Conversation Agent(s)          +-- AI Task(s)
            |                                |
    conversation.ConversationEntity   ai_task.AITaskEntity
            |                                |
    +-- LmStudioBaseLLMEntity (shared)        |
    +-- Model loading/unloading               |
    +-- Streaming responses                   |
    +-- Tool calling loop                     |
```

- **Single connection, multiple agents** — One LM Studio server connection serves all configured sub-entries
- **Lazy model loading** — Models load on-demand and unload after idle timeout to conserve RAM
- **Streaming support** — Real-time token streaming for both conversation and AI task responses
- **Automatic tool loops** — Multi-turn function calling handled transparently

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Cannot connect to LM Studio" | Verify the server URL is correct and LM Studio's local server is running. Check that port 1234 (or your configured port) is accessible. |
| Model not appearing in dropdown | Ensure the model is loaded or available in LM Studio. The integration fetches the list from `GET /v1/models`. |
| Slow responses | Increase context length, enable flash attention, or use a smaller/faster model. Check that your GPU has sufficient VRAM. |
| Tool calls not working | Verify **HA API Access** is set to at least `Read` in the agent's configuration. |
| Model hallucinating tools | The integration provides built-in tools (`get_current_time`, `get_current_date`, `get_live_context`) to match common hallucinated tool names. If the model still hallucinates other tools, add them via system prompt instructions. |

---

### Internet Search

LM Studio supports internet search through its built-in web search feature. Configure a web search provider (e.g., SearXNG, Bing, Google) in LM Studio's settings — the integration passes search tools through automatically to the LLM when available.

---

## Development

This integration uses the official `lmstudio` Python client library for OpenAI-compatible chat completions. The LM Studio server provides a standard OpenAI-compatible API at `/v1/`.

### Key Files

| File | Purpose |
|------|---------|
| `config_flow.py` | UI configuration wizard and sub-entry management |
| `conversation.py` | Conversation agent entity with streaming and tool calling |
| `ai_task.py` | AI task entity for structured data generation |
| `base.py` | Shared LLM entity logic (model management, message history) |
| `client.py` | LM Studio API client wrapper |
| `model_manager.py` | Background model loading/unloading with idle timeout |
| `entity.py` | Shared LLM entity logic (model management, message history, tool loop) |

---

## License

MIT © 2025
