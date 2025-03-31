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

A standard for contracts to self-describe their exported interface.

## Dependencies

None.

## Motivation

It is necessary for tooling, SDKs, and off-chain systems to be able to discover
the functions exported by a contract. Tooling and SDKs must be able to generate
client code for calling contracts. Off-chain systems must be able to present a
human friendly interface describing a called contract interface.

All Wasm files contain a list of exported functions, but the contents of that
list is primitive. The list includes their names, parameters, return values,
but only the primitive types (e.g. i64, i32, u64, u32) of those values, and
nothing about the Soroban host types (e.g. String, Symbol, Map, Vec, I128,
U256, etc) the functions accept.

A richer interface is needed to fully express the Soroban host types a function
expects, and to be able to recreate a contract interface exactly as it was
originally coded.

## Abstract

This SEP defines a format for communicating about a contract's interface, as
well as a common location to store the contract interface inside the Wasm
files.

## Specification

### Wasm Custom Section

The contract interface is stored in one `contractspecv0` Wasm custom section of
the contract Wasm file.

### XDR Encoding

Each entry of the contract interface is structured and encoded using the
`SCSpecEntry` type.

When encoding entries and storing them in the custom section they should be
binary XDR encoded, appended to one another with no frame, no header, no
delimiter, no prefix, including no length prefix. They should be in effect a
stream of `SCSpecEntry` XDR binary encoded values.

Each `SCSpecEntry` describes a function, or a user-defined type.

The following XDR types are specified:

```xdr
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

#### XDR Common Fields

Many of the XDR types that compromise the format of the contract interface have common fields.

The `doc` field is a human readable description of the type, field, or
function. It is intended to be rendered into generated client code, or tooling,
such that users and developers can understand the purpose of the type, field,
or function.

The `name` field is the name of the type, field, or function. It is intended to
be used in generated client code, or tooling, as the identifier.

The `lib` field is the name of the library that the type was imported from. It
is mostly only usedul for contract SDK implementations that support importing
the original library the type was defined in.

#### XDR Spec Entry Kinds

##### `SC_SPEC_ENTRY_FUNCTION_V0`

A function spec entry describes a contract function exported and callable.

The `inputs` field is a list of the function's input parameters.

The `outputs` field is a list of the function's return values.

```xdr
struct SCSpecFunctionV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    SCSymbol name;
    SCSpecFunctionInputV0 inputs<10>;
    SCSpecTypeDef outputs<1>;
};
```

Each input parameter is described by the `SCSpecFunctionInputV0` struct.

The `type` field is the type of the input parameter.

```xdr
struct SCSpecFunctionInputV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string name<30>;
    SCSpecTypeDef type;
};
```

###### Example

In the Soroban Rust SDK the above structure describes a function such as:

```rust
#[contractimpl]
impl MyContract {
    pub fn my_function(input: u64) -> Result<u64, Error> {
        ...
    }
}
```

Which will be encoded to the following XDR:

```
SCSpecEntry::FUNCTION_V0(SCSpecFunctionV0 {
    doc: "",
    name: "my_function",
    inputs: [
        SCSpecFunctionInputV0 {
            doc: "",
            name: "input",
            type: SCSpecTypeDef::U64
        }
    ],
    outputs: [
        SCSpecTypeDef::RESULT(SCSpecTypeResult {
            ok_type: SCSpecTypeDef::U64,
            error_type: SCSpecTypeDef::UDT(SCSpecTypeUDT {
                name: "Error"
            })
        })
    ]
})
```

##### `SC_SPEC_ENTRY_UDT_STRUCT_V0`

A user-defined type struct spec entry describes a user-defined type that has
the properties of a Rust `struct` and that is used as a function parameter, or
as a type within some other type that is a function parameter.

The `fields` field is a list of named fields.

```xdr
struct SCSpecUDTStructV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string lib<80>;
    string name<60>;
    SCSpecUDTStructFieldV0 fields<40>;
};
```

Each field is described by the `SCSpecUDTStructFieldV0` struct.

The `type` field is the type of the field.

```xdr
struct SCSpecUDTStructFieldV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string name<30>;
    SCSpecTypeDef type;
};
```

###### Example

In the Soroban Rust SDK the above structure describes a type such as:

```rust
#[contracttype]
pub struct MyStruct {
    pub field1: u64,
    pub field2: String,
}
```

Which will be encoded to the following XDR:

```
SCSpecEntry::UDT_STRUCT_V0(SCSpecUDTStructV0 {
    doc: "",
    lib: "",
    name: "MyStruct",
    fields: [
        SCSpecUDTStructFieldV0 {
            doc: "",
            name: "field1",
            type: SCSpecTypeDef::U64
        },
        SCSpecUDTStructFieldV0 {
            doc: "",
            name: "field2",
            type: SCSpecTypeDef::STRING
        }
    ]
})
```

##### `SC_SPEC_ENTRY_UDT_UNION_V0`

A user-defined type union spec entry describes a user-defined type that has
the properties of a Rust `enum` with data containing variants and that is used as a function parameter, or
as a type within some other type that is a function parameter.

The `cases` field is a list of union cases.

```xdr
struct SCSpecUDTUnionV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string lib<80>;
    string name<60>;
    SCSpecUDTUnionCaseV0 cases<50>;
};
```

Each case can be either a void case (no data) or a tuple case (contains data).

```xdr
union SCSpecUDTUnionCaseV0 switch (SCSpecUDTUnionCaseV0Kind kind)
{
case SC_SPEC_UDT_UNION_CASE_VOID_V0:
    SCSpecUDTUnionCaseVoidV0 voidCase;
case SC_SPEC_UDT_UNION_CASE_TUPLE_V0:
    SCSpecUDTUnionCaseTupleV0 tupleCase;
};
```

###### Example

In the Soroban Rust SDK the above structure describes a type such as:

```rust
#[contracttype]
pub enum MyUnion {
    NoData,
    WithData(u64, String),
}
```

Which will be encoded to the following XDR:

```
SCSpecEntry::UDT_UNION_V0(SCSpecUDTUnionV0 {
    doc: "",
    lib: "",
    name: "MyUnion",
    cases: [
        SCSpecUDTUnionCaseV0::VOID(SCSpecUDTUnionCaseVoidV0 {
            doc: "",
            name: "NoData"
        }),
        SCSpecUDTUnionCaseV0::TUPLE(SCSpecUDTUnionCaseTupleV0 {
            doc: "",
            name: "WithData",
            type: [
                SCSpecTypeDef::U64,
                SCSpecTypeDef::STRING
            ]
        })
    ]
})
```

##### `SC_SPEC_ENTRY_UDT_ENUM_V0`

A user-defined type enum spec entry describes a user-defined type that has the properties of a Rust
`enum` with C-like integer values and that is used as a function parameter, or as a type within some other
type that is a function parameter.

The `cases` field is a list of enum cases.

```xdr
struct SCSpecUDTEnumV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string lib<80>;
    string name<60>;
    SCSpecUDTEnumCaseV0 cases<50>;
};
```

Each case is described by the `SCSpecUDTEnumCaseV0` struct.

```xdr
struct SCSpecUDTEnumCaseV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string name<60>;
    uint32 value;
};
```

###### Example

In the Soroban Rust SDK the above structure describes a type such as:

```rust
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
#[repr(u32)]
pub enum Color {
    Red = 1,
    Green = 2,
    Blue = 3,
}
```

Which will be encoded to the following XDR:

```
SCSpecEntry::UDT_ENUM_V0(SCSpecUDTEnumV0 {
    doc: "",
    lib: "",
    name: "Color",
    cases: [
        SCSpecUDTEnumCaseV0 {
            doc: "",
            name: "Red",
            value: 1
        },
        SCSpecUDTEnumCaseV0 {
            doc: "",
            name: "Green",
            value: 2
        },
        SCSpecUDTEnumCaseV0 {
            doc: "",
            name: "Blue",
            value: 3
        }
    ]
})
```

##### `SC_SPEC_ENTRY_UDT_ERROR_ENUM_V0`

A user-defined type error enum spec entry describes a user-defined type that has the properties of a Rust
`enum` with C-like integer values and is marked as being used for errors. It is used as a function 
parameter, or as a type within some other type that is a function parameter.

The `cases` field is a list of error enum cases.

```xdr
struct SCSpecUDTErrorEnumV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string lib<80>;
    string name<60>;
    SCSpecUDTErrorEnumCaseV0 cases<50>;
};
```

Each case is described by the `SCSpecUDTErrorEnumCaseV0` struct.

```xdr
struct SCSpecUDTErrorEnumCaseV0
{
    string doc<SC_SPEC_DOC_LIMIT>;
    string name<60>;
    uint32 value;
};
```

###### Example

In the Soroban Rust SDK the above structure describes a type such as:

```rust
#[contracterror]
#[derive(Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
#[repr(u32)]
pub enum Error {
    InvalidInput = 1,
    InsufficientFunds = 2,
    Unauthorized = 3,
}
```

Which will be encoded to the following XDR:

```
SCSpecEntry::UDT_ERROR_ENUM_V0(SCSpecUDTErrorEnumV0 {
    doc: "",
    lib: "",
    name: "Error",
    cases: [
        SCSpecUDTErrorEnumCaseV0 {
            doc: "",
            name: "InvalidInput",
            value: 1
        },
        SCSpecUDTErrorEnumCaseV0 {
            doc: "",
            name: "InsufficientFunds",
            value: 2
        },
        SCSpecUDTErrorEnumCaseV0 {
            doc: "",
            name: "Unauthorized",
            value: 3
        }
    ]
})
```

#### XDR Spec Types

This section describes all the types that can be used in function parameters, return values, and as fields in user-defined types.

##### `SC_SPEC_TYPE_VAL`

A generic value type that could be any type. This is typically used when the contract needs to accept any type of value.

##### `SC_SPEC_TYPE_BOOL`

A boolean type that can be either `true` or `false`.

##### `SC_SPEC_TYPE_VOID`

A void type that represents the absence of a value. This is typically used for functions that do not return anything.

##### `SC_SPEC_TYPE_ERROR`

A generic error type. This is typically used to indicate that a function can return an error without specifying the exact error type.

##### `SC_SPEC_TYPE_U32`

An unsigned 32-bit integer.

##### `SC_SPEC_TYPE_I32`

A signed 32-bit integer.

##### `SC_SPEC_TYPE_U64`

An unsigned 64-bit integer.

##### `SC_SPEC_TYPE_I64`

A signed 64-bit integer.

##### `SC_SPEC_TYPE_TIMEPOINT`

A point in time represented as the number of seconds since the Unix epoch (January 1, 1970 00:00:00 UTC).

##### `SC_SPEC_TYPE_DURATION`

A duration represented as the number of seconds.

##### `SC_SPEC_TYPE_U128`

An unsigned 128-bit integer.

##### `SC_SPEC_TYPE_I128`

A signed 128-bit integer.

##### `SC_SPEC_TYPE_U256`

An unsigned 256-bit integer.

##### `SC_SPEC_TYPE_I256`

A signed 256-bit integer.

##### `SC_SPEC_TYPE_BYTES`

A variable-length array of bytes.

##### `SC_SPEC_TYPE_STRING`

A UTF-8 encoded string.

##### `SC_SPEC_TYPE_SYMBOL`

A symbol is a string-like type that is optimized for equality comparison rather than content manipulation.

##### `SC_SPEC_TYPE_ADDRESS`

An address in the Stellar network. It can represent an account, a contract, or other addressable entity.

##### `SC_SPEC_TYPE_MUXED_ADDRESS`

A muxed address in the Stellar network. It can represent an account with a memo id embedded in the address.

##### `SC_SPEC_TYPE_OPTION`

An option type that represents either a value of the specified type or no value (None/null).

```xdr
struct SCSpecTypeOption
{
    SCSpecTypeDef valueType;
};
```

Example:
```
SCSpecTypeDef::OPTION(SCSpecTypeOption {
    value_type: SCSpecTypeDef::U64
})
```

##### `SC_SPEC_TYPE_RESULT`

A result type that represents either a success value of one type or an error value of another type.

```xdr
struct SCSpecTypeResult
{
    SCSpecTypeDef okType;
    SCSpecTypeDef errorType;
};
```

Example:
```
SCSpecTypeDef::RESULT(SCSpecTypeResult {
    ok_type: SCSpecTypeDef::U64,
    error_type: SCSpecTypeDef::UDT(SCSpecTypeUDT {
        name: "Error"
    })
})
```

##### `SC_SPEC_TYPE_VEC`

A vector type that represents a collection of elements of the same type.

```xdr
struct SCSpecTypeVec
{
    SCSpecTypeDef elementType;
};
```

Example:
```
SCSpecTypeDef::VEC(SCSpecTypeVec {
    element_type: SCSpecTypeDef::STRING
})
```

##### `SC_SPEC_TYPE_MAP`

A map type that represents a collection of key-value pairs where all keys have the same type and all values have the same type.

```xdr
struct SCSpecTypeMap
{
    SCSpecTypeDef keyType;
    SCSpecTypeDef valueType;
};
```

Example:
```
SCSpecTypeDef::MAP(SCSpecTypeMap {
    key_type: SCSpecTypeDef::ADDRESS,
    value_type: SCSpecTypeDef::U64
})
```

##### `SC_SPEC_TYPE_TUPLE`

A tuple type that represents a fixed-size collection of elements of potentially different types.

```xdr
struct SCSpecTypeTuple
{
    SCSpecTypeDef valueTypes<12>;
};
```

Example:
```
SCSpecTypeDef::TUPLE(SCSpecTypeTuple {
    value_types: [
        SCSpecTypeDef::U64,
        SCSpecTypeDef::STRING,
        SCSpecTypeDef::BOOL
    ]
})
```

##### `SC_SPEC_TYPE_BYTES_N`

A fixed-size array of bytes.

```xdr
struct SCSpecTypeBytesN
{
    uint32 n;
};
```

Example:
```
SCSpecTypeDef::BYTES_N(SCSpecTypeBytesN {
    n: 32
})
```

##### `SC_SPEC_TYPE_UDT`

A user-defined type. This is a reference to a type that is defined elsewhere in the contract spec.

```xdr
struct SCSpecTypeUDT
{
    string name<60>;
};
```

Example:
```
SCSpecTypeDef::UDT(SCSpecTypeUDT {
    name: "MyStruct"
})
```

## Example Usage

### Rust soroban-sdk

Contract specs are automatically inserted in code with the Rust `soroban-sdk` by using the [`contractimpl`],
[`contracttype`], and [`contracterror`] macros.

[`contractimpl`]: https://docs.rs/soroban-sdk/latest/soroban_sdk/macro.contractimpl.html
[`contracttype`]: https://docs.rs/soroban-sdk/latest/soroban_sdk/macro.contracttype.html
[`contracterror`]: https://docs.rs/soroban-sdk/latest/soroban_sdk/macro.contracterror.html

## Limitations

### No Claims to SEP Implementations

This proposal does not support a contract claiming to implement any specific interface, or SEP describing an interface.
[SEP-47] provides a way for off-chain systems for discover which SEPs a contract intends to implement.

[SEP-47]: ../ecosystem/sep-0047.md

## Design Rationale

### Custom Sections

The Soroban Environment uses custom sections to store meta information about a contract's Soroban Environment
compatibility. That was documented in [CAP-46-1].

Custom sections are additional binary sections of Wasm files that can be used for any purpose. The Wasm when executing
does not have access to the custom section and is not affected by it.

[CAP-46-1]: ../core/cap-0046-01.md

### XDR Encoding

The XDR encoding is the format used to encode contract interface data. XDR (External Data Representation) is a standard data serialization format that ensures data compatibility across different computer architectures and systems. It is the same format used by the Stellar network for encoding transactions and other data structures.

The contract interface uses XDR to encode the structure of functions and types, allowing tools, SDKs, and clients to reliably decode and understand a contract's interface regardless of the implementation details or the platform used to build the contract.

The XDR is extendable at multiple points and other types other than strings can be trivially added when required. The schema includes version tags in enum discriminants to support backward compatibility as the specification evolves.

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
