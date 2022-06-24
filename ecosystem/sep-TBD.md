## Preamble

```
SEP: 00xx
Title: Smart Contract Spec
Author: Leigh McCulloch (@leighmcculloch)
Status: Draft
Discussion: https://discord.gg/8KXDyVUjUT
Created: 2022-06-23
Version 0.1.0
```

## Summary

This proposal defines a format for describing the exported interface provided by
a smart contract.

## Motivation

Smart contracts are useful if they are usable. Developers need to have a way to
communicate about the interface a smart contract exports so that other
developers know how to call it either directly or via a cross-contract host
function call.

## Abstract

This proposal defines an XDR format for describing the components exported by a
smart contract at an application layer, defined as a list of:

- Functions exported by the contract that may be called, and those functions:
  - Input Types
  - Output Types

- User-Defined Types exported by the contract that are used as input types or output types of functions, that may be:
  - Structs
  - Enums (Rust unit enums)
  - Unions (Rust non-unit enums)

## Specification

### XDR

See https://github.com/stellar/rs-stellar-xdr/pull/76.

### Encoding as Host Types

## Semantics

### Application Layer vs Host Layer

The spec defines the interface at the application layer and not the host layer.
The smart contract host type system on Stellar is rich, containing types such as
vecs and maps, but also simple in that it does not provide first-class
primitives for many other type concepts that are present in programming
languages. To create the best experience possible to contract developers the
spec defines its interface using a wider variety of types that are commonly
available such as tuples, user defined types, optionals, results.

### Enums as SCO_VEC

Enums are defined as vectors of two elements:

1. An integer discriminant.
2. A value.

### Structs as Maps

Structs are defined as maps where each field is an entry in the map:

1. Key = string
2. Value = value

### Type IDs

## Security Concerns

TBD.

## Limitations

TBD.

## Implementations

https://github.com/stellar/rs-stellar-xdr/pull/76
https://github.com/stellar/rs-stellar-contract-sdk/pull/140
https://github.com/stellar/stellar-contract-cli/pull/17
