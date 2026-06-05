## Preamble

```
SEP: To Be Assigned
Title: Contract Verification Registry API
Author: Nando Vieira <@fnando>
Status: Draft
Created: 2026-06-04
Updated: 2026-06-04
Version: 0.1.0
Discussion: https://github.com/orgs/stellar/discussions/1945
```

## Simple Summary

A read-only HTTP API for asking a verification service whether a smart
contract's wasm has been reproduced from its source, and for reading the build
and source metadata behind each result. A client looks a wasm up by its wasm
hash and receives the verifications one or more verifiers have recorded for it,
each described with the
[SEP-58](sep-0058.md)
vocabulary verbatim.

## Dependencies

- [SEP-58](sep-0058.md):
  Contract Build Reproducibility for Verification. Defines the build
  environment and source identification vocabulary (`bldimg`, `bldopt`,
  `source_repo`, `source_rev`, `tarball_url`, `tarball_sha256`) that this API
  reports. This SEP is a transport for SEP-58 results; it adds no vocabulary of
  its own.
- [SEP-46](sep-0046.md):
  Contract Meta (informative). One of the venues a service may read SEP-58
  fields from.

## Motivation

When a wasm is uploaded to a network, the on-chain artifact is opaque bytes.
[SEP-58](sep-0058.md)
defines the vocabulary needed to reproduce those bytes from source, and
anticipates "the creation of verification registries" and off-chain
"verification services" that hold this metadata, but it deliberately does not
say how a client talks to such a service.

Without a shared contract, every block explorer, wallet, and tool that wants to
display "verified" invents its own request and response shape, and a result
produced by one service cannot be consumed by a client built for another. This
SEP defines a small, interoperable HTTP API so that any client can query any
conformant verification service the same way and parse the answer the same way.

The API is intentionally read-only: clients ask questions, they do not submit
work. A service that has not yet looked at a wasm MAY still accept the query
and enqueue the verification, answering `202 Accepted` so the client knows to
retry later.

## Abstract

This SEP defines:

1. One endpoint, `GET /wasms/:wasm_hash.json`, that returns the verifications a
   service holds for a wasm as a single status object, or `202 Accepted` when
   the service has enqueued verification and the client should retry later.
1. A status object keyed on the wasm hash that carries one or more
   `source_code_verifications`, each reusing the SEP-58 vocabulary and a small
   set of status values (`verified`, `mismatched`, `unverified`).
1. Common conventions (HTTPS, optional CORS) and a coded error body shape.

## Roles

The endpoint and status object support these roles:

- **Verifier.** A service that performs rebuilds itself and publishes its
  results directly through this API. Each response carries a single entry in
  `source_code_verifications` — its own.
- **Aggregator.** A service that does not verify anything itself; it queries
  several independent verifiers (each implementing this API), combines their
  responses, and returns them as multiple entries in
  `source_code_verifications`, one per verifier. A consumer then sees the
  agreement and disagreement across verifiers in a single request, without
  having to know or call each verifier directly.
- **Consumer.** A client — block explorer, wallet, or tool — that reads results
  to display them. It resolves a contract address to its wasm hash (e.g. via
  RPC) and queries a verifier or aggregator for that hash.

Because a verifier and an aggregator produce the same shape — a non-empty array
of verifier-attributed results — a consumer written for one works with the
other, and an aggregator can itself be aggregated.

## Specification

### Base path

The base path at which a service exposes these endpoints is configurable and is
deployment-specific. It MAY be a bare origin (e.g.
`https://verify.example.com`) or include a path prefix (e.g.
`https://example.com/stellar`). All paths in this document are written absolute
relative to that configured base — e.g. `/wasms/:wasm_hash.json` — and are appended
to it. For a base of `https://example.com/stellar`, the endpoint resolves to
`https://example.com/stellar/wasms/:wasm_hash.json`. A service publishes its base
path out of band; this SEP does not define a discovery mechanism for it.

### HTTPS Only

All endpoints MUST be served over HTTPS. Clients MUST refuse to send or accept
verification data over plain HTTP.

### Cross-Origin Headers

CORS support is not required, but is recommended. A service intended for
browser-based clients SHOULD set the following on all responses, including
errors:

```
Access-Control-Allow-Origin: *
```

Whether to add CORS headers is entirely up to the service; a service MAY omit
them — for example, to avoid being called directly by large browser fleets — in
which case it is reachable only by non-browser clients such as backends and
CLIs. A consumer therefore cannot assume CORS is present and should expect some
services to be backend-only. If a service supports browsers and also requires
an `Authorization` header, it SHOULD answer the CORS preflight (`OPTIONS`),
since that header is not CORS-safelisted. For the full set of CORS rules and
their caveats, see
[MDN's CORS guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS).

### Authentication and Rate Limiting

This SEP neither requires nor prescribes authentication or rate limiting; both
are left to the service. A public registry MAY leave the API open, while
another MAY gate access or throttle clients. Whatever a service chooses, it
SHOULD signal the outcome with conventional HTTP status codes so clients can
react uniformly:

- `401 Unauthorized` — credentials are missing or invalid.
- `403 Forbidden` — the client is authenticated but not permitted.
- `429 Too Many Requests` — the client has been rate limited. The service MAY
  include a `Retry-After` header indicating when it may retry.

Each of these statuses carries a single meaning, so the HTTP status is the
authoritative signal; this SEP does not define an `error` code for them.
Because they are also commonly enforced by infrastructure in front of the
service (a proxy, gateway, or CDN), their response body is not guaranteed to be
the JSON [error](#errors) body. Clients SHOULD branch on the HTTP status for
these cases.

### API Endpoints

- [`GET /wasms/:wasm_hash.json`](#get-wasmswasm_hashjson)

#### `GET /wasms/:wasm_hash.json`

Returns the verifications a service holds for a single wasm.

A wasm hash is the stable, content-addressed identifier for a contract's code:
the same bytes hash the same on every network, and the hash never changes. A
contract _address_ is not stable — which wasm it points to can change over
time, and even within a ledger — so this API is keyed on the wasm hash, not the
contract address. A client that starts from a contract address resolves it to
the current wasm hash itself (e.g. via RPC) before calling this endpoint.

The path carries a `.json` extension so that responses can be served as plain
files — for example from a git repository, an object store such as S3, or a CDN
— not only by a dynamic application. A static host always returns `200`, so it
cannot express the `202 Accepted` enqueued state; serving precomputed results
statically necessarily presents them as settled. Since `202` and on-demand
enqueue are optional, this is an acceptable trade-off.

##### Request

```
GET /wasms/:wasm_hash.json
```

Path parameters:

| Name   | Type   | Description                                                                                          |
| ------ | ------ | ---------------------------------------------------------------------------------------------------- |
| `wasm_hash` | string | Lowercase hex SHA-256 of the wasm to look up (64 hex characters). The path appends a `.json` suffix. |

Query parameters:

| Name                 | Type   | Description                                                                                                                                                                                                                                                                                                  |
| -------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `network_passphrase` | string | (optional) A hint naming the network the client cares about, as its passphrase. Wasm hashes are network-independent, so this does not change the result; a service MAY use it for context (e.g. to scope auxiliary on-chain lookups) and MAY ignore it. A service MUST NOT reject a request for omitting it. |

Example:

```
GET /wasms/cb2fc3a1b4d5e6f7081928374655647382910abcdef0123456789abcdef01234.json
```

##### Response

Responses are content type `application/json`.

The status code communicates whether a result is available:

| Status Code       | Name        | Reason                                                                                                                                                                                                                                                                                             |
| ----------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `200 OK`          | OK          | The service holds a settled result for this wasm (each verification is a final `verified`, `mismatched`, or settled `unverified`). The body is the status object.                                                                                                                                                                                                |
| `202 Accepted`    | Accepted    | The service has no completed verification yet but has accepted the wasm and enqueued one (or one is in progress). The body is the status object whose `source_code_verifications` entries are `unverified` and omit `processed_at`. The client should retry after a sensible interval (see below). |
| `400 Bad Request` | Bad Request | `wasm_hash` is not a valid lowercase hex SHA-256.                                                                                                                                                                                                                                                  |
| `404 Not Found`   | Not Found   | The service has no verification for this wasm and will not produce one (it does not perform on-demand verification, or declines this wasm).                                                                                                                                                        |

After a `202`, a client should wait a sensible interval (on the order of
minutes) before retrying, and MUST NOT poll tightly; throttling abusive polling
is the service's responsibility (see
[Authentication and Rate Limiting](#authentication-and-rate-limiting)).

Note: a settled `unverified` (`200`) and an enqueued `unverified` (`202`) carry
identical bodies; the distinction is conveyed only by the HTTP status and is not
preserved if the body is stored or forwarded apart from its response. A consumer
that needs to distinguish them MUST do so from the live response status.

A `400 Bad Request` MAY carry content type `application/json` with a coded
error body, as described in [Errors](#errors), to say why the request was
rejected; a client MUST tolerate a `400` without one and treat it as a generic
bad request. The other non-2xx statuses each have a single meaning and are
signaled by the status code alone; a body, if any, is not defined by this SEP.

A `200` and `202` response body is a single status object. Its top-level fields
identify the wasm and the record; the verification results live in an array, so
that a service can report one or several independent verifiers and so that
other verification methods can be added later as sibling arrays without
disturbing the existing shape:

| Name                        | Type            | Description                                                                                                                                                                                                                                                                                                                                            |
| --------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `schema_version`            | string          | The version of the response schema this body conforms to, as `MAJOR.MINOR`, versioned independently of this SEP's `Version`. `MAJOR` increments on a breaking change (a field removed or renamed); `MINOR` increments on an additive change (a new field, or a new value added to an open enumeration). Clients SHOULD branch on `MAJOR` and tolerate a higher `MINOR`, including unrecognized fields and unrecognized enumeration values; for an unrecognized value, a client follows that field's documented fallback recommendation. |
| `wasm_hash`                 | string          | The queried wasm hash, echoed back. Lowercase hex SHA-256.                                                                                                                                                                                                                                                                                             |
| `updated_at`                | string          | RFC 3339 UTC timestamp of when this record was last updated, across all of its verifications (status transitions, re-checks, newly added verifiers). Always present.                                                                                                                                                                                   |
| `source_code_verifications` | array of object | One or more rebuild-from-source verification results, each from one verifier. MUST contain at least one entry. See below.                                                                                                                                                                                                                              |

Each entry of `source_code_verifications` describes one verifier's attempt to
rebuild the wasm from source. Fields sourced from SEP-58 carry the same names
and value formats as defined there, and are present only when the verifier
knows them:

| Name             | Type            | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ---------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `verifier`       | object          | Identity of the verifier that produced (or is producing) this result. See below.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `status`         | string          | One of the [verification status values](#verification-status-values).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `out_of_band`    | boolean         | (optional) When `true`, this verification was established outside SEP-58's reproducible-build mechanisms (e.g. a custom or non-allowlisted build image, or private source). The result is not independently reproducible from the recorded SEP-58 fields; consumers SHOULD weigh it accordingly. Absent or `false` means a standard reproducible SEP-58 verification.                                                                                                                                                                                                                                                                                                                                                                                                        |
| `bldimg`         | string          | SEP-58 `bldimg`. (optional) The build image the wasm records.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `bldopt`         | array of string | SEP-58 `bldopt`. (optional) The build flags the wasm records, one entry per flag. Order is not significant.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `source_repo`    | string          | SEP-58 `source_repo`. (optional)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `source_rev`     | string          | SEP-58 `source_rev`. (optional) Full 40-char SHA-1 of the source commit.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `tarball_url`    | string          | SEP-58 `tarball_url`. (optional)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `tarball_sha256` | string          | SEP-58 `tarball_sha256`. (optional) Lowercase hex SHA-256 of the source tarball.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `rebuilt_hash`   | string          | The conflicting lowercase hex SHA-256 the verifier produced by rebuilding from source. REQUIRED when `status` is `mismatched` and MUST be omitted otherwise: for `verified` it would simply repeat the top-level `wasm_hash`, and `unverified` has no rebuild result.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `processed_at`   | string          | RFC 3339 UTC timestamp of when this verification was processed. REQUIRED for `verified` and `mismatched`; MUST be omitted for `unverified` (which is not a processed result).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `results_urls`   | array of string | (optional) Zero or more URIs where a fuller, externally-published record of this verification can be retrieved (e.g. build logs, the rebuilt artifact, or a signed report). The same record MAY be listed at several locations (e.g. both an IPFS and an Arweave copy). Each entry's scheme is open — `https`, `ipfs`, `ar`, and others are all valid — letting a verifier publish to a content-addressed or permanent store. The SEP does not constrain the format of what is served there. Entries are opaque pointers, not necessarily directly fetchable by a browser; a client resolves each according to its scheme (e.g. an `ipfs` or `ar` URI may require a gateway or a protocol client) and SHOULD treat content-addressed URIs as integrity-checkable references. |

The `verifier` object has the following fields:

| Name       | Type             | Description                                                                                                                                                                                                                                                                                                                                       |
| ---------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`     | string           | A human-readable name for the verifier.                                                                                                                                                                                                                                                                                                           |
| `url`      | string           | (optional) A URL identifying the verifier or describing its methodology.                                                                                                                                                                                                                                                                          |
| `logo_url` | string or object | (optional) A logo for the verifier, for display next to a result. Either a URL string, or an object with `light` and/or `dark` keys holding URL variants for light and dark backgrounds — a client picks the variant matching its UI and falls back to whichever is present. The image SHOULD be square; a transparent background is recommended. |

##### Verification status values

These are the values of each verification's `status`:

| Value        | Meaning                                                                                                                                                                                                                                                                                                             |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `verified`   | The verifier rebuilt the wasm from source and the rebuilt hash matched the top-level `wasm_hash`. No `rebuilt_hash` is reported, since it would simply repeat `wasm_hash`.                                                                                                                                          |
| `mismatched` | The verifier rebuilt the wasm and produced a conflicting hash. `rebuilt_hash` is present and differs from `wasm_hash`.                                                                                                                                                                                              |
| `unverified` | The wasm is not verified. This covers everything that is not a definitive `verified` or `mismatched` result — verification is enqueued or in progress, the wasm lacks the metadata to rebuild, the build environment is unsupported, the source could not be retrieved, or the verifier hit an error, among others. |

Because `mismatched` reports a concrete conflicting `rebuilt_hash`, a verifier
that concludes a wasm does not correspond to its source without producing such a
hash — for example an out-of-band check that compares against an audited copy
rather than rebuilding — reports `unverified`, not `mismatched`.

The HTTP status separates an enqueued or in-progress `unverified` (`202`) from
a settled one (`200`). Clients MUST tolerate a `status` they do not recognize
and SHOULD treat it as `unverified`.

##### Examples

A verified wasm with a single verifier (`200 OK`):

```json
{
  "schema_version": "1.0",
  "wasm_hash": "cb2fc3a1b4d5e6f7081928374655647382910abcdef0123456789abcdef01234",
  "updated_at": "2026-06-04T12:05:00Z",
  "source_code_verifications": [
    {
      "verifier": {
        "name": "Example Verification Service",
        "url": "https://verify.example.com",
        "logo_url": {
          "light": "https://verify.example.com/logo.png",
          "dark": "https://verify.example.com/logo-dark.png"
        }
      },
      "status": "verified",
      "bldimg": "docker.io/stellar/stellar-cli@sha256:1f2e3d4c5b6a79887766554433221100ffeeddccbbaa99887766554433221100",
      "bldopt": ["--manifest-path=contracts/foo/Cargo.toml", "--optimize"],
      "source_repo": "https://github.com/user/my-contract",
      "source_rev": "abc1234567890abcdef1234567890abcdef12345",
      "processed_at": "2026-06-04T12:00:00Z",
      "results_urls": [
        "ipfs://bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        "ar://AbCdEf0123456789AbCdEf0123456789AbCdEf0123456789ABC"
      ]
    }
  ]
}
```

An out-of-band verification (`200 OK`). A verifier may establish a result by
means outside SEP-58's reproducible-build path — for example building with a
custom or non-allowlisted image, working from private or unpublished source
code, comparing against an internal/audited copy of the source, or relying on a
trusted attestation rather than rebuilding. In these cases the
reproducible-build fields (`bldimg`, `source_repo`, …) may be
absent because the result cannot be independently reproduced from them;
`out_of_band` flags this so a consumer can weigh it accordingly:

```json
{
  "schema_version": "1.0",
  "wasm_hash": "cb2fc3a1b4d5e6f7081928374655647382910abcdef0123456789abcdef01234",
  "updated_at": "2026-06-04T12:00:00Z",
  "source_code_verifications": [
    {
      "verifier": { "name": "Example Verification Service" },
      "status": "verified",
      "out_of_band": true,
      "processed_at": "2026-06-04T12:00:00Z"
    }
  ]
}
```

Two verifiers that disagree (`200 OK`):

```json
{
  "schema_version": "1.0",
  "wasm_hash": "cb2fc3a1b4d5e6f7081928374655647382910abcdef0123456789abcdef01234",
  "updated_at": "2026-06-04T13:00:00Z",
  "source_code_verifications": [
    {
      "verifier": { "name": "Verifier A", "url": "https://a.example.com" },
      "status": "verified",
      "source_repo": "https://github.com/user/my-contract",
      "source_rev": "abc1234567890abcdef1234567890abcdef12345",
      "processed_at": "2026-06-04T12:00:00Z"
    },
    {
      "verifier": { "name": "Verifier B", "url": "https://b.example.com" },
      "status": "mismatched",
      "source_repo": "https://github.com/user/my-contract",
      "source_rev": "abc1234567890abcdef1234567890abcdef12345",
      "rebuilt_hash": "999888777666555444333222111000fedcba9876543210fedcba9876543210fe",
      "processed_at": "2026-06-04T13:00:00Z"
    }
  ]
}
```

A settled unverified wasm (`200 OK`):

```json
{
  "schema_version": "1.0",
  "wasm_hash": "cb2fc3a1b4d5e6f7081928374655647382910abcdef0123456789abcdef01234",
  "updated_at": "2026-06-04T12:00:00Z",
  "source_code_verifications": [
    {
      "verifier": { "name": "Example Verification Service" },
      "status": "unverified"
    }
  ]
}
```

A wasm whose verification is enqueued (`202 Accepted`) — same body shape, with
the HTTP status marking it as still in progress:

```json
{
  "schema_version": "1.0",
  "wasm_hash": "cb2fc3a1b4d5e6f7081928374655647382910abcdef0123456789abcdef01234",
  "updated_at": "2026-06-04T12:00:00Z",
  "source_code_verifications": [
    {
      "verifier": { "name": "Example Verification Service" },
      "status": "unverified"
    }
  ]
}
```

An invalid wasm hash (`400 Bad Request`):

```json
{
  "schema_version": "1.0",
  "error": "400_invalid_wasm_hash",
  "message": "wasm_hash is not a valid lowercase hex SHA-256."
}
```

### Errors

A `400 Bad Request` MAY carry an `application/json` body that says why the
request was rejected; the body has these fields. No other status defines a body
(see the [response status codes](#response) and
[Authentication and Rate Limiting](#authentication-and-rate-limiting)).

| Name             | Type   | Description                                                                                                 |
| ---------------- | ------ | ----------------------------------------------------------------------------------------------------------- |
| `schema_version` | string | The version of the response schema this body conforms to, as `MAJOR.MINOR` (see the status object).         |
| `error`          | string | A stable, machine-readable code from the list below. Clients SHOULD branch on this rather than `message`.   |
| `message`        | string | A human-readable description of the error. Wording is not stable and is intended for display and debugging. |

The `error` code is one of:

| `error`                 | Meaning                                                              |
| ----------------------- | -------------------------------------------------------------------- |
| `400_invalid_wasm_hash` | The `wasm_hash` path parameter is not a valid lowercase hex SHA-256. |
| `400_other`             | The request was rejected for another reason described in `message`.  |

A service MUST use the most specific applicable code, falling back to
`400_other` only when no more specific `400` code fits. Clients MUST tolerate
encountering an `error` code they do not recognize and SHOULD fall back to
displaying `message`.

Example:

```json
{
  "schema_version": "1.0",
  "error": "400_invalid_wasm_hash",
  "message": "wasm_hash is not a valid lowercase hex SHA-256."
}
```

### Schema

Machine-readable JSON Schemas (draft 2020-12) for the two response bodies,
along with the examples above as standalone files for testing, are published
alongside this SEP:

- [`status-object-1.0.schema.json`](../contents/sep-contract-verification-registry/status-object-1.0.schema.json)
  — the `200`/`202` status object.
- [`error-1.0.schema.json`](../contents/sep-contract-verification-registry/error-1.0.schema.json)
  — the `400` error body.
- [`examples/`](../contents/sep-contract-verification-registry/examples) — each
  snippet in this document as a file that validates against the schema above.

Each schema's filename carries the `MAJOR.MINOR` it describes and validates that
shape exactly; a future schema version is published as a new file rather than by
editing these in place.

See the
[directory README](../contents/sep-contract-verification-registry/README.md)
for how to run validation.

## Design Rationale

### Why wasm hash as the key, not contract address?

A wasm hash is the stable, content-addressed identifier for a contract's code:
the same bytes hash the same on every network, and the hash never changes. A
contract address is not stable — which wasm it references can change over time,
even within a single ledger — so a client that treats an address as a fixed
pointer to code can be misled. Keying on the wasm hash keeps a service focused
on its one job (associating source with a binary), makes results trivially
cacheable (a wasm-hash → verification mapping is immutable, an address →
wasm-hash mapping is not), and makes them network-independent.

Clients that start from a contract address — explorers, wallets, frontends —
already resolve it to the current wasm hash via RPC and can handle the reality
that one address maps to many wasms over its life; pushing that into every
verifier would burden each with infrastructure outside its concern.

### Why an array of `source_code_verifications` reusing SEP-58 names?

SEP-58 already defines stable names and value formats for every build and
source field, so each entry reuses them verbatim — a client that understands
SEP-58 already understands an entry, with no translation layer. Making it an
array lets the same shape serve a single verifier and an aggregator that
collects several independent verifiers, and lets consumers see and weigh
disagreement in one response.

Grouping the entries under a named method array (rather than flattening one
verifier's fields next to the wasm fields) also leaves room to add other
verification methods later as sibling arrays — without renaming or moving any
existing field, which a flat layout could not do without a breaking change.

### Why echo `wasm_hash` and a per-entry `verifier`?

A result may be cached, stored, or forwarded far from the request that produced
it. Echoing the `wasm_hash` and naming the verifier inside each entry means the
result stays self-describing once detached from the service, and a consumer can
weigh each verification by who produced it without a second request.

### Why is the network only an optional query hint?

The wasm hash is network-independent, so the network is not part of what is
verified and does not belong in the result. A client that cares about a
particular network can pass `network_passphrase` as a hint — for example so the
service can scope auxiliary on-chain lookups — but a service is free to ignore
it, and nothing in the response depends on it.

### Why an open list of `results_urls` rather than a fixed report format?

Verifiers differ in what evidence they retain and where they keep it: some
publish a signed report to a content-addressed store like IPFS or a permanent
store like Arweave, some keep build logs behind an `https` URL, and some
publish to several at once for redundancy. A list of open-scheme URIs lets each
verifier link to whatever it has, in whatever format, without this SEP
standardizing a report schema prematurely. The entry stays the stable,
parseable summary; `results_urls` is the escape hatch to the full record.

### Why an `out_of_band` flag rather than a status value?

How a result was reached is orthogonal to its outcome: an out-of-band
verification is still `verified` or `mismatched`, it just was not produced by
an independently reproducible rebuild. Folding it into `status` would multiply
the enum (`verified` × in-band/out-of-band) and force consumers that only care
about the verdict to learn extra values; a separate boolean keeps `status`
about the outcome and lets a UI add an "out-of-band" qualifier where it
matters.

### Why a `schema_version` on every body, versioned independently of the SEP?

The response shape will evolve, and a result may be cached, stored, or
forwarded far from the request that produced it. Stamping each body with the
shape it conforms to lets a consumer detect a shape it predates and branch on
`MAJOR` rather than guessing from which fields happen to be present. It is kept
separate from the SEP's own `Version` because the document changes for reasons
that do not touch the wire format — clarifications, rationale, security notes —
and bumping the shape version for prose edits would force needless client
churn. The two-part `MAJOR.MINOR` mirrors how clients actually react: `MAJOR`
(a removed or renamed field) can break a parser, while `MINOR` (a new field) is
safe to ignore.

## Security Concerns

### Results are advisory

A `verified` result asserts only that the named source produced the bytes in
the verifier's environment. As SEP-58 notes, it says nothing about whether that
source is correct or non-malicious. Consumers SHOULD weigh results by verifier
reputation and, where it matters, across the independent verifiers a response
may carry rather than trusting a single one.

An `out_of_band` result is weaker still: it rests on the verifier's word, with
no reproducible artifact a third party can recheck, so it leans entirely on
that verifier's reputation. Confidence grows with the number of independent
verifications a wasm accumulates.

### Verifier honesty

A verifier can publish false-positive results. The `verifier` field names who
produced each entry so consumers can attribute and weigh it; an aggregator that
returns several verifiers in one response makes cross-checking easy.

### Enqueue amplification

Because `GET /wasms/:wasm_hash.json` can enqueue a rebuild on first sight, an
attacker could attempt to drive expensive builds by querying many hashes.
Services SHOULD rate-limit, de-duplicate in-flight enqueues, and bound the work
a single hash can trigger.

### Untrusted `results_urls`

The URIs in `results_urls` are chosen by the verifier, and a dishonest or
compromised one can list arbitrary locations. Clients MUST treat anything
fetched from them as untrusted input — not same-origin, not safe to render or
execute, and not authoritative over the status object itself. Fetching them
from a server context also invites SSRF; resolve them in a sandbox or not at
all. Before sending a user to one, clients SHOULD show an interstitial
redirect-confirmation page that displays the destination, rather than
navigating to it directly.

### Transport

HTTPS is required so that a result cannot be altered in transit to misrepresent
a wasm as verified.

## Changelog

- `v0.1.0` - Initial draft.
