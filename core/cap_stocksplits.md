## Preamble

```
SEP: To Be Assigned
Title: Forward and Reverse Stock Splits
Author: <@blocktransfer, @JFWooten4, ...>
Track: <Standard>
Status: Draft
Created: <2021-07-29>
Discussion: <https://groups.google.com/g/stellar-dev/c/40u3UiqMXk0/m/p8-k2mhcAgAJ>
Version: 0.0.1
```

## Simple Summary
Forward and reverse asset splits of arbitrary proportions.

## Motivation

## Abstract
Stellar is a phenomenal blockchain for securities representation, and the core diction of the protocol identifies stocks and bonds as fundamental asset types. However, the protocol doesn't yet have a split operations. While non-native cryptoasset splits are meaningless or even detrimental for stablecoins, spits are a functional requirement for any stock registrars. Furthermore, scrapped-together manual implementations of stock splits require massive intermediate capital illiquidity for any asset in question, among other challenges including clogging the network and interrupting automated market-making. Thus, we proposed two new transaction operations for forward and reverse splits, both of which take in a split ratio. An issuer can execute a split on any non-native asset to update the account balances of all holders and existing unfilled orders.

# Goals Alignment
This CAP is aligned with the following Stellar Network Goals & Values:
* **The Stellar Network should enable users to easily exchange their non-Stellar based assets to Stellar-based assets, and vice versa;**
* **The Stellar Network should make it easy for developers of Stellar projects to create highly usable products;**
  * **The Stellar Protocol should be clear, concise, and opinionated;**
  * New operations and functionality should be opinionated, and straightforward to use; and
  * There should ideally be only one obvious way to accomplish a given task
alongside the implicit benefits of this CAP insofar as creating equitable access to financial markets for billions traditionally disenfranchised from securities ownership.

## Specification
Draft overview: still working to unravel how to implement.

`ForwardSplit` and `ReverseSplit` called by issuing peer:

```ForwardSplit {
  int32 splitRatio
  string assetCode
}

ReverseSplit {
  int32 splitRatio
  string assetCode
}
```
where `splitRatio` is "divided" by 7 for decimal places like account balances, allowing for granular split rations (some companies do weird stuff like 2499:2500 splits or $GE's 104:100 split in 2019).

Operations should multiply (forward) or divide (reverse) all account balances for holders of `assetCode` from the issuer, including the issuer account holdings. Operations should additionally (i) cancel all orders or (ii) similarly scale all order amounts and prices. Not sure yet which is easier to implement, but in theory just cancelling the orders should be fine since most AMMs update ~ every 10 seconds, and the split operation can execute for everyone in one block.

Forward splits have little compatibility issues so long as no split increases balances over `int64_MAX`. We propose that reverse splits round the lowest cut-off value rather than truncate it. For instance, if Alice owns `88.0000255` shares of `MegaXLMcorp` before a 10:1 reverse split (resulting in `8.80000255` shares), then her Stellar account ought resolve to `8.8000026` shares, whereas `8.80000254` shares would round down to `8.8000025` shares post-split. Again, need to look more into how to implement this. Errors may occur if forward splits increase balances over `MAX_TRUSTLINE_AMOUNT`.

## Design Rationale
We know you lose a little bit of 7th-decimal precision in reverse splits, so we can minimize changes to `total_coins` by rounding from `^.5`. The logic for the rest (`splitRatio` size, adjusting pending orders, etc.) just comes down to ease of implementation, which aren't massive undertakings since stock splits are pretty rare.

Still encouraging conversion within the community, namely in the development group above or at https://github.com/stellar/stellar-protocol/issues/1015. Specifically, some concerns may arise around reverse-splitting stablecoins or low-float assets wherein some central exchange may not be given proper notice of the split and trade at incorrect multiples. We think this risk is minimal since the true point of value connection ought come from the anchor ideally executing the actual split. More rationale in the dev. post.


## Security Concerns
Just as messing around with trustline or signer operations can seriously screw up your day, so too can misuse of forward or reverse splits. Namely, a forward split that allows for the circulation of more than the `MAX_TRUSTLINE_AMOUNT` can create capital illiquidity for large assetholders, whereas reverse splits significantly larger than 10:1 can result in tangible loss of precision. Network issuers, especially anchors, should use these operations with caution and foresight. Tests should check balances math for over-/underflow with extremely large split ratios. May be practical to check for this as well when executing splits.
