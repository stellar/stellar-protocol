## Preamble

```
CAP: To Be Assigned
Title: Host Functions for BLS12-381 curve operations
Working Group: 
    Owner: <Person accountable for the CAP - name/email address/github alias>
    Authors: <List of comma separated name/email address/github alias>
    Consulted: <List of comma separated name/email address/github alias>
Status: Draft
Created: 2024-01-05
Discussion: https://github.com/stellar/rs-soroban-env/issues/779
Protocol version: TBD
```

## Simple Summary
Add support for the BLS12-381 elliptical curve to enable zero knowledge proof systems.

## Working Group

This section describes the composition of the working group.

## Motivation
BLS12-381 host functions allow for cryptographic operations in the Soroban execution environment that are otherwise prohibitively expensive. It enables a variety of applications including confidentiality preserving systems, BLS signature schemes, and multiple types of scaling solutions. Pairing-friendly elliptic curves are needed for such systems and BLS12-381 is the state of the art in secure elliptical curves. 

### Goals Alignment
You should reference the Stellar Network goal(s) that this proposal advances, such as:
* The Stellar Network should run at scale and at low cost to all participants of the network.
* The Stellar Network should enable cross-border payments.

## Abstract
Add host functions that enable arithmetic, pairing, and mapping operations for points on the BLS12-381 curve. 

## Specification


### XDR changes

TBD

### Semantics
Eleven host functions are added to enable the BLS12-381 curve, which is fully defined in the [supporting docs](https://github.com/namankumar/stellar-protocol/blob/master/contents/cap-tbd/definitions_and_implementation_notes.md). G1 and G2 are two sets of points on the curve. The mathematical relationship between G1 and G2 enables advanced cryptographic systems.

#### Encoding Rules

Inputs to the specificed functions need to be encoded as specified.

#### Encoding Rules: Field elements
Base field element (Fp) is encoded as 64 bytes by performing BigEndian encoding of the corresponding (unsigned) integer (top 16 bytes are always zeroes). 64 bytes are chosen to have 32 byte aligned ABI (representable as e.g. bytes32[2] or uint256[2]). Corresponding integer must be less than field modulus.
For elements of the quadratic extension field (Fp2) encoding is byte concatenation of individual encoding of the coefficients totaling in 128 bytes for a total encoding. 


#### Encoding Rules: Points in G1 and G2
Points in either G1 (in base field) or in G2 (in extension field) are encoded as byte concatenation of encodings of the x and y affine coordinates. Total encoding length for G1 point is thus 128 bytes and for G2 point is 256 bytes.

#### Encoding Rules: Scalars for Multiplication Pperations
Scalar for multiplication operation is encoded as 32 bytes by performing BigEndian encoding of the corresponding (unsigned) integer. Corresponding integer is not required to be less than or equal than main subgroup size.


### Data Types
Following types are used throughout this proposal.

```
 const BLST_G1_POINT: usize = 96; (rename after adding decoding functions)
 const BLST_G2_POINT: usize = 192;
 const BLST_SCALAR_SIZE: usize = 255;
```
### Curve Operations

#### Addition in G1

```rust
fn bls12_g1add( e: &Host, p0: BLST_G1_POINT, p1: BLST_G1_POINT) -> Result <BLST_G1_POINT, Error>;
```
Perform addition of two points in G1. 
Inputs should be 96 bytes each. 
An error will be thrown if neither input is in G1, input has invalid length, or encoding rules are violated. 

#### Multiplication in G1

```rust
fn bls12_g1mul( e: &Host, scalar: u8, p0: BLST_G1_POINT) -> Result <BLST_G1_POINT, Error>;
```
Perform multiplication between a point in G1 and a scalar.
Input should be 96 bytes and 8 bytes.
An error will be thrown if the input p0 is not in G1, input p1 has invalid length, or encoding rules are violated. 

#### Multiexponentiation in G1

```rust
fn bls12_g1multiexp( e: &Host, scalars: &[u8], p_n: BLST_G1_POINT) -> Result <BLST_G1_POINT, Error>;
```
Perform multipliexponentiation on a point in G1 and a scalar. 
Input should be 96 bytes and 8 bytes.
An error will be thrown if the input p_n is not in G1, input p1 has invalid length, or encoding rules are violated. 

#### Addition in G2

```rust
fn bls12_g2add( e: &Host, p0: BLST_G2_POINT, p1: BLST_G2_POINT) -> Result <BLST_G2_POINT, Error>;
```
Perform addition of two points in G2. 
Inputs should be 192 bytes each. 
An error will be thrown if neither input is in G2, input has invalid length, or encoding rules are violated. 

#### Multiplication in G2

```rust
fn bls12_g2mul( e: &Host, scalar: u8, p0: BLST_G2_POINT) -> Result <BLST_G2_POINT, Error>;
```
Perform multiplication between a point in G2 and a scalar.
Input should be 192 bytes and 8 bytes.
An error will be thrown if the input p0 is not in G2, input p2 has invalid length, or encoding rules are violated. 

#### Multiexponentiation in G2

```rust
fn bls12_g2multiexp( e: &Host, scalars: &[u8], p_n: BLST_G2_POINT) -> Result <BLST_G2_POINT, Error>;
```
Perform multipliexponentiation on a point in G2 and a scalar. 
Input should be 192 bytes and 8 bytes.
An error will be thrown if the input p_n is not in G2, input p_n has invalid length, or encoding rules are violated. 

#### Pairing

```rust
fn bls12_pairing( e: &Host, p_g1: &[BLST_G1_POINT], p_g2: &[BLST_G2_POINT]) -> Result <u32, Error>;
```

Perform pairing between points in G1 and G2. 
Arguments: 
p_g1: point in G1(96 bytes)
p_g1: point in G1(192 bytes)
Returns padded 0x01 if pairing is successful else 0x00.
Error will be thrown if p0_g1 and p1_g1 are not on G1 and G2 respectively, if the points are in the incorrect subgroups, have invalid length, inputs are empty, encoding rules are violated. 

#### Map Base Field Element to G1

```rust
fn bls12_map_fp_to_g1( e: &Host, fp: &[u64]) -> Result <BLST_G1_POINT, Error>;
```
Map an element of the base field (64 bytes) to a point in G1 (96 bytes). 
An error will be thrown if the input p_n is not in G2, input p_n has invalid length, or encoding rules are violated. 

#### Map Extension Field Element to G2

```rust
fn bls12_map_fp2_to_g2( e: &Host, fp2: &[u64]) -> Result <BLST_G2_POINT, Error>;
```
Map an element of the extension field (64 bytes) to a point in G2 (96 bytes). 
An error will be thrown if the input fp2 is not in G2, input fp2 has invalid length, or encoding rules are violated. 

#### Map Arbitrary String to G1

```rust
fn bls12_map_hash_to_g1( e: &Host, str: &[u64]) -> Result <BLST_G1_POINT, Error>;
```
Map an arbitrary array of bytes (64 bytes) to a point in G1 (96 bytes). 
An error will be thrown if the input str is not in G1, input str has invalid length, or encoding rules are violated. 


#### Map Arbitrary String to G2

```rust
fn bls12_map_hash_to_g2( e: &Host, str: &[u64]) -> Result <BLST_G2_POINT, Error>;
```
Map an arbitrary byte array (64 bytes) to a point in G2 (192 bytes). 
An error will be thrown if the input str is not in G2, input str has invalid length, or encoding rules are violated. 



## Design Rationale
The rationale fleshes out the specification by describing what motivated the design and why
particular design decisions were made. It should describe alternate designs that were considered
and related work, e.g. how the feature is supported in other protocols. The rationale may also
provide evidence of consensus within the community, and should discuss important objections or
concerns raised during discussion.

## Protocol Upgrade Transition
Typically CAPs have a direct impact on core that should be well understood,
and indirect impact on other systems in the ecosystem (Horizon, SDKs,
application, etc).

The following sections look at common challenges associated with those
protocol transitions.

### Backwards Incompatibilities
All CAPs that introduce backwards incompatibilities must include a section describing these
incompatibilities and their severity.

The CAP must propose how to deal with these incompatibilities, potentially pointing to other standard documents that complements the CAP (for example SEPs).

CAP submissions with an insufficient discussion of backwards compatibility
may be rejected outright.

### Resource Utilization
Reasonable effort should be made to understand the impact of the CAP on
resource utilization like CPU, memory, network bandwidth and disk/database.

## Security Concerns
All CAPs should carefully consider areas where security may be a concern, and document them
accordingly. If a change does not have security implications, briefly explain why.

## Test Cases
Test cases for an implementation are mandatory for CAPs that are affecting consensus changes. Other
CAPs can choose to include links to test cases if applicable.

## Implementation
The implementation(s) must be completed before any CAP is given "Final" status, but it need not be
completed before the CAP is accepted. While there is merit to the approach of reaching consensus on
the specification and rationale before writing code, the principle of "rough consensus and running
code" is still useful when it comes to resolving many discussions of API details.

[stellar-core repository]: https://github.com/stellar/stellar-core
