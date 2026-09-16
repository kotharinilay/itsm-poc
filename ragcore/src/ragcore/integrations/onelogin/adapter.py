"""OneLogin — a **third-party target system**, reached as an MCP server (ADR-0005).

Not an identity provider. Enterprise identity is Entra, derived once at the gateway, and a second
source of human identity would reopen the identity model (constitution Principle I). OneLogin is a
system an incident may require reading details from or performing an operation against, and it is
the first of an open set rather than a special case.

**There is almost nothing in this module, and that is the evidence ADR-0005 wanted.** Adding a
third-party target system requires registering its capabilities and their governance treatment, and
MUST NOT require a new authorization mechanism, a new approval path, or an exception to any existing
rule (spec FR-EXT-010). If this file needed a bespoke client, a bespoke credential arrangement or a
bespoke governance hook, that claim would be false. It needs a name.

Capabilities become callable through the catalogue and the organisation's entitlement, exactly as a
native one does. Discovery here confers nothing (spec FR-EXT-014).
"""

from __future__ import annotations

from typing import Final

SYSTEM: Final = "onelogin"
"""The platform's name for this system.

It is three things at once and deliberately one string: the key under which the organisation's
credential reference is stored in ``tenant_entitlement``, the key naming its MCP endpoint in
configuration, and the prefix of its catalogue identifiers. Three separate names would be three
places for a mismatch to hide, and the mismatch presents as "entitled but nothing works".
"""

CATALOGUE_PREFIX: Final = f"{SYSTEM}."
"""What a catalogue identifier for this system starts with, for example ``onelogin.user.read``.

:meth:`~ragcore.integrations.mcp.client.McpToolClient.invoke` routes on this prefix, which is why
it is stated here rather than assembled at each call site.
"""
