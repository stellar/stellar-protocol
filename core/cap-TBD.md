## Preamble

```
CAP: TBD
Title: Host functions for ML-DSA signature verification
Working Group:
    Owner: Jay Geng <@jayz22>
    Authors: Jay Geng <@jayz22>
    Consulted: Nicolas Barry <@MonsieurNicolas>, Rocky (Soundness Labs) <@gnosed>
Status: Draft
Created: 2026-06-05
Discussion: https://github.com/orgs/stellar/discussions/1915
Protocol version: 29
```

## Simple Summary

This CAP proposes three host functions for verifying ML-DSA signatures
(FIPS 204, the NIST-standardized module-lattice digital signature algorithm),
one per standardized parameter set: ML-DSA-44, ML-DSA-65 and ML-DSA-87.

## Working Group

As described in the preamble section.

## Motivation

All signature schemes currently supported by Soroban host functions — Ed25519
(`verify_sig_ed25519`), ECDSA secp256k1 (`recover_key_ecdsa_secp256k1`) and
ECDSA secp256r1 (`verify_sig_ecdsa_secp256r1`) — rely on the hardness of the
elliptic curve discrete logarithm problem, an assumption that does not hold
against a sufficiently capable quantum computer.

ML-DSA (Module-Lattice-Based Digital Signature Algorithm,
[FIPS 204]) is one of the two post-quantum signature standards finalized by NIST, and its adoption is underway across the
signing ecosystem:

- NSA's CNSA 2.0 suite includes ML-DSA, with the recommended adoption window
  for software- and firmware-signing running from 2025 to exclusive use by
  2030 ([CNSA 2.0]);
- X.509/PKI algorithm identifiers are standardized ([RFC 9881]);
- general-purpose cryptographic libraries support it ([OpenSSL 3.5]);
- language runtimes ship it (JDK 24, [JEP 497]); and
- cloud key-management services offer it ([AWS KMS ML-DSA]).

Supporting ML-DSA verification as host functions allows Soroban custom
accounts (see [CAP-0046-03] and the custom account interface) to authenticate
with post-quantum signatures, and allows contracts to verify ML-DSA-signed
attestations produced by external systems. As with secp256r1 ([CAP-0051]),
performing the verification on the guest side is not practical: ML-DSA
verification involves expanding a large matrix from a seed via SHAKE-128,
number-theoretic transforms, and matrix-vector products over a 23-bit prime
field — the instruction cost of a guest-side implementation exceeds
reasonable network limits, and a host implementation is both significantly
cheaper and easier to get right once.

This proposal deliberately covers contract-level signature verification only.
It does not change the transaction signature scheme of the Stellar network,
which remains Ed25519; network-level post-quantum migration is a separate,
larger effort.

### Goals Alignment

This CAP is aligned with the following Stellar Network Goals:

- The Stellar Network should make it easy for developers of Stellar projects
  to create highly usable products
- The Stellar Network should facilitate simplicity and interoperability with
  other protocols and networks

## Abstract

This CAP adds three host functions to the Soroban environment's exported
interface, `verify_sig_ml_dsa_44`, `verify_sig_ml_dsa_65` and
`verify_sig_ml_dsa_87`, implementing the FIPS 204 external verification
interface `ML-DSA.Verify` for the three standardized parameter sets. Each
function accepts an encoded verifying (public) key, a message, an encoded
signature, and a context string (0–255 bytes), and traps if the signature is
malformed or verification fails. Verification is deterministic and requires
no randomness. Six new `ContractCostType` metering entries are introduced —
a constant-cost verifying-key decoding type and a message-length-linear
verification type per parameter set.

## Specification

### New host functions

Three new functions with export names `A`, `B` and `C` in the crypto module
(`c`) are added to the Soroban environment's exported interface.

```json
{
    "export": "A",
    "name": "verify_sig_ml_dsa_44",
    "args": [
        { "name": "public_key", "type": "BytesObject" },
        { "name": "msg", "type": "BytesObject" },
        { "name": "signature", "type": "BytesObject" },
        { "name": "context", "type": "BytesObject" }
    ],
    "return": "Void",
    "docs": "Verifies an ML-DSA-44 (FIPS 204) signature using the external interface ML-DSA.Verify. `public_key` must be a 1312-byte encoded verifying key, `signature` a 2420-byte encoded signature, and `context` a domain-separation string of 0-255 bytes (pass empty bytes if unused). Traps with Object/UnexpectedSize if any input length is wrong, or with Crypto/InvalidInput if the signature is malformed or verification fails.",
    "min_supported_protocol": 29
},
{
    "export": "B",
    "name": "verify_sig_ml_dsa_65",
    "args": [
        { "name": "public_key", "type": "BytesObject" },
        { "name": "msg", "type": "BytesObject" },
        { "name": "signature", "type": "BytesObject" },
        { "name": "context", "type": "BytesObject" }
    ],
    "return": "Void",
    "docs": "Verifies an ML-DSA-65 (FIPS 204) signature using the external interface ML-DSA.Verify. `public_key` must be a 1952-byte encoded verifying key, `signature` a 3309-byte encoded signature, and `context` a domain-separation string of 0-255 bytes (pass empty bytes if unused). Traps with Object/UnexpectedSize if any input length is wrong, or with Crypto/InvalidInput if the signature is malformed or verification fails.",
    "min_supported_protocol": 29
},
{
    "export": "C",
    "name": "verify_sig_ml_dsa_87",
    "args": [
        { "name": "public_key", "type": "BytesObject" },
        { "name": "msg", "type": "BytesObject" },
        { "name": "signature", "type": "BytesObject" },
        { "name": "context", "type": "BytesObject" }
    ],
    "return": "Void",
    "docs": "Verifies an ML-DSA-87 (FIPS 204) signature using the external interface ML-DSA.Verify. `public_key` must be a 2592-byte encoded verifying key, `signature` a 4627-byte encoded signature, and `context` a domain-separation string of 0-255 bytes (pass empty bytes if unused). Traps with Object/UnexpectedSize if any input length is wrong, or with Crypto/InvalidInput if the signature is malformed or verification fails.",
    "min_supported_protocol": 29
}
```

The `min_supported_protocol` value is 29, the protocol version this CAP is
released in.

### XDR changes

```diff mddiffcheck.ignore=true
diff --git a/Stellar-contract-config-setting.x b/Stellar-contract-config-setting.x
--- a/Stellar-contract-config-setting.x
+++ b/Stellar-contract-config-setting.x
@@ -293,7 +293,19 @@ enum ContractCostType {
      // Cost of performing BN254 G1 multi-scalar multiplication (MSM)
-    Bn254G1Msm = 85
+    Bn254G1Msm = 85,
+    // Cost of decoding and expanding an ML-DSA-44 verifying key
+    MlDsa44DecodeVerifyingKey = 86,
+    // Cost of decoding and expanding an ML-DSA-65 verifying key
+    MlDsa65DecodeVerifyingKey = 87,
+    // Cost of decoding and expanding an ML-DSA-87 verifying key
+    MlDsa87DecodeVerifyingKey = 88,
+    // Cost of verifying an ML-DSA-44 signature, linear in message length
+    VerifyMlDsa44Sig = 89,
+    // Cost of verifying an ML-DSA-65 signature, linear in message length
+    VerifyMlDsa65Sig = 90,
+    // Cost of verifying an ML-DSA-87 signature, linear in message length
+    VerifyMlDsa87Sig = 91
 };
```

### Semantics

#### ML-DSA parameter sets

ML-DSA is defined in [FIPS 204] over the polynomial ring
`Z_q[X]/(X^256 + 1)` with `q = 8380417`. The three standardized parameter
sets differ in matrix dimensions (k, l) and rejection bounds, trading size
and cost for security margin:

| Parameter set | NIST security category | Matrix (k × l) | Verifying key (bytes) | Signature (bytes) |
| ------------- | ---------------------- | -------------- | --------------------- | ----------------- |
| ML-DSA-44     | 2                      | 4 × 4          | 1312                  | 2420              |
| ML-DSA-65     | 3                      | 6 × 5          | 1952                  | 3309              |
| ML-DSA-87     | 5                      | 8 × 7          | 2592                  | 4627              |

#### Encodings

All encodings are exactly as specified in FIPS 204.

- **Verifying key** (`pkEncode`, FIPS 204 Algorithm 22): the 32-byte seed
  `rho` followed by the bit-packed high-order part `t1` of the public
  vector. The total length (1312/1952/2592 bytes) uniquely identifies the
  parameter set.
- **Signature** (`sigEncode`, FIPS 204 Algorithm 26): the commitment hash
  `c_tilde` (32/48/64 bytes), the bit-packed response vector `z`, and the
  packed hint vector `h`. Total length 2420/3309/4627 bytes.
- **Context**: an application-chosen domain-separation byte string of length
  0 to 255, as defined by the FIPS 204 external interface. An empty context
  is valid and is the default for signers that do not use one.
- **Message**: an arbitrary byte string. The full message must be provided;
  see the design rationale for why a pre-hashed interface is not offered.

#### Verification semantics

Each function implements `ML-DSA.Verify(pk, M, sigma, ctx)` (FIPS 204
Algorithm 3), the *external* interface of the *pure* (non-pre-hashed)
variant. Specifically the host:

1. Decodes `public_key` into `(rho, t1)` and expands the matrix `A_hat` from
   `rho` via SHAKE-128 (`ExpandA`), precomputing the NTT-domain form.
2. Decodes `signature` into `(c_tilde, z, h)`, rejecting structurally
   invalid encodings: a malformed hint encoding (non-monotonic indices or
   counts, FIPS 204 Algorithm 21 returning ⊥) or a response vector with
   `||z||_inf >= gamma_1 - beta`.
3. Computes the message representative
   `mu = H(H(pk) || 0x00 || len(ctx) || ctx || M)` using SHAKE-256.
4. Recomputes the commitment `w1' = UseHint(h, A_hat * NTT(z) - NTT(c) *
   t1_hat * 2^d)` where `c = SampleInBall(c_tilde)`, and accepts if and only
   if `c_tilde == H(mu || w1Encode(w1'))`.

The function returns `Void` on success and traps otherwise.

#### New host functions introduced

The three functions are identical in semantics and differ only in parameter
set (and therefore input lengths and cost types charged). The specification
below applies to all three.

##### `verify_sig_ml_dsa_44` / `verify_sig_ml_dsa_65` / `verify_sig_ml_dsa_87`

**Description**: verify an ML-DSA signature over a message and context
string for a given verifying key, per the FIPS 204 external interface of the
pure variant.

**Cost**: covers decoding and expanding the verifying key
(`MlDsa{44,65,87}DecodeVerifyingKey`), and decoding the signature plus
performing the verification (`VerifyMlDsa{44,65,87}Sig`, linear in the
message length). Input byte copies are covered by the existing `MemCpy` cost
type.

**Error condition**: the function traps if any of the following hold.

- `public_key` length is not exactly 1312/1952/2592 bytes (per variant).
- `signature` length is not exactly 2420/3309/4627 bytes (per variant).
- `context` is longer than 255 bytes.
- The signature is structurally malformed: the hint vector encoding is
  invalid, or the response vector `z` is out of range
  (`||z||_inf >= gamma_1 - beta`).
- Signature verification fails (the recomputed commitment hash does not
  match `c_tilde`).

Length errors — a wrong `public_key` or `signature` length, or a `context`
longer than 255 bytes — are reported as `Object`/`UnexpectedSize`; the
remaining conditions (a structurally malformed signature and a failed
verification) are reported as `Crypto`/`InvalidInput`. As with the existing
signature verification host functions, a failed verification traps rather
than returning a boolean (see [Design Rationale](#design-rationale)).

#### New metering `CostType`s introduced

- `MlDsa44DecodeVerifyingKey` - Cost of decoding an ML-DSA-44 verifying key:
  unpacking `(rho, t1)`, expanding the matrix `A_hat` from `rho` via
  SHAKE-128, and precomputing the NTT-domain values used by verification.
  Type: constant.
- `MlDsa65DecodeVerifyingKey` - Same as above for ML-DSA-65. Type: constant.
- `MlDsa87DecodeVerifyingKey` - Same as above for ML-DSA-87. Type: constant.
- `VerifyMlDsa44Sig` - Cost of decoding an ML-DSA-44 signature and verifying
  it: hint and response-vector unpacking and validation, `SampleInBall`,
  NTTs and matrix-vector products, hint application, and the SHAKE-256
  computation of the message representative `mu`. Type: linear w.r.t. the
  message byte length (the SHAKE-256 absorption of the message is the only
  input-dependent component; everything else is fixed by the parameter set).
- `VerifyMlDsa65Sig` - Same as above for ML-DSA-65. Type: linear w.r.t. the
  message byte length.
- `VerifyMlDsa87Sig` - Same as above for ML-DSA-87. Type: linear w.r.t. the
  message byte length.

Each parameter set receives its own pair of cost types because the fixed
work scales with the matrix dimensions `k × l` (16, 30 and 56 polynomial
products respectively), rather than a single dimension. Final calibration 
parameters are TBD; see [Resource Utilization](#resource-utilization).

## Design Rationale

### Why ML-DSA

Among the NIST-standardized post-quantum signature schemes, ML-DSA
([FIPS 204]) is the one NIST's announcement describes as "intended as the
primary standard for protecting digital signatures" ([NIST 2024]).
SLH-DSA ([FIPS 205]) offers more conservative (hash-based) security
assumptions but with signatures of 8–50 KB and substantially higher
verification cost; it could be added
later by the same pattern if demand arises. FN-DSA (Falcon) is not yet
published as a final standard. ML-DSA additionally has the broadest
ecosystem adoption trajectory among the standardized schemes (see
[Motivation](#motivation)).

All three standardized parameter sets are exposed, rather than only one,
because the choice of security category belongs to the application: external
attestation sources may fix any of the three, and wallet vendors target
different security levels. The three functions share a single generic
implementation in the host, so the marginal cost of exposing all three is
limited to interface and calibration surface.

### High-level verification functions vs. lower-level lattice primitives

An alternative considered was to expose lower-level building blocks —
polynomial/NTT arithmetic over the ML-DSA ring, SHAKE-based expansion and
sampling, hint operations — in the style of the BLS12-381 host functions
([CAP-0059]), letting contracts compose ML-DSA and other lattice schemes
themselves. This was rejected for the following reasons:

- **No composability demand.** Unlike the BLS12-381 functions, from which
  many distinct protocols are built, ML-DSA verification is a single fixed algorithm; 
  there has not been strong requirement signals for its internals from established protocols.
- **The shared layer is too thin.** In practice the generic module-lattice
  algebra (polynomial vectors/matrices and their arithmetic) is a small
  fraction of the scheme. The NTT (with scheme-specific moduli and twiddle
  tables — ML-KEM uses `q = 3329` while ML-DSA uses `q = 8380417`), the
  samplers (`ExpandA`, `SampleInBall`), hint operations, coefficient
  decomposition, and the various range bit-packings are all scheme-specific.
  Covering ML-DSA verification alone would require on the order of 10–15
  host functions across two prime fields.
- **Boundary data movement.** Composing a verification from primitives
  would move intermediate polynomial state (roughly 30–50 KB per
  verification) across the wasm boundary repeatedly; a one-call interface
  keeps all intermediate state in the host which is more clean and efficient.
- **Metering surface.** Every exposed primitive becomes an individually calibrated operation maintained indefinitely. A single verification function per parameter set minimizes
  this surface.

### One function per parameter set vs. a selector parameter

A single `verify_sig_ml_dsa` function taking a parameter-set selector was
considered. Separate functions were chosen because:

- ML-DSA has exactly three standardized parameter sets, fixed by FIPS 204, so
  the set of functions is closed and small;
- each parameter set needs its own cost types regardless, so a selector would
  not reduce the metering surface;
- simplicity: it removes an invalid-selector error path, and the exact
  input-length checks already enforce the parameter set unambiguously.

### External interface with a context string

FIPS 204 defines an internal interface (`ML-DSA.Verify_internal`, intended
for testing and for building wrapper schemes) and an external interface
(`ML-DSA.Verify`) that domain-separates the message with
`0x00 || len(ctx) || ctx`. The external interface of the pure variant is
exposed because it is what conforming signers — HSMs, OS keystores, wallet
libraries, X.509 toolchains — produce. The context string parameter is
exposed (rather than fixed to empty) because signatures produced under a
non-empty context can otherwise never be verified on-chain, and adding the
parameter later would require a new set of host functions. Passing empty
bytes yields the common default behavior.

These functions take the full message, whereas
`verify_sig_ecdsa_secp256r1` takes a 32-byte digest. This reflects a
difference in the schemes' external interfaces, not in key binding. ECDSA
verification operates on `H(M)` directly — the hash is external to the
algorithm and the digest fully determines the verified value — so a digest
interface is faithful. The *pure* ML-DSA external interface implemented here
(FIPS 204 Algorithm 3) formats `M' = 0x00 || len(ctx) || ctx || M`,
embedding the entire message, and passes `M'` to `ML-DSA.Verify_internal`,
which computes the message representative `mu = H(H(pk) || M')` (Algorithm 8)
from it; there is no conforming point at which a caller-supplied digest can
be substituted for `M`. The message length is accounted for by the linear
term of the verification cost types.

FIPS 204 does define a digest-style interface — the pre-hashed variant
HashML-DSA (§5.4, Algorithms 4–5) — which takes `PH(M)` (a pre-hash of the
message) plus an identifier of the pre-hash function, and is then verified
through the *same* `ML-DSA.Verify_internal`. It is omitted here by choice:

- FIPS 204 states the pure variant is generally preferred (§5.4);
- HashML-DSA's message binding additionally depends on the collision
  resistance of a caller-chosen pre-hash function whereas the pure variant 
  carries no such external assumption

It can be added later — as a separate external function that performs the
`0x01 || len(ctx) || ctx || OID` formatting from a caller-supplied digest —
if signer ecosystems converge on it.

### Exposing the external interface rather than the internal interface

A single host function wrapping `ML-DSA.Verify_internal(pk, M', sigma)` —
the deterministic core that both `ML-DSA.Verify` and `HashML-DSA.Verify`
call after constructing `M'` — was considered. It was rejected
because it relocates the guarantees the standard builds into its external
interface out of the host and into the sdk/caller:

- **Domain separation becomes the caller's responsibility.** The leading
  `0x00`/`0x01` byte is what prevents a pure signature from being
  reinterpreted as a pre-hash signature (and vice versa), and
  `len(ctx) || ctx` is what binds the context. `ML-DSA.Verify_internal`
  enforces none of this; a contract that formats `M'` incorrectly would
  obtain "successful" verifications that are not conforming ML-DSA.
- **There is no context parameter to validate.** `ML-DSA.Verify_internal`
  takes only `(pk, M', sigma)` (Algorithm 8); the context is not a distinct
  input but bytes the caller has already folded into `M'`. The internal
  interface cannot check the context since `M'` is deliberately variant-agnostic. 
  The `|ctx| <= 255` bound is a property of the external encoding. Exposing the
  internal interface therefore removes the notion of a context field entirely 
  and makes the whole `M'` layout the caller's responsibility.
- **The pre-hash OID encoding becomes a contract-side footgun.** A contract
  doing pre-hashing must reproduce the exact DER-encoded OID and byte layout
  of Algorithm 4; a subtle error silently verifies a non-standard scheme.

Both variants are therefore better served by distinct external functions than by a single
internal-interface function. The pre-hash variant can be added later if needed.

### Trap on failure

The functions return `Void` and trap on verification failure, consistent
with `verify_sig_ed25519` and `verify_sig_ecdsa_secp256r1`. The general
rationale for trapping on host errors is described in [CAP-0059, contract
panic on error](cap-0059.md#contract-panic-on-error). A boolean-returning
variant can be considered if there is a specific need for fallible verification.

### Choice of the cost types

The decode/verify split mirrors the existing
`ComputeEd25519PubKey`/`VerifyEd25519Sig` decomposition and follows the
selection criteria of [CAP-0046-10]: the two components are distinct,
non-overlapping units of work with different scaling behavior. Key decoding
is dominated by the SHAKE-128 expansion of the `k × l` matrix `A_hat` and
its NTT-domain precomputation — constant per parameter set and independent
of the message. Verification proper (signature decoding, `SampleInBall`,
NTTs, matrix-vector products, hint application, and the `mu` computation) is
constant except for the SHAKE-256 absorption of the message, making it a
clean linear model in message length. Separating key decoding also leaves
room for a future optimization in which expanded verifying keys are cached
across repeated verifications within a transaction, without restructuring
the cost model.

## Protocol Upgrade Transition

The proposed host functions become available at the protocol version this
CAP is released in. For earlier protocol versions, attempting to import any
of these functions in a Wasm module results in a linking error during VM
instantiation, per the standard `min_supported_protocol` gating mechanism.

### Backwards Incompatibilities

This CAP does not introduce any backward incompatibilities. The XDR change
is limited to appending new `ContractCostType` enum entries, whose cost
parameters are introduced through the standard config-setting upgrade
mechanism.

### Resource Utilization

The cost of the new host functions is captured by the new cost types and
must be calibrated before release. Final calibration numbers are TBD.
Preliminary measurements from the prototype implementation indicate that a
full ML-DSA-65 verification (key decoding plus verification of a short
message) costs on the order of a few times an Ed25519 verification in CPU,
with transient host-side memory of roughly 16–57 KB per call (the expanded
`A_hat` matrix, scaling with `k × l`). Input sizes are larger than for
existing schemes (multi-kilobyte keys and signatures), which increases
transaction size and read-bytes consumption for use cases that store keys on
ledger; this is an inherent property of the scheme.

## Security Concerns

- **Implementation maturity.** The host functions wrap an external library
  implementation, and several candidates are being evaluated (both pure Rust
  and other languages). Because broad adoption is still emerging, most
  implementations are early and immature, and lack auditing, formal
  verification, or an official guarantee. Selecting the library to vendor
  requires care and judgment — weighing code quality, development history,
  bug history, and conformance against the standard. At a minimum, the chosen
  implementation is checked against the NIST ACVP vector sets and Wycheproof
  adversarial vectors (see [Test Cases](#test-cases)), and an independent
  review of its verification path should be included in the scope.

- **Logic correctness.** Incorrect implementation of decoding or
  verification corner cases (hint unpacking, range checks) could admit
  forged or malformed signatures. The structural checks mandated by FIPS 204
  (hint validity, `z` range) are enforced; together with the commitment-hash
  comparison these provide the standard's strong-unforgeability properties.
- **Denial of service.** Verification is computationally intensive and the
  inputs are large. Miscalibration of any cost type, or failure to charge
  before performing work, could allow metered cost to significantly
  undershoot actual cost. Charges are applied before the corresponding
  computation, all inputs are length-checked before any expensive work, and
  each parameter set is calibrated independently.
- **Determinism.** Verification is fully deterministic, so the host functions
  introduce no consensus-divergence risk from randomness. However, some
  implementations select platform-dependent code paths at runtime (e.g.
  AVX2/SIMD backends), which can introduce divergence risks across
  architectures; the host implementation should eliminate platform dependency.
- **Scope.** This CAP does not make Stellar post-quantum secure. Transaction
  signatures, account master keys, and the overlay remain Ed25519-based.
  Contracts using these functions obtain post-quantum signature verification
  for their own authentication logic only.

## Test Cases

Conformance is tested against external authoritative vector sets, all of
which are exercised by the prototype implementation:

1. **NIST ACVP ML-DSA sigVer vectors** ([ACVP-Server], FIPS 204 revision):
   both the external-interface cases (pure variant, including non-empty
   contexts, run through the host functions end-to-end) and the
   internal-interface cases (run against the host's decoding layer plus the
   library's internal verification, since the external interface cannot
   replay them by construction). All three parameter sets, valid and invalid
   cases (modified message, commitment, hint and response-vector
   corruptions).
2. **Wycheproof ML-DSA verification vectors** ([Wycheproof]):
   `mldsa_{44,65,87}_verify_test.json`, covering malformed encodings,
   boundary conditions and context-string handling.
3. **Handwritten error-path tests**: wrong key/signature lengths,
   cross-parameter-set inputs, context over 255 bytes, bit-flipped message/
   signature/context, and budget exhaustion.

## Implementation

TBD.

[FIPS 204]: https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.204.pdf
[FIPS 205]: https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.205.pdf
[RFC 9881]: https://datatracker.ietf.org/doc/rfc9881/
[NIST 2024]: https://www.nist.gov/news-events/news/2024/08/nist-releases-first-3-finalized-post-quantum-encryption-standards
[CNSA 2.0]: https://media.defense.gov/2022/Sep/07/2003071836/-1/-1/0/CSA_CNSA_2.0_ALGORITHMS_.PDF
[OpenSSL 3.5]: https://openssl-library.org/post/2025-04-08-openssl-35-final-release/
[JEP 497]: https://openjdk.org/jeps/497
[AWS KMS ML-DSA]: https://aws.amazon.com/about-aws/whats-new/2025/06/aws-kms-post-quantum-ml-dsa-digital-signatures/
[CAP-0046-03]: cap-0046-03.md
[CAP-0046-10]: cap-0046-10.md
[CAP-0051]: cap-0051.md
[CAP-0059]: cap-0059.md
[ACVP-Server]: https://github.com/usnistgov/ACVP-Server
[Wycheproof]: https://github.com/C2SP/wycheproof
