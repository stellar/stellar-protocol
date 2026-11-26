## Preamble

```
SEP: To Be Assigned
Title: Soroban Token Metadata Storage
Author: Leigh McCulloch <@leighmcculloch>
Status: Draft
Created: 2026-10-29
Updated: 2026-10-29
Version: 0.0.1
Discussion: https://github.com/orgs/stellar/discussions/2054
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

[SEP-41] intentionally does not define how a token contract stores its state.
However, data products that ingest Stellar ledger data, such as indexers,
explorers, and ETLs, have come to depend on a common behaviour: many token
contracts write their name, symbol, and decimals into instance storage in one
of two well-known formats. Of the 1,587 Wasm token contracts on mainnet in
October 2026, 89.7% used one of the formats defined in this SEP.

Reading metadata from storage is significantly more efficient for data products
than running a Soroban host to simulate calls to the `name`, `symbol`, and
`decimals` functions.

This SEP captures the existing practice of many token contracts and the
existing dependence of data tools on it.

## Abstract

This SEP defines where and how a token contract stores its name, symbol, and
decimals in its instance storage. It captures the keys and value formats
already written by the most commonly used token implementations, so that data
products can read token metadata directly from ledger data. This SEP does not
replace the requirement for [SEP-41] token contracts to implement the
`decimals()`, `name()`, and `symbol()` functions.

## Specification

### Location

Token metadata is stored in the contract's instance storage. Instance storage
is the `storage` map of the `ScContractInstance` value held in the contract's
instance ledger entry, which is the `CONTRACT_DATA` ledger entry with the
contract's address, the key `ScVal::LedgerKeyContractInstance`, and
`PERSISTENT` durability.

The metadata is a single entry in that map, with one of the keys defined in
[Key](#key) and a value in the format defined in [Value](#value).

Contracts written with the [`soroban-sdk`] store an entry in instance storage
with:

```rust
env.storage().instance().set(&key, &value);
```

### Key

The key is one of:

| XDR-JSON                            | Contract code                                                                                     | First used in                                       |
| ----------------------------------- | ------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `{ "symbol": "METADATA" }`          | <pre>pub const METADATA_KEY: Symbol =<br>&nbsp;&nbsp;&nbsp;&nbsp;symbol_short!("METADATA");</pre> | Stellar Asset Contract, [`soroban-token-sdk`]       |
| `{ "vec": [{ "symbol": "Meta" }] }` | <pre>#[contracttype]<br>pub enum TokenMetadataKey {<br>&nbsp;&nbsp;&nbsp;&nbsp;Meta,<br>}</pre>   | [OpenZeppelin Stellar Contracts][oz-stellar-tokens] |

### Value

The value is an `ScVal` `ScMap` with the following entries:

| Key (XDR-JSON)                                          | Value type | Meaning                             |
| ------------------------------------------------------- | ---------- | ----------------------------------- |
| `{ "symbol": "decimal" }` or `{ "symbol": "decimals" }` | `U32`      | The value returned by `decimals()`. |
| `{ "symbol": "name" }`                                  | `String`   | The value returned by `name()`.     |
| `{ "symbol": "symbol" }`                                | `String`   | The value returned by `symbol()`.   |

The map should contain exactly one of `decimal` or `decimals`. Historically the
Stellar Asset Contract and the `soroban-token-sdk` have used `decimal`, and the
OpenZeppelin Stellar Contracts library has used `decimals`.

As a contract type:

```rust
use soroban_sdk::{contracttype, String};

#[contracttype]
pub struct TokenMetadata {
    pub decimal: u32,
    pub name: String,
    pub symbol: String,
}
```

As XDR-JSON:

```json
{
  "map": [
    { "key": { "symbol": "decimal" }, "val": { "u32": 7 } },
    { "key": { "symbol": "name" }, "val": { "string": "Example Token" } },
    { "key": { "symbol": "symbol" }, "val": { "string": "EXT" } }
  ]
}
```

### Examples

Writing the metadata:

```rust
env.storage().instance().set(&METADATA_KEY, &TokenMetadata {
    decimal: 7,
    name: String::from_str(&env, "Example Token"),
    symbol: String::from_str(&env, "EXT"),
});
```

### Precedence

If a contract stores the metadata under more than one key, or a map contains
both `decimal` and `decimals`, readers should prefer them in the order they are
listed in this SEP: the `Symbol("METADATA")` key over the
`Vec([Symbol("Meta")])` key, and `decimal` over `decimals`.

## Design Rationale

### Capturing existing practice

This SEP standardizes formats already on-chain in most token contracts.

### Two keys and two field names

Both keys and both decimals field names are written by widely used libraries
and already deployed on mainnet. Choosing one would make many existing tokens
non-conforming, with no benefit to readers who must support both regardless.

### A separate SEP instead of a change to SEP-41

[SEP-41] does not prescribe the implementation details of a token contract, and
changing that would be breaking. A separate SEP leaves SEP-41 unchanged.

## Security Concerns

### Storage and functions may disagree

Nothing on-chain enforces that the stored values match the values returned by
the contract's functions. A contract that is incorrectly implemented, or
malicious, could store values that differ from its functions. Contracts calling
the token use the functions, so a reader relying on storage could display or
account for amounts differently to how the token behaves on-chain. Readers that
need certainty for a specific token can compare the stored values with a
simulation of the functions.

### Metadata can change

Any function in a contract can write the metadata entry again, and a Wasm
update can install code that does. A reader that caches the first value it
reads will keep a stale name and symbol, which makes renaming a token after it
is listed an easy spoofing path.

### Values out of range

A contract can store a `decimal`/`decimals` value that is well-formed but
meaningless, such as a value larger than an `i128` amount can represent.
Readers SHOULD validate the value is within a range they can process before
using it to scale amounts.

### Reading the wrong map

Readers that search for `name`, `symbol`, or `decimals` fields in any map in a
contract's storage can read values that describe a different token, such as an
underlying asset referenced by a vault or loan contract.

## Changelog

- `v0.0.1`: Initial draft.

[SEP-41]: sep-0041.md
[SEP-51]: sep-0051.md
[`soroban-sdk`]: https://github.com/stellar/rs-soroban-sdk
[`soroban-token-sdk`]:
  https://github.com/stellar/rs-soroban-sdk/blob/main/soroban-token-sdk/src/metadata.rs
[oz-stellar-tokens]:
  https://github.com/OpenZeppelin/stellar-contracts/blob/main/packages/tokens/src/fungible/storage.rs
