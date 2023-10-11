## Summary

This proposal introduces a standard interface for creating and managing NFT collections on Soroban, ensuring compatibility and interoperability within the Stellar ecosystem, and aligning with the previously defined NFT interface and the ERC-1155 standard.

## Motivation

A standardized interface for NFT collections on Soroban will facilitate seamless interaction within the Stellar ecosystem, enhancing user experience and developer interaction by providing a consistent API for NFT collection creation, management, and interaction, while also allowing for efficient batch transfers and management of both fungible and non-fungible tokens within a single contract.

## Abstract

This proposal defines a Rust trait for NFT collections, ensuring that all NFT collection contracts on Soroban adhere to a common API. This API includes functions for creating new NFTs within a collection, transferring NFTs, querying for ownership, and for accessing metadata necessary for displaying NFT information in wallets and other user interfaces.

## Specification

```rust
pub trait NFTCollectionFactory {
    // Admin interface – privileged functions.
    fn initialize(
        env: Env, 
        admin: Address, 
        collection_name: String, 
        collection_symbol: String
    );

    fn mint_nft(
        env: Env, 
        to: Address, 
        name: String, 
        symbol: String, 
        royalty_recipient: Address, 
        royalty_percentage: u32, 
        short_uri: String, 
        detailed_uri: String, 
        long_uri: String
    ) -> Address; // Returns the address of the minted NFT

    fn batch_mint_nft(
        env: Env, 
        to: Address, 
        names: Vec<String>, 
        symbols: Vec<String>, 
        royalty_recipients: Vec<Address>, 
        royalty_percentages: Vec<u32>, 
        short_uris: Vec<String>, 
        detailed_uris: Vec<String>, 
        long_uris: Vec<String>
    ) -> Vec<Address>; // Returns the addresses of the minted NFTs

    // NFT Interface
    fn transfer(env: Env, from: Address, to: Address, token_id: u32);

    fn batch_transfer(env: Env, from: Address, to: Address, token_ids: Vec<u32>);

    fn approve(
        env: Env, 
        owner: Address, 
        approved: Address, 
        token_id: u32
    );

    fn transfer_from(
        env: Env, 
        from: Address, 
        to: Address, 
        token_id: u32
    );

    // Descriptive Interface
    fn get_metadata(env: Env, token_id: u32) -> Metadata;

    fn decimals(env: Env) -> u32;

    fn name(env: Env) -> String;

    fn symbol(env: Env) -> String;

    fn get_royalty_recipient(env: Env, token_id: u32) -> Address;

    fn get_royalty_rate(env: Env, token_id: u32) -> u32;
}

// Metadata struct to hold NFT metadata, including descriptions and IPFS hashes.
struct Metadata {
    short_description_uri: String,  // IPFS hash or URL
    long_description_uri: String,   // IPFS hash or URL
    data_file_uri: String,          // IPFS hash or URL
}

// Metadata struct to hold NFT Collection metadata.
struct CollectionMetadata {
    name: String,
    symbol: String,
    nfts: Vec<Address>,  // Addresses of all NFTs minted by this collection
}
```

## Notes
  - The batch_mint_nft function allows for the creation of multiple NFTs in a single transaction, which can significantly reduce the cost of creating NFTs.
  - The batch_transfer function allows for the transfer of multiple NFTs in a single transaction, which can significantly reduce the cost of transferring NFTs.
  - The mint_nft function creates a new NFT within the collection, adhering to the previously defined NFT interface, and returns the new NFT's address which can be derived using a known salt and the collection's address.
  - The transfer, approve, and transfer_from functions facilitate the transfer of NFTs between addresses, with approval mechanisms.
  - The get_metadata function retrieves the metadata for a specific NFT, identified by its token_id.
  - The decimals function should always return 0 for NFTs.
  - The get_royalty_recipient and get_royalty_rate functions provide information about the royalty recipient and rate respectively for a specific NFT within the collection.
  - The CollectionMetadata struct holds relevant information about the NFT collection, including the name, symbol, and a vector of addresses representing all NFTs minted by this collection.
  - This draft is a starting point and may need further refinement and additional functions to fully cater to the use-cases and requirements of NFT collections on Soroban while ensuring compatibility with the Stellar token interface

## Changelog

- `v0.1.0` - Initial draftbased on thoughts off the top of my head and a not yet completed implementation.

## Implementations

TBD
