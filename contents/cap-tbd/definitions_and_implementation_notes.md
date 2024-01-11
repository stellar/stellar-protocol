## Curve Definition
BLS12 curve is fully defined by the following set of parameters (coefficient A=0 for all BLS12 curves):

```
Base field modulus = 0x1a0111ea397fe69a4b1ba7b6434bacd764774b84f38512bf6730d2a0f6b0f6241eabfffeb153ffffb9feffffffffaaab
B coefficient = 0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000004
Main subgroup order = 0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001
Extension tower
Fp2 construction:
Fp quadratic non-residue = 0x1a0111ea397fe69a4b1ba7b6434bacd764774b84f38512bf6730d2a0f6b0f6241eabfffeb153ffffb9feffffffffaaaa
Fp6/Fp12 construction:
Fp2 cubic non-residue c0 = 0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001
Fp2 cubic non-residue c1 = 0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001
Twist parameters:
Twist type: M
B coefficient for twist c0 = 0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000004
B coefficient for twist c1 = 0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000004
Generators:
G1:
X = 0x17f1d3a73197d7942695638c4fa9ac0fc3688c4f9774b905a14e3a3f171bac586c55e83ff97a1aeffb3af00adb22c6bb
Y = 0x08b3f481e3aaa0f1a09e30ed741d8ae4fcf5e095d5d00af600db18cb2c04b3edd03cc744a2888ae40caa232946c5e7e1
G2:
X c0 = 0x024aa2b2f08f0a91260805272dc51051c6e47ad4fa403b02b4510b647ae3d1770bac0326a805bbefd48056c8c121bdb8
X c1 = 0x13e02b6052719f607dacd3a088274f65596bd0d09920b61ab5da61bbdc7f5049334cf11213945d57e5ac7d055d042b7e
Y c0 = 0x0ce5d527727d6e118cc9cdc6da2e351aadfd9baa8cbdd3a76d429a695160d12c923ac9cc3baca289e193548608b82801
Y c1 = 0x0606c4a02ea734cc32acd2b02bc28b99cb3e287e85a763af267492ab572e99ab3f370d275cec1da1aaa9075ff05f79be
Pairing parameters:
|x| (miller loop scalar) = 0xd201000000010000
x is negative = true
```
One should note that base field modulus is equal to 3 mod 4 that allows an efficient square root extraction.


## Notes of Encoding
### Field Elements
For elements of the quadratic extension field (Fp2) encoding is byte concatenation of individual encoding of the coefficients totaling in 128 bytes for a total encoding. For an Fp2 element in a form el = c0 + c1 * v where v is formal quadratic non-residue and c0 and c1 are Fp elements the corresponding byte encoding will be encode(c0) || encode(c1) where || means byte concatenation.

Note on the top 16 bytes being zero: it’s required that the encoded element is “in a field” that means strictly < modulus. In BigEndian encoding it automatically means that for a modulus that is just 381 bit long top 16 bytes in 64 bytes encoding are zeroes and it must be checked if only a subslice of input data is used for actual decoding.

If encodings do not follow this spec anywhere during parsing in the precompile the precompile must return an error.
 
### Point of infinity
Also referred to as “zero point”. For BLS12 curves point with coordinates (0, 0) (formal zeroes in Fp or Fp2) is not on the curve, so encoding of such point (0, 0) is used as a convention to encode point of infinity.

 ### Behavior on empty inputs
Certain operations have variable length input, such as multiexponentiations (takes a list of pairs (point, scalar)), or pairing (takes a list of (G1, G2) points). While their behavior is well-defined (from arithmetic perspective) on empty inputs, this proposal discourages such use cases and variable input length operations must return an error if input is empty.


## Field Element to Curve Mapping
See linked [document](https://github.com/namankumar/stellar-protocol/blob/master/contents/cap-tbd/field_element_to_curve_point_mapping.md).



## Test Cases
Due to the large test parameters space we first provide properties that various operations must satisfy. We use additive notation for point operations, capital letters (P, Q) for points, small letters (a, b) for scalars. Generator for G1 is labeled as G, generator for G2 is labeled as H, otherwise we assume random point on a curve in a correct subgroup. 0 means either scalar zero or point of infinity. 1 means either scalar one or multiplicative identity. group_order is a main subgroup order. e(P, Q) means pairing operation where P is in G1, Q is in G2.

Required properties for basic ops (add/multiply):

- Commutativity: P + Q = Q + P
- Additive negation: P + (-P) = 0
- Doubling P + P = 2*P
- Subgroup check: group_order * P = 0
- Trivial multiplication check: 1 * P = P
- Multiplication by zero: 0 * P = 0
- Multiplication by the unnormalized scalar (scalar + group_order) * P = scalar * P
- Required properties for pairing operation:

Degeneracy e(P, 0*Q) = e(0*P, Q) = 1
Bilinearity e(a*P, b*Q) = e(a*b*P, Q) = e(P, a*b*Q) (internal test, not visible through ABI)
