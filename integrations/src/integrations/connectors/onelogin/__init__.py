"""OneLogin — a **third-party target system**, reached as an MCP server (ADR-0005).

Relocated from RagCore by T290; behaviour unchanged from T132.

Not an identity provider. Enterprise identity is Entra, derived once at the gateway, and a second
source of human identity would reopen the identity model (constitution Principle I). OneLogin is a
system an incident may require reading details from or performing an operation against, and it is
the first of an open set rather than a special case.

**There is almost nothing in this module, and that is the evidence ADR-0005 wanted.** Adding a
third-party target system requires registering its capabilities and their governance treatment,
and MUST NOT require a new authorization mechanism, a new approval path, or an exception to any
existing rule (spec `FR-EXT-010`). If this file needed a bespoke client, a bespoke credential
arrangement or a bespoke governance hook, that claim would be false. It needs a name.

**The move to this service did not change that, which is the second piece of evidence.** Separating
the Integrations Service cost this module nothing — the name is the same, the mechanism is the same,
and the capabilities become callable through the catalogue and the organisation's entitlement
exactly as before. Discovery here confers nothing (spec `FR-EXT-014`).
"""

from __future__ import annotations

from typing import Final

__all__ = ["CATALOGUE_PREFIX", "SYSTEM"]

SYSTEM: Final = "onelogin"
"""The platform's name for this system.

It is three things at once and deliberately one string: the key under which the organisation's
credential reference is stored, the key naming its MCP endpoint in the connector registry, and the
prefix of its catalogue identifiers. Three separate names would be three places for a mismatch to
hide, and the mismatch presents as "entitled but nothing works".
"""

CATALOGUE_PREFIX: Final = f"{SYSTEM}."
"""What a catalogue identifier for this system starts with, for example ``onelogin.user.read``.

Stated here rather than assembled at each call site, for the reason above.
"""
