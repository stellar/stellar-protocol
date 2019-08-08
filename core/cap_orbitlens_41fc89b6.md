## Preamble

```
CAP: 0026
Title: Disable Inflation Mechanism
Author: OrbitLens <orbit.lens@gmail.com>
Status: Draft
Created: 2019-07-10
Updated: 2019-08-08
Discussion: https://groups.google.com/forum/#!topic/stellar-dev/LIFvbMi9jPo
Protocol version: TBD
```

## Simple Summary

This CAP disables the inflation mechanism.

## Motivation

Inflation mechanism was originally planned as a simple way for users to support important 
ecosystem projects and keep the overall XLM supply slightly inflationary.

- Currently, it doesn’t serve its original purpose, as users mostly prefer to claim the 
inflation payouts through the inflation pools instead of sponsoring ecosystem projects. 
As a result, inflation micropayouts from XLM pools generate a significant validators 
load and clog the network.
- Payouts get more and more resource consuming for validators over time due to the total 
lumens circulation supply increase.
- Once the validators vote for the significant base fee increase, such payouts became much 
less profitable for most lumen holders, and XLM pools will be forced to raise the minimum 
required account balance to more than 1000XLM to cover transaction fee loses.
- Inflation payouts may lead to additional complications in some edge-cases when 
programming smart contracts.
- Inflation deprecation opens new possibilities for the more effective targeted reward 
distributions that require complex logic, like stimulating DEX liquidity providers.

## Abstract

Turning off inflation requires several changes in Stellar Core, namely `Inflation` and 
`SetOptions` operations behavior as well as fees processing routine. 
At the same time, it can be implemented without XDR changes and breaking protocol changes.

## Specification

This proposal requires the following Core behavior changes:

1. Inflation operation always returns `INFLATION_NOT_TIME` result code.
2. SetOptions operation returns `SET_OPTIONS_INVALID_INFLATION` result code when a users 
tries to change `inflationDest`.
3. Fee processing routine discards paid transaction fees instead of adding them to the fee pool.
4. LedgerHeader properties `feePool` and `inflationSeq` for a newly created ledger are set to zero.

## Design Rationale

The proposed approach does not require breaking protocol changes and allows turning on 
the inflation mechanism in the future if needed. Due to the simplicity of proposed changes, 
the implementation potentially should require minimum efforts.

## Security Concerns

None.

## Backwards Incompatibilities

This CAP contains no breaking changes and is fully backward compatible.

## Questions

- Is it possible (and does it makes sense) to remove `inflationDest` field from 
the `Account` entry, as well as `feePool` and `inflationSeq` from `LedgerHeader`?