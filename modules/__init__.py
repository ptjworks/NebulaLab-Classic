"""Nebula Lab Classic module package.

Keep package import lightweight. Importing ``modules`` itself must not eagerly
import Streamlit or optional AI dependencies.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY_EXPORTS = {
    "ChartBuilder": ("modules.plotting", "ChartBuilder"),
    "DataAnalyzer": ("modules.data_loader", "DataAnalyzer"),
    "DataLoader": ("modules.data_loader", "DataLoader"),
    "DataTools": ("modules.data_tools", "DataTools"),
    "FileAnalysisResult": ("modules.data_loader", "FileAnalysisResult"),
    "OriginBridge": ("modules.origin_bridge", "OriginBridge"),
    "apply_smoothing": ("modules.data_tools", "apply_smoothing"),
    "estimate_tokens": ("modules.utils", "estimate_tokens"),
    "get_data_summary": ("modules.data_tools", "get_data_summary"),
    "get_numeric_columns": ("modules.data_tools", "get_numeric_columns"),
    "init_session_state": ("modules.state_manager", "init_session_state"),
    "load_chat_sessions": ("modules.utils", "load_chat_sessions"),
    "load_config": ("modules.utils", "load_config"),
    "load_data": ("modules.data_loader", "load_data"),
    "save_chat_sessions": ("modules.utils", "save_chat_sessions"),
    "save_config": ("modules.utils", "save_config"),
}

__all__ = sorted(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'modules' has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
