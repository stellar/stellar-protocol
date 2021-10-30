# CAP-00xx: Concurrent Limited Validity Transactions

## Preamble

```text
CAP: 00xx
Title: Concurrent Limited Validity Transactions
Working Group:
    Owner: Leigh McCulloch <@leighmcculloch>
    Authors: Leigh McCulloch <@leighmcculloch>, David Mazières <@stanford-scs>
    Consulted: TBD
Status: Draft
Created: 2021-10-29
Discussion: TBD
Protocol version: TBD
```

## Simple Summary

This proposal provides transactors with the capability to submit transactions
to the Stellar network concurrently, without coordinating the sequence number
of those transactions. This capability is limited to transactions that are
valid for two ledgers only, intended for use in the most common payments and
transacting use case where users are building, signing, and submitting
transactions immediately.

## Working Group

TBD

## Motivation

- Users have to navigate sequence numbers.
- Sequence numbers allow us to guarantee no replay of transactions forever for an account.
- Most users want to submit transactions now and are not presigning transactions or creating preauthorized transactions that need submitting in the future.
- Most users do not need their transactions to sit in the transaction queues for many ledgers.
- Most application developers code for immediate success/failure, and not delayed success.
- Since the vastly most common use case on Stellar is to build a transaction and submit it immediately, we don't need to be able to prevent replay forever.
- Since the vast majority of application developers implement assuming single ledger success/failure, and not delayed success, there is little value in keeping these types of transactions in the transaction queue to be accepted in the near future.
- For most users we only need to be able to prevent replay over a short window of time, and transactions can fail fast, since that's what application developers assume will happen.

### Goals Alignment

This CAP is aligned with the following Stellar Network Goals:

- The Stellar Network should make it easy for developers of Stellar projects to
create highly usable products.

- The Stellar Network should run at scale and at low cost to all participants of
the network.

- The Stellar Network should enable cross-border payments, i.e. payments via 
exchange of assets, throughout the globe, enabling users to make payments between 
assets in a manner that is fast, cheap, and highly usable.

## Abstract

This proposal allows a transaction to be valid if its `seqNum` is zero (`0`), if
the transaction is valid for only two ledgers.

This proposal is dependent on the `ledgerBounds` transaction precondition
proposed in [CAP-21].

## Specification

### XDR changes

```diff mddiffcheck.base=74498070b99a7fb1d18b78d104f95d797b4f4c2c
diff --git a/src/xdr/Stellar-transaction.x b/src/xdr/Stellar-transaction.x
index 1a4e491a..f388c69c 100644
--- a/src/xdr/Stellar-transaction.x
+++ b/src/xdr/Stellar-transaction.x
@@ -1508,7 +1508,9 @@ enum TransactionResultCode
 
     txNOT_SUPPORTED = -12,         // transaction type not supported
     txFEE_BUMP_INNER_FAILED = -13, // fee bump inner transaction failed
-    txBAD_SPONSORSHIP = -14        // sponsorship not confirmed
+    txBAD_SPONSORSHIP = -14,       // sponsorship not confirmed
+
+    txDUPLICATE = -15 // transaction has been included in a prior ledger
 };
 
 // InnerTransactionResult must be binary compatible with TransactionResult

```

### Semantics

This proposal changes the values that are valid for the `seqNum` of a
`TransactionV1Envelope` to not only the next sequence number of its
`sourceAccount`, but also zero (`0`), if its `ledgerBounds` limits
the transaction to being valid only for two ledgers.

A transaction submitted will only be valid if:
- `ledgerBounds` `minLedger` is set to the last ledger, `maxLedger` is set to the next ledger, and its hash was not included in the last ledgers transaction set.
- `ledgerBounds` `minLedger` set to the next ledger and `maxLedger` set to the ledger after.

A transaction submitted with a `seqNum` of zero that does not satisfy
the `ledgerBounds` requirements is rejected with
`TransactionResultCode` `txTOO_LATE` if its `maxLedger` is less than
the next ledger, or `txTOO_EARLY` if its `minLedger` is greater than
the next ledger.

A transaction submitted with a `seqNum` of zero that does satisfy the `ledgerBounds` requirements, but whose hash is included in the last ledgers transaction set, is rejected with `TransactionResultCode` `txDUPLICATE`.

This proposal introduces a new `TransactionResultCode` `txDUPLICATE`.

## Design Rationale



## Protocol Upgrade Transition

### Backwards Incompatibilities

This proposal is backwards compatible.

### Resource Utilization

This proposal requires validators to check that a transaction has not been
included in the last ledger if it has a zero sequence number, and with
`ledgerBounds` set to a range no greater than two ledgers, where that range
overlaps with the last ledger and the next ledger. This will require a cost of
lookup trending towards O(1) assuming a hash set, map, dictionary, or similar
data structure can be used. The size of the data set will be limited to the
number of operations permitted into any ledger. At this time that limit is
1000 operations. Therefore, the data set will be at most 2000 transactions,
and will consume at least 64KB if stored in memory, assuming transaction
hashes are 32bytes.

This proposal requires validators to hold a list of all transactions hashes
from the last ledger. Validators typically already store a list of the
transactions from a number of recent ledgers and so no new storage is
expected.

## Test Cases

None yet.

## Implementation

None yet.

[CAP-21]: https://stellar.org/protocol/cap-21
