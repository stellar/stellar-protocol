Copied from [eip-X](https://github.com/ethereum/EIPs/blob/master/eip-X.md).

## Preamble

```
SEP: <to be assigned>
Title: <Add of IPFS Hash to Memo>
Author: <Brian Ebert, brian@motia.com>
Status: Draft
Created: <date created on, in ISO 8601 (yyyy-mm-dd) format>
```

## Simple Summary
Addition of current IPFS Hash to Memo.

## Abstract
Add a memoType Memo_IPFS_Qm to Memo.

Ingestion of a current IPFS hash to include decode from base 58 and stripping IPFS multihash metadata 0x1220.

The resulting 32 byte sha256 hash is stored as any current memoHash buffer.

## Motivation
IPFS provides distributed storage of authenticated data.  This natural repository for documents pertient to a transaction is already used on stellar, by decoding an IPFS hash from base58 and stripping two bytes of multihash metadata from the front of a 32 byte sha256 hash.  This invests trust in the third party performing the transformation, as well as depending upon a third party to point to IPFS as repository of the preimage. A labeled memo takes advantage of network consensus to explicitly associate collateral documents with a transaction.

Adaptiing Stellar to the full IPFS multihash requires changes to the storage budget for memos, with additional cost of programming. Adding a memo option of today's IPFS hash minimizes cost and schedule.  The incremental change promises data to drive future decisions regarding Stellar and IPFS.

## Specification
Add a memo type MEMO_IPFS_QM.

#### Memo
**new Memo(type, value)**

**Memo** represents memos attached to transactions.

#### Parameters:
Name	| Type  |	Description
----- | ----- | -----------
type	|*string* | MemoNone, MemoID, MemoText, MemoHash, Memo_IPFS_Qm or MemoReturn
value |	*     | *string* for MemoID, MemoText, *buffer* or *hex string* for MemoHash, Memo_IPFS_Qm or MemoReturn

#### Members

##### type
Contains memo type: *MemoNone, MemoID, MemoText, MemoHash or MemoReturn*


##### value
Contains memo value:
* *null* for MemoNone,
* *string* for MemoID, MemoText,
* *Buffer* for MemoHash, Memo_IPFS_Qm, MemoReturn

#### Methods

(static) fromXDRObject(object) → {Memo}
Returns Memo from XDR memo object.

Source:
node_modules/stellar-base/src/memo.js, line 227
Parameters:
Name	Type	Description
object	xdr.Memo	
Returns:
Type:  Memo
(static) hash(hash) → {Memo}
Creates and returns a MemoHash memo.

Source:
node_modules/stellar-base/src/memo.js, line 190
Parameters:
Name	Type	Description
hash	array | string	
32 byte hash or hex encoded string
Returns:
Type:  Memo
(static) id(id) → {Memo}
Creates and returns a MemoID memo.

Source:
node_modules/stellar-base/src/memo.js, line 181
Parameters:
Name	Type	Description
id	string	
64-bit number represented as a string
Returns:
Type:  Memo
(static) none() → {Memo}
Returns an empty memo (MemoNone).

Source:
node_modules/stellar-base/src/memo.js, line 163
Returns:
Type:  Memo
(static) return(hash) → {Memo}
Creates and returns a MemoReturn memo.

Source:
node_modules/stellar-base/src/memo.js, line 199
Parameters:
Name	Type	Description
hash	array | string	
32 byte hash or hex encoded string
Returns:
Type:  Memo
(static) text(text) → {Memo}
Creates and returns a MemoText memo.

Source:
node_modules/stellar-base/src/memo.js, line 172
Parameters:
Name	Type	Description
text	string	
memo text
Returns:
Type:  Memo
toXDRObject() → {xdr.Memo}
Returns XDR memo object.

Source:
node_modules/stellar-base/src/memo.js, line 207
Returns:
Type:  xdr.Memo

## Rationale
The rationale fleshes out the specification by describing what motivated the design and why particular design decisions were made. It should describe alternate designs that were considered and related work, e.g. how the feature is supported in other languages. The rationale may also provide evidence of consensus within the community, and should discuss important objections or concerns raised during discussion.

## Backwards Compatibility
All SEPs that introduce backwards incompatibilities must include a section describing these incompatibilities and their severity. The SEP must explain how the author proposes to deal with these incompatibilities. SEP submissions without a sufficient backwards compatibility treatise may be rejected outright.

## Test Cases
Test cases for an implementation are mandatory for SEPs that are affecting consensus changes. Other SEPs can choose to include links to test cases if applicable.

## Implementation
The implementations must be completed before any SEPs is given status "Final", but it need not be completed before the SEP is accepted. While there is merit to the approach of reaching consensus on the specification and rationale before writing code, the principle of "rough consensus and running code" is still useful when it comes to resolving many discussions of API details.
