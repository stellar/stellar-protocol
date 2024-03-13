## Preamble

```
CAP: 0054
Title: Soroban refined VM instantiation cost model
Working Group:
    Owner: Graydon Hoare <@graydon>
    Authors: Graydon Hoare <@graydon>
    Consulted: Jay Geng <@jayz22>, Dmytro Kozhevin <@dmkozh>
Status: Draft
Created: 2024-03-11
Discussion: https://github.com/stellar/stellar-protocol/discussions/1460
Protocol version: TBD
```

## Simple Summary

Lower total costs by refining the Soroban cost model used for VM instantiation into multiple separate and more-accurate costs. Also prepare for subsequent work lowering certain of these separate costs.

## Working Group

As specified in the Preamble.

## Motivation

To lower the CPU cost charged for each contract invocation transaction thereby admitting more such transactions per ledger and increasing total throughput.

### Goals Alignment

This change is aligned with the goal of lowering the cost and increasing the scale of the network.

## Abstract

As of protocol 20 the model CPU cost (which translates to fees) charged for most contract executions is overwhelmingly dominated by the "VM instantiation" cost model.

This cost model takes the byte-size of a WASM contract as input and outputs a pessimistic cost based on worst-case assumptions about the possible meaning of each byte in the contract code.

A more refined model will enable a tigher bound on costs, essentially charging something closer to the "real" cost rather than the pessimistic assumption.

## Specification

There are three parts to this work:

  1. On contract upload, the initial contract parse and validation pass will initially use the old cost model, but the host will then analyze the contract and extract refined cost-input values (i.e. it will count the number of functions, imports, exports, data segment sizes and so forth).
  2. This new refinedcost-input information will be saved into the ledger along with the uploaded WASM bytecode, so that _subsequent_ instantiations can use a refined cost model.
  3. When instantiating a contract with saved refined cost inputs, the refined cost model will be charged. This will also allow the cost model to properly _reflect_ changes in subsequent CAPs that lower the actual amount of work done during VM instantiation.

### XDR changes

~~~
diff --git a/Stellar-contract-config-setting.x b/Stellar-contract-config-setting.x
index 6b50747..d066029 100644
--- a/Stellar-contract-config-setting.x
+++ b/Stellar-contract-config-setting.x
@@ -139,7 +139,49 @@ enum ContractCostType {
     // Cost of int256 shift (`shl`, `shr`) operation
     Int256Shift = 21,
     // Cost of drawing random bytes using a ChaCha20 PRNG
-    ChaCha20DrawBytes = 22
+    ChaCha20DrawBytes = 22,
+
+    // Cost of parsing wasm bytes that only encode instructions.
+    ParseWasmInstructions = 23,
+    // Cost of parsing a known number of wasm functions.
+    ParseWasmFunctions = 24,
+    // Cost of parsing a known number of wasm globals.
+    ParseWasmGlobals = 25,
+    // Cost of parsing a known number of wasm table entries.
+    ParseWasmTableEntries = 26,
+    // Cost of parsing a known number of wasm types.
+    ParseWasmTypes = 27,
+    // Cost of parsing a known number of wasm data segments.
+    ParseWasmDataSegments = 28,
+    // Cost of parsing a known number of wasm element segments.
+    ParseWasmElemSegments = 29,
+    // Cost of parsing a known number of wasm imports.
+    ParseWasmImports = 30,
+    // Cost of parsing a known number of wasm exports.
+    ParseWasmExports = 31,
+    // Cost of parsing a known number of memory pages.
+    ParseWasmMemoryPages = 32,
+
+    // Cost of instantiating wasm bytes that only encode instructions.
+    InstantiateWasmInstructions = 33,
+    // Cost of instantiating a known number of wasm functions.
+    InstantiateWasmFunctions = 34,
+    // Cost of instantiating a known number of wasm globals.
+    InstantiateWasmGlobals = 35,
+    // Cost of instantiating a known number of wasm table entries.
+    InstantiateWasmTableEntries = 36,
+    // Cost of instantiating a known number of wasm types.
+    InstantiateWasmTypes = 37,
+    // Cost of instantiating a known number of wasm data segments.
+    InstantiateWasmDataSegments = 38,
+    // Cost of instantiating a known number of wasm element segments.
+    InstantiateWasmElemSegments = 39,
+    // Cost of instantiating a known number of wasm imports.
+    InstantiateWasmImports = 40,
+    // Cost of instantiating a known number of wasm exports.
+    InstantiateWasmExports = 41,
+    // Cost of instantiating a known number of memory pages.
+    InstantiateWasmMemoryPages = 42
 };
 
 struct ContractCostParamEntry {
diff --git a/Stellar-ledger-entries.x b/Stellar-ledger-entries.x
index 8a8784e..ff50201 100644
--- a/Stellar-ledger-entries.x
+++ b/Stellar-ledger-entries.x
@@ -508,8 +508,31 @@ struct ContractDataEntry {
     SCVal val;
 };
 
+struct ContractCodeCostInputs {
+    uint32 nInstructions;
+    uint32 nFunctions;
+    uint32 nGlobals;
+    uint32 nTableEntries;
+    uint32 nTypes;
+    uint32 nDataSegments;
+    uint32 nElemSegments;
+    uint32 nImports;
+    uint32 nExports;
+    uint32 nMemoryPages;
+};
+
 struct ContractCodeEntry {
-    ExtensionPoint ext;
+    union switch (int v)
+    {
+        case 0:
+            void;
+        case 1:
+            struct
+            {
+                ExtensionPoint ext;
+                ContractCodeCostInputs costInputs;
+            } v1;
+    } ext;
 
     Hash hash;
     opaque code<>;
~~~

### Semantics

The change consists of two logical changes:

  1. New content stored in `ContractCodeEntry` ledger entries. These are arranged in a new struct `ContractCodeCostInputs` which is added at the existing `ExtensionPoint` of `ContractCodeEntry`, and encode counts of various aspects of the parsed Wasm body of the contract that we intend to feed into subsequent cost models when instantiating the contract.
  2. New cost types added to the enum `ContractCostType`. There are two new cost types for each field in the `ContractCodeCostInputs`, one for the cost of parsing a module and one for the cost of instantiating an already-parsed module.

The way these are intended to be used is as follows:

  - When a new contract is uploaded, it is initially parsed with the old `VmInstantiation` cost model using the contract byte size, in order to check the contract's validity. This already happens today.
  - Next, new code supporting this CAP performs an additional pass is made over the Wasm module extracting numbers for the new `ContractCodeCostInputs`, which is then stored in the new `ContractCodeEntry` ledger entry.
  - When a contract is instantiated, the host checks the `ext` field:
    - If the contract has `ContractCodeCostInputs` then new code supporting this CAP charges the instantiation each of the new `ContractCostType`s using the corresponding `ContractCodeCostInputs` as inputs.
    - Otherwise the instantiation is charged the old `VmInstantiation` cost model using the contract byte size, as happens today.

## Design Rationale

Tightening the cost model to a closer approximation of reality requires two things:

  - Having multiple inputs that more precisely characterize the content of the Wasm module, rather than just its byte size.
  - Having multiple cost models, one for each such input, that more precisely characterize the cost of each type of work that a Wasm module might incur depending on its contents.

Additionally, while currently the `VmInstantiation` cost type charges the cost of parsing, validating and instantiating a given Wasm module all together, we anticipate (and have already implemented) subsequent CAPs will support splitting the parsing and validation stages off of the instantiation stage, in order to support caching modules. We therefore split all the cost types introduced in this CAP in two, one for the parsing and validation stage and one for the instantiation stage.

## Protocol Upgrade Transition

### Backwards Incompatibilities

The change is broadly backward compatible (new software can continue to process old data).

The change adds new fields and new enumeration values, so it is not forward compatible (old software must be upgraded to accept the new data).

### Resource Utilization

The change will add a small additional amount of storage on each contract ledger entry, as well as incurring a small additional amount of work to characterize the contract's code once, on upload (roughly double the CPU cost for an upload, due to parsing the code twice). While we could attempt to minimize this by more invasive changes to wasmi, it seems likely that the cost of an upload is dominated by its storage costs, and in any case uploads are expected to be much less frequent than invocations.

In general this change is aimed at reducing unnecessary costs, so should provide room to add more transactions to a ledger, which will increase overall resource utilization (intentionally).

## Security Concerns

The main security risk is that the new cost model might undercount something, allowing malicious contracts to DoS validators by submitting expensive-to-instantiate contracts that the validators incorrectly assume are cheap-to-instantiate. We have attempted to minimize this in the implementation (eg. by prohibiting certain types of input that never occur in normal benign contracts) and to some extent this risk exists in today's coarse `VmInstantiation` cost model too, the risk is just elevated the tighter we make the cost model.

## Test Cases

TBD

## Implementation

A preliminary implementation is [underway in the soroban-env-host repository](https://github.com/stellar/rs-soroban-env/pull/1359)
