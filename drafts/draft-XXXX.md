## Preamble

```
SEP: <to be assigned>
Title: IPFS Support
Author: Samuel B. Sendelbach <sbsends@gmail.com> 
Status: Draft
Created: 2018-11-11
```

## Simple Summary
Adding IPFS support to Stellar increase functionality of the ecosystem with a smaller initial overhead than building a Stellar-specific large data store and peer-to-peer messenger.

Suggested additions:
1) Add a multi-hash field in the transaction memo.
2) Add an account operation for requesting communication accounts.

## Abstract
Currently Stellar does not support attaching large amounts of data to a transaction (in a decentralized manner), nor does it support decentralized peer-to-peer messaging at the account level. IPFS specializes in data storage and peer-to-peer networking. Formally supporting IPFS on Stellar would bolster Stellar's functionality with a minimal overhead compared to writing a stellar-specific data storage and messaging layer. 

This proposal outlines two suggested additions to the Stellar-protocol. The first proposal is to add a **multi-hash field in the transaction memo** to accommodate referencing data stored on IPFS in a transaction. The second proposed feature is an **account operation for requesting communication between two accounts**. Although not IPFS specific, an `INIT_COMM` operation would immediately enable IPFS p2p messaging as well as many other communication protocols.


## Motivation
"IPFS (the InterPlanetary File System) is a new hypermedia distribution protocol, addressed by content and identities. IPFS enables the creation of completely distributed applications. It aims to make the web faster, safer, and more open." -[IPFS](https://github.com/ipfs/ipfs#overview)

"Using the Stellar network, you can build mobile wallets, banking tools, smart devices that pay for themselves, and just about anything else you can dream up involving payments! Even though Stellar is a complex distributed system, working with it doesn’t need to be complicated." -[SDF](https://www.stellar.org/developers/guides/get-started/)

Both IPFS and Stellar are platforms that open the doors for decentralized applications. Combining a fast payment layer with decentralized data layer would allow the Stellar ecosystem to venture into more complex decentralized applications. Namely machine to machine markets, coordinating multi-signature transactions, and "smarter" smart contracts.

## Specification
The technical specification should describe the syntax and semantics of any new feature.

## Rationale
The rationale fleshes out the specification by describing what motivated the design and why particular design decisions were made. It should describe alternate designs that were considered and related work, e.g. how the feature is supported in other languages. The rationale may also provide evidence of consensus within the community, and should discuss important objections or concerns raised during discussion.

## Backwards Compatibility
Addition rather than subtraction. This proposal should be fully backwards compatible.

## Test Cases
Johansten?

## Implementation
<TBD>
