## Preamble

```
CAP: CAP-0053
Title: Smart Contract Data
Working Group:
    Owner: Graydon Hoare <@graydon>
    Authors: Graydon Hoare <@graydon> 
    Consulted: Siddharth Suresh <@sisuresh>, Jon Jove <@jonjove>, Nicolas Barry <@MonsieurNicolas>, Leigh McCulloch <@leighmcculloch>, Tomer Weller <@tomerweller>
Status: Draft
Created: 2022-05-25
Discussion: https://groups.google.com/g/stellar-dev/c/vkzMeM_t7e8
Protocol version: TBD
```

## Simple Summary

This CAP defines a ledger entry type for storing data records for smart contracts, as well as host functions for interacting with it and some discussion of its interaction with contract invocation and execution.

## Working Group

This protocol change was authored by Graydon Hoare, with input from the consulted individuals mentioned at the top of this document. 

## Motivation

Most nontrivial smart contracts have persistent state. Earlier smart contract CAPs left this topic undefined, this CAP attempts to fill in the gap.

### Goals Alignment

Same goals alignment as CAP-46. This CAP is essentially "a continuation of the work initiated in CAP-46".

## Requirements

  - Smart contracts must be able to store state in the ledger that persists between transactions.
  - Contracts should be given as much flexibility as possible in how they organize their data.
  - As much as possible, multiple contracts should be able to execute in parallel.
  - Parallel execution must maintain a strong consistency model: strict serializability.
  - The performance impact of user-initiated IO should be strictly limited, as IO can be very costly.
  - The granularity of IO should balance the desirability of amortizing fixed per-IO costs with the undesirability of IO on redundant data.

Additionally, several considerations that applied to the data model of CAP-46 apply here, especially around interoperability and simplicity:

  - At least some data should be readable passively without running contract code.
  - Data should be at least somewhat robust to version changes in the contract code accessing it.

## Abstract

A new ledger entry type is added that stores key-value pairs, where both key and val are of type `SCVal` (defined in CAP-46).

New host functions are added to query and modify this ledger entry type directly from within a smart contract.

## Specification

Readers should be familiar with the content of CAP-46 and CAP-47 at least, this cap uses their definitions.

This CAP adds an entry type code `LedgerEntryType.CONTRACT_DATA`, an entry struct `ContractDataEntry`, and a variant of the `LedgerEntry` and `LedgerKey` unions to store the ledger entry and its key material, respectively, under the `CONTRACT_DATA` type code.

The _full key_ of a `CONTRACT_DATA` ledger entry is not just by its `key` field, but also a `ContractID` field (as defined in CAP-47). A contract can only read and write `CONTRACT_DATA` ledger entries that have that contract's `ContractID`.

Host functions are provided to get, put, delete, and check for the existence of a given `CONTRACT_DATA` entry.

### Restrictions

#### Point access only
Contract data IO is restricted to so-called "point access" to specific keys. In particular there is no support for "range queries", upper or lower bounds, or any sort of iteration over the keyspace.

#### Static footprints
To facilitate parallel execution, contract data IO is also restricted to operate on keys that are declared in the so-called _footprint_ of each transaction. The footprint is a set of _full keys_ each of which is marked as either read-only or read-write. The footprint _permits_ any read of a key within it, or a write of any key within it that is makred as read-write. All other reads and writes are not permitted.

Any call to a host function to interact with a _full key_ that is not permitted by the footprint will trap.

The footprint of a transaction is static for the duration of the transaction: it is established before transaction execution begins and does not change during execution. The exact mechanism of defining the footprint of a transaction will be provided in a later CAP that deals with transaction invocation. 

### XDR changes
```diff mddiffcheck.base=8e484c533ea9737127bd9a940b410e18943ee519
diff --git a/src/protocol-next/xdr/Stellar-ledger-entries.x b/src/protocol-next/xdr/Stellar-ledger-entries.x
index d2b303ba6..4c9877103 100644
--- a/src/protocol-next/xdr/Stellar-ledger-entries.x
+++ b/src/protocol-next/xdr/Stellar-ledger-entries.x
@@ -3,6 +3,7 @@
 // of this distribution or at http://www.apache.org/licenses/LICENSE-2.0

 %#include "xdr/Stellar-types.h"
+%#include "xdr/Stellar-contract.h"

 namespace stellar
 {
@@ -100,7 +101,8 @@ enum LedgerEntryType
     CLAIMABLE_BALANCE = 4,
     LIQUIDITY_POOL = 5,
     CONTRACT_CODE = 6,
-    CONFIG = 7
+    CONFIG = 7,
+    CONTRACT_DATA = 8
 };

 struct Signer
@@ -517,6 +519,12 @@ struct ContractCodeEntry {
     ContractBody body;
 };

+struct ContractDataEntry {
+    Hash contractID;
+    SCVal key;
+    SCVal val;
+};
+
 enum ConfigSettingType
 {
     CONFIG_TYPE_UINT32 = 1
@@ -578,6 +586,8 @@ struct LedgerEntry
         LiquidityPoolEntry liquidityPool;
     case CONTRACT_CODE:
         ContractCodeEntry contractCode;
+    case CONTRACT_DATA:
+        ContractDataEntry contractData;
     case CONFIG:
         ConfigEntry config;
     }
@@ -639,6 +649,12 @@ case CONTRACT_CODE:
     {
         Hash contractID;
     } contractCode;
+case CONTRACT_DATA:
+    struct
+    {
+        Hash contractID;
+        SCVal key;
+    } contractData;
 case CONFIG:
     struct
     {
```

### Host function additions

```
/// Stores a CONTRACT_DATA ledger entry with the currently-executing
/// contract ID and the provided key/val pair. Traps if the current
/// footprint does not allow writing to (contract ID, key).
func $contract_data_put (param $key i64) (param $val i64) (result i64)

/// Retrieves the val field from a CONTRACT_DATA ledger entry with
/// the currently-executing contract ID and the provided key pair.
/// Traps if the current footprint does not allow reading from
/// (contract ID, key), or if there is no such ledger entry.
func $contract_data_get (param $key i64) (result i64)

/// Deletes a CONTRACT_DATA ledger entry with the currently-executing
/// contract ID and the provided key pair. Traps if the current
/// footprint does not allow writing to (contract ID, key), or if
/// there is no such ledger entry.
func $contract_data_del (param $key i64) (result i64)

/// Returns a boolean value indicating whether a CONTRACT_DATA ledger
/// entry exists with the currently-executing contract ID and the
/// provided key. Traps if the current footprint does not allow reading
/// from (contract ID, key).
func $contract_data_has (param $key i64) (result i64)
```

### Semantics

The semantics of each host function is described in the associated comments above.

These semantics should be considered in the light of the strict serializability requirement and the understanding that all IO occurs within a transaction. In particular:
  - Each write is visible immediately within the issuing transaction, but not to any other transaction, until the writing transaction commits
  - All reads and writes are observable to transactions as they would be if the transactions executed sequentially in transaction-set application order

## Design Rationale

### Granularity
Granularity of data elements is a key consideration in storage. Too large and IO is wasted loading and storing redundant data; too small and the fixed space and time overheads associated with storing each data element overwhelm the system. Moreover when parallel execution is included in consideration, the storage granularity becomes the unit of contention, with two contracts constrained to execute serially (or with some mechanism to enforce serializable consistency) when they share access to a single data element and at least one of them performs a write.

Keying contract data by arbitrary `SCVal` values allows users to choose the granularity of data entering and leaving IO functions: fine-grained data may be stored under very large and specific keys, or coarser-grained data may be stored under smaller prefixes or "group" keys, with inner data structures such as vectors or maps combining together groups of data values. This is an intentional decision to allow contract authors to experiment and find the right balance, rather than deciding a priori on a granularity.

### Static footprint
The requirement that each transaction have a static footprint serves both to limit arbitrary user-initiated IO mid-transaction (i.e. to enable efficient bulk IO only at transaction endpoints) as well as to enable static scheduling of parallel execution.

This limits transactions to those which _have_ static footprints, which at first glance may seem overly restrictive. To make it work in practice, contracts with dynamic footprints need to be run twice, once "offline" (or out of the main stellar-core processing phase, for example on a horizon server with a recent ledger snapshot) and then once again online, as part of normal stellar-core processing.

The first run is executed in a special trial-run or "recording" mode that permits any reads or writes and just observes and records the footprint; but it also does not actually effect any changes to the ledger, running against a (possibly stale) read-only snapshot and discarding all writes at the end of execution. The recorded footprint is then used as the static footprint for the second run, when the transaction is submitted for real execution against the real ledger, in stellar-core. The second execution thereby validates and enforces the footprint, assuming nothing has changed between recording and enforcing. If the true footprint _has_ changed between recording and enforcing, the transaction fails the second run and the user must retry the cycle.

This technique is taken from the ["deterministic database"](http://cs.yale.edu/homes/thomson/publications/calvin-sigmod12.pdf) and ["conflict-free concurrency control"](https://arxiv.org/abs/1810.01997) literature, where footprints are sometimes also called "read-write sets" and footprint recording is sometimes also called "reconnaissance queries".

## Protocol Upgrade Transition

### Backwards Incompatibilities

There is no backwards incompatibility consideration in this CAP.
### Resource Utilization

By restricting IO to pre-declared static footprints, IO costs are fairly limited. The transaction execution lifecycle will perform bulk IO of all ledger entries in the footprint at the beginning of transaction execution, and write back those modified entries only at the end of execution. Calibrating the costs of such IO and reflecting it in fees charged for use remains an open problem to address. This CAP expects to build on the cost model that CAP-46 and CAP-51 will eventually provide.

## Security Concerns
The main security risk is unauthorized data-writing, as all data on the blockchain is publicly readable in any case.

The authorization model for writes is narrow and easy to understand: contracts are restricted to only being able to write to data with their contract ID. Further authorization checks are delegated to contracts themselves to manage.

## Test Cases
TBD.

## Implementation

There is are two work-in-progress branches associated with this CAP:

  - [stellar-core PR 3439](https://github.com/stellar/stellar-core/pull/3439) including XDR and C++ changes to stellar-core
  - [stellar-contract-env PR 83](https://github.com/stellar/rs-stellar-contract-env/pull/83) including Rust changes to the contract host crate
