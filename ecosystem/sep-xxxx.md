## Preamble

```
SEP: To Be Assigned
Title: On-Chain Storage of Non-Fungible Assets
Author: George Kudrayvtsev (@Shaptic)
Track: Standard
Status: Draft
Created: 2021-11-22
Discussion: TODO
```


## Simple Summary
This SEP describes a specific way to store arbitrary data on-chain with the goal of standardizing the way NFTs are represented in the Stellar ledger.


## Dependencies
While not an explicit dependency, there may be a future CAP that modifies the protocol to allow a 128-byte row of ManageData to be arbitrarily divided into the string "key" and binary "data" portions, as opposed to the current model of having strict 64-byte halves.

With that CAP, the data model introduced [below](#specification) could/should change to be friendlier and more optimized.


## Motivation
With NFT marketplaces on the rise in the Stellar network (e.g. [Litemint](https://litemint.com/) and [Stellar Quest](https://quest.stellar.org/)), it's important to establish standards to ensure cross-compatibility of NFTs. Certain platforms may choose to store their asset--whether that be an image as we often see today or any arbitrary digital trinket--on the Stellar ledger itself rather than delegating to an off-chain storage mechanism such as [IPFS](https://ipfs.io/).

A standard storage mechanism will help these marketplaces and wallets render or otherwise represent the NFT within their applications, enhancing their transferability.


## Abstract
We present an efficient encoding mechanism to store arbitrary binary data on the Stellar ledger via the `ManageData` operation. It will concatenate a MIME-type alongside the aforementioned encoded-text as keys and raw binary data as values.


## Specification
First, we will discuss a common NFT issuance model and its ownership implications. This is not a required model, but sets the stage for why a standardized encoding of digital assets is necessary.

### NFT Issuance
Given an arbitrary digital asset, here's how issuance typically works:

  1. An account is created to represent the digital asset on the ledger
  2. The account stores the entire digital asset within its managed data entries.
  3. The account issues a Stellar asset representing ownership over the digital asset we just stored.
  4. Any account holding that Stellar asset lays claim to the digital asset.

Notice that ownership of the token directly conveys ownership of a unit of the asset, entirely within the Stellar ledger. Other scenarios such as locking down the issuing account to avoid supply increases, ownership transfers via payments, etc. are built on top of this basic model and are thus extraneous to this SEP.

Our focus is Step 2: storing the asset within the account.

### Encoding Binary Data
We begin by describing how binary data should be represented in a `ManageData` entry.

Since the _key_ is restricted specifically to printable characters (ref: Stellar Core's [`isString32Valid()`](https://github.com/stellar/stellar-core/blob/b031954458df3bb31d8d98f136c6fee40523a10d/src/util/types.cpp#L89-L101) and C's [`isprint()`](https://en.cppreference.com/w/cpp/string/byte/isprint)), this gives us an encoding space of 94 characters or ~6.5 bits per character (a ~25% reduction in the space). From some cursory research, the [BasE91] encoding scheme closest to this theoretical limit and outperforms base64 encoding.

The _value_ can be any binary data; thus, no encoding is necessary.

### Representing the Data
With the encoding described [above](#encoding-binary-data), we can now discuss the actual storage. Again, we'll use the `ManageData` operation to store the binary data. 

The first entry _may_ be a [MIME type], followed by the first chunk of data, separated by a dash character (`-`). The MIME type *must* fit in a single key, and so must be <= 63 characters long.

If the MIME type is excluded, the dash _must_ still be included so that readers can easily distinguish where the type starts and the data begins.

Every subsequent entry is simply the next BasE91-encoded chunk, sized to fit into the 64-length key string, and the next 64-byte binary chunk.

For example,

| Key | Value |
|:----|:-----:|
| text/plain-'ZP^gp@... | .. 64 bytes .. |
| Io1Tc%ZEYkE#^IR`0e... | .. 64 bytes .. |
| %yO){B&mA#_1:W8{lT... | .. 64 bytes .. |
| Cvnu8jZBP>1]TX2$g%B'  | <empty> |

would be a valid entry. There's no need for padding.

#### Implementation Note
Because you cannot predict the length of your encoded string without doing the encoding itself, it will be necessary to use trial-and-error to find the longest binary chunk that fits in <= 64 bytes. While this does mildly impact encoding time, it ensures optimality on-chain.

(This is the function of `_encode_nearest()` in the sample implementation, [below](#implementation).)

### Pricing Implications
Every additional `ManageData` entry encurs an increase in the base reserve required by an account by 0.5 XLM. Some napkin-math pricing tables ensue:

| Data Size | ManageData Entries | Cost (XLM) |
|----------:|--------------------|------------|
|  10 B     | 1                  | 0.5        |
|   1 KB    | 9                  | 4.5        |
|  50 KB    | 418                | 209        |
| 112 KB    | 937                | 468.5      |
|   1 MB    | 8358               | 4179       |

Based on an approximation formula to account for encoding expanding the binary size by 10-15%:

    ceil(|data| / ((64 / 1.15) + 64))

Note that accounts are limited to 1000 sub-entries (so just over 100 KiB), so larger assets would need to either be split across multiple accounts or stored off-chain.

### Example Implementation
The following is an example Python implementation of this SEP.

```python
#! /usr/bin/env python3
import math
import base91

from typing import List, Tuple


def encode(mime_type: str, data: bytes) -> List[Tuple[str, bytes]]:
    rows = []
    mime_type += '-' # add separator

    # Prepend the mime type to the first entry
    key, data = _encode_nearest(data, 64 - len(mime_type))
    value, data = data[:64], data[64:]
    rows.append((mime_type + key, value))

    while data:
        key, data = _encode_nearest(data, 64)
        value, data = data[:64], data[64:]
        rows.append((key, value))

    return rows

def decode(rows):
    key1, value1 = rows[0]
    i = key1.rfind('-')     # search from the tail since MIME might contain dash
    mime_type, etc = key1[:i], key1[i+1:]

    binary = base91.decode(etc) + value1
    for key, value in rows[1:]:
        binary += base91.decode(key) + value

    return mime_type, binary

def _encode_nearest(data: bytes, n: int=64) -> Tuple[str, bytes]:
    """ BasE91-encodes `data` as close to (but not exceeding) `n` as possible.
    """
    # We know that BasE91 will never do better than 10% overhead, so that's a
    # reasonable starting point for trying to get exactly an n-sized chunk
    # encoded.
    for i in range(int(math.ceil(n / 1.10)), 0, -1):
        encoded = base91.encode(data[:i])
        if len(encoded) <= n:
            return encoded, data[i:]

    raise ValueError("can't encode %d-byte data into %d-len string" % (data, n))


import random
asset = random.randbytes(int(100e4))
rows = encode("application/octet-stream", asset)
mime, binary = decode(rows)
assert asset == binary
assert mime == "application/octet-stream"
```


## Design Rationale
Due to the ever-evolving nature of the crypto space, we should not restrict ourselves to the specific use cases of NFTs we have today. Therefore, instead of catering directly towards a particular image format, we provide a specification for storing _arbitrary_ data.

There are obviously many ways to encode arbitrary data in a text stream. However, due to the high cost of storing data on chain, every byte counts, so we aim to have an efficient design.

Keeping in mind the restrictions on `ManageData`--specifically, that the key *must* be a valid string (that is, made of printable characters), while the value *can* be any bytes--we need the most efficient encoder of binary to text data we can find. In a similar vein, we _could_ encode the binary values of each `ManageData` row to have consistency across keys and values, but this would be unnecessarily sacrificing a non-trivial efficiency.

While BasE91 is a little more esoteric than the near-universal base64, libraries exist in many languages and the efficient gain is significant enough to be worth the additional implementation overhead. The implementation itself is also very straightforward (for example, [here](https://github.com/aberaud/base91-python/blob/master/base91.py) is a one-page Python implementation).

A comparison with alternative encoding methods follows below. It was done by using the same encoding scheme (that is, encode the key and store the value as-is) and on random data. Random data accurately reflects most _compressed_ data, and (lossless) compression should always be used to ensure no extra rows are needed on chain.

  * `base64`: +5% more entries, on average
  * `uuencode`: +20%
  * `hex`: +24%

If we also encode the value with BasE91 (for consistency across keys and values), we need +13% more entries.


## Security Concerns
The BasE91 encoding does not have the web (or JSON) in mind. Any rendering of the actual entries will need to take care to do proper escaping.


[BasE91]: http://base91.sourceforge.net/
[MIME type]: https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types
