from dataclasses import dataclass
from typing import Optional


@dataclass
class Finding:
    layer: str
    message: str
    step: Optional[int] = None

    def to_dict(self) -> dict:
        return {"layer": self.layer, "message": self.message, "step": self.step}


from . import budget, loop, provenance, recovery, schema, selection  # noqa: E402
from .final_state import check_state  # noqa: E402

CHECKERS = {
    "selection": selection.check,
    "schema": schema.check,
    "provenance": provenance.check,
    "loop": loop.check,
    "recovery": recovery.check,
    "budget": budget.check,
}

__all__ = ["Finding", "CHECKERS", "check_state"]
