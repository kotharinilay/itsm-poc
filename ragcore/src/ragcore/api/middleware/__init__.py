"""Transport-level concerns, in the order they wrap a request.

1. :class:`~ragcore.api.middleware.correlation.CorrelationIdMiddleware` — outermost, so even a
   request the next layer refuses is correlatable and its refusal echoes an identifier.
2. :class:`~ragcore.api.middleware.identity.IdentityHeaderMiddleware` — rejects self-asserted
   authority before routing, so no endpoint ever sees such a request.
3. :mod:`~ragcore.api.middleware.problems` — exception handlers giving every failure one shape.

None of them makes an authorization decision. They screen, bind and reshape; the decisions live
in application and domain policy.
"""
