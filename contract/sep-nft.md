## Preamble

```
CIP: 
Title: NFT
Author: Stellar Development Foundation <@stellar>
Status: Draft
Discussion: TBD
Created: 2023-10-11
Version 0.1.0
```

## Summary

This proposal defines a standard interface that NFTs on Soroban powered
networks, such as the Stellar network, can implement to interoperate with
contracts that use NFTs, and Stellar assets.

## Motivation

A non-fungible asset is ...

## Abstract

This proposal introduces a contract interface for NFTs. The interface is ...

The interface tries to follow an ERC-721 model.

## Specification

```rust
pub trait Interface {
    fn balance_of(env: Env, owner: Address) -> u32;
    fn transfer_from(env: Env, spender: Address, from: Address, to: Address, token_id: u32);
    fn approve(
        env: Env,
        caller: Address,
        operator: Option<Address>,
        token_id: u32,
        expiration_ledger: u32,
    );
    fn set_approval_for_all(
        env: Env,
        caller: Address,
        owner: Address,
        operator: Address,
        approved: bool,
        expiration_ledger: u32,
    );
    fn get_approved(env: Env, token_id: u32) -> Option<Address>;
    fn is_approval_for_all(env: Env, owner: Address, operator: Address) -> bool;
}
```

## Changelog

- `v0.1.0` - Initial draft based on CIP-001.

## Implementations

TBD
