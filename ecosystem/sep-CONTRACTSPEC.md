## Preamble

```
SEP: CONTRACTSPEC
Title: Contract Interface Specification
Author: Leigh McCulloch
Track: Standard
Status: Draft
Created: 2025-03-26
Updated: 2025-03-26
Version: 0.1.0
Discussion: https://github.com/stellar/stellar-protocol/discussions/TBD
```

## Simple Summary

A standard for contracts to self-describe their call interface.

## Dependencies

None.

## Motivation

It should be possible for off-chain tooling and systems to discover the functions exported by a contract and intended to
be called and passed in as inputs.

Wasm files contain a list of exported functions, their names, their parameters and return values, and the primitive
types of the parameters and return values. However, no names are preserved for each parameter, and the primitive types
do not capture the host types that Soroban provides.

Contracts need to be able to communicate a richer set of information about their interface, so that:

- Clients can be code generated with names and rich types for parameters.
- Tooling can present a human friendly interface for calling contracts.

## Abstract

This SEP defines a way well-known location where contracts can communicate to off-chain tooling information about the
contract interface, sufficient to reproduce the contract interface in code.

## Specification

### Wasm Custom Section

Spec entries are stored in one `contractspecv0` Wasm custom section of the contract Wasm file.

Multiple entries may exist in a single custom section.

### XDR Encoding

Each entry is structured and encoded using the `SCSpecEntry` type.

When encoding entries and storing them in the custom section they should be appended to one another with no frame, no
header, and no prefix, including no length prefix. They should be in effect a stream of `SCSpecEntry` XDR binary encoded
values.

```
const SC_SPEC_DOC_LIMIT = 1024;

enum SCSpecType
{
    SC_SPEC_TYPE_VAL = 0,

    // Types with no parameters.
    SC_SPEC_TYPE_BOOL = 1,
    SC_SPEC_TYPE_VOID = 2,
    SC_SPEC_TYPE_ERROR = 3,
    SC_SPEC_TYPE_U32 = 4,
    SC_SPEC_TYPE_I32 = 5,
    SC_SPEC_TYPE_U64 = 6,
    SC_SPEC_TYPE_I64 = 7,
    SC_SPEC_TYPE_TIMEPOINT = 8,
    SC_SPEC_TYPE_DURATION = 9,
    SC_SPEC_TYPE_U128 = 10,
    SC_SPEC_TYPE_I128 = 11,
    SC_SPEC_TYPE_U256 = 12,
    SC_SPEC_TYPE_I256 = 13,
    SC_SPEC_TYPE_BYTES = 14,
    SC_SPEC_TYPE_STRING = 16,
    SC_SPEC_TYPE_SYMBOL = 17,
    SC_SPEC_TYPE_ADDRESS = 19,
    SC_SPEC_TYPE_MUXED_ADDRESS = 20,

    // Types with parameters.
    SC_SPEC_TYPE_OPTION = 1000,
    SC_SPEC_TYPE_RESULT = 1001,
    SC_SPEC_TYPE_VEC = 1002,
    SC_SPEC_TYPE_MAP = 1004,
    SC_SPEC_TYPE_TUPLE = 1005,
    SC_SPEC_TYPE_BYTES_N = 1006,

    // User defined types.
    SC_SPEC_TYPE_UDT = 2000
};

struct SCSpecTypeOption
{
    SCSpecTypeDef valueType;
};

struct SCSpecTypeResult
{
    SCSpecTypeDef okType;
    SCSpecTypeDef errorType;
};

struct SCSpecTypeVec
{
    SCSpecTypeDef elementType;
};

struct SCSpecTypeMap
{
    SCSpecTypeDef keyType;
    SCSpecTypeDef valueType;
};

struct SCSpecTypeTuple
{
    SCSpecTypeDef valueTypes<12>;
};

struct SCSpecTypeBytesN
{
    uint32 n;
};

struct SCSpecTypeUDT
{
    string name<60>;
};

union SCSpecTypeDef switch (SCSpecType type)
{
case SC_SPEC_TYPE_VAL:
case SC_SPEC_TYPE_BOOL:
case SC_SPEC_TYPE_VOID:
case SC_SPEC_TYPE_ERROR:
case SC_SPEC_TYPE_U32:
case SC_SPEC_TYPE_I32:
case SC_SPEC_TYPE_U64:
case SC_SPEC_TYPE_I64:
case SC_SPEC_TYPE_TIMEPOINT:
case SC_SPEC_TYPE_DURATION:
case SC_SPEC_TYPE_U128:
case SC_SPEC_TYPE_I128:
case SC_SPEC_TYPE_U256:
case SC_SPEC_TYPE_I256:
case SC_SPEC_TYPE_BYTES:
case SC_SPEC_TYPE_STRING:
case SC_SPEC_TYPE_SYMBOL:
case SC_SPEC_TYPE_ADDRESS:
case SC_SPEC_TYPE_MUXED_ADDRESS:
    void;
case SC_SPEC_TYPE_OPTION:
    SCSpecTypeOption option;
case SC_SPEC_TYPE_RESULT:
    SCSpecTypeResult result;
case SC_SPEC_TYPE_VEC:
    SCSpecTypeVec vec;
case SC_SPEC_TYPE_MAP:
    SCSpecTypeMap map;
case SC_SPEC_TYPE_TUPLE:
    SCSpecTypeTuple tuple;
case SC_SPEC_TYPE_BYTES_N:
    SCSpecTypeBytesN bytesN;
case SC_SPEC_TYPE_UDT:
    SCSpecTypeUDT udt;
};

struct SCSpecUDTStructFieldV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string name<30>;
    SCSpecTypeDef type;
};

struct SCSpecUDTStructV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string lib<80>;
    string name<60>;
    SCSpecUDTStructFieldV0 fields<40>;
};

struct SCSpecUDTUnionCaseVoidV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string name<60>;
};

struct SCSpecUDTUnionCaseTupleV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string name<60>;
    SCSpecTypeDef type<12>;
};

enum SCSpecUDTUnionCaseV0Kind
{
    SC_SPEC_UDT_UNION_CASE_VOID_V0 = 0,
    SC_SPEC_UDT_UNION_CASE_TUPLE_V0 = 1
};

union SCSpecUDTUnionCaseV0 switch (SCSpecUDTUnionCaseV0Kind kind)
{
case SC_SPEC_UDT_UNION_CASE_VOID_V0:
    SCSpecUDTUnionCaseVoidV0 voidCase;
case SC_SPEC_UDT_UNION_CASE_TUPLE_V0:
    SCSpecUDTUnionCaseTupleV0 tupleCase;
};

struct SCSpecUDTUnionV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string lib<80>;
    string name<60>;
    SCSpecUDTUnionCaseV0 cases<50>;
};

struct SCSpecUDTEnumCaseV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string name<60>;
    uint32 value;
};

struct SCSpecUDTEnumV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string lib<80>;
    string name<60>;
    SCSpecUDTEnumCaseV0 cases<50>;
};

struct SCSpecUDTErrorEnumCaseV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string name<60>;
    uint32 value;
};

struct SCSpecUDTErrorEnumV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string lib<80>;
    string name<60>;
    SCSpecUDTErrorEnumCaseV0 cases<50>;
};

struct SCSpecFunctionInputV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string name<30>;
    SCSpecTypeDef type;
};

struct SCSpecFunctionV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    SCSymbol name;
    SCSpecFunctionInputV0 inputs<10>;
    SCSpecTypeDef outputs<1>;
};

enum SCSpecEntryKind
{
    SC_SPEC_ENTRY_FUNCTION_V0 = 0,
    SC_SPEC_ENTRY_UDT_STRUCT_V0 = 1,
    SC_SPEC_ENTRY_UDT_UNION_V0 = 2,
    SC_SPEC_ENTRY_UDT_ENUM_V0 = 3,
    SC_SPEC_ENTRY_UDT_ERROR_ENUM_V0 = 4
};

union SCSpecEntry switch (SCSpecEntryKind kind)
{
case SC_SPEC_ENTRY_FUNCTION_V0:
    SCSpecFunctionV0 functionV0;
case SC_SPEC_ENTRY_UDT_STRUCT_V0:
    SCSpecUDTStructV0 udtStructV0;
case SC_SPEC_ENTRY_UDT_UNION_V0:
    SCSpecUDTUnionV0 udtUnionV0;
case SC_SPEC_ENTRY_UDT_ENUM_V0:
    SCSpecUDTEnumV0 udtEnumV0;
case SC_SPEC_ENTRY_UDT_ERROR_ENUM_V0:
    SCSpecUDTErrorEnumV0 udtErrorEnumV0;
};
```

Ref: https://github.com/stellar/stellar-xdr/blob/curr/Stellar-contract-spec.x

#### XDR Spec Types

##### `SC_SPEC_TYPE_VAL`

##### `SC_SPEC_TYPE_BOOL`

##### `SC_SPEC_TYPE_VOID`

##### `SC_SPEC_TYPE_ERROR`

##### `SC_SPEC_TYPE_U32`

##### `SC_SPEC_TYPE_I32`

##### `SC_SPEC_TYPE_U64`

##### `SC_SPEC_TYPE_I64`

##### `SC_SPEC_TYPE_TIMEPOINT`

##### `SC_SPEC_TYPE_DURATION`

##### `SC_SPEC_TYPE_U128`

##### `SC_SPEC_TYPE_I128`

##### `SC_SPEC_TYPE_U256`

##### `SC_SPEC_TYPE_I256`

##### `SC_SPEC_TYPE_BYTES`

##### `SC_SPEC_TYPE_STRING`

##### `SC_SPEC_TYPE_SYMBOL`

##### `SC_SPEC_TYPE_ADDRESS`

##### `SC_SPEC_TYPE_MUXED_ADDRESS`

##### `SC_SPEC_TYPE_OPTION`

    SCSpecTypeOption option;

##### `SC_SPEC_TYPE_RESULT`

    SCSpecTypeResult result;

##### `SC_SPEC_TYPE_VEC`

    SCSpecTypeVec vec;

##### `SC_SPEC_TYPE_MAP`

    SCSpecTypeMap map;

##### `SC_SPEC_TYPE_TUPLE`

    SCSpecTypeTuple tuple;

##### `SC_SPEC_TYPE_BYTES_N`

    SCSpecTypeBytesN bytesN;

##### `SC_SPEC_TYPE_UDT`

    SCSpecTypeUDT udt;

## Example Usage

### Rust soroban-sdk

Contract specs are automaticlaly inserted in code with the Rust `soroban-sdk` by using the [`contractimpl!`],
[`contracttype`], [`contracterror`] macros.

[`contractimpl!()`]: https://docs.rs/soroban-sdk/latest/soroban_sdk/macro.contractmeta.html
[`contracttype!()`]: https://docs.rs/soroban-sdk/latest/soroban_sdk/macro.contracttype.html
[`contracterror!()`]: https://docs.rs/soroban-sdk/latest/soroban_sdk/macro.contracterror.html

## Limitations

### No Claims to SEP Implementations

This proposal does not support a contract claiming to implement any specific interface, or SEP describing an interface.
[SEP-47] provides a way for off-chain systems for discover which SEPs a contract intends to implement.

## Design Rationale

### Custom Sections

The Soroban Environment uses custom sections to store meta information about a contract's Soroban Environment
compatibility. That was documented in [CAP-46-1].

Custom sections are additional binary sections of Wasm files that can be used for any purpose. The Wasm when executing
does not have access to the custom section and is not affected by it.

[CAP-46-1]: ../core/cap-0046-01.md

### XDR Encoding

The XDR encoding is ...

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

Contracts may contain spec entries that do not align with the actual functions exported by the contract. A contract may
include spec entries for funtions that do not exist. Or a contract may omit spec entries for functions that do exist.

## Changelog

- `v0.1.0`: Initial draft capturing the status quo as implemented in soroban-sdk.
