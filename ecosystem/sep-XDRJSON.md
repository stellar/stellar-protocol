## Preamble

```
SEP: To Be Assigned
Title: XDR-JSON
Author: Leigh McCulloch
Track: Standard
Status: Draft
Created: 2025-04-16
Updated: 2025-04-16
Version: 0.1.0
Discussion: [Discussion link to be added]
```

## Simple Summary

This proposal defines XDR-JSON, a standard mapping between Stellar's XDR
(External Data Representation) structures and a JSON representation.

## Dependencies

None.

## Motivation

Stellar's protocol data is defined in XDR, a compact binary format that is not
human-readable. In most APIs when the XDR must be shared as text it is base64
encoded, which is also not human-readable or easily mutated. Developer tooling
needs to represent this data in a more accessible format either so it can be
read or modified.

## Abstract

This proposal defines how a subset of the XDR data types defined in [RFC 4506]
is mapped to a JSON representation. It covers primitive types (integers,
booleans), complex types (structs, unions, enums), and special Stellar-specific
types (AccountID, Asset, etc.). The specification ensures that XDR data can be
consistently serialized to JSON and deserialized back to XDR without data loss,
while providing human readability, specifically developers.

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

The XDR 64-bit unsigned integer data type ([RFC 4506 Section 4.5]) maps to JSON
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

```b
00000000: 6162 6364                                abcd
```

XDR Binary Base64 Encoded:

```base64
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

```b
00000000: 0000 0004 6162 6364                      ....abcd
```

XDR Binary Base64 Encoded:

```base64
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

```b
00000000: 0000 000b 6865 6c6c 6fc3 776f 726c 6400  ....hello.world.
```

XDR Binary Base64 Encoded:

```base64
AAAAC2hlbGxvw3dvcmxkAA==
```

String:

```text
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
JSON array with elements encoded according to their type.

For example:

XDR Definition:

```xdr
int identifier[4];
```

XDR Binary:

```b
00000000: 0000 0001 0000 0002 0000 0003 0000 0004  ................
```

XDR Binary Base64 Encoded:

```base64
AAAAAQAAAAIAAAADAAAABA==
```

JSON:

```json
[1, 2, 3, 4]
```

#### Arrays (Variable Length)

The variable-length array data type ([RFC 4506 Section 4.13]) is represented as
a JSON array with elements encoded according to their type.

For example:

XDR Definition:

```xdr
int identifier<>;
```

XDR Binary:

```b
00000000: 0000 0004 0000 0001 0000 0002 0000 0003  ................
00000010: 0000 0004                                ....
```

XDR Binary Base64 Encoded:

```base64
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

```b
00000000: 0000 0003                                ....
```

XDR Binary Base64 Encoded:

```base64
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

```b
00000000: 0102 0304 0506 0708 0910 1112 1314 1516  ................
00000010: 1718 1920 2122 2324 2526 2728 2930 3132  ... !"#$%&'()012
00000020: 0000 0001                                ....
```

XDR Binary Base64 Encoded:

```base64
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
are multiple identifiers in the enum defined as the discriminant. If the union
cases are integers, then the discriminant name becomes the name of the
discriminant suffixed by the integer.

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

```b
00000000: 0000 0000                                ....
```

XDR Binary Base64 Encoded:

```base64
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

```b
00000000: 0000 0001 4142 4344 0000 0000 0000 0000  ....ABCD........
00000010: 0000 0000 0000 0000 0000 0000 0000 0000  ................
00000020: 0000 0000 0000 0000 0000 0000            ............
```

XDR Binary Base64 Encoded:

```base64
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

When the union cases are integers, the union represents as a JSON string with a
name matching the discriminant name suffixed with the integer.

For example:

XDR Definition:

```xdr
union SorobanTransactionMetaExt switch (int v)
{
case 0:
    void;
case 1:
    SorobanTransactionMetaExtV1 v1;
};

```

XDR Binary:

```b
00000000: 0000 0000                                ....
```

XDR Binary Base64 Encoded:

```base64
AAAAAA==
```

JSON:

```json
"v0"
```

#### Void

The XDR void data type ([RFC 4506 Section 4.16]) is omitted in JSON. See
[Discriminated Union](#discriminated-union) for more details.

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

```b
00000000: 0000 0000                                ....
```

XDR Binary Base64 Encoded:

```base64
AAAAAA==
```

JSON:

```json
null
```

When set:

XDR Binary:

```b
00000000: 0000 0001 0000 0001                      ........
```

XDR Binary Base64 Encoded:

```base64
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

- `ScAddress`
  - `SC_ADDRESS_TYPE_ACCOUNT` - `G` strkey
  - `SC_ADDRESS_TYPE_CONTRACT` - `C` strkey
  - `SC_ADDRESS_TYPE_MUXED_ACCOUNT` - `M` strkey
  - `SC_ADDRESS_TYPE_CLAIMABLE_BALANCE` - `B` strkey
  - `SC_ADDRESS_TYPE_LIQUIDITY_POOL` - `L` strkey
- `AccountID` - `G` strkey
- `ContractID` - `C` strkey
- `MuxedAccount`
  - `KEY_TYPE_ED25519` - `G` strkey
  - `KEY_TYPE_MUXED_ED2551` - `M` strkey
- `MuxedAccountMed25519` - `M` strkey
- `MuxedEd25519Account` - `M` strkey
- `PoolID` - `L` strkey
- `ClaimableBalanceID` - `B` strkey
- `PublicKey`
  - `PUBLIC_KEY_TYPE_ED25519` - `G` strkey
- `NodeID`
  - `PUBLIC_KEY_TYPE_ED25519` - `G` strkey
- `SignerKey`
  - `SIGNER_KEY_TYPE_ED25519` - `G` strkey
  - `SIGNER_KEY_TYPE_PRE_AUTH_TX` - `T` strkey
  - `SIGNER_KEY_TYPE_HASH_X` - `X` strkey
  - `SIGNER_KEY_TYPE_ED25519_SIGNED_PAYLOAD` - `P` strkey
- `SignerKeyEd25519SignedPayload` - `P` strkey

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
  - `muxedAccount:`
    - `id`: `1`
    - `ed25519`:
      `0000000000000000000000000000000000000000000000000000000000000000`

XDR Binary:

```b
00000000: 0000 0002 0000 0000 0000 0001 0000 0000  ................
00000010: 0000 0000 0000 0000 0000 0000 0000 0000  ................
00000020: 0000 0000 0000 0000 0000 0000            ............
```

XDR Binary Base64 Encoded:

```base64
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

The `AssetCode` type should be represented according `AssetCode4` and
`AssetCode12`. `AssetCode4` is always 4 encoded characters or less.
`AssetCode12` is always 5 encoded characters or more.

The `AssetCode4` type should be truncated removing all trailing zero bytes.
Bytes should then be encoded according to the [String](#string) XDR data type.

For example:

XDR Definition:

```xdr
typedef opaque AssetCode4[4];
```

An `AssetCode4` filling three bytes:

XDR Binary:

```b
00000000: 4142 4300                                ABC.
```

XDR Binary Base64 Encoded:

```base64
QUJDAA==
```

JSON:

```json
"ABC"
```

The `AssetCode12` type should be truncated removing all trailing zero bytes
down to and including the 6th byte, ensuring that irrespective of how many zero
bytes exist, the resulting encoded string represents at least 5-bytes so as to
distinguish it uniquely from any value encoded for `AssetCode4`. Bytes should
be encoded according to the [String](#string) XDR data type.

For example:

XDR Definition:

```xdr
typedef opaque AssetCode12[12];
```

An `AssetCode12` filling five bytes:

XDR Binary:

```b
00000000: 4142 4344 4500 0000 0000 0000            ABCDE.......
```

XDR Binary Base64 Encoded:

```base64
QUJDREUAAAAAAAAA
```

JSON:

```json
"ABCDE"
```

An `AssetCode12` filling three bytes:

XDR Binary:

```b
00000000: 4142 4300 0000 0000 0000 0000            ABC.........
```

XDR Binary Base64 Encoded:

```base64
QUJDAAAAAAAAAAAA
```

JSON:

```json
"ABC\\0\\0"
```

### JSON Schema

All JSON objects should allow, but not require, the presence of a `$schema`
property with a corresponding value being a URL of a JSON Schema document
describing the type described by the rest of the JSON objects.

For example, for the `Asset` type, the `$schema` property can be optionally
provided:

```json
{
  "$schema": "https://stellar.org/schema/xdr-json/main/Asset.json",
  "credit_alphanum4": {
    "asset_code": "ABCD",
    "issuer": "GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF"
  }
}
```

## Examples

### `TransactionEnvelope`

XDR Binary:

```b
00000000: 0000 0002 0000 0000 e699 2664 c18d f5eb  ..........&d....
00000010: 74cc a2e0 764d 8f0c 963a 97c3 6231 5584  t...vM...:..b1U.
00000020: c6ca f0eb 47a6 2d00 002a 9a64 0000 1a6e  ....G.-..*.d...n
00000030: 0000 0001 0000 0000 0000 0000 0000 0001  ................
00000040: 0000 0000 0000 0018 0000 0001 0000 0001  ................
00000050: 0000 0000 0000 0001 0000 0000 0000 0001  ................
00000060: 0000 0000 0000 0000 0000 0001 0000 0006  ................
00000070: 0000 0001 d792 8b72 c270 3ccf eaf7 eb9f  .......r.p<.....
00000080: f4ef 4d50 4a55 a8b9 79fc 9b45 0ea2 c842  ..MPJU..y..E...B
00000090: b4d1 ce61 0000 0014 0000 0001 0002 3d7d  ...a..........=}
000000a0: 0000 0000 0000 00f8 0000 0000 002a 9a00  .............*..
000000b0: 0000 0001 47a6 2d00 0000 0040 2b0e dc5b  ....G.-....@+..[
000000c0: a942 3e0a c764 4665 7494 5855 b74c 3207  .B>..dFet.XU.L2.
000000d0: b7f2 ae69 a433 a16b df9c 293d c2bc 58a7  ...i.3.k..)=..X.
000000e0: 1778 a4e5 e014 3e6a 4135 e0c6 6da5 a79a  .x....>jA5..m...
000000f0: f4b3 1d85 7a29 696d e924 0d04            ....z)im.$..
```

XDR Binary Base64 Encoded:

```base64
AAAAAgAAAADmmSZkwY3163TMouB2TY8MljqXw2IxVYTGyvDrR6YtAAAqmmQAABpuAAAAAQAAAAAAAAAAAAAAAQAAAAAAAAAYAAAAAQAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAAAAAABAAAABgAAAAHXkotywnA8z+r365/0701QSlWouXn8m0UOoshCtNHOYQAAABQAAAABAAI9fQAAAAAAAAD4AAAAAAAqmgAAAAABR6YtAAAAAEArDtxbqUI+CsdkRmV0lFhVt0wyB7fyrmmkM6Fr35wpPcK8WKcXeKTl4BQ+akE14MZtpaea9LMdhXopaW3pJA0E
```

JSON:

```json
{
  "tx": {
    "tx": {
      "source_account": "GDTJSJTEYGG7L23UZSROA5SNR4GJMOUXYNRDCVMEY3FPB22HUYWQBZIA",
      "fee": 2792036,
      "seq_num": 29059748724737,
      "cond": "none",
      "memo": "none",
      "operations": [
        {
          "source_account": null,
          "body": {
            "invoke_host_function": {
              "host_function": {
                "create_contract": {
                  "contract_id_preimage": {
                    "asset": "native"
                  },
                  "executable": "stellar_asset"
                }
              },
              "auth": []
            }
          }
        }
      ],
      "ext": {
        "v1": {
          "ext": "v0",
          "resources": {
            "footprint": {
              "read_only": [],
              "read_write": [
                {
                  "contract_data": {
                    "contract": "CDLZFC3SYJYDZT7K67VZ75HPJVIEUVNIXF47ZG2FB2RMQQVU2HHGCYSC",
                    "key": "ledger_key_contract_instance",
                    "durability": "persistent"
                  }
                }
              ]
            },
            "instructions": 146813,
            "read_bytes": 0,
            "write_bytes": 248
          },
          "resource_fee": 2791936
        }
      }
    },
    "signatures": [
      {
        "hint": "47a62d00",
        "signature": "2b0edc5ba9423e0ac764466574945855b74c3207b7f2ae69a433a16bdf9c293dc2bc58a71778a4e5e0143e6a4135e0c66da5a79af4b31d857a29696de9240d04"
      }
    ]
  }
}
```

## Design Rationale

### Number Representation for 64-bit Integers

JSON has no bit-size limit on numbers. However, JavaScript cannot precisely
represent numbers greater than 53-bits due to its use of IEEE 754 that output
64-bit numbers in JSON to ensure no precision is lost. XDR-JSON does not use
the string type for 64-bit integers to JSON numbers because non-native JSON
decoders in JavaScript support 64-bit numbers and most other languages do also.

### Hexadecimal Encoding for Binary Data

Hexadecimal encoding is chosen for binary data as it is compact, widely
supported, and easy for a human to understand. Each byte is represented by
exactly two hexadecimal characters, making it easy to parse and validate. Many
of the fields in the Stellar XDR that contain binary data are things like
hashes, which are commonly rendered as hex in applications.

### String Representation for Enums

Using string identifiers for enums rather than their numeric values improves
readability and debugging. It also makes the JSON more self-documenting, as the
enum values state what their value means.

### Externally Tagged Unions

Unions are externally tagged, meaning the discriminant that signals which arm
of the union is active, is placed outside the value as a key in an outer
object. The format is more compact than alternatives for including the
discriminant alongside the value. The approach also lends itself well to when
no value exists in the void case and the object can be simplified into the
discriminant string.

### Null for Optional Values

Using `null` for absent optional values aligns with common JSON practices and
results in a stable encoded representation where all fields are present even
when optional.

### Omission of Floating-Point Types

Stellar XDR does not utilise the Floating-Point types defined in [RFC 4506],
therefore this specification does not include or define them. The
Floating-Point types are defined in the XDR specification as:

- Floating-Point
- Double-Precision Floating-Point
- Quadruple-Precision Floating-Point

## Security Concerns

### Changed with Protocols

XDR-JSON will naturally change from one protocol to the next because the
Stellar XDR can structurally change with the release of new protcols. While
those structural changes will not be binary breaking to the Stellar Protocol,
any use of XDR-JSON should be limited to short-lived developer facing user
interfaces. Other uses requiring more stability can use embedding the `$schema`
as a way to signal schema version and fallback to past versions of the
implementation for passing them appropriately.

### Precision Loss with 64-bit Numbers

XDR-JSON uses the JSON number type for 64-bit integers. JSON has no bit-size
limit. However, JavaScript cannot precisely represent numbers greater than
53-bits due to its use of IEEE 754 that output 64-bit numbers in JSON to ensure
no precision is lost. JavaScript applications must use a non-native JSON
decoder to accurately decode 64-bit numbers otherwise precision may be lost.

## Breaking Changes

Two types of breaking changes can occur in relation to XDR-JSON:

- As a result of XDR structural changes.

  These changes will not result in a change or version change to this document.
  While the structure of the XDR will cause the schema of XDR-JSON to change,
  the XDR-JSON specification itself will not. Applications none-the-less still
  need to coordinate these breakages if the format is used for anything more
  than a short-lived use case.

- As a result of the XDR-JSON specification defined in this proposal.

  These changes will result in a change to this document and an update to the
  specifications version, because the specification itself is changing. These
  will be rarer but will still be coordinated with new protocol releases where
  practical to reduce the need for additional coordination points for the
  Stellar community.

## Implementations

- JSON Schema:
  <https://stellar.org/schema/xdr-json/main/TransactionEnvelope.json>
- Rust: <https://github.com/stellar/rs-stellar-xdr>

## Changelog

- `v22.0.0`: Initial SEP matching existing Protocol v22 XDR-JSON.

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
