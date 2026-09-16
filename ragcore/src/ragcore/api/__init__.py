"""HTTP transport only. Endpoints contain no business policy.

Three audiences, routed by path prefix, each with its own authorization model:

* ``/api/customer/v1`` — every caller is an ``end_user``, staff included.
* ``/api/staff/v1`` — set intersection over independent, non-hierarchical roles.
* ``/api/workload/v1`` — app-only, tenant resolved from the work item.

The audience comes from the route the Gateway matched, never from a request field
(spec FR-SURF-005), so a person cannot promote themselves by anything they supply.

:func:`~ragcore.api.app.create_app` assembles them. :mod:`~ragcore.api.deps` is the only module in
the codebase that calls ``Depends``.
"""
