"""Secret **references** resolve to values at the point of use. Values never travel anywhere else.

**Configuration holds a name; Key Vault holds the value.** A field called ``*_secret_name`` holds
the name of a secret, and a reviewer seeing a value in one knows at once that something is wrong.
That convention is only worth having if something enforces the other half — that a resolved value
cannot then leak into a log line, a trace attribute or an API document. This module is that other
half.

**:class:`SecretValue` is the mechanism, not a wrapper for tidiness.** Its ``__repr__`` and
``__str__`` redact, so the three ways a secret actually escapes all fail closed:

* ``logger.info("dsn=%s", secret)`` — formatting calls ``__str__`` and prints ``<redacted>``
* ``span.set_attribute("dsn", secret)`` — the exporter serialises via ``repr``, and sees only
  ``<redacted>``
* ``{"dsn": secret}`` in a response model — not JSON-serialisable, so it raises rather than ships

Reading the value requires :meth:`SecretValue.reveal`, which is one grep away from an auditor and
reads as a deliberate act at the call site. A plain ``str`` offers none of that: it is
indistinguishable from every other string in the process, and the first debug log gets it for free.

**Startup fails when a required reference cannot be resolved** (research R-019). A missing secret is
a deployment that does not start, which is where a configuration defect is cheapest — not a ``None``
three hours later on the one path nobody tested, and never a silent fallback to an empty string that
turns an authentication failure into a puzzling authorization one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

from ragcore.domain.errors import DomainError

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Iterable, Mapping

REDACTED: Final = "<redacted>"
"""What a secret renders as, everywhere except an explicit :meth:`SecretValue.reveal`."""


class SecretResolutionError(DomainError):
    """A required secret reference could not be resolved.

    Raised at startup and never caught to substitute a default. A process that cannot reach its
    secrets is a process that cannot do its job, and starting anyway converts a clear failure into a
    confusing one further downstream.

    **The message names the secret and the vault, and never the value** — including when the failure
    is that the value was empty.
    """

    def __init__(self, name: str, vault_uri: str, reason: str) -> None:
        super().__init__(
            f"required secret {name!r} could not be resolved from {vault_uri}: {reason}. "
            "Configuration holds secret names; the values live in Key Vault and are resolved "
            "through managed identity at startup."
        )
        self.name = name
        self.vault_uri = vault_uri


@dataclass(frozen=True, slots=True)
class SecretRef:
    """The **name** of a secret. Never its value.

    A distinct type rather than a bare ``str`` so that "this is a reference" survives being passed
    around: a function taking a ``SecretRef`` cannot be handed a resolved value by mistake, and one
    taking a ``str`` gives a reviewer nothing to check.
    """

    name: str

    def __post_init__(self) -> None:
        """Refuse an empty name at construction.

        Raises:
            ValueError: When the name is blank. An empty reference resolves to nothing and would
                otherwise surface as an empty secret, which reads like a vault problem rather than
                the configuration problem it is.
        """
        if not self.name or not self.name.strip():
            raise ValueError(
                "a secret reference needs a name; configuration holds names, not values"
            )

    def __str__(self) -> str:
        """The name. A reference is not sensitive — that is the entire point of using one."""
        return self.name


class SecretValue:
    """A resolved secret that refuses to render itself.

    **Not a convenience type.** Every accidental disclosure path in this platform goes through
    ``str``, ``repr`` or JSON serialisation, and all three are closed here. The only way to the
    underlying string is :meth:`reveal`, which is greppable and reads as a deliberate act.

    Slotted and without ``__eq__``: comparing secrets with ``==`` invites a timing-sensitive
    comparison at a call site that has no idea it is doing one, and an attribute dictionary is one
    more place a debugger or a serialiser can find the value.
    """

    __slots__ = ("_name", "_value")

    def __init__(self, name: str, value: str) -> None:
        self._name = name
        self._value = value

    @property
    def name(self) -> str:
        """The secret's name. Safe to log, and frequently the thing you actually wanted."""
        return self._name

    def reveal(self) -> str:
        """Return the secret itself.

        **The one accessor, and it is named to be noticed.** Call it as late as possible — ideally
        while handing the value to the client that needs it — so the plain string exists for the
        shortest time and in the fewest frames.
        """
        return self._value

    def __str__(self) -> str:
        """``<redacted>``. Closes ``logger.info("%s", secret)`` and every f-string."""
        return REDACTED

    def __repr__(self) -> str:
        """``<redacted>``. Closes ``repr``-based telemetry exporters and debugger displays."""
        return f"SecretValue(name={self._name!r}, value={REDACTED})"

    def __format__(self, format_spec: str) -> str:
        """``<redacted>``. Closes ``f"{secret:>20}"``, which bypasses ``__str__``."""
        del format_spec
        return REDACTED


@runtime_checkable
class SecretResolverPort(Protocol):
    """Resolution of a secret reference to its value.

    A port so that nothing outside infrastructure depends on Key Vault, and so a test can substitute
    a resolver without a vault, a network or a credential.
    """

    async def resolve(self, ref: SecretRef) -> SecretValue:
        """Resolve one reference.

        Raises:
            SecretResolutionError: When the secret is absent, empty or unreachable.
        """
        ...


class KeyVaultSecretResolver:
    """Resolves references from Azure Key Vault, through the shared managed identity.

    **The credential is not constructed here.** It comes from
    :func:`~ragcore.infrastructure.azure_credentials.azure_credential`, the process's single
    construction site — a resolver that built its own would be a second authentication path beside
    the first.

    Values are cached for the lifetime of the process. A secret is fetched once rather than on
    every use: the alternative is a network call on a hot path and a Key Vault throttle under load.
    Rotation therefore takes effect on restart; that is the accepted trade and it is stated here
    rather than discovered.
    """

    def __init__(self, vault_uri: str) -> None:
        """Bind the resolver to a vault.

        Args:
            vault_uri: The vault's URI. **Must be https** — a secret fetched over plaintext is a
                secret in transit to anybody watching.

        Raises:
            ValueError: When the URI is missing or not https.
        """
        if not vault_uri:
            raise ValueError("a Key Vault URI is required to resolve secret references")
        if not vault_uri.startswith("https://"):
            raise ValueError(
                f"the Key Vault URI must be https, got {vault_uri!r}. Secret material is not "
                "fetched over plaintext."
            )

        self._vault_uri = vault_uri
        self._cache: dict[str, SecretValue] = {}

    async def resolve(self, ref: SecretRef) -> SecretValue:
        """Resolve one reference, caching the result.

        Raises:
            SecretResolutionError: When the secret is absent, empty, or the vault is unreachable.
                **An empty secret is a failure, not a value**: a blank credential produces an
                authentication error somewhere unrelated, hours later, with nothing pointing here.
        """
        if ref.name in self._cache:
            return self._cache[ref.name]

        from azure.core.exceptions import AzureError
        from azure.keyvault.secrets.aio import SecretClient

        from ragcore.infrastructure.azure_credentials import azure_credential

        client = SecretClient(vault_url=self._vault_uri, credential=azure_credential())
        try:
            secret = await client.get_secret(ref.name)
        except AzureError as error:
            # The Azure exception is not chained into the message. It can carry request and response
            # detail, and this message reaches logs.
            raise SecretResolutionError(ref.name, self._vault_uri, type(error).__name__) from error
        finally:
            await client.close()

        if not secret.value:
            raise SecretResolutionError(ref.name, self._vault_uri, "the secret is empty")

        resolved = SecretValue(ref.name, secret.value)
        self._cache[ref.name] = resolved
        return resolved


async def resolve_required(
    resolver: SecretResolverPort, references: Iterable[SecretRef]
) -> Mapping[str, SecretValue]:
    """Resolve every required reference, or fail the process.

    Called once, from the application lifespan, **before the application begins serving**. Every
    reference is attempted rather than stopping at the first failure, so a deployment with three
    missing secrets reports three names in one cycle instead of three deployments.

    Args:
        resolver: The resolver to use.
        references: Every secret this process requires to function.

    Returns:
        The resolved values, keyed by name.

    Raises:
        SecretResolutionError: When any required reference cannot be resolved. The process does not
            start. There is deliberately no ``default`` parameter and no partial-success return: a
            caller able to proceed without a required secret would make "required" advisory.
    """
    resolved: dict[str, SecretValue] = {}
    failures: list[str] = []

    for ref in references:
        try:
            resolved[ref.name] = await resolver.resolve(ref)
        except SecretResolutionError as error:
            failures.append(f"{error.name} ({error!s})")

    if failures:
        raise SecretResolutionError(
            failures[0].split(" ", maxsplit=1)[0],
            getattr(resolver, "_vault_uri", "the configured vault"),
            f"{len(failures)} required secret(s) did not resolve: " + "; ".join(sorted(failures)),
        )

    return resolved
