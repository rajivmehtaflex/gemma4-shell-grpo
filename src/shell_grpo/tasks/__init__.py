"""Diagnostic task registry. Importing this package registers all tasks."""

from .base import FixtureCase, Task, WrongScript, all_tasks, get_task, register
from . import diagnostics, heldout, s_fileops, s_repair, s_text, variants  # noqa: F401

__all__ = [
    "FixtureCase",
    "Task",
    "WrongScript",
    "all_tasks",
    "get_task",
    "register",
]
