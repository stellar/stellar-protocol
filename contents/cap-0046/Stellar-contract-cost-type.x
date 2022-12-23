enum ContractCostType {
    // Cost of running 1 wasm tier-0 instruction
    WasmInsnExecT0 = 0,
    // Cost of running 1 wasm tier-1 instruction
    WasmInsnExecT1 = 1,
    // Cost of running 1 wasm tier-2 instruction
    WasmInsnExecT2 = 2,
    // Cost of running 1 wasm tier-3 instruction
    WasmInsnExecT3 = 3,
    // Cost of growing wasm linear memory by 1 page
    WasmMemAlloc = 4,
    // Cost of forming a debug event and pushing it into the event storage
    HostEventDebug = 5,
    // Cost of pushing a contract event it into the event storage
    HostEventContract = 6,
    // Cost of a host function invocation, not including the actual work done by the function
    InvokeHostFunction = 7,
    // Cost of visiting a host object from the host object storage
    VisitObject = 8,
    // Tracks a single Val (RawVal or primative Object like U64) <=> ScVal
    // conversion cost. Most of these Val counterparts in ScVal (except e.g.
    // Symbol) consumes a single int64 and therefore is a constant overhead.
    ValXdrConv = 9,
    // Cost of serializing an xdr object to bytes
    ValSer = 10,
    // Cost of deserializing an xdr object from bytes
    ValDeser = 11,
    // Cost of cloning events
    CloneEvents = 12,
    // Cost of occupying a host object slot
    HostObjAllocSlot = 13,
    // Cost of computing the sha256 hash from bytes
    ComputeSha256Hash = 14,
    // Cost of computing the ed25519 pubkey from bytes
    ComputeEd25519PubKey = 15,
    // Cost of constructing an new map. The input is the number
    // of entries allocated.
    MapNew = 16,
    // Cost of accessing an entry in a map. The input is the count of the number of
    // entries examined (which will be the log of the size of the map under binary search).
    MapEntry = 17,
    // Cost of constructing a new vector. The input is the number of entries allocated.
    VecNew = 18,
    // Cost of accessing one or more elements in a Vector. The input is the count of
    // the number of elements accessed.
    VecEntry = 19,
    // Cost of work needed to collect elements from a HostVec into a ScVec. This does not account for the
    // conversion of the elements into its ScVal form.
    ScVecFromHostVec = 20,
    // Cost of work needed to collect elements from a HostMap into a ScMap. This does not account for the
    // conversion of the elements into its ScVal form.
    ScMapFromHostMap = 21,
    // Cost of work needed to collect elements from an ScVec into a HostVec. This does not account for the
    // conversion of the elements from its ScVal form.
    ScVecToHostVec = 22,
    // Cost of work needed to collect elements from an ScMap into a HostMap. This does not account for the
    // conversion of the elements from its ScVal form.
    ScMapToHostMap = 23,
    // Cost of guarding a frame, which involves pushing and poping a frame and capturing a rollback point.
    GuardFrame = 24,
    // Cost of verifying ed25519 signature of a payload.
    VerifyEd25519Sig = 25,
    // Cost of reading a slice of vm linear memory
    VmMemRead = 26,
    // Cost of writing to a slice of vm linear memory
    VmMemWrite = 27,
    // Cost of instantiation a VM from wasm bytes code.
    VmInstantiation = 28,
    // Roundtrip cost of invoking a VM function from the host.
    InvokeVmFunction = 29,
    // Cost of cloning bytes.
    BytesClone = 30,
    // Cost of deleting a byte from a bytes array,
    BytesDel = 31,
    // Cost of pushing a byte
    BytesPush = 32,
    // Cost of poping a byte
    BytesPop = 33,
    // Cost of inserting a byte into a bytes array at some index
    BytesInsert = 34,
    // Cost of appending a byte to the end of a bytes array
    BytesAppend = 35,
    // Cost of comparing two bytes arrays
    BytesCmp = 36,
    // Cost of charging a value to the budgeting system.
    ChargeBudget = 37,
};

const CONTRACT_COST_COUNT_LIMIT = 1000; // limits the ContractCostParamEntry size to 16kB

typedef uint32 ContractCostParamEntry[2]; // 0 - constant term, 1 - linear term

typedef ContractCostParamEntry ContractCostParams<CONTRACT_COST_COUNT_LIMIT>;