## Preamble

```
CAP: 0046
Title: WebAssembly Smart Contract Runtime Environment
Working Group:
    Owner: Graydon Hoare <graydon@stellar.org>
    Authors: Graydon Hoare <graydon@stellar.org>
    Consulted: Leigh McCulloch <leigh@stellar.org>, Tomer Weller <tomer@stellar.org>, Jon Jove <jon@stellar.org>, Nicolas Barry <nicolas@stellar.org>
Status: Draft
Created: 2022-04-18
Discussion: https://groups.google.com/g/stellar-dev/c/X0oRzJoIr10
Protocol version: TBD
```

## Simple Summary

This CAP specifies the lowest-level **code execution** and **data model** components of a WebAssembly-based (WASM) "smart contract" system for the Stellar network. These components are arranged into separate but related "host" and "guest" environments, which together comprise the "runtime environment" for smart contracts.

Higher-level components of a smart contract system such as ledger entries, host functions and transactions to manage and invoke contracts will be specified in additional CAPs. This CAP focuses only on the lowest-level components.

No new operations or ledger entries are introduced in this CAP. Nothing observably changes in the protocol available to users. This CAP is best understood as a set of building blocks for later CAPs, introducing a vocabulary of concepts, data types and implementation components.

The design in this CAP is derived from a working and much more complete prototype that includes much that is left out of this CAP. This CAP is being proposed separately to facilitate early discussion of the building blocks, and to help decompose the inevitably-large volume of interrelated changes required for a complete smart contract system into smaller, more understandable pieces.

## Working Group

This protocol change was authored by Graydon Hoare, with input from the consulted individuals mentioned at the top of this document.

## Motivation

The Stellar Network currently supports a rich but fixed repertoire of transactions. Developers have indicated this repertoire is insufficiently flexible in adapting to new application needs, and wish to be able to submit custom turing-complete code to run in the transaction-execution phase of the network. This CAP specifies the lowest-level components of such a system.

### Goals Alignment

This CAP is aligned with the following Stellar Network Goals:

- The Stellar Network should make it easy for developers of Stellar projects to create highly usable products

## Abstract

The specification consists of three parts:

  1. A general description of the concepts of host and guest environments, their relationships, constraints, and methods of implementation.

  2. A specification of the new components that provide the host and guest environments, their means of interaction, and their lifecycle phases.

  3. A specification of the data model shared between host and guest.

## Specification

### Environments

The runtime environment for smart contracts is comprised of two separate but related environments:

  - The **host** environment: this consists of portions of the existing C++ code making up stellar-core that can be accessed by smart contracts, as well as some new C++ code implied by this CAP. New C++ code includes the implementation of a WebAssembly (WASM) virtual machine, a set of host objects, and a host context that manages the lifecycle and interaction of the host objects and virtual machines. The host environment is compiled to native code and runs with full access to its enclosing operating system environment, the ledger, the network, etc. The term "host environment" here corresponds to the term with that name in the WebAssembly specification.

  - The **guest** environment: this consists of WASM code _interpreted by_ a WASM virtual machine embedded in the host. Guest code may originate in any programming language able to target WASM, and will be provided by means unspecified in this CAP. Guest code has very limited access to its enclosing host environment: it can only consume CPU and memory resources to the extent that the host environment permits, and it can only call host functions that the host environment explicitly provides access to. The purpose of the guest environment is to act as a so-called "sandbox" to attenuate potential harms caused by erroneous or malicious guest code, while allowing "just enough" programmability to satisfy the needs of users.

#### Determinism

Both the guest environment and any part of the host environment controlled by the guest must execute deterministically in response to inputs, and must be sufficiently well-specified that replaying historical guest code in an upgraded host environment (i.e. a new version of stellar-core) will produce observably-identical results. This includes the result of observable resource exhaustion within host-controlled CPU or memory limits, which implies the need for careful resource accounting on all guest-controlled actions.

### Components

The guest and host environments are provided by two new components added to stellar-core: a virtual machine and a host context.

#### Virtual Machine

Code for a [WebAssembly 1.0](https://www.w3.org/TR/wasm-core-1/) **virtual machine** (VM) is embedded in stellar-core. The VM can be instantiated multiple times in the same stellar-core process, effectively supporting multiple separate guest environments. The VM is configured with specific limits, and **excludes** support for any subsequent WebAssembly specification revisions or proposals.

Input guest code for a guest environment is a single WASM module in the specified WASM binary format, and guest code will pass through all 4 semantic phases defined in the WASM specification: decoding, validation, instantiation and execution. See the linked specification for details.

#### Host context

A **host context** is added to the transaction-processing subsystem of stellar-core. A host context is a container carrying:
  - Zero or more WASM VMs, providing guest environments.
  - Any host objects that the contained guest environments can refer to.
  - A transaction mechanism for discarding host objects on error.
  - Any resource-accounting mechanisms for the guest environments.
  - Any host functions that the guest environments can import.

#### Interface

The **interface** between host and guest environments is very narrow and is defined by the WASM specification of embedding. A summary of some relevant aspects is repeated here:

  - Guest memory ("WASM linear memory") is separated from host memory. The host may have a mechanism to access guest memory, but **the guest has no mechanism to access host memory**.

  - There are **exactly 4 types of data values** shared between guest and host: i32, i64, f32, and f64. These are 32 and 64-bit 2s complement integers (with undefined "signedness") and 32 and 64-bit IEEE754 binary floating point values.

  - Guest code modules carry a list of **exported** functions (that the guest provides and the host can call) and a list of **imported** functions (that the host provides and the guest can call). Both imported and exported functions can only pass a sequence of parameters of the 4 shared data types and return a single value of the 4 shared data types, or a trap.

  - Various error conditions may result in a guest **trap** condition, which is a terminal state for a guest environment: no further execution can occur on a guest after it traps. A trap may be generated within a guest due to an execution error, or may be generated by a host function called from the guest. Therefore any call from guest to host or host to guest may produce a trap result rather than a value. 

#### Lifecycles

A host context has its own **lifecycle**: it is created before any of the host objects or VMs it contains, and destroyed after any of the host objects or VMs it contains.

When a host context is created, it contains no host objects and no VMs.

Adding a WASM VM to a host context involves passing WASM code through the 4 lifecycle phases in the WASM specification. If any phase fails, no further phases will be performed on the failed WASM VM.

Multiple WASM VMs can coexist in a single host context. The intention is that one host context and one WASM VM will be created for an "outermost" invocation of a smart contract, and that "inner" contracts can be invoked by guest code calling a host function that constructs an additional VM and invokes a guest function in that new VM, within the same shared host context. The specific mechanism of calling between contracts is not specified in this CAP.

Multiple WASM VMs in the same host context can refer to the same host objects: this is the mechanism for passing (immutable) information between different smart contracts.

#### Limits

TBD. Implementation-defined **limits** will be specified here before finalization of the CAP.

Additional implementation-defined limits will be specified to restrict the consumption of host resources by guest code. In particular, a step-counter or "gas limit" will be imposed on the number of instructions executed by guest code. Additionally any computation, memory or IO resources consumed by host functions called by guest code will be accounted-for. Any guest code that exceeds limits will terminate with an error.

### Data Model

This CAP defines a **data model** shared between guest and host environments. It consists of a set of _values_ and a set of _objects_:

  - **Values** can be packed into a 64-bit integer, and can therefore be easily passed back and forth between host and guest environments, as arguments or return values from imported or exported functions.
  - **Objects** (also called "host objects") exist only in host memory, in the host context, and can only be _referenced_ in the guest environment by values containing **handles** that _refer to_ objects. If guest code wishes to perform an operation on a host object, it must call a host function with values containing handles that _refer to_ any host object(s) to operate on.

#### Immutability

Values and Objects are both **immutable**: they cannot be changed once created. Any operation on a host object that implies a modification of the object's state will allocate a new object with the modified state, and return a value that refers to the new object. Objects must therefore be relatively lightweight, and reuse shared substructures where possible.

#### Forms

The data model is specified in two separate **forms**:

  - In a set of "host types", of which the "host _value_ type" is shared between host and guest.
  - In XDR, for inclusion in serial forms such as transactions and ledger entries.

The rationale for the two separate forms is given below, in the rationale section.

#### Host value type

The **host value type** is a 64-bit integer carrying a bit-packed disjoint union of several cases:

  - The least-significant bit differentiates between two _primary_ cases:
    - If it is 0, the remaining 63 bits encode a **positive signed 64-bit integer**.
    - If it is 1, the remaining 63 bits encode a low 3-bit **tag** and a high 60-bit **body**.
  - The 8 tag values define an interpretation of the body, from least-significant to most-significant bits:
    - Tag 0: a **32-bit unsigned integer** followed by 30 zero bits.
    - Tag 1: a **32-bit signed integer** followed by 30 zero bits.
    - Tag 2: a **static** set of 60-bit values, of which the first 3 are **void**, **true** and **false**.
    - Tag 3: an **object reference** given by a 28-bit type code followed by a 32-bit handle.
    - Tag 4: a **symbol** having 10 or less 6-bit character codes drawn from the character repertoire `[_0-9A-Za-z]`,  with `_` assigned code 1 and trailing positions in the symbol filled with a zero code, and code positions starting at the least significant 6 bits of the body.
    - Tag 5: a **bitset** consisting of 60 1-bit flags.
    - Tag 6: a **status** value consisting of a 28-bit type code followed by a 32-bit status code.
    - Tag 7: reserved for future use.

#### Host object type(s)

There are many different **host object types**, and we refer to the disjoint union of all possible host object types as **the host object type**. This may be implemented in terms of a variant type, an object hierarchy, or any other similar mechanism in the host.

Every host object is held in host memory and **cannot be accessed directly from guest code**. Host objects can be _referred to_ by host values in either host or guest code: specifically those values with tag 3 (object reference) refer to a host object by type code and handle.

**Host object handles** are assigned sequentially from 1, as host objects are allocated during the lifecycle of a host execution context. Host object handle 0 is reserved as a sentinel value that always denotes an invalid object, on which no host functions are defined. All host object types share a single numerical range of handles. In other words: the type codes held in object references _reflect_ type differences between host objects, to allow guests to switch on host object types without calling host functions to query them, but the object type codes do not subdivide the numeric range of object handles.

There are 2^28 (268,435,456) possible **host object type codes**, of which only the first 16 are defined in this CAP:

  - Object type 0: a **box** which contains a single host value.
  - Object type 1: a **vector** which contains a sequence of host values.
  - Object type 2: a **map** which is an unordered association from host values to host values.
  - Object type 3: an XDR **unsigned 64-bit integer**.
  - Object type 4: an XDR **signed 64-bit integer**.
  - Object type 5: an XDR **string**.
  - Object type 6: an XDR opaque **binary** array.
  - Object type 7: an arbitrary precision **big integer** number.
  - Object type 8: an arbitrary precision **bit rational** number.
  - Object type 9: an XDR **ledger key**.
  - Object type 10: an XDR **operation**.
  - Object type 11: an XDR **operation result**.
  - Object type 12: an XDR **transaction**.
  - Object type 13: an XDR **asset**.
  - Object type 14: an XDR **price**.
  - Object type 15: an XDR **account ID**.

The semantics of 5 of these types -- box, vector, map, big integer and rational -- will be given in a later CAP, in terms of the host functions that act on them. In the scope of this CAP, only the remaining 11 XDR object types have defined semantics or representations, which are given by the existing corresponding Stellar network XDR protocol definitions.


### XDR changes

The data model has an XDR form that differs from the host form for reasons discussed below in the rationale section.

The XDR defining the data model is the only new XDR introduced by this CAP. It is contained entirely in a new XDR file: `Stellar-contract.x`. Its contents are provided here.

~~~
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

enum SCStatic
{
    SCS_VOID = 0,
    SCS_TRUE = 1,
    SCS_FALSE = 2
};

enum SCStatusType
{
    SST_OK = 0,
    SST_UNKNOWN_ERROR = 1
};

union SCStatus switch (SCStatusType type)
{
case SST_OK:
    void;
case SST_UNKNOWN_ERROR:
    uint32 unknownCode;
};

union SCVal switch (SCValType type)
{
case SCV_U63:
    uint64 u63;
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
    SCO_BOX = 0,
    SCO_VEC = 1,
    SCO_MAP = 2,
    SCO_U64 = 3,
    SCO_I64 = 4,
    SCO_STRING = 5,
    SCO_BINARY = 6,
    SCO_BIGINT = 7,
    SCO_BIGRAT = 8,
    SCO_LEDGERKEY = 9,
    SCO_OPERATION = 10,
    SCO_OPERATION_RESULT = 11,
    SCO_TRANSACTION = 12,
    SCO_ASSET = 13,
    SCO_PRICE = 14,
    SCO_ACCOUNTID = 15
};

struct SCMapEntry
{
    SCVal key;
    SCVal val;
};

typedef SCVal SCVec<>;
typedef SCMapEntry SCMap<>;

struct SCBigInt
{
    bool positive;
    opaque magnitude<>;
};

struct SCBigRat
{
    bool positive;
    opaque numerator<>;
    opaque denominator<>;
};

union SCObject switch (SCObjectType type)
{
case SCO_BOX:
    SCVal box;
case SCO_VEC:
    SCVec vec;
case SCO_MAP:
    SCMap map;
case SCO_U64:
    uint64 u64;
case SCO_I64:
    int64 i64;
case SCO_STRING:
    string str<>;
case SCO_BINARY:
    opaque bin<>;
case SCO_BIGINT:
    SCBigInt bi;
case SCO_BIGRAT:
    SCBigRat br;
case SCO_LEDGERKEY:
    LedgerKey* lkey;
case SCO_OPERATION:
    Operation* op;
case SCO_OPERATION_RESULT:
    OperationResult* ores;
case SCO_TRANSACTION:
    Transaction* tx;
case SCO_ASSET:
    Asset asset;
case SCO_PRICE:
    Price price;
case SCO_ACCOUNTID:
    AccountID accountID;
};
~~~

## Design Rationale

### Rationale for WASM

WebAssembly was chosen as a basis for this CAP after extensive evaluation of alternative virtual machines. See ["choosing wasm"](https://www.stellar.org/blog/project-jump-cannon-choosing-wasm) for details, or the underlying [stack selection criteria](https://docs.google.com/document/d/1ggXNHVas-PpazfOY87nAz2TiAjH4MkUqHnASR02C6xg/edit#heading=h.p25wrykk29al) document.

### Rationale for value / object split

The split between values (which can traverse the host/guest interface) and objects (which remain on the host side and are managed by host functions) is justified as a response to a number of observations we made when considering existing blockchains:

  - Many systems spend a lot of guest code footprint (time and space) implementing data serialization and deserialization to and from opaque byte arrays. This code suffers from a variety of problems:
    - It is often to and from an opaque format, making a contract's data difficult to browse or debug, and making SDKs that invoke contracts need to carry special code to serialize and deserialize data for the contract.
    - It is often coupled to a specific version or layout of a data structure, such that data cannot be easily be migrated between versions of a contract.
    - It requires that a contract potentially contains extra copies of serialization support code for the formats used by any contracts it calls.
    - It is often intermixed with argument processing and contract logic, representing a significant class of security problems in contracts. 
    - It is usually unshared code: each contract implements its own copy of serialization and deserialization, and does so inefficiently in the guest rather than efficiently on the host. 

  - Similarly, when guest code is CPU-intensive it is often performing numerical or cryptographic operations which would be better supported by a common library of efficient (native) host functions.

  - As of this writing, WASM defines no mechanism of directly sharing code, which makes it impossible to reuse common guest functions needed by many contracts. Sharing common host functions is comparatively straightforward, and much more so if we define a common data model on which host functions operate.

  - The more time is spent in the guest, the more the overall system performance depends directly on the speed of the guest VM's bytecode-dispatch mechanism (a.k.a. the VM's "inner loop"). By contrast, if the guest VM spends most of its time making a sequence of host calls, the bytecode-dispatch speed of the guest VM is less of a concern. This gives us much more flexibility in choice of VM, for example to choose simple, low-latency and comparatively-secure interpreters rather than complex, high-latency and fragile JITs.

Some systems mitigate these issues by providing byte-buffers of data to guests in a guaranteed input format, such as JSON. This eliminates some of the interoperability concerns but none of the efficiency concerns: the guest still spends too much time parsing input and building data structures.

Ultimately we settled on an approach in which the system will spend _as little time in the guest as possible_, and will furnish the guest with a rich enough repertoire of host objects that it should not need many or any of its own guest-local data structures. We expect that many guests will be able to run without a guest memory allocator at all.

There are various costs and benefits to this strategy. We compared in detail to many other blockchains with different approaches before settling on this one.

Costs:
  - Larger host-object API attack surface to defend.
  - Larger host-object API compatibility surface to maintain.
  - More challenging task to quantify memory and CPU costs.
  - More specification work to do defining host interface.
  - Risks redundant work, guest _may_ choose to ignore host objects.

Benefits:
  - Much faster execution due to most logic being in C++.
  - Smaller guest input-parsing attack surfaces to defend.
  - Smaller guest data compatibility surfaces to maintain. 
  - Much smaller guest code, minimizing storage and instantiation costs:
    - Little or no code to serialize or deserialize data in guest.
    - Little or no common memory-management or data structure code in guest.
  - Auxiliary benefits from common data model:
    - Easier to browse contract data by 3rd party tools.
    - Easier to debug contracts by inspecting state.
    - Easier to test contracts by generating / capturing data.
    - Easier to pass data from one contract to another.
    - Easier to use same data model from different source languages.

It is especially important to note that the (enlarged) attack and maintenance surfaces on the host are costs borne by stellar-core developers, while the (diminished) attack and maintenance surfaces are benefits that accrue to smart contract developers. We believe this is a desirable balance of costs and benefits.

### Rationale for value and object type repertoires

These are chosen based on two criteria:

  - Reasonably-foreseeable use in a large number of smart contracts.
  - Widely-available implementations with efficient immutable forms.

In addition, _values_ are constrained by the ability to be packed into a 64-bit tagged disjoint union.

Implementations of the map and vec object types are based on design techniques from the functional language community, specifically [Relaxed-Radix-Balanced vectors (RRBs)](https://dl.acm.org/doi/10.1145/2784731.2784739) and [Hash Array Mapped Tries (HAMTs)](https://en.wikipedia.org/wiki/Hash_array_mapped_trie). Both of these data types support efficient "modifying copies" that produce new data structures from updates applied to old ones, while sharing most of the memory and substructure of the old object with the new one.

### Rationale for separate XDR and host forms

It would be possible to store all data in memory in the host in its XDR format, but we choose instead to define a separate "host form" for both values and objects in this specification for the following reasons:

  - In the host form, values are bit-packed in order to fit in exactly 64 bits. This bit-packing is implemented in stellar-core but is somewhat delicate and would be undesirable to reimplement in every client SDK and data browser. In the XDR form, the various cases that make up the value union are represented in a standard XDR union, which is automatically supported by many languages' XDR bindings.

  - In the host form, objects and values are separated for reasons explained above, and their separation is mediated through object _references_ and the host _context_ which maps references to objects. In the XDR form, objects and values are _not_ separated, because they should not be: there is no implicit context in which to resolve references, and even if there were it would introduce a new category of potential reference-mismatch error in the serialized form to support it. Instead, in the XDR form values _directly contain_ objects.

  - In the host form, maps and vectors are implemented using memory-efficient substructure-sharing datatypes as described above. Additionally, maps support CPU-efficient hashed lookup by key. In the XDR form, maps are simple linear arrays of key-value pairs, and neither vectors nor maps support any sort of partial substructure-sharing updates.

  - In the host form, big integers and rationals are stored in CPU-dependent forms that support fast CPU-native arithmetic. In the XDR form, they are serialized into platform-agnostic big-endian byte arrays.

### Rationale for immutable objects

We considered the potential costs and benefits of immutable objects, and decided in favor of them.

Costs:
  - More memory allocation.
  - Risk of referring to an old/stale object rather than a fresh/new one.

Benefits:
  - Reduced risk of error through mutating a shared object.
  - Simple model of equality, for using structured values as map keys.
  - Simple model of security: no covert channels, only passed values.
  - Simple model for transactions: discard objects on rollback.

Since we expect smart contracts to run to completion very quickly, and then free all objects allocated, we do not consider the additional memory allocation cost a likely problem in practice. Furthermore as mentioned in the object-repertoire rationale above, we have been using shared-substructure types in our prototype, so most large-object updates should only consume minimal new memory.

Therefore the only real risk we foresee is the increased risk of unintentionally referring to an old/stale object, and we believe this is outweighed by the reduced risk of unintentionally referring to a shared mutable object that it mutated through an alias.


## Protocol Upgrade Transition
This CAP does not introduce any protocol changes.

### Backwards Incompatibilities
This CAP does not introduce any backward incompatibilities.

### Resource Utilization
TBD. Performance evaluation is ongoing on in-progress implementation.

## Security Concerns

There are a variety of security concerns implied by this CAP, including at least the following:

  - The risk of a guest-environment escape due to VM or host function bugs.
  - The risk of a validator crash due to VM or host function bugs.
  - The risk of guest code bugs leading to erroneous transactions. 
  - The risk of mis-metering of guest-controlled resources and denial of service.
  - The risk of increased load on validators and degraded service due to more expensive smart-contract transactions. 
  - The risk of information leakage through side channels to guest code.

## Test Cases

TBD. See in-progress implementation.

## Implementation

An implementation is provided in [PR 3413](https://github.com/stellar/stellar-core/pull/3413) on the stellar-core repository.