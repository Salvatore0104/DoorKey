from __future__ import annotations

import voluptuous as vol
from aiohttp import ClientResponseError

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HR6107Api, validate_api
from .const import CONF_BASE_URL, CONF_TOKEN, DEFAULT_NAME, DOMAIN


class HR6107ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            base_url = user_input[CONF_BASE_URL].rstrip("/")
            api = HR6107Api(async_get_clientsession(self.hass), base_url, user_input.get(CONF_TOKEN, ""))
            try:
                state = await validate_api(api)
            except ClientResponseError as exc:
                errors["base"] = "invalid_auth" if exc.status == 401 else "cannot_connect"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"hr6107-{state.get('device_ip', '501')}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={CONF_BASE_URL: base_url, CONF_TOKEN: user_input.get(CONF_TOKEN, "")},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL, default="http://10.10.1.3:8088"): str,
                vol.Optional(CONF_TOKEN, default=""): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
