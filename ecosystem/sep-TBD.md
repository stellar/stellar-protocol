
## Preamble

```
SEP: To Be Assigned
Title: Interoperability Recommendations for Digital Goods
Authors: George Kudrayvtsev <george@stellar.org>, Frederic Rezeau <frederic.rezeau@gmail.com>
Track: Informational
Status: Draft
Created: 02-22-2022
Updated: 02-22-2022
Version: 0.1.0
Discussion: https://github.com/stellar/stellar-protocol/pull/1139
```

## Simple Summary
This SEP provides informational guidelines on how digital goods can be managed on the Stellar network and within the ecosystem. It outlines some best practices on both _minting_ and _representing_ digital goods to maximize interoperability.


## Dependencies
The guidelines around digital good representation are an extension to [SEP-1][sep1-currency], specifically around the way currencies are represented. It also has a dependence on [SEP-14][sep14] which also extends [SEP-1][sep1] to scale asset metadata storage.


## Motivation
With the digital goods marketplace exploding in popularity, two needs arise: ecosystem _best practices_ for creating digital goods as well as _interoperability guidelines_ that ensure compatibility throughout the space. While both of these exist throughout the ecosystem, a single informational SEP is a necessary point of reference. Note that while the focus of this document is inspired by NFTs, it applies more broadly to digital goods that don't necessarily have strict adherence to non-fungibility.


## Abstract
We address two key concerns of digital goods: _minting_ (creation) and _representation_ (parsing, rendering, etc.). For the former, we outline a set of community-driven best practices (that are by no means a _required_ minting standard), and for the latter, we extend the [SEP-1 currency specification][sep1-currency] in order to maximize interoperability with how the ecosystem already renders assets.


## Specification
As already noted, this informational SEP is split into two parts: digital good _minting_ best practices and digital good _representation_ interoperability.

The minting best practices are merely one way to create digital goods on Stellar and should not be taken as a standard. The interoperability guidelines, however, are important in representing your digital good via [SEP-1][sep1] and maximizing its compatibility with the greater ecosystem.

### Minting Digital Goods
This section presents a guide on _best practices_ (rather than a _standard_) for minting some types of digital goods. It's based heavily on [this community guide][litemint]. Your digital good may or may not need certain elements of this guide, or you may need additional components on top of it. These diversions are noted where appropriate.

At a high level, your digital good is represented by an asset on the Stellar network. Owning the asset _represents_ owning the digital good. This makes your good a "first-class citizen" on the network: it immediately benefits from all of Stellar's native features for assets like [path payments](https://developers.stellar.org/docs/start/list-of-operations/#path-payment-strict-send) and the [decentralized exchange](https://developers.stellar.org/docs/glossary/decentralized-exchange/).

#### Storing your digital good
Regardless of what your digital good represents (artwork, legal contracts, friendship), you need a way to store it. Using decentralized storage such as the [InterPlanetary File System][ipfs] (IPFS) is a recommended best-practice for future-proofing your digital goods. IPFS uses [content identifiers][cid] (CIDs) to address data. These provide **data integrity** and **immutability**: if the underlying digital good changes in any way, its content identifier will also change.

#### Describing your digital good
Since your digital good can be anything, another best practice is storing metadata that describes it. Inspired by Ethereum's [EIP-721](https://eips.ethereum.org/EIPS/eip-721) standard, many digital goods in the ecosystem store JSON metadata file like the following:


```json
{
  "name": "A demonstration of digital good metadata",
  "description": "This is a description of the cool digital good used for an informational SEP demo.",
  "url": "ipfs://QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco/I/m/RickAstleyNeverGonnaGiveYouUp7InchSingleCover.jpg",
  "issuer": "GALAXYVOIDAOPZTDLHILAJQKCVVFMD4IKLXLSZV5YHO7VY74IWZILUTO",
  "code": "DEMOASSET"
}
```

There are a few key elements here: a way to describe the digital good, a reference to the good itself, and a "back-reference" to the Stellar asset that represents ownership of the good. Again, this isn't a standard but rather a set of common best practices: your metadata file (should you decide to use one) may need different fields. You could even publish a JSON schema to help clients validate the digital good's metadata structure.

#### Referencing your digital good
There is a common naming convention within the Ethereum ecosystem and other APIs to associate digital goods with their [content identifiers][cid]. You can use the [`ManageData` operation](https://developers.stellar.org/docs/start/list-of-operations/#manage-data) to store a data entry on your issuing account with `ipfshash` as the key and the IPFS [content identifier][cid] as the value to benefit from parts of the ecosystem that also follow the convention. For example, digital good marketplaces like [Litemint][litemint.io] use the naming convention and look up the CID to discover images, video, audio, full descriptions, and other properties about the digital good seamlessly.

Note that this model has some fundamental limitations: for example, the data entry can only reference the CID describing a single digital good, but you may want the account to issue many different digital goods. You may want to adopt a different model if this one doesn't fit your use case. For example, you could use a `<asset-code>.url` data entry or just rely on your [SEP-1][sep1] file's [currency description][sep1-currency]. Fundamentally, though, it's important to create relationships between your issuing accounts and the digital goods they issue.


### Representing Digital Goods
This section provides interoperability guidance around _representing_ digital goods. 

Since digital goods are represented by Stellar assets and are thus "first-class citizens" in the ecosystem, they should leverage existing interoperability layers. Setting up a [SEP-1 `stellar.toml`][sep1] file provides immediate interoperability with all services and wallets on the Stellar ecosystem. It is highly recommended that all assets you issue on Stellar, digital goods or not, follow the [SEP-1][sep1] standard to provide a valid `stellar.toml` file. This grants your digital good a degree of legitimacy, because most Stellar ecosystem services and wallets tend to discard TOML-less assets and/or flag them as spam. 

#### Using SEP-1
Many of the SEP-1 are highly relevant to digital goods. You should include as many of them as is appropriate for your use case:

  * the `code` and `issuer` fields are essential to describe the Stellar asset that represents your digital good
  * the `name` and `desc` fields provide human-readable information about your digital good
  * the `fixed_number`, `max_number`, and `is_unlimited` fields are mutually exclusive ways to describe the supply of your digital good
  * the `display_decimals` field helps render the right quantity of your digital good, since a single unit of it is likely to be represented by one stroop (i.e. "0.0000001") but you'd want to see "1"
  * the `image` field is how the ecosystem will "draw" your digital good

Note that even if your digital good isn't an image, you may still want to provide a way to represent it as an image (like a logo or symbol) to make it stand out. It's good practice to provide an optimized version of the art to allow fast-loading from services and wallets on Stellar.

Here is an example stellar.toml file describing an asset representing a unique digital image, mimicking the JSON metadata file we described [earlier](#describing-your-digital-good):

```toml
[DOCUMENTATION]
ORG_URL="<https://ink.litemint.store>"

[[CURRENCIES]]
issuer=GAKZGD5BFXZ7P7P45WHTM6DODMOEWWJUSCAIPGYIVIPYQSVR6MM6YR7M
code=DEMOASSET
name="A demonstration of digital good metadata"
desc="This is a description of the cool digital good used in this demo."
image="https://cloudflare-ipfs.com/ipfs/QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco/I/m/RickAstleyNeverGonnaGiveYouUp7InchSingleCover.jpg"
fixed_number=1
display_decimals=7
```

Once you have a `stellar.toml` file under your domain, you should also configure the issuing account's `homedomain` to point to it via the [`SetOptions` operation](https://developers.stellar.org/docs/start/list-of-operations/#set-options). This unifies the three separate components: the account issuing the digital good, the metadata describing the digital good, and the digital good itself.

#### SEP-1 Extensions
Since digital goods can represent anything, but the SEP-1 currency specification does not have a generic way to refer to an "anything." There is an `image` key, but it is generally used

Thus, this SEP adds additional supported fields to the SEP-1 currency specification to faciliate this need:

| Field Name | Description and purpose |
|------------|-------------------------|
| `url`      | A [valid URL][url] pointing to a digital good that this asset represents |
| `urlhash`  | A [SHA-256][sha2] hash of the data pointed to by `url` |

The `urlhash` is optional and provided here as a way to verify the integrity of the digital good. It's particularly useful if the digital good lives on a different server relative to the `stellar.toml` file. Some URLs (like IPFS CIDs) have integrity "batteries included" and won't need this field.


## Design Rationale
A key component of a flourishing digital goods marketplace is interoperability. That drives all of the design decisions in this SEP, especially the fact that it's an informational SEP rather than a standard. The [first section](#minting-digital-goods) is a set of best practices for a _particular_ set of needs in creating digital goods. There is no "one size fits all" way to do this. The [second section](#representing-digital-goods) adds some extremely flexible fields to SEP-1 to accomodate the fact that digital goods can be anything.

It's worth noting that the idea of "ownership" described throughout the SEP--- ownership of an asset and its relationship to owning the respective digital good---is a little diluted: neither the network nor a standard can make any claims about _legitimacy_ of the digital good itself. Owning a unit of the Stellar asset representing your digital good is a way to establish a _relationship_ between buyer and seller that is _linked_ to the digital good, nothing more.


## Security Concerns
This informational SEP does not introduce security concerns pertaining to the Stellar network itself.


## Changelog
- `v0.1.0`: Initial draft. [#1139](https://github.com/stellar/stellar-protocol/pull/1139)


[sep1]: https://stellar.org/protocol/sep-1
[sep1-currency]: https://stellar.org/protocol/sep-1#currency-documentation
[sep14]: https://stellar.org/protocol/sep-14
[litemint]: https://medium.com/stellar-community/best-practices-for-creating-nfts-on-stellar-5c91e53e9eb9
[ipfs]: https://docs.ipfs.io
[cid]: https://github.com/multiformats/cid
[url]: https://url.spec.whatwg.org/
[sha2]: https://datatracker.ietf.org/doc/html/rfc6234#section-6
