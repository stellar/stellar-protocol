## Preamble

```
SEP: META
Title: Contract Meta
Author: Leigh McCulloch
Track: Standard
Status: Draft
Created: 2025-02-13
Updated: 2025-02-13
Version: 0.1.0
Discussion: https://github.com/stellar/stellar-protocol/discussions/1656
```

## Simple Summary

A standard for the storage of metadata in contract Wasm files.

## Dependencies

None.

## Motivation

Contracts need to be able to declare information about themselves, such as their source location, build information, and
compatibility with different SEPs and interfaces.

## Abstract

This SEP defines a way well-known location where contracts can communicate to off-chain systems metadata about the
contract.

## Specification

### Wasm Custom Section

Meta entries are stored in one or more `contractmetav0` Wasm custom section of the contract Wasm file.

Multiple entries may exist in a single custom section.

Multiple custom sections may exist with the same name `contractmetav0`. If multiple exist, they should be interpreted as
if they were one section appended in the order they appear in the Wasm.

Entries should not span sections.

### XDR Encoding

Each entry is structured and encoded using the `SCMetaEntry` type.

When encoding entries and storing them in the custom section they should be appended to one another with no frame, no
header, and no prefix, including no length prefix. They should be in effect a stream of `SCMetaEntry` XDR binary encoded
values.

```
struct SCMetaV0
{
    string key<>;
    string val<>;
};

enum SCMetaKind
{
    SC_META_V0 = 0
};

union SCMetaEntry switch (SCMetaKind kind)
{
case SC_META_V0:
    SCMetaV0 v0;
};
```

Ref: https://github.com/stellar/stellar-xdr/blob/curr/Stellar-contract-meta.x

## Example Usage

### Rust soroban-sdk

Contract meta can be inserted in code with the Rust `soroban-sdk` by using the [`contractmeta!()`] macro.

```rust
soroban_sdk::contractmeta!(key="key1", val="val1");
soroban_sdk::contractmeta!(key="key2", val="val2");
```

[`contractmeta!()`]: https://docs.rs/soroban-sdk/latest/soroban_sdk/macro.contractmeta.html

### Stellar CLI

Contract meta can be inserted via the [`stellar contract build`] at build time using the `--meta` option.

```
$ stellar contract build --meta key1=val2 --meta key2=val2
```

[`stellar contract build`]:
  https://developers.stellar.org/docs/tools/developer-tools/cli/stellar-cli#stellar-contract-build

## Limitations

### Not Contract Deployments (Instances)

This proposal does not provide a way for contract deployments (instances) to communicate metadata. There can exist many
deployments of an uploaded contract and this proposal only defines a location for metadata that relates to the uploaded
contract, not the individual deployments.

### No Registry

This proposal does not define any registry of meta keys. SEPs that have a use for defining meta keys should do so as
part of their own SEPs. SDKs may also have a use for defining meta keys. Not all users of a meta key need open a SEP,
but for some where interoperability is helpful may benefit from doing so. Some attempt should be made to avoid the reuse
of keys across different use cases.

## Design Rationale

### Custom Sections

The Soroban Environment uses custom sections to store meta information about a contract's Soroban Environment
compatibility. That was documented in [CAP-46-1].

Custom sections are additional binary sections of Wasm files that can be used for any purpose. The Wasm when executing
does not have access to the custom section and is not affected by it.

[CAP-46-1]: ../core/cap-0046-01.md

### XDR Encoding

The XDR encoding is kept as lightweight and simple as possible. Strings are used for keys and values because in most
applications there is a desire to render the values to humans. Even if fields are intended to be consumed by machines,
humans ultimately end up viewing the data on block explorers and when debugging.

The XDR is extendable at multiple points and other types other than strings can be trivially added when required.

### XDR Stream Encoding

The entries are stream encoded, by appending them one after the other without frame, header, or prefix for compatibility
with building the custom sections with the Rust compiler. The Rust compiler allows Rust code to embed data encoded at
compile time into the Wasm custom section by using the `#[link_section = "custom-section-name"]` attribute on `static`
byte arrays. When multiple `static` byte arrays specify the same link section the bytes are appended to any existing
section.

XDR types when encoded have a well defined size because every element in an XDR type is either fixed size, contains a
length field to specify the size, or is prefixed with discriminants that deterministically branch on selecting the size
through the next type. As such no length prefix or counter are required.

## Security Concerns

Contracts may choose to place some information into contract meta that makes some claim, such as a claim that the
contract implements a particular SEP, or a claim that the contract was built from a particular repository. Contract meta
carriers no guarantees as to the validity or trustworthyness of the claims. Applications using the meta should do so
with care and define ways to verify claims before taking any action based on them. Specification for how to perform any
such verification is out-of-scope of this proposal and should be defined in any SEP that defines meta keys.

## Changelog

- `v0.1.0`: Initial draft capturing the status quo as implemented in soroban-sdk and stellar-cli.
