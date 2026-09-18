"""RagCore's outbound transport and boundary validation. **Not connectors.**

This package holds the two things that survived the connector removal (T296, ADR-0007), and the
rename is the point. They used to live under ``ragcore.integrations``, and that name had become a
lie: the connectors moved to the Integrations Service, and what was left was the shared HTTP path
and the rule that provider output is checked before it is believed.

**What legitimately remains outbound in RagCore is a short and closed list**, and every item is a
*platform* destination rather than a customer system:

* the AI Gateway (:mod:`ragcore.model`), because reasoning is RagCore's;
* Azure AI Search (:mod:`ragcore.retrieval.search`), because the derived index is RagCore's;
* the Integrations Service itself (:mod:`ragcore.platform_clients.integrations`), through APIM.

**There is no connector here and none may be added.**
``ragcore/tests/architecture/test_no_connector_in_ragcore.py`` asserts it, and
``build/scripts/check-boundaries.sh`` asserts it again at build time — twice, because an absence
assertion passes equally where the path exists and simply has no caller yet.
"""
