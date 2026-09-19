"""How this process reaches Service Bus. **Managed identity, and nothing else.**

There is deliberately no connection string, no shared access key and no SAS token in this module,
in configuration, or anywhere the namespace is named. ``build/policy/azure-identity.json`` lists
Service Bus as ``managedIdentity: required`` with ``Endpoint=sb://``, ``SharedAccessKey`` and
``SharedAccessSignature`` named as forbidden configuration, and
``ragcore/tests/security/test_azure_identity.py`` enforces that against this source.

**The namespace is a name, not a credential.** ``synthia.servicebus.windows.net`` identifies where
to connect and grants nothing; a connection string identifies where *and* authorizes, which is why
one can be committed by accident and the other cannot. A setting that holds a fully qualified name
has a failure mode — wrong namespace — that looks like a configuration error. A setting that holds
a key has a failure mode that looks like nothing at all.

**There is no local-development fallback here, and that is the design.** ``DefaultAzureCredential``
resolves a developer's own signed-in identity locally through the same code path it uses for a
managed identity in Container Apps, so there is no second branch to get wrong and no ``if
environment == "local"`` for a deployment to inherit by mistake. A developer without an Azure
sign-in gets an authentication failure naming the credential chain — the honest outcome — rather
than a key that works on a laptop and then needs removing before release.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ragcore.infrastructure.azure_credentials import azure_credential

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.config.settings import MessagingSettings


class MessagingNotConfiguredError(RuntimeError):
    """Raised when the namespace is absent.

    Fail closed and fail early. The alternative is a publisher that constructs cleanly and fails on
    the first trigger it is asked to send — which, for an outbox dispatcher, means the row is
    retried ten times and marked undispatchable, turning a missing setting into what looks like a
    transport outage.
    """


def require_namespace(settings: MessagingSettings) -> str:
    """The fully qualified Service Bus namespace.

    Args:
        settings: The messaging settings.

    Returns:
        The namespace, for example ``synthia.servicebus.windows.net``.

    Raises:
        MessagingNotConfiguredError: When no namespace is configured.
    """
    namespace = settings.namespace.strip()

    if not namespace:
        raise MessagingNotConfiguredError(
            "No Service Bus namespace is configured. Set SYNTHIA_BUS_NAMESPACE to the fully "
            "qualified namespace, for example 'synthia.servicebus.windows.net'. It is a name, not "
            "a credential: this platform authenticates to Service Bus by managed identity and "
            "accepts no connection string, shared access key or SAS token."
        )

    # A namespace that looks like a connection string is refused rather than parsed. Accepting it
    # "helpfully" is how a shared access key ends up in configuration and then in a pipeline log.
    lowered = namespace.lower()
    if "endpoint=" in lowered or "sharedaccesskey" in lowered or "sharedaccesssignature" in lowered:
        raise MessagingNotConfiguredError(
            "SYNTHIA_BUS_NAMESPACE looks like a connection string. This platform authenticates to "
            "Service Bus by managed identity; supply only the fully qualified namespace."
        )

    return namespace


def service_bus_client(settings: MessagingSettings) -> Any:  # Needs the SDK imported
    """Build the async Service Bus client, authenticated as this process's managed identity.

    The import is local for the same reason it is in
    :mod:`ragcore.infrastructure.azure_credentials`: importing the SDK at module scope would make
    every test that touches messaging pay for it, including the ones that never open a connection.

    Args:
        settings: The messaging settings.

    Returns:
        An ``azure.servicebus.aio.ServiceBusClient``. The caller owns its lifetime — it holds a
        connection, and one nobody closes is a leak that only appears under load.

    Raises:
        MessagingNotConfiguredError: When no namespace is configured.
    """
    from azure.servicebus.aio import ServiceBusClient

    return ServiceBusClient(
        fully_qualified_namespace=require_namespace(settings),
        credential=azure_credential(),
    )
