## Preamble

```
CAP: 0040
Title: EcDsa secp256k1 Signed Payload Signer for Cross-Chain Transaction Signature Disclosure
Working Group:
    Owner: Leigh McCulloch <@leighmcculloch>
    Authors: Leigh McCulloch <@leighmcculloch>
    Consulted: Nicolas Barry <@MonsieurNicolas>, Jon Jove <@jonjove>, David Mazières <@stanford-scs>
Status: Draft
Created: 2021-07-30
Discussion: TBD
Protocol version: TBD
```

## Simple Summary

This proposal adds a new signer type that supports atomic operations between Stellar and other chains.

## Working Group

This protocol change was authored by Leigh McCulloch, with input from the
consulted individuals mentioned at the top of this document.

## Motivation

TODO

### Goals Alignment

This CAP is aligned with the following Stellar Network Goals:

- The Stellar Network should make it easy for developers of Stellar projects to
create highly usable products

## Specification

### XDR Changes

This patch of XDR changes is based on the XDR files in tag `v17.2.0` of
[stellar-core].

```diff mddiffcheck.base=v17.2.0
diff --git a/src/xdr/Stellar-types.x b/src/xdr/Stellar-types.x
index 8f7d5c20..88eea583 100644
--- a/src/xdr/Stellar-types.x
+++ b/src/xdr/Stellar-types.x
@@ -19,6 +19,7 @@ enum CryptoKeyType
     KEY_TYPE_ED25519 = 0,
     KEY_TYPE_PRE_AUTH_TX = 1,
     KEY_TYPE_HASH_X = 2,
+    KEY_TYPE_ECDSASECP256K1_SIGNED_PAYLOAD = 3,
     // MUXED enum values for supported type are derived from the enum values
     // above by ORing them with 0x100
     KEY_TYPE_MUXED_ED25519 = 0x100
@@ -33,7 +34,8 @@ enum SignerKeyType
 {
     SIGNER_KEY_TYPE_ED25519 = KEY_TYPE_ED25519,
     SIGNER_KEY_TYPE_PRE_AUTH_TX = KEY_TYPE_PRE_AUTH_TX,
-    SIGNER_KEY_TYPE_HASH_X = KEY_TYPE_HASH_X
+    SIGNER_KEY_TYPE_HASH_X = KEY_TYPE_HASH_X,
+    SIGNER_KEY_TYPE_ECDSASECP256K1_SIGNED_PAYLOAD = KEY_TYPE_ECDSASECP256K1_SIGNED_PAYLOAD
 };
 
 union PublicKey switch (PublicKeyType type)
@@ -52,6 +54,13 @@ case SIGNER_KEY_TYPE_PRE_AUTH_TX:
 case SIGNER_KEY_TYPE_HASH_X:
     /* Hash of random 256 bit preimage X */
     uint256 hashX;
+case SIGNER_KEY_TYPE_ECDSASECP256K1_SIGNED_PAYLOAD:
+    struct {
+        /* Public key that must sign the payload. */
+        uint256 publicKey;
+        /* Payload to be raw signed by publicKey. */
+        opaque payload<32>;
+    } ecdsasecp256k1SignedPayload;
 };
 
 // variable size as the size depends on the signature scheme used
```

### Semantics

This proposal introduces one new type of signer, the ecdsa secp256k1 signed
payload signer, that is defined as a variable length opaque payload with a
maximum size of 32 bytes and an ecdsa public key. A signature for the signer is
the result of signing the payload with the private key that the public key is
derived using the secp256k1 curve.

The ecdsa secp256k1 signed payload signer is usable everywhere existing signers
may be used.

#### Signature

The signature of a ecdsa secp256k1 signed payload signer is the raw ecdsa
signature of the signer's payload using the private key that derives the
signer's ecdsa public key using the secp256k1 curve.

Unlike other signatures in the Stellar protocol, the payload is not combined
with the network ID or hashed before passing it to the signing algorithm.

#### Signature Hint

The signature hint of an ecdsa secp256k1 signed payload signer is the XOR of the
last 4 bytes of the payload and the last 4 bytes of the ecdsa public key.

#### Transaction Envelopes

This proposal makes no structural changes to transaction envelopes other than
the signature of an ed25519 signed payload signer may be included in the list of
decorated signatures.

#### Signature Checking

Signature checking is changed to include verifying that any ecdsa secp256k1
signed payload signer's have matching signatures.

Ecdsa secp256k1 signed payload signer signatures are verified by performing
ecdsa signature verification using the signature secp256k1, the payload from the
signer, and the ecdsa public key from the signer.

## Design Rationale

This proposal provides a primitive that makes it possible to construct
transactions that reveal signatures that authorize transaction on other chains.

The ecdsa secp256k1 signature scheme is frequently used by other chains.

### Cross-Chain Atomic Operations

The ecdsa secp256k1 signed payload signer can be used to make operations on
Stellar and another chain atomic. This is limited to other chains that utilize
the ed25519 signature scheme and whose operations are authorized by signing a
maximum of 32- bytes.

An ecdsa signer can be added as a signer to a Stellar account also with a weight
lower than any threshold, but high enough such that signatures by both will
authorize the transaction. An ecdsa secp256k1 signed payload signer can be
constructed using a ecdsa public key that can authorize a operation on the other
chain, and using a payload that if signed would authorize an operation on that
other chain. The signer is added to a Stellar account with a weight lower than
any threshold but high enough such that together with the ecdsa signer the
Stellar transaction will be authorized. The operator the Stellar account signs
the transaction with the ecdsa public key and shares the transaction with the
party utilizing the other chain. The party of the other chain may authorize the
Stellar transaction using the signature that authorizes the operation on the
other chain. When the party submits the authorized Stellar transaction the
signature for the operation on the other chain is revealed providing some
guarantee to the operator of the Stellar account that the operation on the other
chain will be authorized.

This process can be applied to cross-chain swaps and other cross-chain atomic
operations.

This works without [CAP-21] by storing the signer on ledger as a signer of the
Stellar account, but CAP-21's `extraSigners` make the atomic operation more
efficient since the ecdsa secp256k1 signed payload signer can be defined without
interacting with the network.

This signer is limited to signing operations on other chains that use the ecdsa
secp256k1 signature scheme, and to signing payloads that are a maximum of
32-bytes.

### Other Uses

This new signer is likely to have other applications in scenarios similar to
where HASH_X signers are currently used, except that the data revealed would not
only be a hash shared by multiple transactions across multiple chains, but could
be a signature for a transaction on another chain, or a siganture for any other
use. However, this has limited use to only signatures of ecdsa keys as
specified.

## Protocol Upgrade Transition

### Backwards Incompatibilities

This proposal is backwards compatible.

### Resource Utilization

No substantial changes to resource utilization.

The size of signatures, and therefore transactions, remain the same.

The effort to verify the signature is similar than the effort to verify an
ed25519 signature.

The size of signers stored in the ledger would be twice the size, at 64 bytes,
for ecdsa secp256k1 signed payload signers compared to 32 bytes for all other signers.

## Test Cases

None yet.

## Security Concerns

None known.

## Implementation

None yet.

[CAP-21]: ./cap-0021.md
