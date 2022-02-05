## Preamble

```
CAP: xxxx
Title: ECDSA Signers with P-256 and secp256k1 Curves
Working Group:
    Owner: Leigh McCulloch <@leighmcculloch>
    Authors: Leigh McCulloch <@leighmcculloch>
    Consulted: TBD
Status: Draft
Created: 2022-02-04
Discussion: TBD
Protocol version: TBD
```

## Simple Summary

This proposal adds ECDSA keys as additional signers to accounts, supporting the
NIST P-256 curve and the secp256k1 curve.

## Working Group

TBD

## Motivation

This proposal has two motivatons:
1. The common requirement in financial institutions to use security modules that
are FIPS approved.
2. The inability that Stellar account holders have today to use cloud hosted
HSMs (Hardware Security Modules) to store account keys.

Financial institutions typically require the cryptographic algorithms and
modules they use to appear in approved lists of the latest relevant FIPS
standard, at this time FIPS 140-3 and FIPS 140-2 and their relevant annexes and
related standards. The US and Canadian governments require FIPS for systems they
run, operate, or buy. This makes FIPS relevant to corporations that work with
governments.

Cloud hosted HSMs have made HSMs accessible and they have become popular for
generating and storing keys securely. Cloud HSMs typically support a small
subset of FIPS approved algorithm implementations along with ECDSA secp256k1
which isn’t FIPS approved, but popular due to Bitcoin’s and Ethereum's use and
broad use in other blockchains.

Stellar supports a single assymetric key type and signing algorithm for
controlling accounts, ed255519. Ed25519 is not included in approved lists of
FIPS 140-2, and there are no known HSMs supporting ed25519 certified as FIPS
compliant. While ed25519 is mentioned in drafts of FIPS 186-5 there is no
evidence that FIPS approved security modules will arise in the immediate future.
Ed25519 is not supported by any cloud hosted HSMs today.

There may be other benefits to supporting secp256k1 signing keys for
compatibility with some other blockchains in certain cross-chain protocols, but
that motivation is not driving this proposal.

### Goals Alignment

The Stellar network aims to integrate with existing financial systems and
support the use of off-the-shelf security products.

## Abstract

The proposal adds ECDSA keys as an option to use as signers of accounts. The
proposal adds includes support for the NIST P-256 curve and the secp256k1 curve.

This proposal makes it possible for a Stellar account holder to store their
account key in FIPS certified modules, or in cloud hosted HSMs.

Nothing in this proposal makes Stellar, or the reference implementation of a
Stellar validator, stellar-core, FIPS certified. Nothing in this proposal
requires a Stellar validator, or the reference implementation stellar-core, to
utilize a HSM.

## Specification

### XDR Changes

This patch of XDR changes is based on the XDR files in commit (`394b9413180969e2035e19742194d9c04c5bf5d9`) of stellar-core.
```diff mddiffcheck.base=394b9413180969e2035e19742194d9c04c5bf5d9
diff --git a/src/xdr/Stellar-types.x b/src/xdr/Stellar-types.x
index 8f7d5c20..740aa15c 100644
--- a/src/xdr/Stellar-types.x
+++ b/src/xdr/Stellar-types.x
@@ -19,6 +19,9 @@ enum CryptoKeyType
     KEY_TYPE_ED25519 = 0,
     KEY_TYPE_PRE_AUTH_TX = 1,
     KEY_TYPE_HASH_X = 2,
+    KEY_TYPE_ECDSA_P256 = 3,
+    KEY_TYPE_ECDSA_SECP256K1 = 4,
+
     // MUXED enum values for supported type are derived from the enum values
     // above by ORing them with 0x100
     KEY_TYPE_MUXED_ED25519 = 0x100
@@ -33,7 +36,9 @@ enum SignerKeyType
 {
     SIGNER_KEY_TYPE_ED25519 = KEY_TYPE_ED25519,
     SIGNER_KEY_TYPE_PRE_AUTH_TX = KEY_TYPE_PRE_AUTH_TX,
-    SIGNER_KEY_TYPE_HASH_X = KEY_TYPE_HASH_X
+    SIGNER_KEY_TYPE_HASH_X = KEY_TYPE_HASH_X,
+    SIGNER_KEY_TYPE_ECDSA_P256 = KEY_TYPE_ECDSA_P256,
+    SIGNER_KEY_TYPE_ECDSA_SECP256K1 = KEY_TYPE_ECDSA_SECP256K1
 };
 
 union PublicKey switch (PublicKeyType type)
@@ -52,6 +57,16 @@ case SIGNER_KEY_TYPE_PRE_AUTH_TX:
 case SIGNER_KEY_TYPE_HASH_X:
     /* Hash of random 256 bit preimage X */
     uint256 hashX;
+case SIGNER_KEY_TYPE_ECDSA_P256:
+    struct {
+        uint256 x;
+        uint256 y;
+    } ecdsaP256;
+case SIGNER_KEY_TYPE_ECDSA_SECP256K1:
+    struct {
+        uint256 x;
+        uint256 y;
+    } ecdsaSecp256k1;
 };
 
 // variable size as the size depends on the signature scheme used

```

### Semantics

#### SignerKey

SignerKey is modified to include arms for ECDSA P-256 and secp2561k1 public
keys. The X and Y points are stored in transactions and in the ledger
uncompressed which requires 64 bytes of space for both key types.

#### PublicKey

PublicKey is not modified because the proposal does not change the keys intended
for use in identification on the network. Specifically the keys available for
identifying accounts and nodes on the network are unchanged and will continue to
be limited to ed25519.

## Design Rationale

The proposal is intentionally surgical, introducing the new signers into only
the parts of the protocol that are required to enable signing keys.

The proposal does not add support for the new key types as account identifiers,
because that would be unnecessary. Any Stellar account holder who wishes to
control a Stellar account with a new key type can do so by changing the signers.
Also, a change to account identifiers would have a substantially larger
downstream impact on Horizon, SDKs, wallets, and other ecosystem applications.

The proposal does not add support for the new key types as node identifiers,
because that would be unnecessary for the motivation of the proposal. If a need
is identified for node operators to use HSMs for node keys that would be a
separate proposal.

Uncompressed form is used for the ECDSA public keys requiring 64 bytes of
storage for each key. Compressed form is not used, which requires only 33 bytes
per key, because decompressing the key requires solving y^2 = x^3 - 3x + b and
finding the square-root of a value. This is a trade-off between ledger storage
space and the CPU time a validator must expend to verify a signature. It would
not be ideal for validators, as part of verifying signatures, to need to
decompress the key each time. If it is practical to cache decompress keys in
memory, or the CPU time of decompression is not meaningful, this rationale
should be revisited. The choice to use uncompressed form in the XDR does not
limit whether the strkey definition uses compressed form, and so the use of
uncompressed form in the protocol does not impact the UX.

## Protocol Upgrade Transition

As soon as this CAP becomes active, Stellar accounts may have the new signer
types. Any application, such as Horizon, that performs analysis on the signers
of accounts may encounter the new types. Any application that performs analysis
on transactions signed by the new types, or transactions that use a SetOptionsOp
with the new types, may encounter the new types.

### Backwards Incompatibilities

This proposal is backwards compatible.

### Resource Utilization

This proposal will require Stellar validators to verify ECDSA signatures.

This proposal may introduce some change in performance characteristics due to
the CPU utilization differences between the ECDSA and EdDSA (ed25519)
algorithms. Ed25519 has assembly optimized implementations in multiple langauges
and is typically considered to be faster than ECDSA. These differences are
difficult to comment on generally as it depends on CPU architecture and the
implementation in use.

The reference implementation of the Stellar protocol, stellar-core, uses
libsodium. Libsodium uses optimized vector instructions and 128-bit arithmetic
and is considered to be an optimal implementation for ed25519 on amd64/x86.

Simiarily optimized versions of ECDSA in OpenSSL may be able to verify only 0.5x
the signatures as libsodium.

Related material:
- https://monocypher.org/speed
- https://essay.utwente.nl/75354/1/DNSSEC%20curves.pdf

## Security Concerns

TBD

## Test Cases

TBD

## Implementation

TBD
