## Preamble

```
SEP: TBD
Title: Contract Metadata URI
Author: Farbod Ghasemlu <@farbodghasemlu>
Track: Standard
Status: Draft
Created: 2026-06-22
Updated: 2026-06-22
Version: 0.1.0
Discussion: https://github.com/orgs/stellar/discussions/1966
```

## Simple Summary

This SEP defines a single, optional contract interface, `metadata_uri() -> String`, that lets any Soroban contract advertise a URI pointing to a document that describes it. The interface standardizes only the pointer. It is transport-agnostic (https, ipfs, or other content-addressed schemes) and payload-agnostic (the format of the document it points to is intentionally out of scope and may be defined by a separate SEP).

## Related Work

- SEP-1 (`stellar.toml`): one possible target for the URI in the asset case.
- SEP-50 `token_uri`: the per-token analog of this contract-level pointer.
- SEP-46 (Contract Meta): Wasm-level, build-time metadata, which this complements rather than replaces.

## Motivation

There is no standard way for a Soroban contract to advertise where its descriptive metadata lives. The closest existing pieces each miss this case:

- SEP-50's `token_uri` is per-token, with no notion of the contract or collection as a whole.
- SEP-1 is asset-focused and bound to DNS plus https, so it fits poorly for generic, non-asset contract metadata (descriptions, documentation links, "what this contract is").
- SEP-46 contract meta is stored in the Wasm and fixed at build time, so it cannot express mutable, per-instance information.

As a result, builders improvise in incompatible ways. The Tansu project reused the SEP-1 format to describe registered projects and found it too asset-focused to be a good fit; Soroban Domains built its own key-value database for a similar need. Two independent teams solving the same problem differently is the case for standardizing at least the discovery layer, so that wallets, explorers, and indexers can find a contract's metadata uniformly regardless of where or how it is stored.

This SEP is intentionally minimal. It standardizes the pointer and nothing else, so it can ship on its own. A generic, non-asset contract metadata format is a larger, separate effort and is explicitly left to a future SEP.

## Specification

### Interface

```rust
/// Returns a URI pointing to a document describing this contract.
///
/// The returned value is a URI, for example:
///   "https://example.com/.well-known/stellar.toml"
///   "https://example.com/metadata.json"
///   "ipfs://bafy..."
///
/// Returns an empty string if the contract advertises no metadata URI.
fn metadata_uri(env: Env) -> String;
```

Requirements:

1. The function is a read-only getter. It MUST NOT require authorization and MUST NOT modify state.
2. The returned value MUST be either the empty string (no metadata advertised) or a valid URI including a scheme.
3. The value is reported at the contract-instance level. Two instances built from the same Wasm hash MAY return different URIs.
4. How the contract stores the value (constant, instance storage, or admin-settable) is left to the implementer. If the value can change, the contract SHOULD gate any setter behind its own access control; such a setter is out of scope for this SEP.

### Transport agnosticism

Consumers resolve the URI according to its scheme. At minimum:

- `https` URIs are fetched over HTTPS.
- `ipfs` and other content-addressed URIs are resolved through the corresponding transport, which has the benefit that the referenced document can be immutable and verifiable.

Other schemes are permitted. This SEP does not mandate https and does not bake DNS into the standard.

### Payload is out of scope

This SEP standardizes the pointer, not the document it points to. The media type and schema of the referenced document are out of scope and are expected to be addressed separately. In particular:

- For an asset contract, the URI MAY point to a SEP-1 `stellar.toml`. A consumer that recognizes this MAY resolve SEP-1 and read the relevant `[[CURRENCY]]` entry. This is optional and not required by this SEP.
- For a non-asset contract, the URI MAY point to any document the contract chooses. A future SEP may define a generic, non-asset contract metadata schema for this case.

### Discoverability

A contract implementing this SEP SHOULD declare it in its SEP-46 contract meta so off-chain tools can detect support statically.

## Design Rationale

- **URI, not a bare domain.** Returning a full URI rather than a domain keeps the standard from hardcoding DNS plus https, and lets contracts use ipfs or other content-addressed transports. This mirrors SEP-50's `token_uri` at the contract level (and parallels the contract-level metadata pointers used in other ecosystems). The exact function name is open to editor and community input.
- **Pointer only, format deferred.** Standardizing the document format is a much larger, opinion-heavy effort. Separating the pointer from the payload lets the pointer ship now and the format mature on its own track, rather than holding a simple, useful primitive hostage to a long schema debate.
- **Instance-level function, not SEP-46 meta.** SEP-46 covers Wasm-level, build-time metadata and explicitly does not cover per-deployment information. A per-instance, mutable pointer therefore needs a function.

## Security Considerations

- `metadata_uri()` is a self-asserted claim. A contract can name any URI. Consumers MUST NOT treat the pointed-to document as trusted on the basis of this function alone. Trust comes from out-of-band reputation (curated lists), or, for the asset case, from existing SEP-1 mechanisms.
- Resolution over https depends on standard transport security. Content-addressed schemes give integrity by construction, since the identifier is derived from the content.
- The interface adds no privileged operation, no authorization path, and no required state, so it introduces no new on-chain attack surface.

## Changelog

- `0.1.0` Initial draft.
