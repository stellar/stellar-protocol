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

The XDR 32-bit signed integer data type ([RFC 4506 Section 4.1]) maps to JSON numbers.

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

The XDR 32-bit unsigned integer data type ([RFC 4506 Section 4.2]) maps to JSON numbers.

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

The XDR 64-bit signed integer data type ([RFC 4506 Section 4.5]) maps to JSON numbers.

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

The XDR 64-bit signed integer data type ([RFC 4506 Section 4.5]) maps to JSON numbers.

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

The XDR fixed-length opaque data type ([RFC 4506 Section 4.9]) are represented as a hexadecimal string.

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

The fixed-length array data type ([RFC 4506 Section 4.12]) are represented as JSON arrays with elements
encoding acccording to their type.

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

      4.13. Variable-Length Array ....................................11
      4.14. Structure ................................................12
      4.15. Discriminated Union ......................................12
      4.16. Void .....................................................13
      4.17. Constant .................................................13
      4.18. Typedef ..................................................13
      4.19. Optional-Data ............................................14

#### Arrays (Variable Length)

Variable-length arrays (XDR `array<>`) are also represented as JSON arrays:

```json
["value1", "value2", "value3"]
```

#### Enum

XDR enum data types ([RFC 4506 Section 4.3]) are represented in JSON with a
string, derived from the name-identifier that corresponds to their value. The
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
...
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

XDR structs are mapped to JSON objects, with each field name as a property:

```json
{
  "fieldName1": "value1",
  "fieldName2": 42
}
```

#### Union

XDR discriminated unions are represented using the serde externally tagged model, where the tag is the variant name and
the value is the variant's content:

```json
{
  "accountId": "GBZXN7PIRZGNMHGA7MUUUF4GWPY5AYPV6LY4UV2GL6VJGIQRXFDNMADI"
}
```

For a union with multiple variants, each variant would be represented as a separate object with a single key-value pair:

```json
{
  "native": null
}
```

Or for variants with content:

```json
{
  "alphanum4": {
    "assetCode": "USD",
    "issuer": "GBZXN7PIRZGNMHGA7MUUUF4GWPY5AYPV6LY4UV2GL6VJGIQRXFDNMADI"
  }
}
```

#### Void

XDR void is represented as `null` in JSON.

#### Optional Types (Nullable)

XDR optional types (`option<>`) are represented as either the JSON value or `null`:

```json
null
```

or

```json
"some value"
```

### Stellar-Specific Types

#### AccountID

Represented as a Stellar public key in string format:

```json
"GBZXN7PIRZGNMHGA7MUUUF4GWPY5AYPV6LY4UV2GL6VJGIQRXFDNMADI"
```

#### MuxedAccount

Represented as either a standard account or a multiplexed account:

```json
{
  "type": "KEY_TYPE_ED25519",
  "ed25519": "GBZXN7PIRZGNMHGA7MUUUF4GWPY5AYPV6LY4UV2GL6VJGIQRXFDNMADI"
}
```

or

```json
{
  "type": "KEY_TYPE_MUXED_ED25519",
  "med25519": {
    "id": "123",
    "ed25519": "GBZXN7PIRZGNMHGA7MUUUF4GWPY5AYPV6LY4UV2GL6VJGIQRXFDNMADI"
  }
}
```

#### Asset

Represented based on asset type:

```json
{
  "type": "ASSET_TYPE_NATIVE"
}
```

or

```json
{
  "type": "ASSET_TYPE_CREDIT_ALPHANUM4",
  "alphaNum4": {
    "assetCode": "USD",
    "issuer": "GBZXN7PIRZGNMHGA7MUUUF4GWPY5AYPV6LY4UV2GL6VJGIQRXFDNMADI"
  }
}
```

#### Hash

Represented as a base64 or hex string (implementation may vary, but must be consistent):

```json
"AAABBBCCC=="
```

#### Timepoint

XDR timepoint (uint64) is represented as a string to avoid precision issues:

```json
"1639084800"
```

### Examples

#### Transaction Envelope

A simplified transaction envelope representation using the externally tagged union model:

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

- Stellar XDR types follow PascalCase naming convention (e.g., `AccountId`, `TransactionEnvelope`)
- Generated JSON object keys for these types match the original case

#### Field Names

Field naming follows consistent conventions:

- Field names use camelCase format (e.g., `sourceAccount`, `assetCode`)
- The first letter is lowercase
- Acronyms within field names are treated as regular words with only their first letter capitalized (e.g., `accountId`
  not `accountID`)
- Special names like `ed25519` retain their lowercase format as exceptions

#### Enum Values

Enum values are represented as uppercase strings with underscores, matching their XDR definitions:

- Example: `KEY_TYPE_ED25519`, `ASSET_TYPE_NATIVE`

### String Representation for 64-bit Integers

JavaScript cannot precisely represent all 64-bit integers as numbers due to its use of IEEE 754 double-precision
floating-point format. Using strings ensures that no precision is lost when transferring data between systems.

### Hexadecimal Encoding for Binary Data

Hexadecimal encoding is chosen for binary data as it is compact, widely supported, and unambiguous. Each byte is
represented by exactly two hexadecimal characters, making it easy to parse and validate.

### String Representation for Enums

Using string identifiers for enums rather than their numeric values improves readability and debugging. It also makes
the JSON more self-documenting, as the enum values are explicit.

### Externally Tagged Unions

The externally tagged model for unions provides a clean and explicit representation that clearly indicates which variant
is being used. This approach aligns well with Serde's serialization model and makes the JSON structure intuitive to work
with in both statically and dynamically typed languages.

### Null for Optional Values

Using `null` for absent optional values aligns with common JSON practices and is more explicit than omitting the field
entirely.

### Ommission of Floating-Point Types

Stellar XDR does not utilise the Floating-Point types defined in [RFC 4506],
therefore this specification does not include or define them. The Floating-Point types are defined in the XDR specification as:
- Floating-Point
- Double-Precision Floating-Point
- Quadruple-Precision Floating-Point

## Security Concerns

1. **Precision Loss**: Applications must be careful when handling 64-bit integers. Even though they are represented as
   strings in the JSON, applications might convert them to numbers, potentially causing precision loss. This is
   particularly important for values like sequence numbers and timepoints.

2. **Consistent Hex Encoding Implementation**: Systems must use consistent hexadecimal encoding/decoding implementations
   to ensure binary data is interpreted correctly. Hexadecimal strings should always use lowercase letters (a-f) for
   consistency.

3. **String Escaping**: Proper implementation of the string escaping rules via the `escape_bytes` crate or equivalent is
   essential to prevent injection attacks and ensure strings are correctly processed.

4. **Validation**: When converting from JSON to XDR, implementations should validate that the JSON structure adheres to
   the expected schema to prevent injection attacks or malformed data.

5. **Canonicalization**: This specification does not define a canonical form for the JSON representation. Applications
   requiring cryptographic verification of JSON data may need additional canonicalization steps.

## Changelog

- `v0.1.0`: Initial draft. [PR to be created]

[RFC 4506]: https://datatracker.ietf.org/doc/html/rfc4506
[RFC 4506 Section 4.1]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.1
[RFC 4506 Section 4.2]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.2
[RFC 4506 Section 4.3]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.3
[RFC 4506 Section 4.4]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.4
[RFC 4506 Section 4.5]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.5
[RFC 4506 Section 4.6]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.6
[RFC 4506 Section 4.7]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.7
[RFC 4506 Section 4.8]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.8
[RFC 4506 Section 4.9]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.9
[RFC 4506 Section 4.10]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.10
[RFC 4506 Section 4.11]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.11
[RFC 4506 Section 4.12]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.12
[RFC 4506 Section 4.13]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.13
[RFC 4506 Section 4.14]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.14
[RFC 4506 Section 4.15]: https://datatracker.ietf.org/doc/html/rfc4506#section-4.15
