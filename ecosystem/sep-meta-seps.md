## Preamble

```
SEP: META
Title: Contract Meta: Interface Implementation Indicators
Author: Leigh McCulloch
Track: Standard
Status: Draft
Created: 2025-02-13
Updated: 2025-02-13
Version: 0.1.0
Discussion: TBA
```

## Simple Summary

A standard for indicating which SEPs containing contract interfaces a contract implements.

## Dependencies

None.

## Motivation

Contract standards are defined in SEPs (Stellar Ecosystem Proposals). These SEPs contain interface definitions that contracts may implement. When a contract implements an interface defined in a SEP, it needs a way to indicate this to wallets and other clients that want to interact with the contract. A standard way of indicating which SEPs a contract implements allows clients to reliably determine if a contract supports a specific interface.

## Abstract

This SEP defines a standard way for contracts to indicate which SEPs containing contract interfaces they implement. Each implemented SEP is indicated by a meta entry with a key in the format "sepNNNN" where NNNN is the SEP number, and a value that is either empty or defined by the implemented SEP.

## Specification

A contract that implements an interface defined in a SEP MUST include a meta entry for that SEP. The meta entry key MUST be in the format "sepNNNN" where NNNN is the SEP number padded with leading zeros to 4 digits. For example, a contract implementing SEP-41 would have a meta entry with key "sep0041".

The value of the meta entry SHOULD be an empty string ("") by default. However, SEPs MAY define specific values to be used in this field that are relevant to their interface. The content and format of these values are determined by the individual SEPs and are out of scope for this specification.

### Storage

Meta entries are stored in the `contractmetav0` WebAssembly custom section of the contract. Each entry is encoded using the following XDR:

```
namespace stellar
{

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

}
```

### Examples

A contract implementing SEP-41 (Token Interface) can declare its meta entries using the `contractmeta!` macro from the Soroban SDK:

```rust
use soroban_sdk::contractmeta;

contractmeta! {
    key: "sep0041",
    val: ""  // or a value defined by SEP-41 if it specifies one
}
```

A contract implementing multiple SEPs would include multiple meta entries:

```rust
use soroban_sdk::contractmeta;

contractmeta! {
    key: "sep0041",
    val: "",
    key: "sep0042",
    val: ""  // or a value defined by SEP-42 if it specifies one
}
```

Meta entries can also be added during contract build time using the Soroban CLI:

```sh
soroban contract build --meta key=sep0041,val=""
```

Or multiple entries:

```sh
soroban contract build --meta key=sep0041,val="" --meta key=sep0042,val=""
```

## Design Rationale

The format "sepNNNN" for meta keys was chosen for several reasons:
1. The "sep" prefix clearly identifies the standard as a Stellar Ecosystem Proposal
2. Four digits for the number allows for consistent sorting and future expansion
3. Using lowercase maintains consistency with existing Stellar naming conventions

The default empty string value provides a simple way to indicate implementation while allowing SEPs to define their own values if needed for additional functionality.

## Security Concerns

None.

## Changelog

- `v0.1.0`: Initial draft.
