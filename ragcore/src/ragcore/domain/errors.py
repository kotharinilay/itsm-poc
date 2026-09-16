"""Domain errors.

Errors and invalid state surface at the earliest point they can be detected, and no caught
error is silently swallowed (constitution Principle VIII).
"""

from __future__ import annotations


class DomainError(Exception):
    """Base for every error the domain raises. Never carries provider or transport detail."""


class TenantNotAdmittedError(DomainError):
    """The organisation is not in a state where work may proceed."""


class AuthorizationError(DomainError):
    """The principal holds no role the operation accepts."""


class TreatmentNotInCatalogueError(DomainError):
    """No catalogue entry exists for the proposed operation.

    A refusal, never a default. The absence of a treatment is not permission to proceed.
    """


class AuthorizationExpiredError(DomainError):
    """The execution validity window elapsed.

    Expiry MUST NOT be reported as an error to the user (spec FR-EXEC-001); this type exists so
    the execution path can distinguish it from a failure, not so it can be surfaced as one.
    """


class WorkAlreadyClaimedError(DomainError):
    """Another consumer holds the claim. At-least-once delivery makes this routine."""
