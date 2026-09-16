"""Duo — a **third-party target system**, reached as an MCP server (ADR-0005).

Not a verification step and not part of the governance path. Placing it there would make a
third-party system a participant in whether an operation may proceed, and authority in this platform
comes from the catalogue and from recorded human decisions — never from an external system
(spec FR-EXT-006).

Like :mod:`ragcore.integrations.onelogin.adapter`, this module is almost empty, and the emptiness is
the point: a new target system costs a name, a catalogue registration and an entitlement, not a new
authorization mechanism (spec FR-EXT-010).
"""

from __future__ import annotations

from typing import Final

SYSTEM: Final = "duo"
"""The platform's name for this system — credential key, endpoint key and catalogue prefix."""

CATALOGUE_PREFIX: Final = f"{SYSTEM}."
"""What a catalogue identifier for this system starts with, for example ``duo.device.read``."""
