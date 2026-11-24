"""PyQt6 typing glue.

PyQt6's stub for `pyqtSignal` marks `arguments=` as required, though PyQt itself
gives it a default, so every plain `pyqtSignal(int)` fails type-checking. `Signal`
is the very same object at runtime; only the type checker sees a corrected
signature, so signals keep their bound-signal typing everywhere they are used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import pyqtSignal

if TYPE_CHECKING:

    def Signal(*types: Any, name: str = ...) -> pyqtSignal: ...

else:
    Signal = pyqtSignal

__all__ = ["Signal"]
