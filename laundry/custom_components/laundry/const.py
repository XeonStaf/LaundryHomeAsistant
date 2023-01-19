"""Constants for the laundry integration."""

from enum import Enum

DOMAIN = "laundry"
CYCLES_TO_CONFIRM_FINISHING = 50


class States(Enum):
    IDLE = 0
    RUNNING = 1
    FINISHING = 2
    CLEAN = 3


states_eng = {0: "IDLE", 1: "Running", 2: "Finishing", 3: "Clean"}
