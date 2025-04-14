## Preamble

```
SEP: To Be Assigned
Title: XDR-JSON
Author: Leigh McCulloch
Track: Standard
Status: Draft
Created: 2025-04-03
Updated: 2025-04-03
Version: 0.1.0
Discussion: [Discussion link to be added]
```

## Simple Summary

This proposal defines XDR-JSON, the standard mapping between Stellar's XDR
(External Data Representation) structures and their JSON representation.

## Dependencies

None.

## Motivation

Stellar's protocol data is defined in XDR, a compact binary format that is not
human-readable. In most APIs when the XDR must be shared as text it is base64
encoded, which is also not human-readable or easily mutated. Developer tooling
needs to represent this data in a more accessible format either so it can be
read or modified.

## Abstract

This proposal defines how a subset of XDR data type defined in [RFC 4506] is
mapped to a JSON representation. It covers primitive types (integers,
booleans), complex types (structs, unions, enums), and special Stellar-specific
types (AccountID, Asset, etc.). The specification ensures that XDR data can be
consistently serialized to JSON and deserialized back to XDR without data loss,
while providing human readability.

## Specification

### XDR Data Types

#### Integer (32-bit)

The XDR 32-bit signed integer data type ([RFC 4506 Section 4.1]) maps to JSON
numbers.

For example:

XDR Definition:

```xdr
int identifier;
```

XDR Binary:

```b
00000000: 7fff ffff                                ....
```

XDR Binary Base64 Encoded:

```base64
f////w==
```

JSON:

```json
2147483647
```

#### Unsigned Integer (32-bit)

The XDR 32-bit unsigned integer data type ([RFC 4506 Section 4.2]) maps to JSON
numbers.

For example:

XDR Definition:

```xdr
unsigned int identifier;
```

XDR Binary:

```b
00000000: ffff ffff                                ....
```

XDR Binary Base64 Encoded:

```base64
/////w==
```

JSON:

```json
4294967295
```

#### Hyper Integer (64-bit)

The XDR 64-bit signed integer data type ([RFC 4506 Section 4.5]) maps to JSON
numbers.

For example:

XDR Definition:

```xdr
hyper identifier;
```

XDR Binary:

```b
00000000: 7fff ffff ffff ffff                      ........
```

XDR Binary Base64 Encoded:

```base64
f/////////8=
```

JSON:

```json
9223372036854775807
```

_Note: JavaScript runtime implementations of JSON do not support numbers that
require more than 53-bits. JavaScript applications should use a JSON decoder
supporting 64-bit numbers in JSON numbrs. JSON decoders in other languages do
not typically have this constraint and support numbers up to 64-bits._

#### Unsigned Hyper Integer (64-bit)

The XDR 64-bit signed integer data type ([RFC 4506 Section 4.5]) maps to JSON
numbers.

For example:

XDR Definition:

```xdr
unsigned hyper identifier;
```

XDR Binary:

```b
00000000: ffff ffff ffff ffff                      ........
```

XDR Binary Base64 Encoded:

```base64
//////////8=
```

JSON:

```json
18446744073709551615
```

_Note: JavaScript runtime implementations of JSON do not support numbers that
require more than 53-bits. JavaScript applications should use a JSON decoder
supporting 64-bit numbers in JSON numbrs. JSON decoders in other languages do
not typically have this constraint and support numbers up to 64-bits._

#### Boolean

The XDR boolean data type ([RFC 4506 Section 4.4]) maps to the JSON boolean.

For example:

XDR Definition:

```xdr
bool identifier;
```

XDR Binary:

```b
00000000: 0000 0001                                ....
```

XDR Binary Base64 Encoded:

```base64
AAAAAQ==
```

JSON:

```json
true
```

#### Opaque Data (Fixed Length)

The XDR fixed-length opaque data type ([RFC 4506 Section 4.9]) are represented
as a hexadecimal string.

XDR Definition:

```xdr
opaque identifier[4];
```

XDR Binary:

```
00000000: 6162 6364                                abcd
```

XDR Binary Base64 Encoded:

```
YWJjZA==
```

JSON:

```json
"61626364"
```

#### Opaque Data (Variable Length)

The XDR variable-length opaque data type ([RFC 4506 Section 4.10]) are
represented as a hexadecimal string.

For example:

XDR Definition:

```xdr
opaque identifier<>;
```

XDR Binary:

```
00000000: 0000 0004 6162 6364                      ....abcd
```

XDR Binary Base64 Encoded:

```
AAAABGFiY2Q=
```

JSON:

```json
"61626364"
```

#### String

The string data type ([RFC 4506 Section 4.11]) is interpreted as ASCII and when
encoding the bytes into a string, all non-printable ASCII characters are
escaped.

Character escaping occurs following these rules:

- Nul is escaped as `\0`.
- Tab is escaped as `\t`.
- Line feed is escaped as `\n`.
- Carriage return is escaped as `\r`.
- Backslash is escaped as `\\`.
- Any character in the printable ASCII range `0x20..=0x7e` is not escaped.
- Any other character is hex escaped in the form `\xNN`.

When the encoded string is stored in JSON, backslashes are escaped a second
time because JSON strings escape backslash.

For example:

XDR Definition:

```xdr
string identifier<>;
```

XDR Binary:

```
00000000: 0000 000b 6865 6c6c 6fc3 776f 726c 6400  ....hello.world.
```

XDR Binary Base64 Encoded:

```
AAAAC2hlbGxvw3dvcmxkAA==
```

String:

```
hello\xc3world
```

JSON:

```json
"hello\\xc3world"
```

_Note: When entering the above JSON on a terminal command line, depending on
the shell in use, the backslash (`\`) may need to be additionally escaped as
well, resulting in the need to type `"hello\\\\xc3world"`._

#### Arrays (Fixed Length)

The fixed-length array data type ([RFC 4506 Section 4.12]) is represented as a
JSON array with elements encoded acccording to their type.

For example:

XDR Definition:

```xdr
int identifier[4];
```

XDR Binary:

```
00000000: 0000 0001 0000 0002 0000 0003 0000 0004  ................
```

XDR Binary Base64 Encoded:

```
AAAAAQAAAAIAAAADAAAABA==
```

JSON:

```json
[1, 2, 3, 4]
```

#### Arrays (Variable Length)

The variable-length array data type ([RFC 4506 Section 4.13]) is represented as
a JSON array with elements encoded acccording to their type.

For example:

XDR Definition:

```xdr
int identifier<>;
```

XDR Binary:

```
00000000: 0000 0004 0000 0001 0000 0002 0000 0003  ................
00000010: 0000 0004                                ....
```

XDR Binary Base64 Encoded:

```
AAAABAAAAAEAAAACAAAAAwAAAAQ=
```

JSON:

```json
[1, 2, 3, 4]
```

#### Enum

The XDR enum data type ([RFC 4506 Section 4.3]) is represented in JSON with a
string, derived from the name-identifier that corresponds to its value. The
string is the name-identifier modified to be snake_case, and truncated removing
any shared prefix if there are multiple identifiers in the enum.

For example:

XDR Definition:

```xdr
enum SCValType
{
    SCV_BOOL = 0,
    SCV_VOID = 1,
    SCV_ERROR = 2,
    SCV_U32 = 3,
    SCV_I32 = 4,
//...
}
```

XDR Binary:

```
00000000: 0000 0003                                ....
```

XDR Binary Base64 Encoded:

```
AAAAAw==
```

JSON:

```json
"u32"
```

#### Struct

The XDR struct data type ([RFC 4506 Section 4.14]) is represented in JSON as an
object with each struct component declaration mapping to a key-value pair in
the object. The key is name of the component declaration, modified to be
snake_case.

For example:

XDR Definition:

```xdr
struct TtlEntry
{
    Hash keyHash;
    uint32 liveUntilLedgerSeq;
}
```

XDR Binary:

```
00000000: 0102 0304 0506 0708 0910 1112 1314 1516  ................
00000010: 1718 1920 2122 2324 2526 2728 2930 3132  ... !"#$%&'()012
00000020: 0000 0001                                ....
```

XDR Binary Base64 Encoded:

```
AQIDBAUGBwgJEBESExQVFhcYGSAhIiMkJSYnKCkwMTIAAAAB
```

JSON:

```json
{
  "key_hash": "0102030405060708091011121314151617181920212223242526272829303132",
  "live_until_ledger_seq": 1
}
```

#### Discriminated Union

The XDR discriminated union data type ([RFC 4506 Section 4.15]) is represented
in JSON as either a string, or an object. In both cases the discriminant name
is modified to be snake_case, and truncated removing any shared prefix if there
are multiple identifiers in the enum defined as the discriminant.

The union represents as a JSON string containing the modified and truncated
discriminant name, if the union arm is void.

For example:

XDR Definition:

```xdr
union Asset switch (AssetType type)
{
case ASSET_TYPE_NATIVE:
    void;
case ASSET_TYPE_CREDIT_ALPHANUM4:
    AlphaNum4 alphaNum4;
//...
};
```

XDR Binary:

```
00000000: 0000 0000                                ....
```

XDR Binary Base64 Encoded:

```
AAAAAA==
```

JSON:

```json
"native"
```

The union represents as a JSON object with a single key-value pair, if the
union arm is a type other than void. The key is the modified and truncated
discriminant name. The value is the value of the union arm.

XDR Binary:

```
00000000: 0000 0001 4142 4344 0000 0000 0000 0000  ....ABCD........
00000010: 0000 0000 0000 0000 0000 0000 0000 0000  ................
00000020: 0000 0000 0000 0000 0000 0000            ............
```

XDR Binary Base64 Encoded:

```
AAAAAUFCQ0QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
```

JSON:

```json
{
  "credit_alphanum4": {
    "asset_code": "ABCD",
    "issuer": "GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF"
  }
}
```

#### Void

The XDR void data type ([RFC 4506 Section 4.16]) is omitted in JSON. See
[Discriminated Union](#discriminated-union) for more details.

TODO: What about uses in structs? Or independent uses?

#### Optional Data

The XDR optional data type ([RFC 4506 Section 4.19]) is represented in JSON as
null when not set, or a value depending on the type when set.

For example:

XDR Definition:

```xdr
int* identifier;
```

When not set:

XDR Binary:

```
00000000: 0000 0000                                ....
```

XDR Binary Base64 Encoded:

```
AAAAAA==
```

JSON:

```json
null
```

When set:

XDR Binary:

```
00000000: 0000 0001 0000 0001                      ........
```

XDR Binary Base64 Encoded:

```
AAAAAQAAAAE=
```

JSON:

```json
1
```

### Stellar-Specific Types

#### Address Types

The following Stellar XDR types describing addresses, signers, and keys are
represented in JSON as a string containing a [SEP-23 Strkey]:

TODO: Add XDR examples for each?

- `ScAddress`
- `AccountID`
- `ContractID`
- `MuxedAccount`
- `MuxedAccountMed25519`
- `MuxedEd25519Account`
- `PoolID`
- `ClaimableBalanceID`
- `PublicKey`
- `SignerKey`
- `NodeID`
- `SignerKeyEd25519SignedPayload`

For example:

XDR Definition:

```xdr
union SCAddress switch (SCAddressType type)
{
case SC_ADDRESS_TYPE_ACCOUNT:
    AccountID accountId;
case SC_ADDRESS_TYPE_CONTRACT:
    ContractID contractId;
case SC_ADDRESS_TYPE_MUXED_ACCOUNT:
    MuxedEd25519Account muxedAccount;
case SC_ADDRESS_TYPE_CLAIMABLE_BALANCE:
    ClaimableBalanceID claimableBalanceId;
case SC_ADDRESS_TYPE_LIQUIDITY_POOL:
    PoolID liquidityPoolId;
};
```

Constructed with:

- `SC_ADDRESS_TYPE_MUXED_ACCOUNT`
  - `id`: `1`
  - `ed25519`:
    `0000000000000000000000000000000000000000000000000000000000000000`

XDR Binary:

```
00000000: 0000 0002 0000 0000 0000 0001 0000 0000  ................
00000010: 0000 0000 0000 0000 0000 0000 0000 0000  ................
00000020: 0000 0000 0000 0000 0000 0000            ............
```

XDR Binary Base64 Encoded:

```
AAAAAgAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
```

JSON:

```json
"MAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFNZG"
```

#### Asset Code Types

The following Stellar XDR types should render as a JSON string encoded
according to the below instructions.

- `AssetCode`
- `AssetCode4`
- `AssetCode12`

The `AssetCode` type should be represented according to its sub-components with
no additional information encoded.

TODO: XDR Example

The `AssetCode4` type should be truncated removing all trailing zero bytes.
Bytes should be encoded according to the [String](#string) XDR data type.

TODO: XDR Example

The `AssetCode12` type should be truncated removing all trailing zero bytes
down to the 6th byte, ensuring that irrespective of how many zero bytes exist,
the resulting string represents at least 5-bytes so as to distinguish it
uniquely from any value encoded for `AssetCode4`. Bytes should be encoded
according to the [String](#string) XDR data type.

TODO: XDR Example

### Examples

#### Transaction Envelope

A simplified transaction envelope representation using the externally tagged
union model:

```json
{
  "v1": {
    "tx": {
      "sourceAccount": {
        "ed25519": "GBZXN7PIRZGNMHGA7MUUUF4GWPY5AYPV6LY4UV2GL6VJGIQRXFDNMADI"
      },
      "fee": 100,
      "seqNum": "103420918407103888",
      "timeBounds": {
        "minTime": "0",
        "maxTime": "1640995199"
      },
      "memo": {
        "text": "Hello, Stellar!"
      },
      "operations": [
        {
          "sourceAccount": null,
          "body": {
            "payment": {
              "destination": {
                "ed25519": "GDWZCOEQRODFCH3IETLYXXHYPJ4HZYJNNWTQNKH5JFQI3OHBQRC7AGE5"
              },
              "asset": {
                "native": null
              },
              "amount": "1000000000"
            }
          }
        }
      ],
      "ext": {
        "v": 0
      }
    },
    "signatures": [
      {
        "hint": "00010203",
        "signature": "0011223344556677889900"
      }
    ]
  }
}
```

## Design Rationale

### Naming Conventions

#### Type Names

XDR type names are preserved in their original form from the XDR definitions:

- Stellar XDR types follow PascalCase naming convention (e.g., `AccountId`,
  `TransactionEnvelope`)
- Generated JSON object keys for these types match the original case

#### Field Names

Field naming follows consistent conventions:

- Field names use camelCase format (e.g., `sourceAccount`, `assetCode`)
- The first letter is lowercase
- Acronyms within field names are treated as regular words with only their
  first letter capitalized (e.g., `accountId` not `accountID`)
- Special names like `ed25519` retain their lowercase format as exceptions

#### Enum Values

Enum values are represented as uppercase strings with underscores, matching
their XDR definitions:

- Example: `KEY_TYPE_ED25519`, `ASSET_TYPE_NATIVE`

### String Representation for 64-bit Integers

JavaScript cannot precisely represent all 64-bit integers as numbers due to its
use of IEEE 754 double-precision floating-point format. Using strings ensures
that no precision is lost when transferring data between systems.

### Hexadecimal Encoding for Binary Data

Hexadecimal encoding is chosen for binary data as it is compact, widely
supported, and unambiguous. Each byte is represented by exactly two hexadecimal
characters, making it easy to parse and validate.

### String Representation for Enums

Using string identifiers for enums rather than their numeric values improves
readability and debugging. It also makes the JSON more self-documenting, as the
enum values are explicit.

### Externally Tagged Unions

The externally tagged model for unions provides a clean and explicit
representation that clearly indicates which variant is being used. This
approach aligns well with Serde's serialization model and makes the JSON
structure intuitive to work with in both statically and dynamically typed
languages.

### Null for Optional Values

Using `null` for absent optional values aligns with common JSON practices and
is more explicit than omitting the field entirely.

### Ommission of Floating-Point Types

Stellar XDR does not utilise the Floating-Point types defined in [RFC 4506],
therefore this specification does not include or define them. The
Floating-Point types are defined in the XDR specification as:

- Floating-Point
- Double-Precision Floating-Point
- Quadruple-Precision Floating-Point

## Security Concerns

1. **Precision Loss**: Applications must be careful when handling 64-bit
   integers. Even though they are represented as strings in the JSON,
   applications might convert them to numbers, potentially causing precision
   loss. This is particularly important for values like sequence numbers and
   timepoints.

2. **Consistent Hex Encoding Implementation**: Systems must use consistent
   hexadecimal encoding/decoding implementations to ensure binary data is
   interpreted correctly. Hexadecimal strings should always use lowercase
   letters (a-f) for consistency.

3. **String Escaping**: Proper implementation of the string escaping rules via
   the `escape_bytes` crate or equivalent is essential to prevent injection
   attacks and ensure strings are correctly processed.

4. **Validation**: When converting from JSON to XDR, implementations should
   validate that the JSON structure adheres to the expected schema to prevent
   injection attacks or malformed data.

5. **Canonicalization**: This specification does not define a canonical form
   for the JSON representation. Applications requiring cryptographic
   verification of JSON data may need additional canonicalization steps.

## Changelog

- `v0.1.0`: Initial draft. [PR to be created]

[SEP-23 Strkey]: sep-0023.md
[RFC 4506]: https://datatracker.ietf.org/doc/html/rfc4506
[RFC 4506 Section 4.1]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.1
[RFC 4506 Section 4.2]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.2
[RFC 4506 Section 4.3]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.3
[RFC 4506 Section 4.4]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.4
[RFC 4506 Section 4.5]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.5
[RFC 4506 Section 4.9]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.9
[RFC 4506 Section 4.10]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.10
[RFC 4506 Section 4.11]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.11
[RFC 4506 Section 4.12]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.12
[RFC 4506 Section 4.13]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.13
[RFC 4506 Section 4.14]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.14
[RFC 4506 Section 4.15]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.15
[RFC 4506 Section 4.16]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.16
[RFC 4506 Section 4.19]:
  https://datatracker.ietf.org/doc/html/rfc4506#section-4.19
