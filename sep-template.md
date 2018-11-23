Copied from [eip-X](https://github.com/ethereum/EIPs/blob/master/eip-X.md).

## Preamble

```
SEP: <to be assigned>
Title: Add IPFS Hash to Memo
Author: Brian Ebert, brian@motia.com
Status: Draft
Created: <date created on, in ISO 8601 (yyyy-mm-dd) format>
```

## Simple Summary
Addition of *current* IPFS Hash to Memo.

## Abstract
Add a memoType MemoIPFS_Qm to Memo.

Ingestion of a current IPFS hash to include decode from base 58 and stripping IPFS multihash metadata 0x1220.

The resulting 32 byte sha256 hash is stored as any current memoHash buffer.

## Motivation
IPFS provides distributed storage of authenticated data.  This natural repository for documents pertient to a transaction is already used on stellar, by decoding an IPFS hash from base58 and stripping two bytes of multihash metadata from the front of a 32 byte sha256 hash.  This invests trust in the third party performing the transformation, as well as depending upon a third party to point to IPFS as repository of the preimage. A labeled memo explicitly associates collateral documents with a transaction.

## Specification
#### Memo
**new Memo(type, value)**

**Memo** represents memos attached to transactions.

#### Parameters:
Name	| Type  |	Description
----- | ----- | -----------
type	|*string* | MemoNone, MemoID, MemoText, MemoHash, MemoIPFS_Qm or MemoReturn
value |	*     | *string* for MemoID, MemoText, *buffer* or *hex string* for MemoHash, MemoIPFS_Qm or MemoReturn

#### Members

* type
Contains memo type: **MemoNone, MemoID, MemoText, MemoHash, MemoIPFS_Qm or MemoReturn**


* value
Contains memo value:
  * *null* for MemoNone,
  * *string* for MemoID, MemoText,
  * *Buffer* for MemoHash, MemoIPFS_Qm, MemoReturn

#### New Methods

(static) ipfs_qm(hash) → {Memo}

Creates and returns a MemoIPFS_Qm memo.

##### Parameters:
Name | Type | Description
---- | ---- | ------------
hash |	*array* or *string*	 | 32 byte hash or hex encoded string

##### Returns:
Type:  *Memo*

## Rationale
Adaptiing Stellar to the full IPFS multihash requires changes to the storage budget for memos, with additional cost of programming. Adding a memo option of today's IPFS hash minimizes cost and schedule.  The incremental change promises data to drive future decisions regarding Stellar and IPFS.  If true multihash capability is implemented in another SEP, MemoIPFS_Qm can be deprecated.

## Backwards Compatibility
This SEP does not introduce backward incompatibility.

## Test Cases
This SEP does not affect consensus.

## Implementation
Too be proposed after determining SEP viability
