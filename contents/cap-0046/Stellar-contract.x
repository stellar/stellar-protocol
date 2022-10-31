// Copyright 2022 Stellar Development Foundation and contributors. Licensed
// under the Apache License, Version 2.0. See the COPYING file at the root
// of this distribution or at http://www.apache.org/licenses/LICENSE-2.0

% #include "xdr/Stellar-types.h"
namespace stellar
{
/*
 * Smart Contracts deal in SCVals. These are a (dynamic) disjoint union
 * between several possible variants, to allow storing generic SCVals in
 * generic data structures and passing them in and out of languages that
 * have simple or dynamic type systems.
 *
 * SCVals are (in WASM's case) stored in a tagged 64-bit word encoding. Most
 * signed 64-bit values in Stellar are actually signed positive values
 * (sequence numbers, timestamps, amounts), so we don't need the high bit
 * and can get away with 1-bit tagging and store them as "unsigned 63bit",
 * (u63) separate from everything else.
 *
 * We actually reserve the low _four_ bits, leaving 3 bits for 8 cases of
 * "non-u63 values", some of which have substructure of their own.
 *
 *    0x_NNNN_NNNN_NNNN_NNNX  - u63, for any even X
 *    0x_0000_000N_NNNN_NNN1  - u32
 *    0x_0000_000N_NNNN_NNN3  - i32
 *    0x_NNNN_NNNN_NNNN_NNN5  - static: void, true, false, ... (SCS_*)
 *    0x_IIII_IIII_TTTT_TTT7  - object: 32-bit index I, 28-bit type code T
 *    0x_NNNN_NNNN_NNNN_NNN9  - symbol: up to 10 6-bit identifier characters
 *    0x_NNNN_NNNN_NNNN_NNNb  - bitset: up to 60 bits
 *    0x_CCCC_CCCC_TTTT_TTTd  - status: 32-bit code C, 28-bit type code T
 *    0x_NNNN_NNNN_NNNN_NNNf  - reserved
 *
 * Up here in XDR we have variable-length tagged disjoint unions but no
 * bit-level packing, so we can be more explicit in their structure, at the
 * cost of spending more than 64 bits to encode many cases, and also having
 * to convert. It's a little non-obvious at the XDR level why there's a
 * split between SCVal and SCObject given that they are both immutable types
 * with value semantics; but the split reflects the split that happens in
 * the implementation, and marks a place where different implementations of
 * immutability (CoW, structural sharing, etc.) will likely occur.
 */

// A symbol is up to 10 chars drawn from [a-zA-Z0-9_], which can be packed
// into 60 bits with a 6-bit-per-character code, usable as a small key type
// to specify function, argument, tx-local environment and map entries
// efficiently.
typedef string SCSymbol<10>;

enum SCValType
{
    SCV_U63 = 0,
    SCV_U32 = 1,
    SCV_I32 = 2,
    SCV_STATIC = 3,
    SCV_OBJECT = 4,
    SCV_SYMBOL = 5,
    SCV_BITSET = 6,
    SCV_STATUS = 7
};

% struct SCObject;

enum SCStatic
{
    SCS_VOID = 0,
    SCS_TRUE = 1,
    SCS_FALSE = 2,
    SCS_LEDGER_KEY_CONTRACT_CODE = 3
};

enum SCStatusType
{
    SST_OK = 0,
    SST_UNKNOWN_ERROR = 1,
    SST_HOST_VALUE_ERROR = 2,
    SST_HOST_OBJECT_ERROR = 3,
    SST_HOST_FUNCTION_ERROR = 4,
    SST_HOST_STORAGE_ERROR = 5,
    SST_HOST_CONTEXT_ERROR = 6,
    SST_VM_ERROR = 7,
    SST_CONTRACT_ERROR = 8
    // TODO: add more
};

enum SCHostValErrorCode
{
    HOST_VALUE_UNKNOWN_ERROR = 0,
    HOST_VALUE_RESERVED_TAG_VALUE = 1,
    HOST_VALUE_UNEXPECTED_VAL_TYPE = 2,
    HOST_VALUE_U63_OUT_OF_RANGE = 3,
    HOST_VALUE_U32_OUT_OF_RANGE = 4,
    HOST_VALUE_STATIC_UNKNOWN = 5,
    HOST_VALUE_MISSING_OBJECT = 6,
    HOST_VALUE_SYMBOL_TOO_LONG = 7,
    HOST_VALUE_SYMBOL_BAD_CHAR = 8,
    HOST_VALUE_SYMBOL_CONTAINS_NON_UTF8 = 9,
    HOST_VALUE_BITSET_TOO_MANY_BITS = 10,
    HOST_VALUE_STATUS_UNKNOWN = 11
};

enum SCHostObjErrorCode
{
    HOST_OBJECT_UNKNOWN_ERROR = 0,
    HOST_OBJECT_UNKNOWN_REFERENCE = 1,
    HOST_OBJECT_UNEXPECTED_TYPE = 2,
    HOST_OBJECT_OBJECT_COUNT_EXCEEDS_U32_MAX = 3,
    HOST_OBJECT_OBJECT_NOT_EXIST = 4,
    HOST_OBJECT_VEC_INDEX_OUT_OF_BOUND = 5,
    HOST_OBJECT_CONTRACT_HASH_WRONG_LENGTH = 6
};

enum SCHostFnErrorCode
{
    HOST_FN_UNKNOWN_ERROR = 0,
    HOST_FN_UNEXPECTED_HOST_FUNCTION_ACTION = 1,
    HOST_FN_INPUT_ARGS_WRONG_LENGTH = 2,
    HOST_FN_INPUT_ARGS_WRONG_TYPE = 3,
    HOST_FN_INPUT_ARGS_INVALID = 4
};

enum SCHostStorageErrorCode
{
    HOST_STORAGE_UNKNOWN_ERROR = 0,
    HOST_STORAGE_EXPECT_CONTRACT_DATA = 1,
    HOST_STORAGE_READWRITE_ACCESS_TO_READONLY_ENTRY = 2,
    HOST_STORAGE_ACCESS_TO_UNKNOWN_ENTRY = 3,
    HOST_STORAGE_MISSING_KEY_IN_GET = 4,
    HOST_STORAGE_GET_ON_DELETED_KEY = 5
};

enum SCHostContextErrorCode
{
    HOST_CONTEXT_UNKNOWN_ERROR = 0,
    HOST_CONTEXT_NO_CONTRACT_RUNNING = 1
};

enum SCVmErrorCode {
    VM_UNKNOWN = 0,
    VM_VALIDATION = 1,
    VM_INSTANTIATION = 2,
    VM_FUNCTION = 3,
    VM_TABLE = 4,
    VM_MEMORY = 5,
    VM_GLOBAL = 6,
    VM_VALUE = 7,
    VM_TRAP_UNREACHABLE = 8,
    VM_TRAP_MEMORY_ACCESS_OUT_OF_BOUNDS = 9,
    VM_TRAP_TABLE_ACCESS_OUT_OF_BOUNDS = 10,
    VM_TRAP_ELEM_UNINITIALIZED = 11,
    VM_TRAP_DIVISION_BY_ZERO = 12,
    VM_TRAP_INTEGER_OVERFLOW = 13,
    VM_TRAP_INVALID_CONVERSION_TO_INT = 14,
    VM_TRAP_STACK_OVERFLOW = 15,
    VM_TRAP_UNEXPECTED_SIGNATURE = 16,
    VM_TRAP_MEM_LIMIT_EXCEEDED = 17,
    VM_TRAP_CPU_LIMIT_EXCEEDED = 18
};

enum SCUnknownErrorCode
{
    UNKNOWN_ERROR_GENERAL = 0,
    UNKNOWN_ERROR_XDR = 1
};

union SCStatus switch (SCStatusType type)
{
case SST_OK:
    void;
case SST_UNKNOWN_ERROR:
    SCUnknownErrorCode unknownCode;
case SST_HOST_VALUE_ERROR:
    SCHostValErrorCode valCode;
case SST_HOST_OBJECT_ERROR:
    SCHostObjErrorCode objCode;
case SST_HOST_FUNCTION_ERROR:
    SCHostFnErrorCode fnCode;
case SST_HOST_STORAGE_ERROR:
    SCHostStorageErrorCode storageCode;
case SST_HOST_CONTEXT_ERROR:
    SCHostContextErrorCode contextCode;
case SST_VM_ERROR:
    SCVmErrorCode vmCode;
case SST_CONTRACT_ERROR:
    uint32 contractCode;
};

union SCVal switch (SCValType type)
{
case SCV_U63:
    int64 u63;
case SCV_U32:
    uint32 u32;
case SCV_I32:
    int32 i32;
case SCV_STATIC:
    SCStatic ic;
case SCV_OBJECT:
    SCObject* obj;
case SCV_SYMBOL:
    SCSymbol sym;
case SCV_BITSET:
    uint64 bits;
case SCV_STATUS:
    SCStatus status;
};

enum SCObjectType
{
    // We have a few objects that represent non-stellar-specific concepts
    // like general-purpose maps, vectors, numbers, blobs.

    SCO_VEC = 0,
    SCO_MAP = 1,
    SCO_U64 = 2,
    SCO_I64 = 3,
    SCO_BYTES = 4,
    SCO_BIG_INT = 5,
    SCO_CONTRACT_CODE = 6,
    SCO_ACCOUNT_ID = 7

    // TODO: add more
};

struct SCMapEntry
{
    SCVal key;
    SCVal val;
};

const SCVAL_LIMIT = 256000;

typedef SCVal SCVec<SCVAL_LIMIT>;
typedef SCMapEntry SCMap<SCVAL_LIMIT>;

enum SCNumSign
{
    NEGATIVE = -1,
    ZERO = 0,
    POSITIVE = 1
};

union SCBigInt switch (SCNumSign sign)
{
case ZERO:
    void;
case POSITIVE:
case NEGATIVE:
    opaque magnitude<256000>;
};

enum SCContractCodeType
{
    SCCONTRACT_CODE_WASM = 0,
    SCCONTRACT_CODE_TOKEN = 1
};

union SCContractCode switch (SCContractCodeType type)
{
case SCCONTRACT_CODE_WASM:
    opaque wasm<SCVAL_LIMIT>;
case SCCONTRACT_CODE_TOKEN:
    void;
};

union SCObject switch (SCObjectType type)
{
case SCO_VEC:
    SCVec vec;
case SCO_MAP:
    SCMap map;
case SCO_U64:
    uint64 u64;
case SCO_I64:
    int64 i64;
case SCO_BYTES:
    opaque bin<SCVAL_LIMIT>;
case SCO_BIG_INT:
    SCBigInt bigInt;
case SCO_CONTRACT_CODE:
    SCContractCode contractCode;
case SCO_ACCOUNT_ID:
    AccountID accountID;
};
}
