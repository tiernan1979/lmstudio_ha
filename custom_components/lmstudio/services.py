async def async_setup_services(hass):
    client = hass.data["lmstudio"]["client"]

    async def list_models(call):
        models = await client.list_models()
        hass.states.async_set("lmstudio.models", str(models))

    async def load_model(call):
        model = call.data["model"]
        await client.load_model(model)

        hass.data["lmstudio"]["selected_model"] = model
        hass.data["lmstudio"]["loaded_model"] = model

    async def download_model(call):
        await client.download_model(call.data["model"])

    hass.services.async_register("lmstudio", "list_models", list_models)
    hass.services.async_register("lmstudio", "load_model", load_model)
    hass.services.async_register("lmstudio", "download_model", download_model)