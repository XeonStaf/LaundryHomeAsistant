"""Sensor platform for Laundry integration."""
from __future__ import annotations
from homeassistant.helpers import config_validation as entity_platform
from homeassistant.helpers import selector
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
import voluptuous as vol
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event, Event
import logging
from .const import States, states_eng, DOMAIN, CYCLES_TO_CONFIRM_FINISHING
import datetime


_LOGGER = logging.getLogger("lopbop")

OPTION_FOR_RESET = (
    {
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=DOMAIN)
        ),
    },
)


def reset_machine(entity_id, call):
    entity_id.reset_machine()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Laundry config entry."""
    registry = er.async_get(hass)
    # Validate + resolve entity registry id to entity_id
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )
    name = config_entry.title
    unique_id = config_entry.entry_id
    new = laundrySensorEntity(hass, unique_id, name, entity_id)
    async_add_entities([new])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "reset_machine",
        OPTION_FOR_RESET,
        reset_machine,
    )


class laundrySensorEntity(SensorEntity):
    """laundry Sensor."""

    _attr_icon = "mdi:washing-machine"

    def __init__(self, hass, unique_id: str, name: str, wrapped_entity_id: str) -> None:
        """Initialize Laundry Sensor."""
        super().__init__()
        async_track_state_change_event(hass, wrapped_entity_id, self.update_handler)
        self.laundry_sensor = wrapped_entity_id
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_native_value = States.IDLE.value
        self._old_power = 0
        self._max_power = -1
        self._seconds_pass = 0

        self._attr_wash_started = datetime.datetime.now()
        self._attr_awerage_time_for_wash = -1

    async def update_handler(self, event: Event = None) -> None:
        if event is None:
            return
        now_power = float(event.data.get("new_state").state)
        new_state = self._define_state(now_power)

        if new_state != -1:
            self._attr_native_value = new_state
            await self.async_update_ha_state()

    @property
    def icon(self):
        status = self._attr_native_value
        icons_match = {
            States.IDLE.value: "mdi:washing-machine-off",
            States.RUNNING.value: "mdi:washing-machine",
            States.FINISHING.value: "mdi:washing-machine",
            States.CLEAN.value: "mdi:washing-machine-alert",
        }
        return icons_match[status]

    @property
    def state(self) -> str:
        return states_eng[self._attr_native_value]

    def _define_state(self, current_power):
        now_state = self._attr_native_value
        result = -1
        if current_power == 0:
            zeta = 0
        else:
            zeta = (self._old_power - current_power) / current_power

        if (
            now_state == States.IDLE.value or now_state == States.CLEAN.value
        ) and zeta > 0:
            self._max_power = max(self._max_power, current_power)
            self._attr_wash_started = datetime.datetime.now()
            result = States.RUNNING.value

        if now_state == States.RUNNING.value:
            self._max_power = max(self._max_power, current_power)

            if zeta > 1 and current_power < self._max_power / 2:
                self._seconds_pass += 1
                _LOGGER.error(self._seconds_pass)
            if (
                zeta > 1
                and self._seconds_pass > CYCLES_TO_CONFIRM_FINISHING
                and current_power < self._max_power / 2
            ):
                result = States.FINISHING.value
                self._seconds_pass = 0

        if current_power == 0 and (
            now_state == States.FINISHING.value or States.RUNNING.value
        ):
            spent_time = datetime.datetime.now() - self._attr_wash_started
            if self._attr_awerage_time_for_wash == -1:
                self._attr_awerage_time_for_wash = spent_time
                self._attr_awerage_time_for_wash = (
                    self._attr_awerage_time_for_wash + spent_time
                ) / 2
            result = States.CLEAN.value

        self._old_power = current_power
        return result

    @property
    def extra_state_attributes(self):
        if self._attr_wash_started == -1 or self._attr_awerage_time_for_wash == -1:
            wash_started = awerage = expected = "Gathering Info"
        else:
            wash_started = self._attr_wash_started
            awerage = self._attr_awerage_time_for_wash.seconds
            expected = self._attr_wash_started + self._attr_awerage_time_for_wash
        return {
            "wash_started": wash_started,
            "awerage_time_for_wash (sec)": awerage,
            "expected_end_time": expected,
        }

    def reset_machine(self):
        self._attr_native_value = States.IDLE.value
