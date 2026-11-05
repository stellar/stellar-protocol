## Preamble

```
SEP: To Be Assigned
Title: Contract Interface Specification: Display
Author: Leigh McCulloch <@leighmcculloch>
Status: Draft
Created: 2026-11-05
Updated: 2026-11-05
Version: 0.0.1
Discussion: TBD
```

## Simple Summary

An extension to [SEP-48] that lets a contract's spec describe how a call to a
function should be displayed to a human approving it.

## Dependencies

- [SEP-48]
- [SEP-41]

## Motivation

Wallets can decode a contract invocation using the [SEP-48] spec, but the spec
only gives arguments names and types. A call such as
`transfer(from, to, amount = 1000000000)` does not tell a user they are sending
100 USDC, because nothing in the spec says which token defines the units of
`amount`. Users are asked to approve calls they cannot read.

## Abstract

This SEP defines a new version of the [SEP-48] function spec entry that carries
an optional display description: an intent identifier, an assertion about the
function's authorization, and a list of labelled and formatted fields. It also
defines how wallets use display descriptions.

## Specification

### XDR

The following changes are made to the [SEP-48] XDR in
`Stellar-contract-spec.x`.

```diff mddiffcheck.base=4f524bbac80c781c06e4fb5fc93a2d0d331d6705
diff --git a/Stellar-contract-spec.x b/Stellar-contract-spec.x
index d87e643..0f1fe20 100644
--- a/Stellar-contract-spec.x
+++ b/Stellar-contract-spec.x
@@ -251,6 +251,158 @@ struct SCSpecEventV0
     SCSpecEventDataFormat dataFormat;
 };

+// Maximum length of the text in display descriptions.
+const SC_SPEC_DISPLAY_TEXT_LIMIT = 64;
+
+// Kind of a step in a display path.
+enum SCSpecDisplayPathStepKind
+{
+    // Step into an element of a vec or tuple.
+    SC_SPEC_DISPLAY_PATH_STEP_INDEX = 0,
+    // Step into a field of a struct user-defined type.
+    SC_SPEC_DISPLAY_PATH_STEP_FIELD = 1
+};
+
+// A step from a value into a value contained within it.
+union SCSpecDisplayPathStep switch (SCSpecDisplayPathStepKind kind)
+{
+case SC_SPEC_DISPLAY_PATH_STEP_INDEX:
+    // Index of the element. Negative values count from the end, -1 being the
+    // last element.
+    int32 index;
+case SC_SPEC_DISPLAY_PATH_STEP_FIELD:
+    // Name of the struct field.
+    string field<30>;
+};
+
+// A path to a value within a function's arguments.
+struct SCSpecDisplayPath
+{
+    // Name of the function input the path starts at.
+    string input<30>;
+    // Steps into the input's value. Empty selects the input's value itself.
+    SCSpecDisplayPathStep steps<8>;
+};
+
+// Kind of reference to the token that defines an amount's units.
+enum SCSpecDisplayTokenKind
+{
+    // The invoked contract is the token.
+    SC_SPEC_DISPLAY_TOKEN_SELF = 0,
+    // The token's contract address is located at a path.
+    SC_SPEC_DISPLAY_TOKEN_PATH = 1
+};
+
+// Reference to the token that defines an amount's units.
+union SCSpecDisplayToken switch (SCSpecDisplayTokenKind kind)
+{
+case SC_SPEC_DISPLAY_TOKEN_SELF:
+    void;
+case SC_SPEC_DISPLAY_TOKEN_PATH:
+    // Path to an address argument containing the token's contract address.
+    SCSpecDisplayPath path;
+};
+
+// Labels displayed in place of a bool value.
+struct SCSpecDisplayBoolV0
+{
+    // Label displayed when the value is true.
+    string trueLabel<SC_SPEC_DISPLAY_TEXT_LIMIT>;
+    // Label displayed when the value is false.
+    string falseLabel<SC_SPEC_DISPLAY_TEXT_LIMIT>;
+};
+
+// Label displayed in place of an integer value.
+struct SCSpecDisplayEnumCaseV0
+{
+    // Value matched, of the SCVal type matching the field's spec type.
+    SCVal value;
+    // Label displayed when the value matches.
+    string label<SC_SPEC_DISPLAY_TEXT_LIMIT>;
+};
+
+// Kind of format used to display a value.
+enum SCSpecDisplayFormatKind
+{
+    // The value as decoded according to its spec type.
+    SC_SPEC_DISPLAY_FORMAT_RAW = 0,
+    // A token amount, scaled by the token's decimals, with its symbol.
+    SC_SPEC_DISPLAY_FORMAT_AMOUNT = 1,
+    // Seconds since the Unix epoch, as a date and time.
+    SC_SPEC_DISPLAY_FORMAT_TIMESTAMP = 2,
+    // Seconds, as days, hours, minutes and seconds.
+    SC_SPEC_DISPLAY_FORMAT_DURATION = 3,
+    // A ratio scaled by a power of ten, as a percentage.
+    SC_SPEC_DISPLAY_FORMAT_PERCENT = 4,
+    // A bool, as one of two labels.
+    SC_SPEC_DISPLAY_FORMAT_BOOL = 5,
+    // An integer, as the label of a matching case.
+    SC_SPEC_DISPLAY_FORMAT_ENUM = 6
+};
+
+// Format used to display a value.
+union SCSpecDisplayFormat switch (SCSpecDisplayFormatKind kind)
+{
+case SC_SPEC_DISPLAY_FORMAT_RAW:
+case SC_SPEC_DISPLAY_FORMAT_TIMESTAMP:
+case SC_SPEC_DISPLAY_FORMAT_DURATION:
+    void;
+case SC_SPEC_DISPLAY_FORMAT_AMOUNT:
+    // Token that defines the amount's units.
+    SCSpecDisplayToken token;
+case SC_SPEC_DISPLAY_FORMAT_PERCENT:
+    // Power of ten the ratio is scaled by, from 0 to 38.
+    uint32 decimals;
+case SC_SPEC_DISPLAY_FORMAT_BOOL:
+    // Labels for true and false.
+    SCSpecDisplayBoolV0 labels;
+case SC_SPEC_DISPLAY_FORMAT_ENUM:
+    // Labels for integer values. Values without a case are displayed raw.
+    SCSpecDisplayEnumCaseV0 cases<50>;
+};
+
+// A value to display for a function call.
+struct SCSpecDisplayFieldV0
+{
+    // Path to the value within the function's arguments.
+    SCSpecDisplayPath path;
+    // Label displayed with the value.
+    string label<SC_SPEC_DISPLAY_TEXT_LIMIT>;
+    // Format the value is displayed in.
+    SCSpecDisplayFormat format;
+};
+
+// Claim about the arguments of the function's authorizations.
+enum SCSpecDisplayAuthV0
+{
+    // No claim is made.
+    SC_SPEC_DISPLAY_AUTH_UNSPECIFIED = 0,
+    // Every authorization for the function carries exactly the function's
+    // arguments in order.
+    SC_SPEC_DISPLAY_AUTH_FN_ARGS = 1
+};
+
+// Description of how to display a call to a function.
+struct SCSpecFunctionDisplayV0
+{
+    // Identifier of the action, e.g. "transfer", that wallets display as a
+    // localized phrase.
+    string intent<SC_SPEC_DISPLAY_TEXT_LIMIT>;
+    // Claim about the arguments of the function's authorizations.
+    SCSpecDisplayAuthV0 auth;
+    // Values to display, in display order.
+    SCSpecDisplayFieldV0 fields<20>;
+};
+
+// A function with an optional display description.
+struct SCSpecFunctionV1
+{
+    // The function's spec, as it would appear in a V0 function entry.
+    SCSpecFunctionV0 functionV0;
+    // How to display a call to the function, if described.
+    SCSpecFunctionDisplayV0* display;
+};
+
 enum SCSpecEntryKind
 {
     SC_SPEC_ENTRY_FUNCTION_V0 = 0,
@@ -258,7 +410,8 @@ enum SCSpecEntryKind
     SC_SPEC_ENTRY_UDT_UNION_V0 = 2,
     SC_SPEC_ENTRY_UDT_ENUM_V0 = 3,
     SC_SPEC_ENTRY_UDT_ERROR_ENUM_V0 = 4,
-    SC_SPEC_ENTRY_EVENT_V0 = 5
+    SC_SPEC_ENTRY_EVENT_V0 = 5,
+    SC_SPEC_ENTRY_FUNCTION_V1 = 6
 };

 union SCSpecEntry switch (SCSpecEntryKind kind)
@@ -275,6 +428,8 @@ case SC_SPEC_ENTRY_UDT_ERROR_ENUM_V0:
     SCSpecUDTErrorEnumV0 udtErrorEnumV0;
 case SC_SPEC_ENTRY_EVENT_V0:
     SCSpecEventV0 eventV0;
+case SC_SPEC_ENTRY_FUNCTION_V1:
+    SCSpecFunctionV1 functionV1;
 };

 }
```

### Function Entry V1

`SC_SPEC_ENTRY_FUNCTION_V1` contains a `SCSpecFunctionV0` that describes the
function exactly as a `SC_SPEC_ENTRY_FUNCTION_V0` entry does, with the addition
of an optional `display`. A V1 entry without a `display` is equivalent to a V0
entry.

A spec must contain at most one function entry, of either version, for each
function name. Tooling that reads V0 entries should read V1 entries in the same
way.

### Display

The `intent` is a string that is expected to be an identifier for the action
the call performs, from the perspective of the user approving it. Wallets
display it as a phrase in the user's language. The following intents are
examples:

| Intent     | English                |
| ---------- | ---------------------- |
| `transfer` | Send tokens            |
| `approve`  | Approve token spending |
| `burn`     | Burn tokens            |
| `mint`     | Mint tokens            |
| `swap`     | Swap tokens            |

Wallets can map identifiers to their own short phrases in the languages they
support. An index or glossary of intents and recommended phrases is not
included in this proposal, and may be defined in the future by another proposal
or some other mechanism. A wallet that does not have a phrase for an intent
should display the intent identifier itself.

The `fields` are the values to display, in order, each with a `label`. All
`intent` and `label` strings must be non-empty printable ASCII.

The `auth` field states whether every authorization for the function, as
recorded in a `SorobanAuthorizedInvocation`, carries exactly the function's
arguments in order:

- `SC_SPEC_DISPLAY_AUTH_FN_ARGS`: the function's authorizations use its
  arguments, such as when the contract calls `require_auth()`.
- `SC_SPEC_DISPLAY_AUTH_UNSPECIFIED`: no claim is made, such as when the
  contract calls `require_auth_for_args(...)` with other values.

### Paths

A path selects a value within the function's arguments. The `input` is the name
of a function input. Each step descends into the value:

- `SC_SPEC_DISPLAY_PATH_STEP_INDEX` selects an element of a `vec` or `tuple`.
  Negative indexes count from the end.
- `SC_SPEC_DISPLAY_PATH_STEP_FIELD` selects a field of a struct user-defined
  type.

Paths do not step into maps, options, or unions.

### Formats

Each format applies to a limited set of spec types:

| Format      | Spec types                                 | Displayed as                                                    |
| ----------- | ------------------------------------------ | --------------------------------------------------------------- |
| `raw`       | any                                        | The value as decoded according to its spec type.                |
| `amount`    | `i32`, `u32`, `i64`, `u64`, `i128`, `u128` | `value / 10^decimals` followed by the token's symbol.           |
| `timestamp` | `u64`, `timepoint`                         | An RFC 3339 UTC date and time.                                  |
| `duration`  | `u32`, `u64`, `duration`                   | Days, hours, minutes and seconds, e.g. `1h 30m`.                |
| `percent`   | `i32`, `u32`, `i64`, `u64`, `i128`, `u128` | `value / 10^decimals` multiplied by 100, followed by `%`.       |
| `bool`      | `bool`                                     | The `trueLabel` or `falseLabel`.                                |
| `enum`      | `i32`, `u32`, `i64`, `u64`                 | The `label` of the case whose `value` equals the value, if any. |

The token for an `amount` is the invoked contract
(`SC_SPEC_DISPLAY_TOKEN_SELF`) or a contract address found at a path
(`SC_SPEC_DISPLAY_TOKEN_PATH`). Its `decimals` and `symbol` are those of the
[SEP-41] token.

Values must be displayed exactly, without rounding. The raw value must remain
viewable.

### Wasm Custom Section

V1 entries are stored in the `contractspecv0` custom section with all other
entries, as defined in [SEP-48].

SDKs should only emit a V1 entry for functions that have a `display`, and emit
a V0 entry otherwise.

### Usage by Wallets

A display description is a claim made by its author. The author of a contract
can claim a malicious call is harmless. Wallets must only display an `intent`
and `label`s from a display description if the wallet trusts the source, such
as when a party the wallet trusts has reviewed the Wasm. How that trust is
established is out of scope of this proposal.

Before using a display description a wallet must check that it is consistent
with the spec: each path resolves to an input of the function, each format
applies to the spec type at the end of its path, and each token path ends at an
`address`.

For each invocation, a wallet must check that the argument count matches the
function's inputs, and that the value at the end of each formatted or token
path is of the expected type. A path index beyond the end of a vec omits that
field.

When a display description is used, a wallet must display the phrase for the
`intent`, the contract address, the function name, and the fields. All
arguments must remain viewable.

For authorization entries, a wallet must only use a display description for a
`SorobanAuthorizedInvocation` if `auth` is `SC_SPEC_DISPLAY_AUTH_FN_ARGS`.

When a display description is not trusted, missing, or inconsistent, wallets
must display the contract address, function name and all arguments, and
indicate that the call has no description.

### Stellar Asset Contract

The Stellar Asset Contract has no Wasm. Wallets should treat the following as
its spec and display descriptions, using the asset code as the symbol and `7`
as the decimals, after verifying that the asset's contract address is the
invoked contract address:

```rust
#[display(intent = transfer, auth = fn_args)]
#[display(field(amount, label = "Amount", format = amount(token = self)))]
#[display(field(to, label = "Recipient"))]
#[display(field(from, label = "From"))]
fn transfer(from: Address, to: MuxedAddress, amount: i128);

#[display(intent = approve, auth = fn_args)]
#[display(field(spender, label = "Spender"))]
#[display(field(amount, label = "Allowance", format = amount(token = self)))]
#[display(field(live_until_ledger, label = "Expires (ledger)"))]
#[display(field(from, label = "Owner"))]
fn approve(from: Address, spender: Address, amount: i128, live_until_ledger: u32);

#[display(intent = burn, auth = fn_args)]
#[display(field(amount, label = "Amount", format = amount(token = self)))]
#[display(field(from, label = "From"))]
fn burn(from: Address, amount: i128);
```

## Example Usage

### Rust soroban-sdk

The syntax below is illustrative of how an SDK could support display
descriptions.

```rust
#[contractimpl]
impl Token {
    #[display(intent = transfer, auth = fn_args)]
    #[display(field(amount, label = "Amount", format = amount(token = self)))]
    #[display(field(to, label = "Recipient"))]
    #[display(field(from, label = "From"))]
    pub fn transfer(env: Env, from: Address, to: MuxedAddress, amount: i128) {
        from.require_auth();
        // ...
    }
}
```

Which will be encoded to the following `SCSpecEntry`, expressed as XDR-JSON:

```json
{
  "function_v1": {
    "function_v0": {
      "doc": "",
      "name": "transfer",
      "inputs": [
        { "doc": "", "name": "from", "type_": "address" },
        { "doc": "", "name": "to", "type_": "muxed_address" },
        { "doc": "", "name": "amount", "type_": "i128" }
      ],
      "outputs": []
    },
    "display": {
      "intent": "transfer",
      "auth": "fn_args",
      "fields": [
        {
          "path": { "input": "amount", "steps": [] },
          "label": "Amount",
          "format": { "amount": "self" }
        },
        {
          "path": { "input": "to", "steps": [] },
          "label": "Recipient",
          "format": "raw"
        },
        {
          "path": { "input": "from", "steps": [] },
          "label": "From",
          "format": "raw"
        }
      ]
    }
  }
}
```

A wallet displaying a call to `transfer` with an amount of `1000000000` for a
token with 7 decimals and symbol `USDC` might show:

```
Send tokens

Contract   CDLZ…7XQJ
Function   transfer
Amount     100 USDC
Recipient  GB7X…K2QF
From       GA3R…9MPL
```

### Paths

A swap function that receives a list of hops, where the output token is the
last element of the last hop, can reference it with a path:

```rust
#[display(field(out_min, label = "Min. received",
    format = amount(token = path(swaps_chain[-1].2))))]
pub fn swap_chained(env: Env, user: Address,
    swaps_chain: Vec<(Vec<Address>, BytesN<32>, Address)>,
    token_in: Address, in_amount: u128, out_min: u128) -> u128;
```

## Limitations

### Intent, Not Effect

A display description states what a call is intended to do, not what it will
do. Previews of a call's effects, such as by simulation, are out of scope.

### Wasm, Not Instances

Display descriptions apply to every instance of a Wasm. There is no way to
describe one instance differently to another.

### Existing Contracts

Contracts already deployed have no display descriptions, and wallets display
their calls without one until they are rebuilt and upgraded.

### No Trust Mechanism

This proposal does not define how wallets decide which display descriptions to
trust, or how reviews are published.

### Labels Are Not Localized

Intents are identifiers that wallets localize, but labels are text chosen by
the contract and are displayed as written.

## Design Rationale

### Function Entry V1

The display description belongs to a function, and placing it in the function's
entry alongside its `doc` means it is authored, generated, and read alongside
the function. There is no need to refer to the function by name, and no
possibility of describing a function that does not exist.

`SCSpecFunctionV0` cannot be changed without changing the encoding of every
existing contract's spec, so a new version is introduced. The V1 entry embeds
the V0 function so that the function's description is defined once and tooling
can reuse its existing handling of V0 functions. The `display` is optional so
that V1 can be the general successor to V0.

### Compatibility

The `contractspecv0` custom section is a stream without length prefixes, so
tooling that does not know the V1 entry kind cannot decode any spec that
contains one. This is the same step taken when events were added to [SEP-48].
SDKs emitting V1 entries only for functions that have a display description
limits the impact to contracts that use this proposal.

### Spec Instead of Off-Chain JSON

Defining display descriptions in the [SEP-48] XDR means they use the same
types, the same XDR-JSON, and the same decoders as the rest of the spec,
including on hardware wallets that already decode XDR. SDKs can generate them
from contract source, so implementations of the same interface carry
descriptions that match their own parameter names.

### Contract Defined

A contract's spec only describes that contract, and display descriptions follow
the same rule: they are defined by the contract, in its own Wasm, and are bound
to that Wasm. There is no separate document to distribute, match to a Wasm, or
keep in sync with it.

### Intent Identifiers

An intent is an identifier rather than text so that wallets can display it in
the user's language, and so that the phrase a user sees is chosen by the wallet
rather than the contract. Contracts using the same identifier for the same
purpose also makes calls read the same across contracts.

### Authorization

A `SorobanAuthorizedInvocation` contains the arguments a contract passed when
requiring authorization, which are not always the function's arguments. The
spec alone cannot tell the difference, so the `auth` field states it
explicitly, and defaults to making no claim.

## Security Concerns

### Display Descriptions Can Lie

A display description is a claim by its author, and a malicious author can
describe a harmful call as harmless. This is why wallets must only use display
descriptions from sources they trust. Checking a display description against
the spec only shows that it is consistent with the function's interface, not
that it is truthful.

### Readable Is Not Safe

A truthful display description on a malicious contract instance still displays
a truthful result, such as `Send tokens 100 SCAM`. Wallets should continue to
display the contract address and apply any other risk signals they use.

### Token Metadata

A token's `decimals` and `symbol` are reported by the token contract and can be
chosen to mislead. Wallets should prefer token metadata from trusted sources,
and must not allow a symbol to alter the layout of what is displayed.

### Code Can Change

A contract can be upgraded between when a call is approved and when it
executes. The display description shown is for the Wasm at the time of
approval.

## Changelog

- `v0.0.1`: Initial draft.

[SEP-41]: ./sep-0041.md
[SEP-48]: ./sep-0048.md
