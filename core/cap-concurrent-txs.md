# CAP-00xx: Concurrent Transactions

## Preamble

```text
CAP: 00xx
Title: Concurrent Transactions
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

Users of the Stellar network must coordinate and navigate the sequence number
for their account when transacting with more than one transaction at a time.

Typically this involves throttling payments to be processed serially and
risking the failure of one transaction invalidating a subsequent transaction.

Users who need to transact concurrently, or who do not wish to risk failed
subsequent transactions, can create a pool of Stellar accounts that exist
only to be the source accounts of transactions to provide sequence numbers.
Users must create the pool of accounts, maintain their balances to cover
transaction fees, and operate a database or infrastructure supporting
synchronized locking of the accounts. An account is locked when selected for
use with a transaction and unlocked after the transaction's time bounds have
been exceeded by a closed ledger.

These problems are very similar to the problems faced by users of credit
network acquiring payment systems that do not allow concurrent payments on a
single virtual terminal. This problem is one of the problems often abstracted
from merchants of credit networks by payment gateways and payment service
providers.

These problems increase the complexity of integrating with the Stellar
network.

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
`sourceAccount`, but also zero (`0`), if its `ledgerBounds` is set to
a non-zero value and limits the transaction to being valid only for
two or less ledgers.

A transaction submitted will be valid only if, for a next ledger `n`:
- `ledgerBounds` `minLedger` is set to the `n-1` or `n`, `maxLedger`
is set to `n`, and its hash was not included in the last ledgers
transaction set.
- `ledgerBounds` `minLedger` set `n` and `maxLedger` set to `n` or
`n+1`.

A transaction submitted with a `seqNum` of zero that does not satisfy
the `ledgerBounds` requirements is rejected with
`TransactionResultCode` `txTOO_LATE` if its `maxLedger` is less than
the next ledger, or `txTOO_EARLY` if its `minLedger` is greater than
the next ledger.

A transaction submitted with a `seqNum` of zero that satisfies the
`ledgerBounds` requirements, but whose hash is included in the last
ledgers transaction set, is rejected with `TransactionResultCode`
`txDUPLICATE`.

This proposal introduces a new `TransactionResultCode` `txDUPLICATE`
that is used whenever a transaction is submitted a subsequent time
after it has been included in a past ledger, and no other condition
makes the transaction invalid.

## Design Rationale

Sequence numbers allow the protocol to guarantee that no replay of a
transaction is ever possible for an account, forever, without a
validator needing to remember all transactions that have been
included in past ledgers. This reduces the storage and lookup costs
for a validator.

However, for the majority of transactions on the Stellar network
sequence numbers do not need to provide this guarantee forever. The
majority of users of the Stellar network build, sign, and submit
transactions immediately with an expectation of success or failure
within a single ledger. Even though the Stellar network provides a
transaction queue which allow transactions to be accepted in a near
future ledger during congestion, most application developers assume
success or failure within a single ledger. We could argue from this
behavior by application developers that they do not signal a need
for most transactions to be valid for more than a single ledger.

These qualities of the majority of use cases submitting transactions
to the network indicate that the network does not need to prevent
replay using sequence numbers forever.

Validators can efficiently check that a transaction has not occurred
in the last ledger with limited storage or memory requirements since
the transaction set is limited to the transactions in a single
ledger.

### Sequence Number Zero

The zero (`0`) sequence number is selected because it has no meaning
within the Stellar protocol since no transaction is valid with that
value. The zero value is also the default integer value and in the
Stellar protocol the zero value is routinely used as an indicator of
no value being set, as is the case in `TimeBounds`. The zero (`0`)
sequence number does have meaning in [SEP-10] as a method for
creating a Stellar transaction that is guaranteed to be invalid on
any Stellar network, however that invariance of invalidity can be
maintained by [SEP-10] transactions never setting the
`ledgerBounds` field of a transaction.

### Ledger Bounds

The `ledgerBounds` precondition proposed in [CAP-21] allows a
user to define a transaction that is valid only for a fixed range
of ledgers. The precondition allows a user to specify that a
transaction is valid only for the next ledger, and is more accurate
at achieving this than `timeBounds`.

### Transaction Result Code Duplicate

The `TransactionResultCode` `txDUPLICATE` is introduced because
other result codes semantics do not fit the case where the
`ledgerBounds` are valid but a transaction is valid. When a
duplicate transaction is submitted with the protocol today it
will likely receive a `txBAD_SEQ` result code, however in this
case the sequence number is zero or not set.

## Protocol Upgrade Transition

### Backwards Incompatibilities

This proposal is completely backwards compatible as it defines new
functionality that is only accessible with transactions that are currently
invalid.

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
