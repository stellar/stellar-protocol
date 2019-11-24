## Preamble

```
SEP: To Be Assigned
Title: Identicons for Stellar Accounts
Author: Lobstr.co
Track: Informational
Status: Draft
Created: 2019-11-20
Discussion: https://groups.google.com/forum/#!topic/stellar-dev/kAqhpCMe96c
```

## Simple Summary
This SEP defines a way to generate identicons for Stellar accounts - unique icons, based on the public key of the account.  
It's a visual representation of the Stellar address, that serves to identify the account as a form of an avatar.

As an example, here's the identicon for this Stellar account `GALAXYVOIDAOPZTDLHILAJQKCVVFMD4IKLXLSZV5YHO7VY74IWZILUTO`:

![image](https://id.lobstr.co/GALAXYVOIDAOPZTDLHILAJQKCVVFMD4IKLXLSZV5YHO7VY74IWZILUTO.png)


## Motivation
The goal is to define a standard way to generate identicons for Stellar addresses.

Having a standard algorithm and readily available tools to generate identicons would simplify the integration for the service providers. At the same time, end users would benefit from seeing the same icon for their Stellar account in different projects across the ecosystem.


## Abstract
Identicon for a Stellar account is an image generated based on a public key ("G...").

Identicons can be used in the interface of products built on Stellar to improve the user experience, because they:
- allow users to visually distinguish different addresses;
- may help to verify that the sending of funds is done to correct account;
- may help to visualize history of transactions or multisig configuration;
- may help to identify which account user is currently logged in with;

This SEP describes the algorithm used to generate the images and provides links to several reference implementations.


## Specification

The generator takes a public key ("G...") as an input.

First, the public key is converted to a sequence of bytes, in a manner identical to the `keypair.rawPublicKey()` function of JS Stellar SDK. A portion of bytes from the raw public key in the position from 2 to 16 are used for the identicon generation (`keypair.rawPublicKey().slice(2,16)`), while the remaining bytes are ignored.

The first byte of that slice is used to pick a color for the identicon.  
The byte value is used to determine hue parameter in the HSV color scheme, with the static values for saturation and value parameters.  Hence, the identicon may be colored in one of the 256 colors.

The remaining bytes are used to generate a 7x7 matrix, with a vertical symmetry, where each cell is either filled with selected color or left blank, depending on the value of individual bits in the bytes sequence.

Finally, the matrix and the color are used to generate the image for the identicon.

Please refer to the Implementations sections below for the code samples.


## Implementations

Here are the reference implementations of the identicon generator:
- Javascript library: https://github.com/Lobstrco/stellar-identicon-js
- npm package: https://www.npmjs.com/package/stellar-identicon-js
- Python library: https://github.com/Lobstrco/stellar-identicon-py

The recommendation is to use the default parameters (sizes and colors) for image generation for consistency purposes.

Another option to generate identicons is through the public web API at https://id.lobstr.co/.  
This service dynamically generates identicons, caches them and quickly serves over HTTPS.  
See it in action [here](https://id.lobstr.co/GBIDGDSVQXAHGZNOETS7ADUMWCDSQJU4R53EZRK6ONP3BA42UJL5PAHR.png) or follow [this link](https://github.com/Lobstrco/stellar-identicon-py#web-api) for more details.


## Design Rationale

Good algorithm for generating identicons should have the following properties:
- the resulting images are distinct and easy to remember;
- for 2 similar public keys the resulting images are looking differently;
- different public keys should result in a different images with a sufficiently high probability;
- given a public key it should be difficult to generate another public key with the same identicon;

Each identicon image is a square consisting of 7x7 mono colored blocks (pixels).  
Identicons have a vertical line of symmetry, which makes it's easier to memorize them.

The images are using PNG format, which is efficient for images with mono colored blocks and supported on most platforms.
The resulting images have a size of about 1KB.  

Alternative implementations of identicons in other blockchain protocols:
- https://github.com/ethereum/blockies
- https://github.com/man15h/vue-jazzicon


## Security Concerns

The total number of different identicons is `256*2^(3*7+7)=68,719,476,736`, as the whole identicon can be colored in any of the 256 colors and the structure can be defined by 3 left columns and a central column (due to vertical symmetry). Each column has 7 pixels, each pixel can be in one of 2 states: filled or empty.

However, the number of existing public keys greatly exceeds the amount of different identicons.  
So, collisions are possible - different public keys may have the same identicon.

For most practical purposes the probability of these collisions is rather low, as there are over 68 billion possible identicons.

Still, identicons should be used only as an additional tool in the application UI, to provide more context to the user and help prevent errors. A full public address should still be visible to the user and available for verification.
