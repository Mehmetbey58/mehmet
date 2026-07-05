"""FSM states used when a command is invoked without its required
argument, so the bot can prompt for it instead of just failing."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AccountStates(StatesGroup):
    waiting_for_add_username = State()
    waiting_for_remove_username = State()
    waiting_for_profile_username = State()
