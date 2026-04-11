# LM Studio for Home Assistant

Local LLM integration for Home Assistant using a custom API backend.

## Features
- Assist integration (voice + chat)
- Model loading & switching
- Model downloading
- Conversation memory
- Smart home tool execution
- HACS installable

## Requirements
Your backend must implement:

- GET /api/v1/models
- POST /api/v1/chat
- POST /api/v1/models/load
- POST /api/v1/models/download
- GET /api/v1/models/download/status/:job_id

## Install
Add via HACS → Custom Repository → Integration

Then configure in UI.