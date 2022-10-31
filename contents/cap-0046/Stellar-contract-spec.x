// Copyright 2022 Stellar Development Foundation and contributors. Licensed
// under the Apache License, Version 2.0. See the COPYING file at the root
// of this distribution or at http://www.apache.org/licenses/LICENSE-2.0

// The contract Contractspec XDR is highly experimental, incomplete, and still being
// iterated on. Breaking changes expected.

% #include "xdr/Stellar-types.h"
% #include "xdr/Stellar-contract.h"
namespace stellar
{

enum SCSpecType
{
    SC_SPEC_TYPE_VAL = 0,

    // Types with no parameters.
    SC_SPEC_TYPE_U32 = 1,
    SC_SPEC_TYPE_I32 = 2,
    SC_SPEC_TYPE_U64 = 3,
    SC_SPEC_TYPE_I64 = 4,
    SC_SPEC_TYPE_BOOL = 5,
    SC_SPEC_TYPE_SYMBOL = 6,
    SC_SPEC_TYPE_BITSET = 7,
    SC_SPEC_TYPE_STATUS = 8,
    SC_SPEC_TYPE_BYTES = 9,
    SC_SPEC_TYPE_BIG_INT = 10,
    SC_SPEC_TYPE_INVOKER = 11,
    SC_SPEC_TYPE_ACCOUNT_ID = 12,

    // Types with parameters.
    SC_SPEC_TYPE_OPTION = 1000,
    SC_SPEC_TYPE_RESULT = 1001,
    SC_SPEC_TYPE_VEC = 1002,
    SC_SPEC_TYPE_SET = 1003,
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

struct SCSpecTypeSet
{
    SCSpecTypeDef elementType;
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
case SC_SPEC_TYPE_U64:
case SC_SPEC_TYPE_I64:
case SC_SPEC_TYPE_U32:
case SC_SPEC_TYPE_I32:
case SC_SPEC_TYPE_BOOL:
case SC_SPEC_TYPE_SYMBOL:
case SC_SPEC_TYPE_BITSET:
case SC_SPEC_TYPE_STATUS:
case SC_SPEC_TYPE_BYTES:
case SC_SPEC_TYPE_BIG_INT:
case SC_SPEC_TYPE_INVOKER:
case SC_SPEC_TYPE_ACCOUNT_ID:
    void;
case SC_SPEC_TYPE_OPTION:
    SCSpecTypeOption option;
case SC_SPEC_TYPE_RESULT:
    SCSpecTypeResult result;
case SC_SPEC_TYPE_VEC:
    SCSpecTypeVec vec;
case SC_SPEC_TYPE_MAP:
    SCSpecTypeMap map;
case SC_SPEC_TYPE_SET:
    SCSpecTypeSet set;
case SC_SPEC_TYPE_TUPLE:
    SCSpecTypeTuple tuple;
case SC_SPEC_TYPE_BYTES_N:
    SCSpecTypeBytesN bytesN;
case SC_SPEC_TYPE_UDT:
    SCSpecTypeUDT udt;
};

struct SCSpecUDTStructFieldV0
{
    string name<30>;
    SCSpecTypeDef type;
};

struct SCSpecUDTStructV0
{
    string lib<80>;
    string name<60>;
    SCSpecUDTStructFieldV0 fields<40>;
};

struct SCSpecUDTUnionCaseV0
{
    string name<60>;
    SCSpecTypeDef *type;
};

struct SCSpecUDTUnionV0
{
    string lib<80>;
    string name<60>;
    SCSpecUDTUnionCaseV0 cases<50>;
};

struct SCSpecUDTEnumCaseV0
{
    string name<60>;
    uint32 value;
};

struct SCSpecUDTEnumV0
{
    string lib<80>;
    string name<60>;
    SCSpecUDTEnumCaseV0 cases<50>;
};

struct SCSpecUDTErrorEnumCaseV0
{
    string name<60>;
    uint32 value;
};

struct SCSpecUDTErrorEnumV0
{
    string lib<80>;
    string name<60>;
    SCSpecUDTErrorEnumCaseV0 cases<50>;
};

struct SCSpecFunctionInputV0
{
    string name<30>;
    SCSpecTypeDef type;
};

struct SCSpecFunctionV0
{
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

}
