# Contract Verification Results

## Preamble

```
SEP: To Be Assigned
Title: Contract Verification Results
Author: Jia Chen <@jia57b>
Status: Draft
Created: 2026-09-10
Updated: 2026-10-13
Version: 0.1.0
Discussion: https://github.com/orgs/stellar/discussions/2037
```

## Simple Summary

How to read contract verification results from a verifier.

[SEP-58](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0058.md)
defines the vocabulary for reproducing a contract's Wasm from source. This SEP
defines the documents a verifier publishes once it has done so, and the routes
that serve them — so an explorer can ask "has this verifier verified this
contract, and on what basis?" and get the same answer shape from every
verifier.

It does not define how a verification is requested or performed, and it does
not define how the answers of several verifiers are combined into one view.
That second half is a companion proposal, _Contract Verification Aggregation_,
which depends on this SEP and is deliberately separate from it: reading one
verifier is a settled shape, and combining many raises trust questions that
should not hold it up.

## Dependencies

- [SEP-58](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0058.md):
  Contract Build Reproducibility for Verification. This SEP carries its field
  names (`bldimg`, `bldarg`, `bldopt`, `source_sha256`, `source_uri`)
  unchanged.
- [SEP-46](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0046.md):
  Contract Meta, via SEP-58.
- [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339) for timestamps,
  [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) for MUST/SHOULD/MAY.
- JSON Schema 2020-12. The normative schemas are in
  `../contents/sep-contract-verification-results/schemas/`, and non-normative
  example bodies for every document and every status this SEP names are beside
  them in `../contents/sep-contract-verification-results/examples/`.

## Motivation

Verification is only useful if it can be read by something other than the
verifier that produced it. Today each verifier invents its own shape, so an
explorer integrates once per verifier and a reader cannot compare two answers.

**One verifier, one shape.** A wallet or explorer writes one reader, and points
it at any verifier.

That is the whole of this SEP's scope. The second half of the problem — that
independent verification is worth more than one verifier's word, but only if
the disagreement is visible — needs the shape defined here before it can be
addressed at all, and is addressed in the companion _Contract Verification
Aggregation_ proposal.

The thing it deliberately does _not_ do is standardise submission. Who may ask
for a verification, at what cost, under what abuse controls, is a verifier's
own business, and a spec that dictated it would exclude reasonable deployments.

## Prior art and acknowledgements

This SEP builds on the **Contract Verification Registry API** draft by
[@fnando](https://github.com/fnando)
([stellar-protocol#1944](https://github.com/stellar/stellar-protocol/pull/1944)),
and on the decisions reached in its
[discussion](https://github.com/orgs/stellar/discussions/1945). That draft
defined the per-hash read route and the status object this SEP grows from;
Appendix A maps its fields onto these and is written for an implementer moving
between the two.

The disposition of #1944 is its author's to decide. Nothing in this document
asserts anything about it.

## Abstract

A verifier publishes a **result root**: a static, publicly readable origin
under which `wasms/{wasm_hash}.json` is the status object for that Wasm hash.
The result root's URL is the verifier's identity.

Three JSON documents, each naming itself in a `schema` field:

| `schema`                      | What it is                            |
| ----------------------------- | ------------------------------------- |
| `stellar-verification-status` | One Wasm hash, one entry per verifier |
| `stellar-verification-page`   | One page of a bulk-load stream        |
| `stellar-verification-error`  | Any non-2xx body                      |

Routes, relative to a base URL a verifier advertises:

| Route                            | Answers                       |
| -------------------------------- | ----------------------------- |
| `GET /v1/wasms/{wasm_hash}.json` | `stellar-verification-status` |
| `GET /v1/wasms`                  | `stellar-verification-page`   |

## Specification

### 1. Roles and conformance

A **verifier** publishes its own results. It MUST serve a result root and the
status object at `wasms/{wasm_hash}.json` under it. It SHOULD serve
`GET /v1/wasms` so its corpus can be enumerated.

An **aggregator** — a deployment that reads several verifiers over these routes
and serves a combined view — is defined by the companion _Contract Verification
Aggregation_ proposal, along with the obligations that come with that role.
This SEP defines only what such a reader consumes, and nothing here requires an
aggregator to exist: every route above is answerable by, and readable from, a
single verifier.

### 2. The result root

The result root is an HTTPS origin plus optional path prefix, serving static
JSON. It is the verifier's identity throughout this SEP, and wherever anything
built on it keeps a set of verifiers: two members of such a set cannot share a
result root, because the same result root **is** the same verifier.

Two roots are the same verifier when they are equal after this normalisation:

1. Lowercase the scheme and the host.
2. Drop a default port for the scheme (`:443` under `https`).
3. Strip **all** trailing `/` from the path — `https://v.example/a//` and
   `https://v.example/a` are one verifier.
4. Keep the rest of the path, case-sensitive.
5. Keep the query string, if any. A root that carries one is unusual, but
   dropping it silently would merge two roots their operator kept apart.
6. Drop the fragment; it is not sent to a server.

These six sit **on top of** RFC 3986 syntax normalisation — dot-segment
removal, percent-encoding case, dropped userinfo — which a URL parser does for
free and an implementation hand-rolling string comparison does not. Parse
before you compare.

The rule is spelled out to this depth because it is otherwise the first thing
two implementations disagree about, and the disagreement is invisible: each one
is internally consistent and they simply see a different number of verifiers.

Required under the root:

```
wasms/{wasm_hash}.json      the status object
```

### 3. Status object

Normative schema:
[`stellar-verification-status-1.0.schema.json`](../contents/sep-contract-verification-results/schemas/stellar-verification-status-1.0.schema.json).

```json
{
  "schema": "stellar-verification-status",
  "schema_version": "1.0",
  "wasm_hash": "3f8c2a1b9e4d7c05a6b3f8129d4e5a7c0b1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f",
  "updated_at": "2026-09-08T10:00:00Z",
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
      "processed_at": "2026-09-08T09:58:11Z",
      "results_urls": [
        {
          "type": "report",
          "location": "verifier_self_storage",
          "url": "https://verify.example.org/reports/5e4d3c2b1a09f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c5b4a392817060.json",
          "sha256": "5e4d3c2b1a09f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c5b4a392817060"
        }
      ]
    }
  ]
}
```

**Entries are keyed by verifier identity, never by array position.** A writer
merging a new result MUST locate its own entry by `verifier.url` and leave
every other entry untouched; a reader looking for one verifier MUST match on
`verifier.url` rather than taking `source_code_verifications[0]`.

**A result root holds one entry per hash — the verifier's own.** The container
is an array because this document descends from a draft in which one document
gathered several verifiers' results for a hash, and because keying on identity
rather than position is the property worth keeping from it: a reader that
indexes `[0]` is correct until the day it is not, and nothing surfaces the
difference. Cross-verifier results are a different document with a different
`schema`, defined by the companion proposal — not more entries in this one.

#### 3.1 `verifier`

`url` is REQUIRED and is the identity (§2). `name` is OPTIONAL,
**self-claimed**, and MUST NOT be used as a key or read as an endorsement by
whoever relayed it. `logo_url` is OPTIONAL and is either a URI or an object
with `light` and/or `dark` URIs; see Security Concerns before rendering it.

#### 3.2 `status` and the verdict-conditional fields

`status` is `verified`, `mismatched`, or `unverified`. A consumer that does not
recognise a value MUST treat it as `unverified` — never reject the document.

`recipe_source`, `image_trust_level`, `source_sha256` and `processed_at` are
present exactly when `status` is not `unverified`. `rebuilt_hash` is present
exactly when `status` is `mismatched`. **An `unverified` entry is exactly
`{verifier, status}`** — every other field is forbidden on it.

This is a MUST rather than "these fields are optional" because the fields do
not exist yet at the moment an `unverified` entry is legitimately published —
see §4's `202`, where the job is queued, the rebuild that decides recipe
provenance has not run, and the build environment may still be resolving.

- `recipe_source` — where the build recipe came from: `on_chain_metadata` (the
  SEP-58 fields carried in the contract's SEP-46 meta) or `submitted` (supplied
  with the verification request).
- `image_trust_level` — how the build environment came about:
  `official_trusted` (an image the official Stellar pipeline publishes),
  `upstream_pinned` (composed by the verifier from pinned official components),
  `publicly_auditable` (digest-pinned with a public reproducible definition),
  or `arbitrary` (digest-pinned, provenance not established).

These two replace the Registry API draft's single `out_of_band` boolean, and
they are independent: where the recipe came from says nothing about how much
the environment that ran it can be trusted.

**The build inputs are SEP-58's, carried and not redefined.** `bldimg`,
`bldarg` and `bldopt` are the recipe as it was recorded. This SEP adds no
meaning to them: it does not define their vocabulary, and it does not require
any of them on a `verified` or `mismatched` entry — a verifier with nothing to
record for one omits it, and an `unverified` entry carries none of them under
the rule above. Two properties a carrier has to respect anyway.

`bldarg` is **ordered**, and nothing that carries it may sort or reorder it: a
reordered argument vector is a different build, and the document would then
describe a recipe that was never run.

**An absent `bldarg` and an empty one mean the same thing** — SEP-58's default,
`contract build`. A consumer MUST NOT read `[]` as an empty argument vector; a
producer MAY publish either. It is stated because the two spellings are
identical in effect and trivially different in code: a reader that takes `[]`
literally derives a recipe nobody ran, rebuilds to different bytes, and reports
a mismatch that is its own. `bldopt` needs no companion rule — it has no
default, so an empty one means no build options and says so.

#### 3.3 `results_urls` and `verified_source_code_uris`

`results_urls` links what the verifier published. Two axes, independent: `type`
is what the link points at (`report`, `provenance`, `attestation`, `sbom`,
`audit`), `location` is where the bytes live (`verifier_self_storage`,
`arweave`). A report and its permanent archive copy share a `type` and differ
in `location`.

`location` is named for the _relationship_ rather than the technology — a
verifier serving its own root from object storage, a plain web server or a CDN
is `verifier_self_storage` in all three cases. Naming the technology would have
made the vocabulary grow with deployment choices no reader cares about.

Every entry pointing at content the publishing verifier controls MUST carry
`sha256`. That is what lets a reader fetch the bytes and confirm they are the
ones the entry is about, from any mirror.

`sha256` is nevertheless OPTIONAL in the schema, and the gap is deliberate:
`provenance` and `attestation` links may point at bytes the verifier does not
control and cannot vouch for. The MUST binds the publisher for its own content;
the schema cannot distinguish the two cases, so it does not try.

The array is appended to and never reset: an archive copy arriving later is a
new entry, not a replacement.

`verified_source_code_uris` is where **this** verifier serves a retrievable
copy of the source that produced the match — `{location, url}` entries, same
`location` vocabulary. There is no `type` because every entry is the same kind
of thing, and no per-entry `sha256` because the entry's parent already carries
`source_sha256` over the same bytes.

#### 3.4 Merge rules

Per `(verifier, wasm_hash)`:

| Existing entry | New verdict                  | Published               |
| -------------- | ---------------------------- | ----------------------- |
| none           | verified or mismatched       | the new one             |
| mismatched     | verified                     | the verified            |
| **verified**   | **mismatched**               | **the existing stands** |
| verified       | verified, different source   | the newer verified      |
| mismatched     | mismatched, different source | the newer mismatched    |

Row 3 is load-bearing. Where anyone may submit any source for any contract, an
unqualified latest-wins lets a third party make a verified contract read
`mismatched` by submitting source that does not build. See Design Rationale.

`updated_at` is the last change to the document across all its entries,
including an archive reference added to an existing one. It is the clock a
bulk-load consumer synchronises on, so a writer that changes any byte MUST
advance it.

### 4. Verifier read API

**`GET /v1/wasms/{wasm_hash}.json`**

| Status | Body                                                                     |
| ------ | ------------------------------------------------------------------------ |
| `200`  | the status object                                                        |
| `202`  | a status object whose single entry is `{verifier, status: "unverified"}` |
| `400`  | error envelope; `error` ∈ `400_invalid_wasm_hash` \| `400_other`         |
| `404`  | error envelope; `error` is `not_found`                                   |
| `503`  | error envelope; `error` is `storage_unavailable`                         |

The `200` bytes SHOULD be identical to the static `wasms/{wasm_hash}.json`.

`202` means a verification for this hash is queued or running. It is not a
promise: a read request never causes a verification to start.

**This route's `400` is the one closed `error` vocabulary in this SEP**:
exactly `400_invalid_wasm_hash` and `400_other`, inherited from the Registry
API draft where those two were the only codes it defined. The restriction is
per _status_, not per route — the `404` and `503` above carry an envelope like
every other route, and adding one cannot break a draft-era client, which never
read a body on those statuses at all (see Appendix A).

This is the one route in this SEP that keeps a `.json` suffix, because its
`200` **is** the static document; see §7.

**`GET /v1/wasms`** — see §5.

### 5. Bulk load

Normative schema:
[`stellar-verification-page-1.0.schema.json`](../contents/sep-contract-verification-results/schemas/stellar-verification-page-1.0.schema.json).

```
GET /v1/wasms?order=asc&limit=200&cursor={cursor}
```

- `order` — `asc` or `desc`, default `asc`, echoed in the response.
- `limit` — an integer; a server MUST document its bounds and SHOULD accept at
  least `1..200`. A value outside them is a `400`, not a silent clamp: a
  consumer that asked for 500 and got 200 has no way to notice.
- `cursor` — from the previous page. Absent starts at the beginning.

`cursor` is **opaque**. The schema pins a format (`{timestamp}-{wasm_hash}`) so
that one implementation's pages are self-describing, but a consumer MUST NOT
parse, construct or compare cursors, and a cursor is valid **only within the
stream that issued it**: two streams ordered by different clocks can share a
format while meaning different positions. `null` means the end of the stream.

A verifier's page carries **pointers** — `{wasm_hash, updated_at}` — not
documents. The consumer fetches the status object it cares about. That keeps
enumeration cheap and, more importantly, keeps the result read at its source.

**The envelope is shared; the record shape belongs to the role serving the
stream.** This SEP defines the envelope and the verifier's record. Another SEP
MAY define a different record shape for a different role over the same `schema`
— the companion aggregation proposal does, with whole aggregated documents as
records — and a consumer knows which it will get because it knows what it
asked. A consumer MUST NOT infer the role from a record it did not expect.

Two rules consumers get wrong:

- **An empty page means caught up, not empty corpus.** It is a valid page.
- **A record MAY reappear on a later page.** The stream is ordered by
  publication update time, and a backfill advances it. Consumers upsert by
  `wasm_hash`; re-delivery is not duplication.

A verifier that serves no bulk load is readable per hash but not enumerable.
That is a conformance class, not a defect — but nothing can synchronise against
it, which is why `GET /v1/wasms` is a SHOULD rather than a MAY.

### 6. Errors

Normative schema:
[`stellar-verification-error-1.0.schema.json`](../contents/sep-contract-verification-results/schemas/stellar-verification-error-1.0.schema.json).

Every non-2xx body of the **API routes** in §§4–5:

```json
{
  "schema": "stellar-verification-error",
  "schema_version": "1.0",
  "error": "not_found",
  "message": "No verification result for that Wasm hash."
}
```

Clients branch on `error` and MUST tolerate codes they do not recognise. Adding
a code is not a breaking change; a client that treats it as one fails against
every deployment ahead of it. `message` is for display and debugging — wording
is not stable and MUST NOT be branched on.

The one closed vocabulary is `GET /v1/wasms/{wasm_hash}.json`'s **`400`** (§4).
Everywhere else it is open, and a server SHOULD document the codes it emits;
`not_found`, `storage_unavailable`, `invalid_request` and `rate_limited` are
the ones a client is most likely to meet — the first two because §4's read
route emits them, which is the route a consumer polls.

**The static result root is out of scope for this section, necessarily.** A
missing key under §2's root returns whatever the origin serving it produces —
an object store's XML, a web server's HTML — and no verifier can make a static
origin emit this envelope. A consumer reading the static form gets a bare
status code and cannot distinguish "no such hash" from "misconfigured origin";
that asymmetry is one of the reasons the dynamic route in §4 exists.

This is the one **document** here that is not closed to a producer: diagnostic
fields beside the four are permitted. See Design Rationale.

An aggregator serves this same envelope, on the routes the companion proposal
defines and under the same rules; that SEP does not redefine it.

Implementations should note that this applies to responses their framework
generates as well as the ones they write — an unmatched route's `404` and an
unhandled `500` are exactly where a client's envelope check gets tested.

### 7. Versioning and tolerance

Each document carries `schema` and `schema_version`, versioned independently of
this SEP and of each other. Adding a field is a MINOR; removing or redefining
one is a MAJOR.

**The producer/consumer split is normative per document, not one general
paragraph.** For each of the three:

- A **producer** writes exactly the fields its `schema_version` names.
- A **consumer** validates with `additionalProperties` relaxed, MUST accept a
  higher MINOR of a MAJOR it knows, and MUST NOT reject a document for a
  missing `schema`. A document written before this SEP has no `schema` field at
  all.
- A consumer MUST NOT reject a document for **a vocabulary value it does not
  recognise**, in any field carrying one — not only `status`. The vocabularies
  are `status` (§3.2), `recipe_source` and `image_trust_level` (§3.2), and a
  link's `type` and `location` (§3.3). Each is closed for a producer and open
  for a reader, because adding a value is a MINOR and this SEP already expects
  to: §3.3 names `ipfs` as a `location` candidate. Where an unrecognised value
  has a safe reading the SEP gives it (`status` reads as `unverified`); where
  it does not, the value is carried as it came and displayed rather than
  branched on.

  **A vocabulary is not the same as a fixed set**, and the distinction is worth
  stating because the rule is otherwise unbounded. `order`'s `asc`/`desc` (§5)
  is not a vocabulary: it is an echo of what the consumer asked for, a third
  value is a server contradicting the request rather than extending a list, and
  a page whose ordering a reader cannot determine is unusable rather than
  merely less detailed. A consumer MAY reject that.

  This rule is the one most easily lost in implementation, because it is
  invisible in a schema: a validator generated from the producer's enums looks
  correct, passes every test written against today's vocabulary, and drops a
  conformant peer's **entire document** the first time one adds a word.

That last clause is spelled out per document deliberately. Stated once as a
general principle it gets implemented once, on the document the implementer was
looking at; the failure mode is not a validation error but a document silently
dropping out of whatever is reading it, which nothing surfaces.

**One opening in the schemas.** `stellar-verification-error` is open at the
document level — a producer may add diagnostic fields (§6). The status object
and the page are `additionalProperties: false`. The companion aggregation
proposal adds a second, of a different kind and for a different reason, on a
document defined there.

**Routes.** A path ending in `.json` denotes a document a static origin can
serve as-is. Dynamic routes — parameterised, or answering states a file cannot
— carry no suffix. The one deliberate overlap is
`GET /v1/wasms/{wasm_hash}.json` in §4, whose `200` is the static bytes.

A `MAJOR` of this SEP's documents does not oblige the companion aggregation
proposal to move with it, and the reverse holds too: the two version
independently, which is the point of `schema` naming the document rather than
the SEP.

Two hazards worth naming, both found by implementing this:

- On routers with path-to-regexp semantics, a `{wasm_hash}` parameter will
  happily swallow a literal `.json` suffix. If both spellings are served,
  declare the suffixed one first — and assert on the response **body**, since
  both return `200`.
- A route a consumer holds in its own configuration cannot be renamed
  atomically — nobody can redeploy every reader at once. Serve the old spelling
  as a deprecated alias with `Deprecation` and `Sunset` headers for a stated
  window; otherwise a consumer nobody re-seeded loses the route silently, and
  reads it as the verifier having nothing.

## Limitations

- **Submission is out of scope.** Deliberately: see Motivation.
- **Aggregation is out of scope**, and so is everything it needs: no verifier
  discovery, no list document, no rule for combining two verifiers' answers. A
  consumer of this SEP alone reads one verifier at a time, from a base URL it
  was given out of band. The companion _Contract Verification Aggregation_
  proposal is where that is addressed.
- **Nothing is signed.** This SEP defines no signature scheme and no key
  distribution. See Design Rationale.
- **No extension point.** 1.0 defines no namespaced extension object. A
  producer that needs one today has only the error envelope's openness, which
  is not a general mechanism. This is a candidate for a later MINOR, once there
  is a second implementation whose need is concrete.
- **No per-entry verification history.** An entry is the current result. The
  audit question is answered by the report artifacts in `results_urls` plus the
  bulk-load stream. History could arrive as a MINOR if a consumer needs it.
- **`logo_url` is declared and unproven.** It is in the schema, no reference
  implementation populates it, and Security Concerns says what a renderer must
  not do with it. It is carried because a UI listing verifiers wants it, not
  because anything has exercised it.
- **Verifier internals are out of scope** — sandboxing, build isolation, abuse
  controls, and how `image_trust_level` is arrived at.
- **The verifier manifest is not defined here.** Implementations serve a
  self-description — build-image and source-mode policy, retention, whom to
  contact — and this SEP specifies neither its shape nor a route to it.
  Everything a consumer needs is served from the result root in §§2–5.
  Standardising it needs a consumer that reads it for something the result root
  does not already answer.
- **SEP-58 vocabulary changes are out of scope.** This SEP carries those
  fields; it does not redefine them.

## Design Rationale

### Nothing is signed

The Registry API draft and earlier revisions of this SEP carried detached
signatures over the report, with the verifier's public key distributed
alongside its result root. It was implemented and then removed.

The premise did not survive the question _what is the signature buying?_

A verification result is not a claim that needs trust. It is a claim the reader
can **re-run**: the recipe is published, the source hash is published, and
anyone can rebuild and compare. Signing it substitutes _who said it_ for _you
can check it_, which is the weaker property.

The anchor was circular besides. Wherever a consumer learned the key, it had
learned the result root from the same place, and reached it over TLS — not an
independent root, a second link on a closed chain. And there is nothing here
whose forgery is dangerous in the way a signed binary's is: this SEP publishes
no runnable artifact.

What actually does the integrity work is `sha256` on every `results_urls` entry
(§3.3). A reader fetching a report from a mirror, a cache, or an archive can
confirm the bytes are the ones the entry names. That is offline-checkable and
needs no key.

Implementing the signature is what made the question answerable rather than a
matter of taste: it wanted a key to distribute, a rotation list for archived
reports, a strkey validator with a checksum obligation, one more document type,
and the first secret credential on the publish path. Weighed against a property
`sha256` already provided.

Reopening it needs a threat the reproducibility argument does not answer.

### The result root is the identity

A verifier supplies a URL, plus an optional self-claimed `name`. Everything
that keys on a verifier keys on the URL, because the same result root **is**
the same verifier — which is why §2 spells the comparison out to a depth that
otherwise looks excessive, and why the field is REQUIRED while `name` is not.

An earlier revision let whoever relayed an entry attach its own label and its
own local id beside the peer's block. Both are gone: a label that overwrites
the peer's `name` misattributes a claim, and an id minted by one reader means
nothing to the next.

A reader wanting a name it can hold someone to derives one from the URL — its
certificate, or the reader's own records. That is a UI concern, not this
document's.

The same reasoning names the field `url` rather than `cdn_root`: **a public
contract must not assume a CDN.** A verifier may serve its root from object
storage, a plain web server, or anything else.

### A verified result is not displaced by a mismatch

Row 3 of §3.4's merge table is the anti-defacement rule, and it draws the
obvious objection: _does this let a verifier suppress negative results?_

It does not. The row is scoped to one `(verifier, wasm_hash)` pair and to
**re-submission of different source**. A `mismatched` result for source that
was already `verified` means the _new_ submission does not build to the
deployed bytes — which says nothing about the deployed contract and everything
about what was just submitted. The earlier `verified` entry names its own
`source_sha256`, so a reader can check the claim it actually makes.

Without the row, any third party can degrade any verified contract by
submitting source that does not build. With it, the worst a submitter achieves
is a result that is not published.

Disagreement _between verifiers_ is untouched by this. This row governs one
verifier's own entry about one hash; nothing here lets a verifier suppress
another's, and reporting that disagreement is the companion aggregation
proposal's job.

### The error envelope is the one open document

The other two documents are closed to a producer, and that is what makes a
`schema_version` mean something: a consumer can rely on a document of a known
version carrying exactly the fields that version names.

An error body is different in kind. It carries one field a consumer parses
(`error`) and one for a person (`message`); everything else is operator
diagnostics. Closing it would delete text an operator debugs from, to buy a
consistency no consumer asked for. So the four fields are required and a
producer may send more.

### Two axes on `results_urls`

`type` and `location` are separate because they answer different questions. A
report and its Arweave copy are the same artifact — same `type`, same `sha256`
— stored in two places. Collapsing them into one axis (`report` vs
`report_arweave`) would make a consumer parse the vocabulary to learn what is a
category and what is a storage detail, and would grow combinatorially with each
new location.

## Security Concerns

**Every URL in these documents is attacker-influenced.** `logo_url`,
`source_uri`, and the entries of `results_urls` and `verified_source_code_uris`
are strings a verifier published about source somebody else submitted. A
consumer MUST NOT dereference any of them as a side effect of rendering or
validating a document, MUST NOT send credentials, cookies or ambient authority
with a fetch it does make, and MUST NOT proxy one from a host that can reach a
network a reader cannot. A renderer that inlines `logo_url` is loading a third
party's bytes into its own page, and tells that third party who is looking at
which contract.

**A server-side reader is a confused deputy.** Fetching a result root on a
user's behalf is a request to a URL the user chose: resolve and reject
loopback, link-local and private-range destinations, cap the response size and
the time spent, and do not follow a redirect out of the origin the reader
started at. The same applies to a redirect chain that begins at a URL inside a
document.

**`name` is self-claimed and `verifier.url` is the only identity.** A consumer
MUST NOT key on `name`, and a UI that shows it without showing the result root
invites impersonation — two verifiers may claim the same name, in homoglyphs a
reader cannot tell apart. §2's normalisation is the identity comparison;
hand-rolled string equality over unparsed URLs is how two readers come to
disagree about how many verifiers they are looking at, each internally
consistent.

**A `200` is not a document.** A static origin answers a missing key with its
own error page, and a misconfigured one answers everything with a `200`. A
consumer MUST check `schema` before believing anything else in a body, and MUST
NOT infer a verdict from a status code.

**These documents are mutable and unsigned.** A result root can change what it
says about a hash at any time, and this SEP defines nothing that detects a
rollback. A reader that needs a point-in-time claim retains the bytes it read,
and uses the `sha256` on a `results_urls` entry to confirm an archived report
is the one that entry named. That digest is the only integrity anchor here —
see Design Rationale for why there is no second one.

**A read never starts work.** §4's `202` reports that a verification is already
queued or running. An implementation that starts one on read turns an
unauthenticated `GET` into a way to spend its build capacity, for any hash an
attacker can name.

**Publishing source publishes source.** `verified_source_code_uris` serves a
retrievable copy of what was submitted. A verifier accepting private
submissions MUST NOT populate it for them; there is no field here that marks a
copy as restricted, and a reader is entitled to fetch what the document links.

## Appendix A: Migrating from the Registry API draft

**Non-normative.** This appendix records how a document written under the
Contract Verification Registry API draft
([stellar-protocol#1944](https://github.com/stellar/stellar-protocol/pull/1944))
relates to this SEP. Nothing here adds a requirement; §§1–7 are the normative
text.

The draft defines one route and one document. It has no bulk load, no
aggregation, no verifier discovery — a service "publishes its base path out of
band" — and no error envelope beyond a body shape for the one route.

| Draft                              | Here                                  |
| ---------------------------------- | ------------------------------------- |
| no `schema` field                  | `schema` + `schema_version`           |
| `GET /wasms/{hash}.json`           | `GET /v1/wasms/{hash}.json`           |
| — (no bulk load)                   | `GET /v1/wasms` (§5)                  |
| — (no discovery)                   | the companion aggregation proposal    |
| `out_of_band: bool`                | `recipe_source` + `image_trust_level` |
| `results_urls: string[]`           | `{type, location?, url, sha256?}`     |
| `verifier: {name, url?}`           | `verifier: {url, name?}`              |
| `{schema_version, error, message}` | adds `schema`; vocabulary opened      |
| non-2xx other than `400`: no body  | error envelope on every API status    |

Fields this SEP carries that the **draft does not define** — they come from
SEP-58 and from implementation experience, not from #1944: `bldarg`,
`source_sha256`, `source_uri`, `verified_source_code_uris`, `rebuilt_hash`.

**The last row reverses an explicit rule, not an omission.** The draft's own
error schema says: "The body a `400 Bad Request` MAY carry to disambiguate why
the request was rejected. Other non-2xx statuses are signaled by status code
and define no body." This SEP gives every API status an envelope (§6), which is
why §4's `404` and `503` name codes the draft had no room for. A draft-era
client is unaffected: it never read those bodies.

That rule is also load-bearing for an implementer migrating _from_ the draft —
a service built to it will have bodyless `404` and `503` arms, and they are the
part of the read route this SEP changes rather than extends.

**`out_of_band` maps to `recipe_source: "submitted"`, and the mapping is a
choice.** The draft describes `out_of_band` as a verification "established
outside SEP-58's reproducible-build mechanisms", which reads on one hand as
_where the recipe came from_ and on the other as _how much the build image can
be trusted_. This SEP splits those into two fields precisely because they are
independent, and maps the boolean onto the chain-of-custody reading. Under the
other reading the mapping is lossy: a migrator cannot recover
`image_trust_level` from the boolean and must supply it from its own records.

**The `verifier` change is semantic, not just structural.** In the draft, `url`
is "a URL identifying the verifier **or describing its methodology**" and
`name` is the required field. Here `url` is the result root (§2). Two
consequences for a migrator:

- A draft document may carry **no** result root at all — `url` was optional.
- A draft document that _does_ carry one may be carrying a documentation page.
  Copying it forward imports a methodology URL as an identity, and every reader
  downstream then treats it as a place to fetch documents from.

So a writer upgrading **its own** entry may supply its own result root — that
is recovering a value it knows, not inventing one — while for anyone else's
there is nothing to recover and guessing is the failure this describes. In
practice the upgrade refuses a foreign legacy entry and the caller leaves the
document alone rather than publishing something the schema rejects.

**`location` has no value for `ipfs://`.** The draft's own examples carry
`ipfs://` and `ar://` entries. 1.0 defines `verifier_self_storage` and
`arweave` only; a legacy entry that is neither migrates **without** `location`,
which the schema permits. Adding `ipfs` is a candidate for a MINOR once a
producer wants it.

**Migrate on write, not in a sweep.** A document in the draft shape is read
tolerantly and upgraded the next time any writer touches it. No batch job, and
no window where some documents are readable and others are not.

## Changelog

- `0.1.0` — Initial draft, building on the Contract Verification Registry API
  draft
  ([stellar-protocol#1944](https://github.com/stellar/stellar-protocol/pull/1944)).
