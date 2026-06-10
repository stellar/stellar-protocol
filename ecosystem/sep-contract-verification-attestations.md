## Preamble

```
SEP: 0000
Title: Soroban Contract Build Attestations and Content-Addressed Distribution
Author: Ethan Frey <@ethanfrey>
Status: Draft
Created: 2026-06-10
Updated: 2026-06-10
Version: 0.1.0
Discussion: TBD
```

## Simple Summary

Define a normalized, hashable build claim, a cheap signed verification result over that claim, and a content-addressing convention so that claims, source archives, and wasm bytes can be distributed and looked up by hash. Builds on the build-environment vocabulary defined in the companion reproducibility SEP; adds the missing layer that lets independent verifiers produce byte-identical attestations and publish them where anyone can find them.

## Dependencies

- Companion SEP: [SEP-58](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0058.md): Soroban Contract Build Reproducibility and Verification (the "vocabulary SEP"). Defines the `bldimg` and `bldopt` build-environment fields this SEP packages into a claim, and the source-identity fields. This SEP consumes the build-environment fields verbatim, promotes the source hash to a required claim field, and treats the source URL as an optional retrieval hint outside the claim.
- [SEP-46](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0046.md): Contract Meta. The `contractmetav0` custom section from which a claim is reconstructed when the fields are embedded on-wasm.
- [SEP-55](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0055.md): Soroban Smart Contracts Build Verification (informative). Defines an attestation produced by a trusted CI. This SEP defines an attestation produced by *any* verifier over an independent rebuild; the two attest to different things and can coexist on the same contract.

## Motivation

The vocabulary SEP makes a build reproducible: given the fields, a third party can set up a matching environment and rebuild. But it deliberately says nothing about what a verifier then *does* with the result. In practice three gaps remain.

First, two honest verifiers with the same inputs have no agreed-upon way to refer to "the same build." They each know they rebuilt and matched, but there is no shared identifier they can both compute and compare. Without a canonical claim, verification outcomes cannot be deduplicated, aggregated, or cross-checked.

Second, a verification result is only useful if it can be published cheaply and trusted selectively. A consumer should be able to see "verifier X, whom I trust, rebuilt this and got a match" without rebuilding themselves, and without trusting a single central registry. That requires a signed, self-describing result keyed to the claim.

Third, the fields point at retrieval channels (`source_repo`, `tarball_url`) whose contents can drift even when a commit SHA or tarball hash is recorded. URLs change, hosts disappear, and a git ref can be force-pushed. Anything a verifier needs to reach a verdict should be addressable by the hash of its bytes, with URLs demoted to retrieval hints.

This SEP closes those three gaps with a normalized claim, a signed result, and a content-addressing convention, in that order.

## Abstract

This SEP defines:

1. A **build claim**: a canonical XDR structure assembled from the build-environment fields, the source hash, and the claimed wasm hash, whose SHA-256 is a stable identifier any verifier can recompute.
2. A **content-addressing convention**: wasm bytes, source archives, and build claims are identified by the SHA-256 of their canonical bytes; URLs are hints, not trust anchors.
3. A **canonical source archive**: a deterministic way to reduce a source tree (typically a git commit) to a single hashable file, so the source hash is reproducible.
4. A **signed verification**: a small, cheap-to-publish record binding a claim hash to a result (match / no-match / did-not-run) and a verifier identity, signed with a Stellar key and communicated either out of band or as a registry contract call.
5. **Claim reconstruction and meta reproduction**: how a verifier derives a claim from a wasm's embedded meta, and re-embeds that meta byte-for-byte on rebuild, without storing meta about meta.

## Specification

Capitalized keywords (MUST, SHOULD, MAY) are to be interpreted per RFC 2119. All hashes are SHA-256 unless stated otherwise. Content addresses are written as the lowercase hex encoding of the 32-byte digest.

### 1. The build claim

A build claim captures *what was built* (the claimed wasm) together with *how and from what* (the build-environment fields and the source hash), in a form whose serialization is canonical so that its hash is reproducible across implementations.

```rust
type Hash = [u8; 32];

// A build-environment field as defined in the companion reproducibility SEP.
// `key` is one of: bldimg, bldopt. `bldopt` MAY repeat.
struct BuildField {
    pub key: String,
    pub val: String,
};

struct BuildClaim {
    pub claimedWasmHash: Hash,      // SHA-256 of the wasm bytes being attested to
    pub sourceHash: Hash,           // SHA-256 of the canonical source archive (section 3)
    pub fields: Vec<BuildField>,    // build-environment fields, canonically ordered
};
```

`sourceHash` is mandatory: it is the content address of the source the wasm was built from, and a claim without it cannot be verified by rebuild. It is given a typed field of its own rather than living in `fields` because it is essential and fixed in meaning, whereas `fields` holds the open-ended build-environment vocabulary. The remaining source-identity information from the vocabulary SEP collapses to an optional *source URL* — a retrieval hint that helps a verifier locate the source bytes. The source URL is NOT part of the claim and never enters the claim hash, because URLs drift while the hash must not; when the source can be found out of band, the URL may be omitted entirely.

The `fields` array MUST be ordered canonically: ascending by `key` (byte-wise), and within an equal `key` ascending by `val` (byte-wise). A producer MUST NOT include a field whose value is the baseline default described in the vocabulary SEP; only deviations are recorded, so two builds that differ only in default-equal options yield the same claim. Producers MUST NOT include duplicate `(key, val)` pairs.

The **claim hash** is `SHA-256(XDR(BuildClaim))`. Because the encoding and ordering are fully determined, every verifier that assembles the same fields, source hash, and wasm hash computes the same claim hash. The claim hash is the stable identifier used everywhere else in this SEP.

### 2. Content-addressed distribution

Three object kinds are content-addressed. The address of an object is the SHA-256 of its canonical bytes:

| object | canonical bytes | address |
|---|---|---|
| wasm | the deployed wasm bytes | `claimedWasmHash` |
| source archive | the canonical archive bytes (section 3) | `sourceHash` |
| build claim | `XDR(BuildClaim)` | the claim hash |

The wasm address is the value Soroban already uses, not a parallel one. Each contract references its code by a 32-byte wasm hash that is the SHA-256 of the file, and a Soroban RPC server can return the full bytecode for a given hash today. So `claimedWasmHash` is exactly the digest the ledger and RPC already expose, and the same one IPFS and similar content-addressed stores key on. A verifier can obtain the wasm from RPC, from an explorer, or from any content-addressed store using that single value.

Retrieval is out of band: this SEP specifies how an object is *named*, not where it is fetched from, mirroring the content-addressed source case in the vocabulary SEP. An implementation MAY expose any retrieval channel (an HTTP gateway, an on-chain registry, a peer-to-peer store); whatever channel is used, the consumer MUST verify that the retrieved bytes hash to the requested address before relying on them. A source URL, when provided, is a hint that MAY speed retrieval and MUST NOT be treated as authoritative: the source archive is trusted because its bytes hash to `sourceHash`, not because of where they came from.

### 3. Canonical source archive

`sourceHash` is the SHA-256 of a *canonical source archive*: a single file produced from the source tree in a way any verifier can reproduce byte-for-byte. Because the hash is load-bearing, the archive construction MUST be deterministic; an archive that varies by who built it, when, or with which tool version cannot serve as a content address.

> **This section is not yet finalized.** The construction below is a starting point. The ecosystem needs to converge on one exact, tested recipe — and ideally pin the archiving tool — before this is normative.

For a git source, the natural basis is the tree at a pinned commit:

```
git archive --format=tar.gz <commit> > source.tar.gz
```

Given a fixed commit, `git archive` is a reasonable starting point because file contents and per-entry mtimes are determined by the commit object rather than by wall-clock time. Several details still break reproducibility and MUST be controlled:

- **gzip non-determinism.** gzip embeds a timestamp and the original filename in its header, so the same tar compresses to different bytes each run. Either produce the gzip with `--no-name`/`-n` (`git archive --format=tar <commit> | gzip -n`), or — preferably — define `sourceHash` over the *uncompressed* tar and treat compression as transport only, sidestepping gzip entirely.
- **git version drift.** `git archive` output (pax/extended headers, the embedded commit-id comment, default permissions and ordering) can differ across git versions. The recipe SHOULD pin a git version, or the archiving tool SHOULD be part of the pinned build image so the same tool always produces the archive.
- **attribute and line-ending filters.** `.gitattributes` directives (`text=auto`, `export-subst`, `export-ignore`) rewrite or drop content during archiving. Verifiers MUST apply identical attribute handling; setting `core.autocrlf=false` and fixing or disabling export filters keeps the bytes stable.

For a non-git source, `sourceHash` is simply the SHA-256 of the agreed archive bytes; the same determinism requirements apply. Either way the archive is content-addressed by `sourceHash` per section 2, so a verifier obtains exactly the bytes that were hashed and is never exposed to URL drift.

There is a relevant discussion here (TODO).

As an alternate proposal for this section: if a canonical, reproducible git archive tools is deemed too complex, the original builder can run this archive tool and push the resulting file to IPFS and later reference that file by sha256 hash. This only requires a robust archiving tool that works, not that it must produce byte-identical output on multiple runs on different machines and versions.

### 4. Signed verification

A verification is the cheap, publishable result of an attempt to reproduce a claim. It is small by design: it carries the claim hash, not the claim, so it is cheap to publish to the blockchain, while the full claim data can be stored off-chain. Consumers can scan many verifications and resolve only the claims they care about, as the hash -> claim lookup is easily resolvable by any off-chain client. 

```rust
enum VerificationResult {
    VERIFICATION_MATCH        = 0, // rebuilt wasm hash equals claimedWasmHash
    VERIFICATION_NO_MATCH     = 1, // rebuild succeeded, hash differs
    VERIFICATION_DID_NOT_RUN  = 2,  // environment could not be reproduced
};

struct Verification {
    pub claimHash: Hash, // SHA-256(XDR(BuildClaim)) from Section 1
    pub result: VerificationResult,
}
```

**Out-of-band attestation.** The `SignedVerification` bytes can be stored in a content-addressed store (section 2) or any registry, and the address is announced. The detached `sig` carries the verifier's signature, so the record is self-verifying wherever it ends up.

```rust
struct SignedVerification {
    pub verification: Verification,
    pub pubkey: PublicKey,
    pub sig: Signature,
}
```

`PublicKey` and `Signature` are the existing Stellar XDR types, so a verifier's identity is an ordinary Stellar account and tooling can reuse existing key handling.

The signing payload is domain-separated to prevent a verification signature from being valid in any other context:

```
payload = SHA-256( "SEP-XXXX-verification:v1" || claimHash || result-as-u32-BE )
sig     = Sign(verifier-secret, payload)
```

A consumer verifies a `SignedVerification` by recomputing `payload` and checking `sig` against `verifier`. A `VERIFICATION_MATCH` from a verifier the consumer trusts means: that verifier reconstructed the claim, reproduced the build environment, rebuilt, and the rebuilt wasm hashed to `claimedWasmHash`. Trust in the verdict is exactly trust in `verifier`; this SEP does not centralize it. Consumers SHOULD aggregate verifications from independent verifiers and weight them by reputation, as no single verification is self-justifying.

The signed claim hash and result are the payload; how they travel is open, and two channels are expected.

**On-chain registry call.** More commonly, the verifier submits the result by invoking a registry contract — for example a function `verify(claim_hash: BytesN<32>, result: u32)` — in a transaction signed by the verifier's account. Here the transaction envelope signature *is* the verifier's signature over the call arguments, so a separate detached `sig` is redundant for this channel. The registry SHOULD emit an event (for example, topics `("verify", verifier, claim_hash)` carrying the result) so consumers and indexers can observe verifications without scanning call data. Multiple registries MAY adopt the same function name and event shape, making a single submission convention portable across them so a consumer reads any compatible registry the same way.

Whatever the channel, the key elements are identical: the canonically constructed claim, its hash, and a signature over `(claim_hash, result)` by the verifier identity. The transport does not change what is being attested.

### 5. Reconstructing a claim and reproducing meta

A claim MUST be reconstructable so that the claim hash is not a number a producer asserts but one a verifier derives. The reconstruction also avoids a recursion: build options are part of what determines the wasm, but if a verifier had to embed "the meta that records the meta" the description would never terminate.

The resolution is that vocabulary fields are stored as plain data and the wasm's embedded meta is *read*, never re-synthesized:

1. Fetch the original wasm by `claimedWasmHash` (e.g. from RPC, section 2) and read its `contractmetav0` section (per SEP-46).
2. From that meta, collect the build-environment fields (`bldimg`, `bldopt`) and the source-hash entry. Union the build-environment fields with any supplied externally (registry, verification service, or out-of-band), with external fields filling gaps but never overriding on-wasm values for the same `(key, val)`.
3. Drop any build-environment field equal to its baseline default; canonically order the remainder per section 1.
4. Set `claimedWasmHash` to the SHA-256 of the wasm bytes as received, and `sourceHash` to the source-hash entry (or to an externally supplied source hash when not on-wasm).
5. The claim hash is `SHA-256(XDR(BuildClaim))`.

A verifier then reproduces the build environment from the claim's `bldimg` and `bldopt` fields, obtains the source archive by `sourceHash` (section 3), rebuilds, and compares the rebuilt wasm's hash to `claimedWasmHash`. The recorded `bldopt` entries are replayed as build arguments; they are never themselves re-recorded as new meta.

Embedded meta is part of the wasm bytes, so a rebuild only hashes to `claimedWasmHash` if its `contractmetav0` section is byte-identical to the original's. The verifier therefore MUST extract the complete `contractmetav0` section from the original wasm (fetched in step 1) and embed exactly those meta entries into the rebuild — every entry, in the same form, including entries this SEP does not define and entries the verifier does not interpret. The verifier does not need to understand a meta entry to reproduce it; it copies it. Any divergence in the meta section — a missing entry, a reordered one, an extra one — changes the wasm hash and produces a spurious `NO_MATCH`. The reproducibility tooling SHOULD provide a way to inject the captured meta verbatim so this does not depend on the verifier re-deriving each entry by hand.

A wasm whose vocabulary fields are entirely on-wasm yields a claim derivable from the wasm alone, which is the strongest reproducibility position: the claim hash depends on nothing the verifier has to be told.

## Limitations

- This SEP defines a claim format, a naming convention, and a signature; it does not define a registry API, a retrieval protocol, or a reputation system. Those are left to tooling, as in the vocabulary SEP.
- A signed `VERIFICATION_MATCH` attests that some source produces some bytes in some environment. It says nothing about whether the source is correct, audited, or non-malicious. That is an orthogonal concern, unchanged from the vocabulary SEP.
- Content addressing guarantees integrity of bytes once obtained; it does not guarantee availability. Whether a claim, source archive, or wasm can actually be fetched is the consumer's problem.
- Canonicalization correctness is essential: an implementation that orders `fields` differently, or includes a default-equal field, computes a different claim hash and fails to interoperate. Conformance tests SHOULD cover ordering and default elision explicitly.
- The canonical source archive recipe (section 3) is not yet finalized; until the ecosystem fixes one exact, tested construction, two verifiers can compute different `sourceHash` values for the same tree.
- Byte-identical meta reproduction (section 5) depends on the build tooling being able to re-embed captured meta verbatim, including entries the tool itself normally generates. If the tool cannot reproduce a tool-written entry exactly, the rebuild will not match even when source and environment are correct.

## Design Rationale

**Why XDR rather than sorted JSON?** The claim hash must be reproducible to the byte. XDR has a single canonical encoding for a given value, so canonicalization is structural rather than a set of JSON rules (key ordering, number formatting, whitespace, Unicode normalization) that each implementation must get identically right. XDR is also already the encoding of `contractmetav0` and the rest of Stellar, so the same tooling applies. A JSON projection is fine for display; the hash is computed over XDR.

**Why hash the claim instead of signing it directly?** Separating the claim (large, shared, content-addressed) from the verification (small, per-verifier, signed) means many verifiers attest to one claim without each re-storing it, and a consumer can deduplicate verdicts by claim hash. It also makes the claim independently citable: a registry, an explorer, and a wallet can all refer to the same claim hash without coordinating.

**Why SHA-256 for the wasm address?** Reusing the ledger's existing wasm hash avoids inventing a second identifier for the same bytes. Soroban references contract code by the SHA-256 of the file and RPC serves bytecode by that hash, so a claim binds directly to what the network already points at, with no translation step. The artifact stays reachable through tooling that already exists, and through IPFS-style stores that key on the same digest.

**Why reuse Stellar `PublicKey`/`Signature`?** A verifier identity is then an ordinary account, publishable in a `stellar.toml`, verifiable with existing libraries. This is the concrete form of the signed-build idea raised in the discussion thread; making the key a Stellar account lets a builder or a hosted service prove "we produced this" with infrastructure that already exists.

**Why domain-separate the signature?** A bare signature over a hash can be lifted into any other protocol that signs hashes with the same key. Prefixing a version-tagged context string binds the signature to this use, so a verification can never be replayed as, say, a transaction authorization or an SEP-10 challenge.

**Why three results rather than a boolean?** `DID_NOT_RUN` is distinct from `NO_MATCH`: the former means the verifier could not even reconstruct the environment (image unavailable, source unreachable), the latter means it rebuilt and got different bytes. Collapsing them would let an availability failure masquerade as a verification failure, which is both unfair to the builder and misleading to the consumer.

**Why read meta from the wasm instead of storing it alongside?** Build options influence the wasm, so a naive design records them as meta — but that meta is itself part of the build and would need its own meta to describe it, without end. Treating the on-wasm fields as authoritative data to be read, and replaying `bldopt` as arguments rather than re-embedding them, terminates the regress and makes the claim derivable from the artifact.

**Relationship to SEP-55.** SEP-55 attests that a trusted CI compiled the wasm; the consumer trusts the CI's signing infrastructure and skips rebuilding. This SEP attests that a verifier *independently rebuilt* the wasm; the consumer trusts the verifier's rebuild rather than the original builder's CI. A contract can carry vocabulary fields supporting rebuild, a SEP-55 attestation, and any number of these verifications at once, and a consumer picks the path matching its threat model.

## Security Concerns

- **Verifier honesty.** A verifier can sign a false `VERIFICATION_MATCH`. The signature proves *who* attested, not that the attestation is true. Consumers SHOULD require corroboration from independent verifiers and weight by reputation.
- **Image and toolchain trust.** Inherited unchanged from the vocabulary SEP: a digest-pinned `bldimg` guarantees identical bytes but not an honest toolchain. A malicious image can emit attacker-chosen bytes that nonetheless reproduce. Verifiers SHOULD restrict `bldimg` to an allowlist of independently vetted images and SHOULD disclose their own toolchain, since the verifier's environment is itself part of the rebuild.
- **Claim grinding.** Because the claim hash is derived from public inputs, anyone can compute the claim hash for any wasm. This is intended: the claim hash is an identifier, not a secret. Security rests on the signature over the result, not on the claim being unguessable.
- **Signature replay across versions.** The domain-separation string is versioned (`:v1`). A future change to the payload format MUST bump the version so old and new signatures cannot be confused.
- **Registry trust.** A registry keyed by claim hash can omit or reorder verifications. Consumers SHOULD treat a registry as a discovery convenience and re-verify the signatures of any verifications it returns rather than trusting its curation.

## Appendix A: Worked example

Take the wasm from the discussion thread. The verifier fetches the original wasm by its hash (e.g. from RPC), reads its `contractmetav0` section, and collects the build-environment fields and the source hash. In canonical order the claim's build-environment fields are:

```
bldimg = docker.io/stellar/stellar-cli@sha256:cb2fc3...
bldopt = --manifest-path=contracts/foo/Cargo.toml
bldopt = --optimize
```

with the source identified by hash:

```
sourceHash = 3a7b...   (SHA-256 of the canonical source archive, section 3)
```

A source URL (`https://github.com/user/my-contract` at commit `abc1234...`) MAY accompany the claim as a retrieval hint, but is not part of the claim hash.

It sets `claimedWasmHash` to the SHA-256 of the wasm, encodes the `BuildClaim`, and computes:

```
claimHash = SHA-256(XDR(BuildClaim)) = 9f0a...   (the shared identifier)
```

It obtains the source archive by `sourceHash`, reproduces the environment (pull `bldimg` by digest), and rebuilds with the recorded `bldopt` flags. Crucially, it re-embeds the original wasm's entire `contractmetav0` section into the rebuild so the meta is byte-identical. The rebuilt hash equals `claimedWasmHash`, so it records `VERIFICATION_MATCH` and either:

- signs `SHA-256("SEP-XXXX-verification:v1" || 9f0a... || 0)` with its Stellar key and publishes the `SignedVerification` out of band, or
- submits `verify(9f0a..., 0)` to a registry contract in a transaction signed by `GBVERIFIER...`, letting the envelope signature stand in for the detached one.

A wallet that trusts `GBVERIFIER...` resolves the claim hash to confirm which build it refers to, checks the signature (or reads the registry event), and shows the contract as verified — without rebuilding anything. A second, independent verifier attesting to the same `claimHash` raises the consumer's confidence without any coordination between the two.

## Appendix B: Storage convergence (non-normative)

This SEP names objects by hash but does not say where they live, and mandates nothing here. For the ecosystem to interoperate in practice, however, claims and source archives must be *retrievable*, not merely nameable. It would be valuable to converge on at least one shared, well-supported storage solution so any consumer can resolve a claim hash or source hash without bespoke integration per verifier.

Some possibilities, not mutually exclusive:

- **IPFS** — content addressing is native; a SHA-256-keyed object maps cleanly to a CID, and any participant can pin what it cares about.
- **Arweave** — durable, pay-once storage suited to artifacts meant to stay verifiable for the life of an immutable contract.
- **Verifier-hosted retrieval** — because a verifier produces the very bytes it hashes (the claim, and often the source archive), it can serve them over plain HTTP or any protocol at near-zero marginal cost; a small convention (a well-known path keyed by hash) would make such hosts interchangeable.

A reasonable end state is that the same hash resolves through several of these, so availability does not depend on any single host. Converging on a shared convention is left to a follow-up discussion; the only property this SEP requires is that whatever serves an object, the consumer verifies the bytes against the requested hash before trusting them (section 2).

## Changelog

* `v0.1.0` - Initial draft. Defines the build claim, content-addressing convention, signed verification, and claim reconstruction as a companion to the build-environment vocabulary SEP.
