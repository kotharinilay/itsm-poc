"""The one Azure credential this process holds. **Constructed here and nowhere else.**

``DefaultAzureCredential`` resolves the managed identity in Container Apps and the developer's own
signed-in identity locally — the same code path either way, so there is no environment branch to get
wrong and no credential type that works only on a laptop.

**Zero standing secrets.** Nothing this process holds can be exfiltrated and replayed, because it
holds nothing: the credential mints short-lived tokens on demand against an identity the platform
assigns. That is the property Key Vault exists to give, and a client secret configured to *read* the
vault would hand it straight back.

**One instance, shared by every client.** A client that constructs its own is a second
authentication path beside the first — with no rule saying which is authoritative and, in practice,
only one of them reviewed. ``tests/security/test_azure_identity.py`` asserts this module is the sole
construction site, and the .NET side asserts the same of its own configuration root.

The import of ``azure.identity`` is **deliberately local** to :func:`azure_credential`. Importing it
at module scope pulls in the whole Azure identity stack for anything that merely wants the type or
the docstring, including tests that assert the rule without authenticating to anything.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from azure.core.credentials_async import AsyncTokenCredential


@lru_cache(maxsize=1)
def azure_credential() -> Any:  # noqa: ANN401 — the concrete type needs the SDK imported
    """Return the process-wide Azure credential.

    Cached, because the credential caches tokens internally: constructing a second one throws away
    that cache and re-authenticates on the next call, which on a managed identity endpoint under
    load is a self-inflicted throttle.

    Returns:
        The shared :class:`AsyncTokenCredential`. Every Azure SDK client in this process takes this
        object rather than building its own.
    """
    from azure.identity.aio import DefaultAzureCredential

    return DefaultAzureCredential()


async def close_azure_credential() -> None:
    """Release the shared credential's underlying transport.

    Called from the application lifespan on shutdown. The credential owns an HTTP session; a session
    nobody closes is a warning on every test run and a file-descriptor leak in a long-lived worker.

    Safe to call when no credential was ever constructed — a process that never reached Azure has
    nothing to release, and making the caller check would put that knowledge in the lifespan.
    """
    if azure_credential.cache_info().currsize == 0:
        return

    credential: AsyncTokenCredential = azure_credential()
    await credential.close()
    azure_credential.cache_clear()
