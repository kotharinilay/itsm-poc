# Runbook — rotate the gateway client certificate

**The order is the control.** Widen the allow-list, *then* switch the certificate. Performing these
steps in the other order is a total outage of every audience on **all three deployables**, with no
deployment and no code change to point at.

**Three backends now share one certificate** (ADR-0007): RagCore, the Integrations Service and the
monolith. That widens what this procedure can break rather than changing how it works — and it adds
a failure mode worth naming up front. Health probes are exempt from gateway provenance, so a backend
you forget to widen **stays green while serving nothing**. Its readiness endpoint answers; every real
request gets a 403.

Read that sentence before reading anything else on this page. Everything below is an elaboration of
it.

---

## What this certificate does

APIM presents it on every backend connection. Container Apps ingress validates it and republishes
its SHA-256 hash as `X-Forwarded-Client-Cert`. Both backends compare that hash against a configured
allow-list, and refuse any request whose hash is not in it.

That check is what lets the backends treat the closed `X-Idp-*` contract as evidence rather than
input — see `build/policy/edge-trust.json` and `ragcore/src/ragcore/api/middleware/provenance.py`.
While the certificate is mismatched, **every** application request is refused with `403`. Health
probes keep passing, because they are exempt, so the container apps stay green and in rotation
while serving nothing.

## Why rotation is manual here

Azure will sync a Key Vault certificate into APIM automatically, within about four hours of it
changing. We have deliberately turned that off, by pinning a version in the Key Vault certificate
identifier.

This is the one place where the safer-looking Azure default is the dangerous option:

- The backends pin the **leaf** certificate hash.
- Automatic sync changes the leaf, at a time Azure chooses.
- Nothing in Azure updates the backend allow-list to match.

So an ordinary renewal in the vault would propagate on its own schedule and take production down
unattended, most likely at whatever hour the four-hour window happened to land on. A reviewed
release is slower and cannot do that.

**The cost of this choice** is that nothing renews the certificate for us any more. That is why
expiry monitoring is not optional. The alert is what makes this strategy safe to have chosen.

## What will actually tell you

Provisioned in `build/infra/monitoring/gateway-certificate-expiry.json`.

| When | Signal | Reaches you by |
|---|---|---|
| 45 days out | Key Vault certificate lifetime action | Email to the certificate contacts |
| **30 days out** | `CertificateNearExpiry` → Azure Monitor **Sev2** | **Pages the on-call group** |
| A new version appears | `CertificateNewVersionCreated` → Sev3 | Informational — a rotation has *started* |
| Expired | `CertificateExpired` → **Sev0** | Pages; the platform is already down |

**Treat the 30-day page as the deadline, not the 45-day email.** Azure fixes the certificate
near-expiry event at 30 days and offers no setting for it — only the *key* near-expiry event is
configurable. So 45 days is the earliest we can be *told*, over the weaker channel, and 30 days is
the earliest we can be *woken*. One holiday period consumes the difference.

The Sev3 "new version" alert is not noise. Because APIM is pinned to a version, a new certificate
version changes nothing on its own — which means a half-finished rotation is otherwise invisible:
the new certificate exists, it looks like the job was done, and the allow-list was never widened.
That alert is what keeps the gap between step 2 and step 5 below visible while it is still open.

---

## Rotation

### 1. Issue the new certificate into Key Vault

Add a new **version** of the existing certificate. Do not create a new certificate object — the
APIM certificate entity points at the certificate, and reusing it keeps step 3 a one-line change.

Record the new version's SHA-256 thumbprint as lowercase hex, no colons:

```bash
az keyvault certificate show \
  --vault-name "$VAULT" --name synthia-gateway-client \
  --query "x509ThumbprintHex" -o tsv | tr '[:upper:]' '[:lower:]'
```

> The backends fold case, quotes and colons before comparing, so a value pasted from a certificate
> viewer will still match. Startup validation rejects anything that is not 64 hex characters, so a
> truncated paste fails the deployment rather than the requests.

### 2. Widen the allow-list — **both** deployables, before anything else

Append the new thumbprint to the existing value, comma-separated. Keep the outgoing one.

| Deployable | Setting |
|---|---|
| .NET monolith | `EdgeTrust__GatewayCertificateThumbprints` |
| RagCore | `SYNTHIA_EDGE_GATEWAY_CERTIFICATE_THUMBPRINTS` |

```
<outgoing-thumbprint>,<incoming-thumbprint>
```

Deploy both. Wait for every replica to be running the new revision.

**Do not proceed until this is true of all three deployables.** Both certificates are now accepted
on every backend, which is the whole point of the overlap: there is no instant in this procedure at
which neither is.

Check the Integrations Service explicitly rather than inferring it from the other two. It was the
last backend added, it is the one a reader of an older copy of this runbook would omit, and — because
its probes are provenance-exempt — omitting it produces a healthy-looking service that refuses every
call RagCore makes to it.

### 3. Switch the certificate in APIM

Point the APIM certificate entity at the new Key Vault version — that is, update the versioned
identifier it holds.

The APIM policy references the certificate by `certificate-id`, not by thumbprint, so the policy
itself does not change. **This matters:** a policy identifying a Key Vault certificate by thumbprint
silently stops resolving it after rotation and quietly stops attaching a client certificate at all.
`check-edge-path.sh` fails the build if that spelling reappears.

### 4. Confirm

- Application requests succeed through Front Door on all three audiences.
- No `403` with problem type `gateway-provenance-required` in backend logs.
- On the .NET side, no event `1104` (`Refused a request to {Path} that could not prove gateway
  provenance`).

Give it long enough to cover a full replica cycle before deciding it worked.

### 5. Narrow the allow-list

Remove the outgoing thumbprint from both settings and deploy.

Do not skip this. An allow-list that accumulates retired certificates is one where a stolen old key
still opens the door, and the whole control is an allow-list precisely so that removal means
something.

---

## If it goes wrong

**Symptom: every application request returns `403`, health probes are fine, no deployment went out.**

That is this certificate, and almost certainly step 3 having happened without step 2.

**Recovery:** add the *currently presented* certificate's thumbprint to both allow-lists and deploy.
That is a forward fix and is usually faster than reverting APIM, because the allow-list is an
environment variable and the APIM certificate entity is not.

Rolling back APIM to the previous Key Vault version also works if the old certificate has not
expired. If it *has* expired, the allow-list is the only way out — which is another reason the
45-day alert exists.

**Symptom: `403` on every request, and the APIM policy was recently edited.**

Check that `<authentication-certificate>` still uses `certificate-id`. If somebody changed it to
`thumbprint`, APIM is silently sending no client certificate at all and the guard would have caught
it in CI — so this means the change reached the gateway without going through the pipeline.

---

## Related

- `build/policy/edge-trust.json` — the shared registry both stacks enforce
- `build/infra/apim/global.inbound.xml` — where the certificate is attached
- `build/infra/monitoring/gateway-certificate-expiry.json` — the alerting described above
- `build/policy/azure-identity.json` — the named exemption for this certificate, with its review date
- `build/scripts/check-edge-path.sh` — the guard, proven to fail by `verify-edge-guard.sh`
- `docs/adr/` — ADR-002, Front Door + WAF as the public edge, APIM as the trust boundary
