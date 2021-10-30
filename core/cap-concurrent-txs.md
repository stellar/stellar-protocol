# CAP-00xx: Concurrent Limited Validity Transactions

## Preamble

```text
CAP: 00xx
Title: Concurrent Limited Validity Transactions
Working Group:
    Owner: Leigh McCulloch <@leighmcculloch>
    Authors: Leigh McCulloch <@leighmcculloch>
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

This proposal allows a transaction to be valid with a zero sequence number if
the transaction is valid for only two ledgers. Transactions are typically valid
only if their sequence number is the next sequence number after the sequence
number of the account at the time they are executed.

This proposal is dependent on the `ledgerBounds` transaction precondition
proposed in [CAP-21].

## Specification

### XDR changes

None.

### Semantics



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
