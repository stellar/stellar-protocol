## Preamble

```
SEP: ????
Title: NFT Data Entries
Author: Leigh McCulloch <@leighmcculloch>, Tyler van der Hoeven <@tyvdh>
Status: Draft
Created: 2021-04-07
Updated: 2021-11-17
Version: 0.2.0
```

## Simple Summary

Defines common namespaces and fields for account data entries used to
identify and describe NFTs (non-fungible tokens) on the issuing account.

## Abstract

This SEP defines data entries that a Stellar account issuing a single asset
that is an NFT can define on itself to describe the NFT it is issuing without
needing to rely on a home domain hosting a stellar.toml containing asset
information about the NFT.

## Motivation

NFTs have become popular over the recent months and there has been an uptick
in experimentation with NFTs on Stellar.

An analysis of account data entries on the Stellar testnet and pubnet
indicates that there is a common approach to the issuing of NFTs on the
Stellar network. A Stellar account is created, it issues an amount of an
asset that is the NFT, it sets data entries on itself describing the digital
or real-world asset tokenized by the asset, and the account is locked
ensuring that the issued NFT has a fixed supply and any data entries created
on the account cannot be changed.

For the most part it appears that the experimental NFTs on Stellar have
converged on similar basic setup. However, there appears to be no common set
of data entries in use.

This fragmentation in the format and definition of data entries describing
NFTs makes it difficult for a developer to display meaningful information
about an NFT within a wallet or block explorer, and for products to
interoperate with NFT assets created by other products.

It is worth noting that it is possible that NFTs will appear on Stellar that
do not follow the setup described above and may change substantially such as
by not locking the issuing account, or by other changes. It is not the
motivation of this protocol to limit that possibility, and this protocol does
not define how an NFT is created other than a minimal set of data entries
that describe it.

## Specification

A Stellar account that issues an NFT asset may use the following data entries
to refer to the digital or real-world asset that the NFT tokenizes.

All data entries are optional.

All data entries are within the data entry namespace `nft`. Data entry
namespaces were introduced in [SEP-18].

The presence of any data entry within the `nft` namespace indicates that the
account is an issuer of an NFT asset.

A Stellar account that issues an NFT and uses any of these data entries can
use any additional data entries to describe additional features,
capabilities, or attributes that are unique to the NFT or the product
creating the NFT.

### Data Entries

#### Keys
Name | Type | Description
-----|------|------------
`nft.asset.encoding` | string | A value indicating how the asset is encoded. Valid values: `url`, `ipfshash`, `compactv1`.
`nft.asset.url[n]` | string | Present if encoding is `url`. One or more data entries where `n` starts at `0`, where the combined value of all the data entries is a URL to the asset tokenized by the NFT. URLs may be any URL, such as a `https://` or `ipfs://` URL, but may use some schemes noted in this document.
`ipfshash`* | string | Present if encoding is `ipfshash`. A single data entry containing an IPFS CID. Equivalent to `nft.asset.url[0]` with a value of
`ipfs://<CID>`.
`nft.asset.sha256` | string | A SHA-256 hash of the asset referenced by the `nft.asset.url[n]` data entries.
`nft.meta.url[n]` | string | One or more data entries where `n` starts at `0`, where the combined value of all the data entries is a URL to a JSON document containing any meta data about the NFT. URLs may be any URL, such as a `https://` or `ipfs://` URL, but may use some schemes noted in this document.
`nft.meta.sha256` | string | A SHA-256 hash of the meta data referenced by the `nft.meta.url[n]` data entries.

\* `ipfshash` is compatible with [Litemint.io].

#### Encoding: `url`

When an asset is URL encoded it is either referenced by a URL such as a
`https://` or `ipfs://` URL, or embedded using a data URL such as
`data:image/gif;base64,...`. The URL is encoded in `nft.asset.url[n]` fields
where `n` starts at `0`, where the combined value of all the data entries is the
URL of the asset tokenized by the NFT.

#### Encoding: `ipfshash`

When an asset is IPFS hash encoded it is stored in IPFS and the CID hash of the document or object is stored as the value.

#### Encoding: `compactv1`

When an asset is compact encoded it's data is encoded into the key and value
fields of data entries inside the Stellar account.

The first 2 bytes of the key are an indexing value from 0 to 999. The last 46
bytes are the first/next chunk of the data. The value is a slice of 64 bytes of
the next chunk of the data buffer. A data entry is added repeatedly until the
data is fully rendered in the keys and values.

#### Examples

##### Example (storing data on IPFS)
Name | Description
-----|------------
`nft.asset.url[0]` | `ipfs://QmYyamp4LUZc3vPFN5ohUH2gChQHsbciN89iXbLEeDLQ22`
`nft.asset.sha256` | `2171267fe329525d63780e8cfeeee9c9e00d0ceb9417ab402b62e10f5c98085f`
`nft.meta.url[0]` | `ipfs://QmXmjeRNV8dDkGRcXqyaFydaM2NYwvYqwpmbnQUnxCsDbQ`
`nft.meta.sha256` | `c917791b24df003ba347caf2a7259b21d78e7c236115f285cc2b08c30c16b1d9`

##### Example (storing data on Stellar inside a data URL)
Name | Description
-----|------------
`nft.asset.url[0]` | `data:image/gif;base64,R0lGODlhAQABAIcAAP8AAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[1]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[2]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[3]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[4]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[5]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[6]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[7]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[8]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[9]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[10]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[11]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[12]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[13]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[14]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[15]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
`nft.asset.url[16]` | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACH/C05FVFNDQVBFMi4wAwEAAA`
`nft.asset.url[17]` | `Ah+QQEAAAAACwAAAAAAQABAAAIBAABBAQAOw==`
`nft.asset.sha256` | `0355d1adbb1acc92b8886081145bad232e99188255c19b27e9ef4c6f5118914f`
`nft.meta.url[0]` | `data:application/json;base64,ewogICJuYW1lIjogIkZhbGwiLAogICJkZXN`
`nft.meta.url[1]` | `jcmlwdGlvbiI6ICJQaG90byBvZiBsZWF2ZXMg7aC87b2BIGFuZCBza3kg4puF77i`
`nft.meta.url[2]` | `PIGluIFNhbiBGcmFuY2lzY28uIgp9`
`nft.meta.sha256` | `5a3c6f43d394aa971260d1690b9b200e83c67c5afa8c6c2ae2872e8bcde040af`

##### Example (storing data on Stellar inside data entries using the compact v1 format)
Name | Description
-----|------------
`nft.asset.url[0]` | `-:compactv1`
`00iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAEI0lEQVRYR8WXS0` | `aVVVUlRILzJQalRLTmozNHlWcGtsamowVkU3MVpDbGowbXpiQWlpRnBWVkx0SUtJS2lSVkRRb29paUlCZEYwWA==`
`01MRtVCTmikriRBa9CApWvQmNYXRmRzNGW2+OHe8M/d7zmcR3o1+d84953f+59z7` | `M2M5V0x0ZktEMUdOc1JoKzNJTk5EbFRMT1ZYdnhpSStCZ0p6a2dEU2xtK21BS3VMZktqT0hXWTJ1N3pqVEcwdg==`
`029f5mv9/rt6O586upbXf4FGyDckAu8Bxgho0P67Hev1Gx6PSsqZYCqyNxkP0f2g` | `MGhOQUJxU3dwZW1SVk5UWmRJa3FWU2ZZOUVVbmJCaEJzaWhKaWtLWUE2dUtYSUJrWnFDRzVtQ0dBbCtHQlhOOA==`
`03...` | `...`
`nft.asset.sha256` | `0355d1adbb1acc92b8886081145bad232e99188255c19b27e9ef4c6f5118914f`
`nft.meta.url[0]` | `data:application/json;base64,ewogICJuYW1lIjogIkZhbGwiLAogICJkZXN`
`nft.meta.url[1]` | `jcmlwdGlvbiI6ICJQaG90byBvZiBsZWF2ZXMg7aC87b2BIGFuZCBza3kg4puF77i`
`nft.meta.url[2]` | `PIGluIFNhbiBGcmFuY2lzY28uIgp9`
`nft.meta.sha256` | `5a3c6f43d394aa971260d1690b9b200e83c67c5afa8c6c2ae2872e8bcde040af`

### Meta Format

The meta document referenced by the `nft.meta.url[n]` data entries must be
encoded in JSON. The following fields are defined. All fields are optional.

Any other field may be added to the meta data document to describe additional
features, capabilities, or attributes that are unique to the NFT or the
product creating the NFT.

#### Fields
Name | Type | Description
-----|------|------------
`name` | string | A short name for the NFT.
`description` | string | A long description of the NFT.
`description` | string | A [mime-type](https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types) describing the content-type of the asset referenced by the `nft.asset.url[n]` data entries. e.g. `image/gif`.

#### Example

```json
{
  "name": "Fall",
  "description": "Photo of leaves 🍁 and sky ⛅️ in San Francisco.",
  "content_type": "image/jpg"
}
```

## Design Rationale

This protocol is intentionally lightweight and limited in its specification
to limit the chance that this protocol limits innovation. It describes a
minimal set of data entries – two URLs – that NFTs can use to reference the
asset being tokenized. These minimal data entries limit the data required
on-network, limiting the cost of issuing NFTs, while providing enough
information for applications to display some meaningful information about the
NFT.

This protocol also defines for each field that references data off-network a
`sha256` hash. The hash is of the data file referenced by the URLs and can be
used by applications downloading the data to ensure the data has not changed
or been tampered with. Including hashes of off-chain data is common in NFTs
of other blockchains.

## Implementations

### Example

[makenft.web.app] hosts an example implementation that creates NFT assets on
the Stellar network using the data entries and meta data described in this
protocol. The source code is available at:
[github.com/leighmcculloch/makenft].

[SEP-18]: ./SEP-0018.md
[makenft.web.app]: https://makenft.web.app
[github.com/leighmcculloch/makenft]: https://github.com/leighmcculloch/makenft
[Litemint.io]: https://litemint.com
