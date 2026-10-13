# Contract Verification Aggregation

## Preamble

```
SEP: To Be Assigned
Title: Contract Verification Aggregation
Author: Jia Chen <@jia57b>
Status: Draft
Created: 2026-09-10
Updated: 2026-10-13
Version: 0.1.0
Discussion: https://github.com/orgs/stellar/discussions/2039
```

## Simple Summary

How to combine several verifiers' contract verification results into one view,
and how to publish who is being combined.

[_Contract Verification Results_](https://github.com/stellar/stellar-protocol/pull/2038)
defines what one verifier publishes and the routes that serve it. This SEP
defines the document an **aggregator** serves for one Wasm hash across
verifiers, the list of verifiers it draws on, and the rules that keep the
combined view a relay rather than a judgment.

## Dependencies

- **Contract Verification Results** (draft, proposed in
  [stellar/stellar-protocol#2038](https://github.com/stellar/stellar-protocol/pull/2038);
  SEP number to be assigned). Every verifier this SEP reads is read over that
  SEP's routes, its result root is that SEP's identity (§2 there), and the
  entries relayed here are the entries defined there. Nothing in this SEP is
  implementable without it.
- [SEP-58](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0058.md):
  Contract Build Reproducibility for Verification, via that SEP.
- [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339) for timestamps,
  [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) for MUST/SHOULD/MAY.
- JSON Schema 2020-12. The normative schemas are in
  `../contents/sep-contract-verification-aggregation/schemas/`, and
  non-normative example bodies are beside them in
  `../contents/sep-contract-verification-aggregation/examples/`.

## Motivation

Independent verification is worth more than one verifier's word — but only if a
reader can see all of it at once, including the parts that disagree.

A consumer can do this itself: fetch a list of verifiers from somewhere, read
each one, and merge. Every consumer that does will make the same handful of
decisions differently — what to do about a verifier that times out, what a
result read an hour ago is worth now, whether two answers that differ mean
"disputed" or "the newer one wins" — and none of those decisions will be
visible to the person reading the answer.

So the merge is worth specifying, and the specification is mostly a list of
things the merger must **not** do: not relabel a peer, not re-version a relayed
entry, not silence a peer it could not reach, and not turn disagreement into a
verdict.

This is deliberately a separate proposal from _Contract Verification Results_.
Reading one verifier is a settled shape with an implementation behind it;
combining many raises questions about who is trusted and who decides that
should not hold the first half up.

## Prior art and acknowledgements

The per-verifier read surface this builds on grows from the **Contract
Verification Registry API** draft by [@fnando](https://github.com/fnando)
([stellar-protocol#1944](https://github.com/stellar/stellar-protocol/pull/1944));
_Contract Verification Results_ carries that history and its migration
appendix. The draft defines nothing about aggregation, so this SEP inherits no
shapes from it and asserts nothing about its disposition.

## Abstract

An **aggregator** reads verifiers over the _Contract Verification Results_
routes and serves a combined view. It publishes two documents of its own:

| `schema`                         | What it is                      |
| -------------------------------- | ------------------------------- |
| `stellar-verification-aggregate` | One Wasm hash, across verifiers |
| `stellar-trusted-verifiers-list` | Who it aggregates               |

It takes `stellar-verification-error` from that SEP unchanged, for every
non-2xx body, and serves that SEP's `stellar-verification-page` envelope under
the same `schema` value with a record shape of its own (§4).

Routes, relative to a base URL an aggregator advertises:

| Route                                       | Answers                                     |
| ------------------------------------------- | ------------------------------------------- |
| `GET /v1/wasms/{wasm_hash}`                 | `stellar-verification-aggregate`            |
| `GET /v1/wasms`                             | `stellar-verification-page`                 |
| `GET /v1/verifiers`                         | `stellar-trusted-verifiers-list`            |
| `GET /v1/contracts/{network}/{contract_id}` | `stellar-verification-aggregate` (OPTIONAL) |

## Specification

### 1. Roles and conformance

An **aggregator** reads other verifiers over the public routes _Contract
Verification Results_ defines and serves a combined view. It MUST serve
`GET /v1/wasms/{wasm_hash}` and `GET /v1/verifiers`; it SHOULD serve
`GET /v1/wasms`.

An aggregator is not an authority. It has no way to make a verifier's claim
truer, and this SEP gives it no way to express one of its own: every verdict in
every document here belongs to a verifier, and the aggregator's contribution is
the list it drew on and the honesty of the relay.

One deployment may be both a verifier and an aggregator. When it is, it MUST
read its own results through the public read surface like any other member, not
through a private path — otherwise the aggregate is only reproducible by its
operator, and the one entry a reader has most reason to scrutinise is the one
entry that took a different route to the page.

### 2. The aggregated document

Normative schema:
[`stellar-verification-aggregate-1.0.schema.json`](../contents/sep-contract-verification-aggregation/schemas/stellar-verification-aggregate-1.0.schema.json).

```json
{
  "schema": "stellar-verification-aggregate",
  "schema_version": "1.0",
  "wasm_hash": "7d1e4b9a2c6f08315e8d0a4b7c2f9e6d3a0b5c8f1e4d7a0b3c6f9e2d5a8b1c40",
  "updated_at": "2026-09-08T14:10:00.442Z",
  "source_code_verifications": [
    {
      "verifier": {
        "url": "https://verify.example.org",
        "name": "Example Verify"
      },
      "status": "verified",
      "recipe_source": "on_chain_metadata",
      "image_trust_level": "official_trusted",
      "bldimg": "docker.io/stellar/stellar-cli@sha256:1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f809",
      "bldarg": [],
      "bldopt": ["--package=token"],
      "source_sha256": "9c8b7a6d5e4f30211f2e3d4c5b6a79880f1e2d3c4b5a69788796a5b4c3d2e1f0",
      "source_uri": "https://github.com/example/token/archive/refs/tags/v1.4.0.tar.gz",
      "processed_at": "2026-09-08T09:58:11.204Z",
      "results_urls": [
        {
          "type": "report",
          "location": "verifier_self_storage",
          "url": "https://verify.example.org/reports/5e4d3c2b1a09f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c5b4a392817060.json",
          "sha256": "5e4d3c2b1a09f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c5b4a392817060"
        },
        {
          "type": "report",
          "location": "arweave",
          "url": "ar://kP7nQx2LmR9vT4wY6bH1cJ8sD3fG5aZ0eN2iU7oX9yM",
          "sha256": "5e4d3c2b1a09f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c5b4a392817060"
        }
      ],
      "verified_source_code_uris": [
        {
          "location": "verifier_self_storage",
          "url": "https://verify.example.org/sources/9c8b7a6d5e4f30211f2e3d4c5b6a79880f1e2d3c4b5a69788796a5b4c3d2e1f0.tar.gz"
        }
      ],
      "schema_version": "1.0",
      "retrieved_at": "2026-09-08T14:00:03.512Z"
    }
  ],
  "unavailable_verifiers": [
    {
      "url": "https://other.example.org",
      "name": "Other Verify",
      "reason": "timeout",
      "error": "connect ETIMEDOUT after 5000ms"
    },
    {
      "url": "https://legacy.example.net/results",
      "name": "Legacy Verify",
      "reason": "refused",
      "error": "destination rejected by fetch policy"
    }
  ],
  "agreement": "single"
}
```

An entry in `source_code_verifications` is a verifier's own entry, read from
that verifier's status object and carried through: the fields, their vocabulary
and the conditions on them are _Contract Verification Results_ §3's, not
restated here. **Including the conditional ones** — an entry whose `status` is
not `unverified` carries `recipe_source`, `image_trust_level`, `source_sha256`
and `processed_at`, because the entry it was read from had to. An aggregator
that abbreviated an entry would be editing it.

Exactly two fields are the aggregator's own and appear in no status object:
`retrieved_at` on a retained entry, and the envelope's `updated_at`. Everything
else in the example above is the peer's, byte for byte.

**An aggregator relays; it does not translate.** Concretely:

- The `verifier` block is the peer's own, **unchanged**. An aggregator MUST NOT
  substitute its own label for the verifier's, and needs no second identity
  block and no aggregator-local id — the result root identifies without anyone
  asserting anything.
- A relayed entry MUST keep fields this schema does not name. It is the one
  object in this SEP left open for that reason: an aggregator that dropped an
  unrecognised field would be editing the claim it is passing on.

  **The schema names six fields, and that is the whole of what it types.** Five
  are the aggregator's own subject matter — who the entry is from, what version
  it was read at, the verdict, when the verifier reached it, when we read it —
  and the sixth is `results_urls`, typed because its `sha256` is what lets a
  consumer leave the aggregator and check an entry at its source. Everything a
  verifier's status object may carry beyond those, `verified_source_code_uris`
  and the recipe fields included, crosses unnamed and unexamined. That is the
  design and not an omission: an aggregator has no business typing a field it
  makes no promise about, and a schema that copied the status object would turn
  every future field of that SEP into a breaking change for this one.

  It has one consequence worth stating plainly, because it is the only place
  relay is not lossless in principle. A peer whose `results_urls` are not
  structured entries cannot be relayed conformantly — there is no shape for it
  in this document — so the aggregator MUST report that peer in
  `unavailable_verifiers` rather than serve an entry that fails this schema.
  For every other field, a shape this SEP does not recognise costs nothing: it
  is passed through as it arrived.

- A relayed entry carries the `schema_version` **of the document it was read
  from**, not the envelope's. An aggregator that re-versioned entries would be
  a silent translator.

  An aggregator that caches therefore MUST store a version per retained entry.
  Stated because it is otherwise satisfiable only by an aggregator that never
  caches — which is not the interesting case.

- An unrecognised `status` is served as `unverified`. This applies at **two**
  points: when reading a peer, and again when serving — an aggregator that
  coerced only on read passes the raw string through to its own consumers. The
  relayed `status` is a free string in the schema precisely because the entry
  is open; the MUST above, not the schema, is what closes it.

`updated_at` is when the aggregator assembled the view. A reader wanting when a
verifier reached its verdict reads the entry's `processed_at`. `retrieved_at`
is when the aggregator last read the entry, and is present only on a retained
copy — a stale result is served honestly with its age, not withheld.

**`unavailable_verifiers`** is always present, empty when nothing failed.
Omitting it conflates "nobody has a result" with "we could not reach some",
which is the one distinction an aggregator must not blur. Entries are
identified by `url`, exactly as contributing entries are, so a consumer lines
the two lists up on one field. `name` is the aggregator's own label — there is
no peer document to relay — and `error` is operator-facing detail, part of no
contract.

`reason` is one of `fetch_failed`, `invalid_response`, `timeout`, `refused`.
Every one of them is something that happened to a request, which is the whole
vocabulary: "we have not looked yet" is not a peer being unavailable, it is the
aggregator being unable to answer, and §6 puts that in a `503` rather than in a
`200` body. It describes what the aggregator observed and MUST NOT be derived
at serve time from something else — an implementation that stored only a
message and reported everything as `fetch_failed` makes a peer it refused to
call indistinguishable from one that is down, and only the former is actionable
by talking to the aggregator.

**`agreement`** is descriptive and never a verdict: `no_data`, `single`,
`unanimous_verified`, `unanimous_mismatched`, `disputed`, `unverified_only`.
One entry is `single`, not `unanimous_verified` — unanimity among one
overstates. Disagreement is reported, not adjudicated.

### 3. Trusted Verifiers List

Normative schema:
[`stellar-trusted-verifiers-list-1.0.schema.json`](../contents/sep-contract-verification-aggregation/schemas/stellar-trusted-verifiers-list-1.0.schema.json).

`GET /v1/verifiers` on an aggregator lists every verifier it aggregates.

```json
{
  "schema": "stellar-trusted-verifiers-list",
  "schema_version": "1.0",
  "updated_at": "2026-09-08T10:00:00Z",
  "verifiers": [
    {
      "url": "https://verify.example.org",
      "manifest_url": "https://verify.example.org/verifier-manifest.json",
      "bulk_load_url": "https://api.example.org/v1/wasms",
      "display_name": "Example Verify",
      "status": "active",
      "added_at": "2026-07-01T00:00:00Z"
    }
  ]
}
```

The list is authored by the **aggregating operator**. A verifier describes
itself and does not admit itself to anyone's list, which is why this SEP
defines no verifier-registration API.

**`status` is `active`, `paused` or `disabled`, and paused and disabled members
stay listed.** Removing a member from the document is how an aggregator
silently omits a verifier; keeping it listed is what makes the promise
checkable from outside. A `paused` member is not read, and its retained entries
are still served with their `retrieved_at`. A `disabled` member's entries are
neither served nor counted in `agreement`, and disabling it moves the
aggregation time of every hash it contributed to, so a synchronising consumer
sees the withdrawal.

`url` is the entry's identity. `display_name` is the operator's own label —
distinct from the verifier's self-claimed `name` in _Contract Verification
Results_ §3.1 — and `trust_tier` is the operator's own assessment, free-form,
interpreted by nothing across lists. `added_at` is when the operator admitted
this member, for its own audit. `id` is OPTIONAL and implementation-local: it
means nothing outside the aggregator that minted it, and no other document
refers to it.

`manifest_url` is OPTIONAL and opaque to this SEP. It points at a verifier's
own self-description — its build-image and source-mode policy, its retention,
whom to contact — and 1.0 defines neither that document's shape nor any field
read out of it. Its absence is not a defect: it means the verifier publishes no
such self-description, and every field either SEP specifies is served from the
result root or from the routes above. A consumer MAY fetch it to show an
operator something; it MUST NOT derive a status, a result root or an identity
from it, and MUST NOT treat a missing, unreachable or unparseable manifest as a
reason to exclude the entry.

### 4. Bulk load

An aggregator's `GET /v1/wasms` serves `stellar-verification-page` — the
envelope, the parameters (`order`, `limit`, `cursor`) and the two rules
consumers get wrong are all as _Contract Verification Results_ §5 defines them,
and are not restated here.

One difference, and it is the point of the route: **an aggregator's records are
whole `stellar-verification-aggregate` documents**, not pointers. A consumer of
a verifier fetches the status object it cares about because the result should
be read at its source; a consumer of an aggregator has already accepted that
the aggregator is the one doing the reading, and traversing the list and
synchronising against every member itself is exactly what it came here to
avoid.

Normative schema:
[`stellar-verification-page-aggregated-1.0.schema.json`](../contents/sep-contract-verification-aggregation/schemas/stellar-verification-page-aggregated-1.0.schema.json).
It is the same envelope under the same `schema` value; only `records` differs.
A consumer knows which record shape it will get because it knows which role it
asked, and MUST NOT infer the role from a record it did not expect.

**A cursor does not cross the boundary.** An aggregator's stream is ordered by
the aggregator's own clock — when it last assembled a view — and a verifier's
by that verifier's publication update time. The two share a format and mean
different positions. A cursor is valid only within the stream that issued it,
which is why _Contract Verification Results_ §5 makes it opaque.

### 5. Resolving by contract address

An aggregator MAY serve `GET /v1/contracts/{network}/{contract_id}`, resolving
the contract's current Wasm hash and answering as `/v1/wasms/{wasm_hash}`
would. Explorers index by contract address, not by Wasm hash.

### 6. Errors

Every non-2xx body of the routes in §§2–5 is a `stellar-verification-error`,
exactly as _Contract Verification Results_ §6 defines it — same four required
fields, same openness to diagnostic ones, same obligation on a client to
tolerate a code it does not recognise. This SEP defines no error document of
its own and no closed vocabulary.

The vocabulary is open here as it is there, and a server SHOULD document the
codes it emits. An aggregator has occasion for codes a verifier does not —
`aggregation_unavailable`, `invalid_cursor`, `invalid_limit`, `invalid_order`,
and, on §5's route, `invalid_network`, `invalid_contract_id` and
`contract_not_found` are typical — and adding one is not a breaking change.

One distinction is worth stating as a rule rather than leaving to taste: **an
aggregator that cannot currently answer MUST NOT answer as though it had.** A
`404` reads as "no verifier has this"; so, more quietly, does a `200` carrying
`agreement: "no_data"` and an empty `unavailable_verifiers`, which asserts that
every member was asked. Before an aggregator has read its list for the first
time neither is true of anything, so §§2 and 4 MUST both answer `5xx` with a
code that says the aggregator is not ready — not an empty answer a consumer
records as synchronised and never revisits.

A peer being unreachable is **not** an error of this API. It is
`unavailable_verifiers` in a `200` body (§2).

### 7. Versioning and tolerance

The rules of _Contract Verification Results_ §7 apply unchanged to the two
documents defined here: `schema` and `schema_version` on every document, a
producer writes exactly its version's fields, a consumer relaxes
`additionalProperties`, accepts a higher MINOR of a MAJOR it knows, and never
rejects a document for a missing `schema`.

Two things are specific to this SEP:

1. **The relayed entry is open at the object level** (§2) — the one place a
   producer MUST pass through fields it does not recognise, rather than merely
   being permitted to. It is the mirror image of the error envelope's openness
   in the other SEP: that one exists for diagnostics, this one for relay
   fidelity.
2. **The two SEPs version independently.** A MAJOR here obliges nothing there,
   and the reverse. That is what it means for `schema` to name the document
   rather than the proposal — and it is why a relayed entry carries the
   `schema_version` it was read at.

## Limitations

- **Who belongs on a list is not specified.** This SEP says how a list is
  published and what an aggregator must not do with it. It defines no admission
  criteria, no audit, no revocation protocol, and no way for one aggregator's
  list to be checked against another's. `trust_tier` is free-form precisely
  because nothing here can give it a shared meaning.
- **Nothing is signed**, and an aggregate is not attributable to the verifiers
  it names. A reader who does not trust the aggregator re-reads the verifiers
  directly — which the other SEP's routes make possible, and which is the
  practical answer to "why is this trustworthy" rather than a signature. Design
  Rationale there carries the argument.
- **`agreement` describes, and stops there.** No weighting, no quorum, no
  tie-break. A consumer that wants a decision makes it itself, from entries it
  can see.
- **Caching policy is the aggregator's own.** `retrieved_at` says when an entry
  was read; nothing says how stale is too stale, and two aggregators may serve
  different views of the same hash without either being wrong.
- **No push, no subscription.** §4's stream is polled. A consumer that needs
  latency reads verifiers directly.
- **The verifier manifest is not defined.** `manifest_url` is an OPTIONAL
  pointer at a verifier's self-description; 1.0 defines neither its shape nor
  any field read out of it, which is also why it is optional rather than
  required — a required link to an undefined document would make conformance
  turn on bytes no reader is allowed to interpret.

## Design Rationale

### An aggregator relays; it does not adjudicate

Every rule in §2 is one instance of this, and it is worth saying why the rules
are MUSTs rather than good practice.

An aggregator sits where a consumer cannot see. If it relabels a peer, the
consumer reads a claim attributed to the wrong party. If it re-versions a
relayed entry, the consumer validates against a schema the document was never
written to. If it drops an unrecognised field, it edits a claim in transit. If
it decides which of two verifiers is right, it has replaced the thing worth
having — independent answers — with its own, while still displaying two names.

None of these failures is visible from the outside. That is the argument for
spelling them out: a rule whose violation a consumer could detect could be left
to reputation.

### `agreement` is descriptive, never a verdict

Six values, and the interesting one is `single`. One verifier saying `verified`
is not `unanimous_verified`: unanimity among one is a statement about the size
of the sample dressed up as a statement about agreement, and a UI that renders
the two the same way tells a reader that one verifier's answer has been
corroborated.

`disputed` is likewise not a failure state. Two honest verifiers can disagree —
different build environments, different moments, a contract upgraded between
them — and the value exists so a reader can go look, not so a UI can show a
warning triangle.

### The list is the aggregating operator's document

`GET /v1/verifiers` is a MUST because the alternative is an aggregator whose
inputs are private. A consumer that cannot enumerate the list cannot tell a
missing verifier from an omitted one, and cannot reproduce the aggregate.

For the same reason a `paused` or `disabled` member stays listed. Removing the
entry is exactly the operation that makes an omission invisible; keeping it
with a status is what makes the promise checkable from outside.

There is no registration API here, and that is a decision rather than an
omission. A verifier describes itself; it does not admit itself to somebody
else's list, and a protocol for asking to be admitted would imply a duty to
answer.

## Security Concerns

**A Trusted Verifiers List is a supply of URLs an aggregator will fetch.** It
is authored by the operator, so the trust question is not "is this list honest"
but "what does an entry make my service do": resolve and reject loopback,
link-local and private-range destinations before fetching a member, cap
response size and time, and do not follow redirects out of the origin the
result root names. An aggregator with a broad list is a general-purpose fetcher
if it does not.

**A relayed entry is untrusted content that this SEP requires you to keep.**
The pass-through rule in §2 means an aggregator serves bytes a peer chose,
including fields it does not recognise and strings it never validated. It must
not be reflected into anything that interprets it — a template, a shell, a SQL
fragment, a page — and a consumer must treat every relayed string as hostile
even though it arrived from the aggregator. The one field an aggregator does
constrain is `status`, coerced to `unverified` when unrecognised, at read and
again at serve.

**`manifest_url` and `logo_url` are pointers, not documents.** A consumer MUST
NOT derive a status, a result root or an identity from a manifest, MUST NOT
treat a missing or unparseable one as grounds to exclude an entry, and MUST NOT
dereference either as a side effect of rendering the list.

**`display_name` and `trust_tier` are the operator's assertions about somebody
else.** They mean nothing outside the list that carries them. A UI that shows a
tier without showing whose list it came from has manufactured a reputation
system out of one operator's notes.

**Fan-out is the denial-of-service surface.** One request for one hash can
become one request per member. An aggregator serves from its own store and
synchronises on its own schedule; it MUST NOT make an unauthenticated read
trigger a fresh pass over the list, or a slow member becomes a way to hold its
connections open.

**Silence must stay visible.** `unavailable_verifiers` is always present and
`reason` records what was actually observed. An implementation that omits the
list when it is empty, or that reports everything as `fetch_failed`, makes a
peer it refused to call indistinguishable from a peer that is down — and the
first is the operator's own decision, which a reader is entitled to see.

**Staleness is a claim about the past.** A retained entry carries
`retrieved_at`, and serving it without one asserts a currency the aggregator
does not have. A reader making a decision on a `verified` entry read a week ago
should be able to know that.

## Changelog

- `0.1.0` — Initial draft.
