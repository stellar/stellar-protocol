## Preamble

```
SEP: To Be Assigned
Title: Token Metadata Storage
Author: Leigh McCulloch <@leighmcculloch>
Status: Draft
Created: 2026-10-29
Updated: 2026-10-29
Version: 0.0.1
Discussion: TBD
```

## Simple Summary

A standard location and format in contract storage for a token contract's name,
symbol, and decimals, so that anyone reading ledger data can learn a token's
metadata without executing the contract.

## Dependencies

- [SEP-41]: Soroban Token Interface. Defines the `name`, `symbol`, and
  `decimals` functions whose values this SEP stores.
- [SEP-51] (informative): XDR-JSON. Used for the examples in this document.

## Motivation

[SEP-41] defines the interface of a token contract: the functions it exposes
and the events it emits. It does not define how a token contract stores its
state, and that is intentional. Contracts are free to store their state however
best suits them, and contracts that call a token use the functions, not the
storage.

However, data products such as indexers, block explorers, analytics pipelines,
and ETLs that ingest Stellar ledger data have come to depend on a common
behaviour of token contracts. Many token contracts write their name, symbol,
and decimals into their contract instance storage in one of two well-known
formats. Data products read the metadata directly from that storage.

The two formats come from the libraries most token contracts are built with:

- The Stellar Asset Contract (SAC) and the [`soroban-token-sdk`] store the
  metadata under the key `Symbol("METADATA")`.
- [OpenZeppelin Stellar Contracts][oz-stellar-tokens] fungible tokens store the
  metadata under the key `Vec([Symbol("Meta")])`, using the enum data-key
  pattern that is common in contracts to disambiguate storage entries.

An analysis by the SDF Data team in October 2026 of every Wasm token contract
on mainnet that had emitted a SEP-41 transfer, mint, or burn event (1,587
contracts, Stellar Asset Contracts excluded) found that 86.3% use the
`Symbol("METADATA")` format, 3.5% use the `Vec([Symbol("Meta")])` format, and
the remaining approximately 10% either store metadata in bespoke formats or do
not store it at all. Every Stellar Asset Contract uses the `Symbol("METADATA")`
format.

Reading metadata from storage is significantly more efficient for data products
than the alternative. To call the `name`, `symbol`, and `decimals` functions a
data product must run a Soroban host, load the contract's Wasm and the ledger
entries it accesses, and simulate the invocation, for every token, and again
for every point in history it needs the value at. Reading storage requires only
decoding a ledger entry that the data product is already ingesting, and because
ledger entry changes are part of ledger close meta, the value at any point in
history is available without re-execution.

When a token stores its metadata in a format data products do not recognise,
the consequences can be significant. Decimals in particular has financial
impact: a token whose decimals is not found is typically assumed to use 7
decimals, and amounts are mis-scaled by orders of magnitude when that
assumption is wrong. This has caused real reporting errors in the ecosystem
where a token stored its decimals under a bespoke key.

This SEP captures the existing practice of the large majority of token
contracts and the existing dependence of data tools on that practice, so that
token contract developers know how to make their token's metadata discoverable
on-chain, and data product developers know which formats to support.

## Abstract

This SEP defines two storage formats for a token contract's metadata, both
stored in the contract's instance storage:

1. Key `Symbol("METADATA")` with a map value containing the fields `decimal`,
   `name`, and `symbol`.
2. Key `Vec([Symbol("Meta")])` with a map value containing the fields
   `decimals`, `name`, and `symbol`.

Token contracts implementing this SEP store their metadata in one of the two
formats. Readers implementing this SEP support both formats. The SEP includes
Rust `contracttype` definitions for the keys and values of both formats, which
produce exactly the formats written by the Stellar Asset Contract, the
`soroban-token-sdk`, and OpenZeppelin Stellar Contracts.

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in RFC 2119.

### Location

Token metadata is stored in the contract's instance storage. Instance storage
is the `storage` map of the `ScContractInstance` value held in the contract's
instance ledger entry, which is the `CONTRACT_DATA` ledger entry with the
contract's address, the key `ScVal::LedgerKeyContractInstance`, and
`PERSISTENT` durability.

The metadata is a single entry in that map, keyed by one of the keys defined
below.

### Format 1: `METADATA`

Key:

```
Symbol("METADATA")
```

Value, a map with exactly the following entries:

| Key (`Symbol`) | Value type | Meaning                             |
| -------------- | ---------- | ----------------------------------- |
| `decimal`      | `U32`      | The value returned by `decimals()`. |
| `name`         | `String`   | The value returned by `name()`.     |
| `symbol`       | `String`   | The value returned by `symbol()`.   |

Note that the field holding the decimals is named `decimal` (singular) in this
format.

This is the format written by the Stellar Asset Contract and by the
[`soroban-token-sdk`].

#### Contract Types

```rust
use soroban_sdk::{contracttype, symbol_short, String, Symbol};

pub const TOKEN_METADATA_KEY: Symbol = symbol_short!("METADATA");

#[contracttype]
pub struct TokenMetadata {
    pub decimal: u32,
    pub name: String,
    pub symbol: String,
}
```

Writing:

```rust
env.storage().instance().set(&TOKEN_METADATA_KEY, &TokenMetadata {
    decimal: 7,
    name: String::from_str(&env, "Example Token"),
    symbol: String::from_str(&env, "EXT"),
});
```

#### XDR-JSON

Key:

```json
{ "symbol": "METADATA" }
```

Value:

```json
{
  "map": [
    { "key": { "symbol": "decimal" }, "val": { "u32": 7 } },
    { "key": { "symbol": "name" }, "val": { "string": "Example Token" } },
    { "key": { "symbol": "symbol" }, "val": { "string": "EXT" } }
  ]
}
```

### Format 2: `Meta`

Key:

```
Vec([Symbol("Meta")])
```

Value, a map with exactly the following entries:

| Key (`Symbol`) | Value type | Meaning                             |
| -------------- | ---------- | ----------------------------------- |
| `decimals`     | `U32`      | The value returned by `decimals()`. |
| `name`         | `String`   | The value returned by `name()`.     |
| `symbol`       | `String`   | The value returned by `symbol()`.   |

Note that the field holding the decimals is named `decimals` (plural) in this
format.

This is the format written by [OpenZeppelin Stellar
Contracts][oz-stellar-tokens] fungible tokens.

#### Contract Types

A unit variant of a `contracttype` enum is encoded as a `Vec` containing a
single `Symbol` of the variant's name. A contract using the enum data-key
pattern can include the `Meta` variant in its own storage key enum, alongside
its other variants, and the variant will be encoded identically.

```rust
use soroban_sdk::{contracttype, String};

#[contracttype]
pub enum TokenMetadataKey {
    Meta,
}

#[contracttype]
pub struct TokenMetadata {
    pub decimals: u32,
    pub name: String,
    pub symbol: String,
}
```

Writing:

```rust
env.storage().instance().set(&TokenMetadataKey::Meta, &TokenMetadata {
    decimals: 7,
    name: String::from_str(&env, "Example Token"),
    symbol: String::from_str(&env, "EXT"),
});
```

#### XDR-JSON

Key:

```json
{ "vec": [{ "symbol": "Meta" }] }
```

Value:

```json
{
  "map": [
    { "key": { "symbol": "decimals" }, "val": { "u32": 7 } },
    { "key": { "symbol": "name" }, "val": { "string": "Example Token" } },
    { "key": { "symbol": "symbol" }, "val": { "string": "EXT" } }
  ]
}
```

### Token Contracts

A token contract implementing this SEP:

- MUST store its metadata in instance storage in Format 1 or Format 2.
- SHOULD NOT store its metadata in both formats. If it does, the values in both
  MUST be identical.
- MUST store values that are identical to the values returned by its
  `decimals()`, `name()`, and `symbol()` functions.
- MUST update the stored values in the same invocation as any change to the
  values returned by those functions, including a change introduced by a
  contract upgrade.
- SHOULD store the metadata no later than the first invocation that emits a
  SEP-41 event, for example in the contract's constructor.
- SHOULD NOT store a `decimal`/`decimals` value greater than 38, as an `i128`
  amount cannot represent a whole unit of a token with more than 38 decimals.

The simplest way for a token contract to implement this SEP is to have its
`decimals()`, `name()`, and `symbol()` functions read from the stored metadata,
which is what the Stellar Asset Contract, the `soroban-token-sdk`, and
OpenZeppelin Stellar Contracts do.

### Readers

A reader, such as a data product, implementing this SEP:

- MUST support both Format 1 and Format 2.
- MUST read the metadata only from the entries in instance storage with the
  keys defined in this SEP, and MUST NOT read `name`, `symbol`, `decimal`, or
  `decimals` fields from other maps in the contract's storage, as other maps
  may describe other tokens.
- SHOULD prefer Format 1 if a contract stores both formats.
- SHOULD ignore map entries other than those defined for the format.
- SHOULD treat a value whose map is missing a required entry, or whose entries
  have different types to those defined, as the contract not implementing this
  SEP.
- SHOULD re-read the metadata whenever the contract's instance ledger entry
  changes, as the metadata may change, including after a contract upgrade.

A reader MAY use other means, such as simulating the `decimals()`, `name()`,
and `symbol()` functions, to learn the metadata of token contracts that do not
implement this SEP.

## Design Rationale

### Capturing existing practice

This SEP standardizes formats that are already on-chain in the large majority
of token contracts, rather than introducing a new format. A new format would
take years to reach the coverage these formats already have, and existing
contracts that are not upgradeable would never adopt it. Standardizing the
existing formats gives data products a well-defined target today and gives
token developers a clear rule to follow that already works with the data
products that exist.

### Two formats instead of one

The two formats differ in both their key and the name of the decimals field.
Ideally there would be a single format. However, both are written by widely
used libraries, both are already deployed in contracts on mainnet, and both are
already supported by data products. Choosing one would make a significant
number of existing tokens non-conforming without any benefit to readers, who
need to support both formats regardless.

The `Symbol("METADATA")` format uses a plain `Symbol` key. The
`Vec([Symbol("Meta")])` format is the result of the enum data-key pattern,
where a contract defines all of its storage keys as variants of a single
`contracttype` enum, so that keys cannot collide. Both patterns are idiomatic
in Soroban contracts, so this SEP supports a format compatible with each.

### Instance storage

Instance storage is stored in the same ledger entry as the contract instance,
so the metadata shares the lifetime of the contract instance, does not require
a separate TTL to be maintained, and is available to a reader that is tracking
the contract instance entry without tracking any other entries.

### A separate SEP instead of a change to SEP-41

This SEP is not part of [SEP-41] because SEP-41 explicitly does not prescribe
the implementation details of a token contract. That is an intentional
attribute of SEP-41: it defines only the interface, so that any contract
implementing the interface is a token, regardless of how it is implemented.
Adding storage requirements to SEP-41 would change that attribute, and would be
inappropriate. A separate SEP leaves SEP-41 unchanged, and lets token contracts
opt in to making their metadata discoverable in storage.

### Storage is not a replacement for the interface

This SEP does not change [SEP-41]. Contracts calling a token MUST continue to
use the `decimals()`, `name()`, and `symbol()` functions, and the functions
remain the interface of a token. This SEP describes a convention for off-chain
readers of ledger data.

### Alternatives considered

- **Contract meta ([SEP-46]).** Contract meta is stored in the Wasm and is
  shared by every contract deployed from the same Wasm, while token metadata
  typically differs per deployment. Contract meta also cannot change without an
  upgrade.
- **Events.** A token could emit an event with its metadata when it is set.
  Readers would need to have ingested the full history of events from the
  contract's deployment to know the current value, and no existing libraries
  emit such an event.
- **Simulating the functions.** This is what data products would have to do in
  the absence of this SEP, and is significantly more costly, as discussed in
  the motivation.

### Formats not included

Other formats are observed on mainnet, such as bespoke keys like
`TokenDecimals`, `VaultDecimals`, or `Config` maps, and metadata stored in
persistent storage. These are each used by a small number of contracts, and are
not written by common libraries. Including them would increase the burden on
readers and encourage further fragmentation. Readers are free to support them
as heuristics, but they are not part of this SEP.

## Security Concerns

### Metadata is self-reported

The metadata stored by a contract is chosen by the contract, the same as the
values returned by the SEP-41 functions. Any contract can store a name and
symbol that imitates another token. Readers MUST NOT use the name or symbol as
an identifier of a token, and MUST use the contract address.

### Storage and functions may disagree

Nothing on-chain enforces that the stored values match the values returned by
the contract's functions. A contract that is incorrectly implemented, or
malicious, could store values that differ from its functions. Contracts calling
the token use the functions, so a reader relying on storage could display or
account for amounts differently to how the token behaves on-chain. Readers that
need certainty for a specific token can compare the stored values with a
simulation of the functions.

### Values out of range

A contract can store a `decimal`/`decimals` value that is well-formed but
meaningless, such as a value larger than an `i128` amount can represent.
Readers SHOULD validate the value is within a range they can process before
using it to scale amounts.

### Reading the wrong map

Readers that search for `name`, `symbol`, or `decimals` fields in any map in a
contract's storage can read values that describe a different token, such as an
underlying asset referenced by a vault or loan contract. This is why the
specification requires readers to read only from the keys defined in this SEP.

## Changelog

- `v0.0.1`: Initial draft.

[SEP-41]:
  https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0041.md
[SEP-46]:
  https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0046.md
[SEP-51]:
  https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0051.md
[`soroban-token-sdk`]:
  https://github.com/stellar/rs-soroban-sdk/blob/main/soroban-token-sdk/src/metadata.rs
[oz-stellar-tokens]:
  https://github.com/OpenZeppelin/stellar-contracts/blob/main/packages/tokens/src/fungible/storage.rs
