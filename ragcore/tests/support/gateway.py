"""The gateway this test suite pretends to be.

**There is no test-only bypass of gateway provenance, and there must not be.** The suite simulates
APIM rather than disabling the check, because a bypass would mean the pipeline under test is not
the pipeline that ships — and the one control whose absence is invisible in production would be the
one control never exercised.

The values below are syntactically valid SHA-256 digests corresponding to no real certificate. They
are not secret material: a thumbprint is the hash of a *public* certificate, and the constitution's
no-credential-in-tests rule is about credentials, which this is not.
"""

from __future__ import annotations

from typing import Final

CERTIFICATE_HASH: Final = "1111111111111111111111111111111111111111111111111111111111111111"
"""The certificate hash this suite's requests present."""

UNKNOWN_CERTIFICATE_HASH: Final = "2222222222222222222222222222222222222222222222222222222222222222"
"""A syntactically valid hash belonging to some other gateway.

Used to assert that a well-formed certificate from the wrong holder is refused. The check must be an
allow-list, not a format check — the latter would accept any certificate at all.
"""

FORWARDED_CLIENT_CERT_HEADER: Final = "X-Forwarded-Client-Cert"


def forwarded_client_cert(certificate_hash: str = CERTIFICATE_HASH) -> str:
    """Format a hash as Container Apps ingress forwards it.

    Args:
        certificate_hash: The hash to present.

    Returns:
        The header value.
    """
    return f'Hash={certificate_hash};Subject="CN=synthia-gateway";URI='


def gateway_headers(certificate_hash: str = CERTIFICATE_HASH) -> dict[str, str]:
    """The headers a request arriving through APIM carries.

    Returns:
        A mapping suitable as a ``TestClient`` default-header set.
    """
    return {FORWARDED_CLIENT_CERT_HEADER: forwarded_client_cert(certificate_hash)}
