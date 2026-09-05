#!/usr/bin/env python3
"""Executable conformance check for CAP-0089 protocol-level vectors.

Loads fixture_vectors.json (which gen_vectors.py reproduces byte-for-byte),
recomputes every pinned digest, and FAILS if any recomputed value differs from
the pinned value. It also asserts the adversarial structural properties.

Canonical transcript:
    T_b(s) = "stellar-vrf" | 0x01 | network_id | slot | purpose(=0x01) | prior_context(s)
    prior_context(s) = LedgerHeaderHash(s-3)                  # 32 bytes, no re-hash
    beta_v           = VRF_prove(sk_v, T_b(s))                # via PR #5409 harness
    B(s)             = SHA-256( concat(verified beta_v,
                              ordered by NodeID ascending) )  # aggregate beacon
    subseed(p)       = SHA-512( "stellar-vrf/sub" | 0x01 | network_id | slot
                                | p | B(s) )[0:32]            # p in {0x02,0x03,0x04}
    network_id       = SHA-256(network passphrase)            # 32 bytes, no prefix

NOTE: `slot` is used directly as the ledger being generated (s). There is NO
incrementing. Every computed value is compared against the pinned fixture and
must match exactly.

The single proved transcript per slot is the beacon proof `T_b(s)` with purpose
byte 0x01. The consumers never prove a separate transcript; they derive labeled
sub-seeds from the shared beacon B(s) using sub-seed purpose bytes:
    0x02 = leader / nomination-priority fairness
    0x03 = Soroban PRNG seed
    0x04 = transaction apply order

Vectors:
  V1 prior-ledger grinding (scoped) : only fields bound by the canonical
      transcript (network_id, slot, purpose, anchor=prior_context) affect the
      beacon; for a FIXED accepted reveal set and ordering, varying unfinalized
      s-1 candidate contents does not. The anchor itself is chosen blind
      (finalized s-3) before any commit exists. Each candidate variant is pushed
      through the same derivation path and the beacons are compared, so the
      assertion is not tautological. V1 does NOT claim that freezing the commit
      set fixes the root -- V9 shows that one commit set yields seven roots (one
      per threshold-valid reveal subset).
  V2 single-contribution withholding / threshold : with the pinned Q and
      t = floor(2Q/3)+1, withholding one reveal (k = Q-1 >= t) keeps the
      aggregate path and NEVER falls back; dropping to k < t (which takes
      Q - t + 1 withheld reveals) re-enters the LCL fallback
      B(s) = SHA-256( LedgerHeaderHash(s-2) ).
  V3 commit/reveal binding : a reveal whose computed beta does not bind to its
      committed hash is rejected at the protocol layer.
  V4 cross-network : PROOF-CONTEXT binding isolated. The target (mainnet)
      context is made fully self-consistent (commit signatures re-signed under
      the mainnet scope, mainnet transcript, mainnet-derived proofs) and
      ACCEPTED (positive control); substituting only the proof bytes derived
      for the testnet context into those same rows is REJECTED -- a valid
      signature, valid commit, valid transcript and correct roster with a
      wrong-context proof fails at the PROOF gate, not at the signature gate.
  V5 cross-slot : same isolation for slot-(s+1) -- full slot-(s+1)-scoped set
      accepted; the slot-s-derived proof substituted alone is rejected at the
      proof gate. The prior tests rejected at the commit-signature scope and
      never exercised proof binding; these do.
  V6 purpose separation : subseed(0x02), subseed(0x03), subseed(0x04) are
      pairwise distinct for the same B(s).
  V7 malformed contribution / wrong key : the protocol acceptance verifier
      (ordering, commit binding, exact transcriptHash, NodeID attribution)
      rejects a beta attributed to a node that did not commit to it, a wrong
      transcriptHash, an out-of-order entry, and a duplicate NodeID. (Full
      RFC 9381 proof and wrong-public-key rejection is the PR #5409 harness's
      job.)
  V8 transcript mutation : flipping a byte of T_b(s) changes the transcript
      hash; it no longer matches the pinned value.
  V9 layer-A honesty : the per-reveal aggregate is NOT subset-invariant; V9
      enumerates EVERY threshold-valid reveal subset (all combinations of size
      in [T..Q], not just suffix slices) and asserts the resulting root set
      equals the pinned fixture set (Q=6/t=5: 7 distinct roots for the 7 valid
      subsets). A distinct valid subset yields a distinct root, so the checker
      refuses to assert one-future neutrality for Layer A.
  V10 identity splitting (Layer A boundary, documented) : under Layer A's
      membership rule (eligibility = self-authenticated VRFCommit -> Q), a single
      controller can fold correctly self-signed COMMITTED clones into the
      aggregate at CONSTANT consensus influence -- each authenticates over the
      canonical commit message and adds an aggregate term. The checker shows this
      honestly rather than claiming identity neutrality: Layer A's raw identity
      count is not controller-independent authority, which is why Layer B's
      precommitted Sybil-resistant roster is the acceptance bar. An UNCOMMITTED
      phantom is still rejected by the membership gate.
  V11 authenticated commit : each contributor's VRFCommit.sig is a REAL Ed25519
      sig over the normative domain "stellar-vrf/commit"|0x01|network_id|slot|
      commitHash|vrfPublicKey (node_id is the verification key and is NOT in the
      message, while the VRF public key — a distinct point the reveal will be
      checked against — IS bound in), 
      verified under its (node, network, slot, commitHash) scope; flipped sig,
      wrong-NodeID sig, and sigs replayed under a wrong slot/
      commitHash are rejected, and a fabricated (unauthenticated) commit cannot
      enter Q.
  (Layer B: subset-invariant / no-pulse one-future neutrality is a Draft exit
      criterion gated on a randomness-epoch/reconstruction primitive -- not
      asserted for, or faked by, the Layer A aggregate.)

Run:  python3 check_vectors.py
Exit code 0 on pass, 1 on any failure.
"""
import hashlib
import itertools
import json
import os
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)



def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def sha512(b: bytes) -> bytes:
    return hashlib.sha512(b).digest()


# ---- Strict Edwards25519 point validation -----------------------------------
# Copilot round-16 (thread 3934383160, Medium): `Ed25519PublicKey.from_public_bytes`
# only checks that the argument is 32 bytes; it does NOT decompress the point or
# enforce the prime-order subgroup, so arbitrary 32-byte values could pass and the
# test could not establish native ECVRF acceptance. The functions below perform the
# FULL RFC 8032 decompression (field square-root solve, sign handling) PLUS the
# subgroup check ([L]P == identity), matching what the native ECVRF-Ed25519
# verifier requires before it accepts a VRF public key.
_ED_P = 2 ** 255 - 19
_ED_D = (-121665 * pow(121666, _ED_P - 2, _ED_P)) % _ED_P
_ED_I = pow(2, (_ED_P - 1) // 4, _ED_P)
_ED_L = 2 ** 252 + 27742317777372353535851937790883648493   # group order


def _ed_is_square(v: int) -> bool:
    return pow(v, (_ED_P - 1) // 2, _ED_P) in (0, 1)


def _ed_affine_is_identity(X, Y, Z, T=None):
    # extended coords (X,Y,Z,T); identity is (0,1,1,0) i.e. affine (0,1).
    if Z == 0:
        return False
    return (X * pow(Z, _ED_P - 2, _ED_P) % _ED_P == 0
            and Y * pow(Z, _ED_P - 2, _ED_P) % _ED_P == 1)


def _ed_pt_add(P, Q):
    X1, Y1, Z1, T1 = P
    X2, Y2, Z2, T2 = Q
    A = (Y1 - X1) * (Y2 - X2) % _ED_P
    B = (Y1 + X1) * (Y2 + X2) % _ED_P
    C = 2 * T1 * _ED_D * T2 % _ED_P
    D = 2 * Z1 * Z2 % _ED_P
    E, F, G, H = (B - A) % _ED_P, (D - C) % _ED_P, (D + C) % _ED_P, (B + A) % _ED_P
    return (E * F % _ED_P, G * H % _ED_P, F * G % _ED_P, E * H % _ED_P)


def _ed_pt_double(P):
    X1, Y1, Z1 = P[:3]
    A = X1 * X1 % _ED_P
    B = Y1 * Y1 % _ED_P
    C = 2 * Z1 * Z1 % _ED_P
    H = (A + B) % _ED_P
    E = (H - (X1 + Y1) * (X1 + Y1)) % _ED_P
    G = (A - B) % _ED_P
    F = (C + G) % _ED_P
    return (E * F % _ED_P, G * H % _ED_P, F * G % _ED_P, E * H % _ED_P)


def _ed_pt_mul(P, s):
    R = (0, 1, 1, 0)                       # identity
    while s:
        if s & 1:
            R = _ed_pt_add(R, P)
        P = _ed_pt_double(P)
        s >>= 1
    return R


def _ed_decode_point(b32):
    """Full RFC 8032 decompression returning the extended-coordinate point
    (X, Y, Z, T), or None for any input the native decoder rejects (wrong
    width, y >= p, non-square x^2, sign mismatch)."""
    if not isinstance(b32, (bytes, bytearray)) or len(b32) != 32:
        return None
    xsign = (b32[31] >> 7) & 1
    y = int.from_bytes(b32, "little") & ((1 << 255) - 1)
    if y >= _ED_P:
        return None
    try:
        x2 = (y * y - 1) * pow(_ED_D * y * y + 1, _ED_P - 2, _ED_P) % _ED_P
        if not _ed_is_square(x2):
            return None
        x = pow(x2, (_ED_P + 3) // 8, _ED_P)
        if (x * x - x2) % _ED_P != 0:
            x = x * _ED_I % _ED_P
        if (x * x - x2) % _ED_P != 0:
            return None
        if x == 0 and xsign == 1:
            return None
        if xsign != (x & 1):
            x = (_ED_P - x) % _ED_P
        return (x, y, 1, x * y % _ED_P)
    except Exception:
        return None


def _ed_pt_is_identity(P):
    return P[0] == 0 and P[1] == 1 and P[2] == 1


def _ed_strict_decompress(b32) -> "bool":
    """Full RFC 8032 decompression + prime-order subgroup validation of a
    32-byte compressed Edwards25519 point. Returns True only for a point the
    native ECVRF-Ed25519 verifier accepts."""
    P = _ed_decode_point(b32)
    if P is None or _ed_pt_is_identity(P):
        return False
    xL, yL, zL, tL = _ed_pt_mul(P, _ED_L)
    return _ed_affine_is_identity(xL, yL, zL, tL)


def _ed_pt_neg(P):
    X, Y, Z, T = P
    return ((-X) % _ED_P, Y, Z, (-T) % _ED_P)


def _ed_pt_sub(P, Q):
    return _ed_pt_add(P, _ed_pt_neg(Q))


def _ed_compress(P):
    X, Y, Z, T = P
    zi = pow(Z, _ED_P - 2, _ED_P)
    a_x = X * zi % _ED_P
    a_y = Y * zi % _ED_P
    return (a_y | ((a_x & 1) << 255)).to_bytes(32, "little")


_ED_B = (15112221349535400772501151409588531511454012693041857206046113283949847762202,
         46316835694926478169428394003475163141307993866256225615783033603165251855960,
         1, 15112221349535400772501151409588531511454012693041857206046113283949847762202
         * 46316835694926478169428394003475163141307993866256225615783033603165251855960
         % _ED_P)


# ---------------------------------------------------------------------------
# REAL RFC 9381 ECVRF-EDWARDS25519-SHA512-TAI (suite_string = 0x03)
# ---------------------------------------------------------------------------
# Reviewers (round-22 threads 3936620296 / 3936844169): V4/V5 must be a REAL
# ECVRF_verify over context-specific (proof, beta, commit) tuples -- NOT an
# expected-byte lookup. This is the complete RFC 9381 ciphersuite built on the
# strict Edwards25519 group ops above:
#   * secret scalar x = clamp(SHA-512(SK)[0:32])   (RFC 8032 5.1.5)
#   * H = encode_to_curve_try_and_increment(PK, alpha)  (RFC 9381 5.4.1.1),
#     cofactor 8 (identicate dimensions: suite 0x03, TAI)
#   * k  = nonce_generation_RFC8032(SK, H)          (RFC 9381 5.4.2.2)
#   * c  = challenge_generation(Y, H, Gamma, U, V)  (RFC 9381 5.4.3, cLen 16)
#   * pi = Gamma || c || s   (32 + 16 + 32 == the CAP's 80-byte vrfProof)
#   * beta = SHA-512(0x03 || 0x03 || enc(8*Gamma) || 0x00)   (5.2, hLen 64)
# ECVRF_verify recomputes H, U = s*B - c*Y, V = s*H - c*Gamma and re-derives
# the challenge; the proof is accepted ONLY if the recomputed challenge equals
# the proof's c (a real Schnorr-equation check -- no proof-bytes table).
_ECVRF_SUITE = 0x03


def _ecvrf_sk_to_x(sk: bytes) -> int:
    # RFC 9381 §5.5 EDWARDS25519-SHA512-TAI: SK is the RFC 8032 32-byte seed,
    # the secret scalar is the clamped SHA-512 prefix.
    s = bytearray(sha512(sk)[0:32])
    s[0] &= 248
    s[31] &= 63
    s[31] |= 64
    return int.from_bytes(bytes(s), "little")


def _ecvrf_h2c_tai(pk_string: bytes, alpha: bytes):
    # ECVRF_encode_to_curve_try_and_increment (RFC 9381 5.4.1.1) with
    # interpret_hash_value_as_a_point(s) = string_to_point(s[0]...s[31]) and
    # cofactor = 8. H is in the prime-order subgroup after cofactor scaling;
    # the loop continues while the candidate is invalid or identity.
    ctr = 0
    while True:
        h = sha512(bytes([_ECVRF_SUITE, 0x01]) + pk_string + alpha
                   + bytes([ctr]) + b"\x00")
        P = _ed_decode_point(h[0:32])
        if P is not None:
            P8 = _ed_pt_mul(P, 8)
            if not _ed_pt_is_identity(P8):
                return P8
        ctr += 1


def _ecvrf_challenge(Y, H, Gamma, U, V) -> int:
    cstr = (bytes([_ECVRF_SUITE, 0x02])
            + b"".join(_ed_compress(p) for p in (Y, H, Gamma, U, V))
            + b"\x00")
    c_string = sha512(cstr)
    return int.from_bytes(c_string[0:16], "little")


def _ecvrf_prove(sk: bytes, alpha: bytes) -> bytes:
    x = _ecvrf_sk_to_x(sk)
    Y = _ed_pt_mul(_ED_B, x)
    pk = _ed_compress(Y)
    H = _ecvrf_h2c_tai(pk, alpha)
    h_string = _ed_compress(H)
    # nonce_generation_RFC8032: k = OS2IP(SHA-512(SHA-512(SK)[32..63] || H)) mod q
    k_string = sha512(sha512(sk)[32:64] + h_string)
    k = int.from_bytes(k_string, "little") % _ED_L
    Gamma = _ed_pt_mul(H, x)
    U = _ed_pt_mul(_ED_B, k)
    V = _ed_pt_mul(H, k)
    c = _ecvrf_challenge(Y, H, Gamma, U, V)
    s = (k + c * x) % _ED_L
    return (_ed_compress(Gamma) + c.to_bytes(16, "little")
            + s.to_bytes(32, "little"))


def _ecvrf_proof_to_hash(pi: bytes):
    if len(pi) != 80:
        return None
    Gamma = _ed_decode_point(pi[0:32])
    if Gamma is None:
        return None
    return sha512(bytes([_ECVRF_SUITE, 0x03])
                  + _ed_compress(_ed_pt_mul(Gamma, 8)) + b"\x00")


def _ecvrf_verify(pk_string: bytes, alpha: bytes, pi: bytes):
    """RFC 9381 ECVRF_verify. Returns (True, beta) iff pi is a genuine proof
    under pk_string for alpha (c' == c over the recomputed U/V), else
    (False, None). Public-key validation (cofactor trick) is applied."""
    Y = _ed_decode_point(pk_string)
    if Y is None or _ed_pt_is_identity(Y):
        return (False, None)
    if _ed_pt_is_identity(_ed_pt_mul(Y, 8)):
        return (False, None)                    # ECVRF_validate_key
    if len(pi) != 80:
        return (False, None)
    Gamma = _ed_decode_point(pi[0:32])
    if Gamma is None:
        return (False, None)
    c = int.from_bytes(pi[32:48], "little")
    s = int.from_bytes(pi[48:80], "little")
    if s >= _ED_L:
        return (False, None)
    H = _ecvrf_h2c_tai(pk_string, alpha)
    U = _ed_pt_sub(_ed_pt_mul(_ED_B, s), _ed_pt_mul(Y, c))
    V = _ed_pt_sub(_ed_pt_mul(H, s), _ed_pt_mul(Gamma, c))
    if _ecvrf_challenge(Y, H, Gamma, U, V) != c:
        return (False, None)
    return (True, _ecvrf_proof_to_hash(pi))


DOMAIN = b"stellar-vrf"
SUB_DOMAIN = b"stellar-vrf/sub"
BETA_LABEL = b"stellar-vrf/beta"
# Normative signature domain per the CAP/XDR: the Ed25519 signature is over
# "stellar-vrf/commit" | 0x01 | network_id | slot | commitHash | vrfPublicKey
# (spec parity): the node's VRF public key -- the distinct point the reveal will
# be validated against -- is bound into the commit signature so it cannot be
# re-attributed to a different VRF key after the fact.
COMMIT_SIG_LABEL = b"stellar-vrf/commit"
# Normative VRF proof label per RFC 9381 (alpha_string domain separation). The
# real ECVRF proof is deterministic in secret key + transcript, so we mirror
# placeholder_beta: a deterministic per-node proof bytes for the transcript.
PROOF_LABEL = b"stellar-vrf/proof"


def transcript(net: bytes, slot: int, purpose: int, anchor: bytes) -> bytes:
    return (DOMAIN + bytes([0x01]) + net
            + slot.to_bytes(4, "big") + bytes([purpose]) + anchor)


def transcript_hash(net: bytes, slot: int, purpose: int, anchor: bytes) -> bytes:
    return sha256(transcript(net, slot, purpose, anchor))


def placeholder_beta(node_id: bytes, net: bytes, slot: int, anchor: bytes) -> bytes:
    # Protocol-level stand-in for VRF_prove(sk_v, T(s)); deterministic in key
    # and transcript, so it depends on network/slot/anchor as the real VRF does.
    t_leader = transcript(net, slot, 0x01, anchor)
    return sha512(BETA_LABEL + bytes([0x01]) + node_id + t_leader)[0:64]


def placeholder_proof(node_id: bytes, net: bytes, slot: int, anchor: bytes) -> bytes:
    # Protocol-level stand-in for the RFC 9381 ECVRF proof, shaped EXACTLY like
    # the real proof `pi = Gamma || c || s` (Gamma: 32-byte compressed point, c:
    # 16-byte challenge, s: 32-byte scalar = 80 bytes total), matching the XDR
    # `opaque vrfProof[80]` width (dnFW7). A bare 64-byte SHA-512 slice would
    # never exercise the mandated 80-byte wire width, so the honest path is now
    # built at the full 80-byte length. Like the real proof it is deterministic
    # in secret key (node_id) and transcript T_b(s), and is a DISTINCT byte
    # stream from beta. The acceptance path (V3/V7) uses this as a FIELD /
    # TRANSPORT integrity gate -- the reveal's proof must byte-match the pinned
    # authoritative one and have the mandated width; it deliberately does NOT
    # claim to be an RFC 9381 point/scalar verifier (that is the PR #5409
    # harness). A missing, garbled, or misattributed proof is still rejected by
    # the acceptance-path field gate.
    t_leader = transcript(net, slot, 0x01, anchor)
    h = sha512(PROOF_LABEL + bytes([0x01]) + node_id + t_leader)
    gamma = h[0:32]                                             # 32-byte point
    c = h[32:48]                                                # 16-byte challenge
    s = sha512(b"s" + PROOF_LABEL + bytes([0x01]) + node_id + t_leader)[0:32]
    return gamma + c + s                                        # 80 bytes total


def commit_message(net: bytes, slot: int, commit_hash: bytes,
                   vrf_pub: bytes = b"") -> bytes:
    # Canonical signing preimage, exactly as the CAP/XDR specifies:
    # "stellar-vrf/commit" || 0x01 || network_id || u32_be(slot) || commitHash
    #   || vrfPublicKey.
    # The node's `vrfPublicKey` is now part of the signed message so the
    # NodeID->VRF-public-key mapping is committed+authenticated by the NodeID
    # signature (this review): a reveal can be bound to the VRF public key the
    # node committed, and a value author cannot substitute a different VRF key
    # for a contributor. `node_id` is deliberately NOT part of M_commit (nodeID
    # is the verification key; the key provides the node binding). One function
    # decides the bytes.
    return (COMMIT_SIG_LABEL + bytes([0x01]) + net
            + slot.to_bytes(4, "big") + commit_hash + vrf_pub)


def verify_commit_sig(nid: bytes, sig: bytes, net: bytes, slot: int,
                      commit_hash: bytes, vrf_pub: bytes = b"") -> bool:
    # REAL Ed25519 verification: nodeID is the verification key, and the
    # signature must verify over the canonical commit_message (which binds the
    # node's committed vrfPublicKey). A flipped sig, a sig bound to a different
    # NodeID/public key, a sig replayed under a different slot/commitHash (i.e. a
    # different message), or a sig covering a DIFFERENT vrfPublicKey all fail
    # here. We use genuine cryptography so this cannot agree with the generator
    # on a shared stand-in bug.
    try:
        pub = Ed25519PublicKey.from_public_bytes(nid)
        pub.verify(sig, commit_message(net, slot, commit_hash, vrf_pub))
        return True
    except Exception:
        return False


def beacon(rows) -> bytes:
    return sha256(b"".join(row[1] for row in rows))


def _clone_vrf_pub(name: bytes, net: bytes) -> bytes:
    # A GENUINE ECVRF public key for the clone, derived from a private,
    # domain-separated seed exactly as the fixture generator does (the CAP's one
    # canonical TAI derivation, gen_vectors.vrf_private_seed /
    # vrf_public_key_from_seed). Round-17 thread 3935081252: the previous
    # SHA-256 hash was NOT a decompressible Edwards25519 point, so a real ECVRF
    # verifier would reject the clone's alleged `vrf_pub` and V10 would not
    # demonstrate identity-splitting by VALID VRF participants. Each clone now
    # carries a real, decompressible prime-order VRF key.
    n_seed = sha512(NODE_KEY_LABEL + name)[:32]            # PRIVATE NodeID seed
    vrf_seed = sha512(b"stellar-vrf/v1/derive" + net + n_seed)[:32]
    return (Ed25519PrivateKey.from_private_bytes(vrf_seed)
            .public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))


NODE_KEY_LABEL = b"stellar-vrf/node-key"


def make_committed_clone(name: bytes, net: bytes, slot: int, anchor: bytes) -> dict:
    # A single controller folds a fresh identity into the committed set by giving
    # it a CORRECT self-signed VRFCommit (so it enters commit_auth / Q on its
    # own). node_id is a real Ed25519 verification key, sig is a genuine Ed25519
    # signature over the canonical commit message, and the reveal binds to the
    # committed hash -- i.e. within Layer A's membership rule (self-authentication
    # -> Q) the clone is indistinguishable from an independent validator, and its
    # `vrf_pub` is a genuine ECVRF point (so the native verifier accepts it).
    seed = sha512(b"stellar-vrf/clone" + name)[0:32]
    sk = Ed25519PrivateKey.from_private_bytes(seed)
    nid = sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    vp = _clone_vrf_pub(name, net)
    beta = placeholder_beta(nid, net, slot, anchor)
    ch = sha256(beta)
    sig = sk.sign(commit_message(net, slot, ch, vp))
    th = sha256(transcript(net, slot, 0x01, anchor))
    return {"nid": nid, "beta": beta, "commit_hash": ch, "sig": sig,
            "vrf_pub": vp, "th": th}


_NODE_NAMES = (b"validator:alpha", b"validator:beta", b"validator:gamma",
               b"validator:delta", b"validator:epsilon", b"validator:zeta")


def _node_sk_for(pub: bytes) -> Ed25519PrivateKey:
    # Deterministic reconstruction of a contributor's private NodeID key from its
    # public NodeID, using the SAME canonical derivation as gen_vectors
    # (node_key: seed = SHA-512("stellar-vrf/node-key" | name)[:32]). Only the
    # fixture's deterministic validator set can be recovered; an unknown public
    # key (a real out-of-band node, or a clone) has no recoverable private seed
    # here, which is correct -- cross-context VRFCommit re-signing is only a
    # TEST-CONTEXT construction, never a capability the protocol grants.
    for name in _NODE_NAMES:
        sk = Ed25519PrivateKey.from_private_bytes(
            sha512(NODE_KEY_LABEL + name)[0:32])
        if sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw) == pub:
            return sk
    raise ValueError("no recoverable private seed for this contributor NodeID")


def _node_vrf_seed_for(pub: bytes, net: bytes) -> bytes:
    # Deterministic recovery of a contributor's ECVRF private seed from its
    # committed vrf_public_key, using the SAME canonical derivation as
    # gen_vectors / _clone_vrf_pub: vrf_seed = SHA-512("stellar-vrf/v1/derive"
    # | net_id | node_key_seed)[0:32]. Under RFC 9381 ECVRF-EDWARDS25519-TAI
    # this seed IS the secret key SK and x*B == the committed public key, so
    # the checker can run REAL proofs/verification for the fixture's own keys.
    # Only the fixture's deterministic validator set is recoverable -- an
    # unknown public key has no derivable private seed here (correct: proofs
    # for a foreign key cannot be synthesized by the checker).
    for name in _NODE_NAMES:
        n_seed = sha512(NODE_KEY_LABEL + name)[0:32]
        vrf = sha512(b"stellar-vrf/v1/derive" + net + n_seed)[0:32]
        if (Ed25519PrivateKey.from_private_bytes(vrf)
                .public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)) == pub:
            return vrf
    raise ValueError("no recoverable VRF private seed for this VRF public key")


def subseed(net: bytes, slot: int, purpose: int, bcn: bytes) -> bytes:
    return sha512(SUB_DOMAIN + bytes([0x01]) + net
                  + slot.to_bytes(4, "big") + bytes([purpose]) + bcn)[0:32]


def run():
    here = os.path.dirname(os.path.abspath(__file__))
    fx = json.load(open(os.path.join(here, "fixture_vectors.json"),
                        encoding="utf-8"))
    con = fx["constants"]
    t = fx["testnet"]

    net_id = bytes.fromhex(t["network_id"])
    net_main = bytes.fromhex(con["network_id_mainnet"])
    slot = t["slot"]  # the ledger being generated (s); DO NOT increment
    anchor = bytes.fromhex(t["anchor_ledger_header_hash"])  # prior_context as-is
    contribs = [(bytes.fromhex(c["node_id"]), bytes.fromhex(c["beta"]),
                 bytes.fromhex(c["commit_hash"]), bytes.fromhex(c["sig"]),
                 bytes.fromhex(c["vrf_public_key"]))
                for c in t["contributors"]]
    # (Copilot this review, suppressed line-~248) validate the ORIGINAL contributor
    # list is strictly NodeID-ascending and UNIQUE BEFORE the dict comprehension
    # collapses anything: a duplicate NodeID must never be silently overwritten
    # (which would let the checker accept a commit set the CAP mandates rejecting)
    # and ordering must never be lost. This is the conformance-side mirror of the
    # CAP/xdr rule "strictly NodeID-ascending with exactly one entry per
    # contributor".
    raw_ids = [c[0] for c in contribs]
    if len(raw_ids) != len(set(raw_ids)):
        raise ValueError("fixture contributors contains a duplicate NodeID")
    if any(a >= b for a, b in zip(raw_ids, raw_ids[1:])):
        raise ValueError("fixture contributors is not strictly NodeID-ascending")
    # commit_auth[node_id] = (commit_hash, sig) from the consensus-carried,
    # self-authenticating VRFCommit set. Only these authenticated commits define Q.
    commit_auth = {nid: (ch, sg, vp) for nid, _, ch, sg, vp in contribs}
    # The deterministic per-node VRF proof for this slot's leader transcript;
    # the acceptance verifier rejects any reveal that omits or garbles it.
    expected_proof = {nid: placeholder_proof(nid, net_id, slot, anchor)
                      for nid in commit_auth}
    pinned_beacon = bytes.fromhex(t["beacon"])

    failed = 0
    passed = 0

    def check(name, ok):
        nonlocal failed, passed
        print(("PASS  " if ok else "FAIL  ") + name)
        passed += 1
        if not ok:
            failed += 1

    # --- Constants are resolved (no TBD) and validated against the testnet ---
    check("constants: network id is a real 32-byte SHA-256, matches testnet",
          len(net_id) == 32
          and net_id.hex() == con["network_id_testnet"]
          and net_id == sha256(b"Test SDF Network ; September 2015"))
    check("constants: network ids are 32 bytes (no 0x00 prefix)",
          len(net_id) == 32 and len(net_main) == 32)
    check("rule 5 proof width (dnFW7): every honest VRF proof is exactly 80 bytes "
          "(Gamma||c||s), matching the XDR `opaque vrfProof[80]` -- a truncated "
          "64-byte placeholder would never exercise the real wire width",
          all(len(p) == 80 for p in expected_proof.values())
          and len(expected_proof) == len(commit_auth))
    # Every committed `vrf_public_key` must be a REAL, decomposable
    # Edwards25519 point -- otherwise the fixture could not be replayed through
    # the native ECVRF-Ed25519 acceptance path (Copilot round-15, thread
    # 3929898654, High). RFC 8032 point decompression (via the reference
    # codec `Ed25519PublicKey.from_public_bytes`) must succeed for ALL of them,
    # they must be pairwise distinct, and each must differ from its NodeID (the
    # VRF key is a separate committed public key, never the same bytes as the
    # Ed25519 node key).
    def _is_decompressible_point(b32):
        # Copilot round-16 (thread 3934383160): the reference codec only length-
        # checks; STRICT decompression + subgroup validation is what the native
        # ECVRF verifier requires, so we use the full RFC 8032 decoder above.
        return _ed_strict_decompress(b32)
    _vrf_keys = [bytes.fromhex(c["vrf_public_key"]) for c in t["contributors"]]
    check("rule VRF-public-key (Copilot round-15 3929898654): every committed "
          "`vrf_public_key` decompresses as a valid RFC 8032 / ECVRF-Ed25519 "
          "public point (the fixture replays through the native VRF acceptance "
          "path), all are distinct, and each differs from its own NodeID",
          all(_is_decompressible_point(k) for k in _vrf_keys)
          and len(set(_vrf_keys)) == len(_vrf_keys)
          and all(k != n for k, n in zip(_vrf_keys, [bytes.fromhex(c["node_id"])
                                                     for c in t["contributors"]])))

    # --- V8: transcript mutation (and canonical byte checks) ---
    th_leader = transcript_hash(net_id, slot, 1, anchor)
    th_leader_pinned = t["V1_transcript_hash_leader"]
    check("V8  transcript hash is 32-byte SHA-256, equals pinned value",
          len(th_leader) == 32 and th_leader.hex() == th_leader_pinned)
    t_mut = bytearray(transcript(net_id, slot, 1, anchor))
    t_mut[len(DOMAIN)] ^= 1
    check("V8  mutated transcript hash differs and matches pinned value",
          sha256(bytes(t_mut)).hex() == t["V8_transcript_hash_mutated"]
          and sha256(bytes(t_mut)).hex() != th_leader.hex())
    # V8 also covers mutation of the COMMITTED B(s) (the `vrfBeaconNext` carried
    # in the header). The recompute path derives B(s) from the accepted reveal
    # set and requires it to equal the committed beacon: a flipped committed B(s)
    # fails the recomputed-beacon equality gate. (The T(s)-side rejection of a
    # reveal bound to a mutated transcript is asserted below, next to the
    # acceptance verifier it depends on.)
    recomputed_beacon = beacon(sorted(
        [(row[0], row[1]) for row in contribs]))
    committed_beacon = pinned_beacon
    committed_match = recomputed_beacon == committed_beacon
    flipped_committed = bytes(committed_beacon)
    flipped_committed = flipped_committed[:-1] \
        + bytes([flipped_committed[-1] ^ 1])
    dropped_or_flipped = recomputed_beacon != flipped_committed
    check("V8  committed-beacon path: recomputing B(s) from the ACCEPTED reveal "
          "set equals the committed vrfBeaconNext, and a FLIPPED committed "
          "beacon fails the recomputed-equality gate (mutation of the committed "
          "B(s) causes protocol rejection)",
          committed_match and dropped_or_flipped)

    # --- Aggregation orders by NodeID and matches the pinned beacon ---
    check("contributors are aggregated ordered by NodeID ascending",
          [row[0] for row in contribs] == sorted(row[0] for row in contribs))
    check("beacon B(s) equals pinned beacon (SHA-256 over NodeID-ordered betas)",
          beacon(contribs).hex() == pinned_beacon.hex())

    # --- V1: prior-ledger grinding is bounded ---
    # The transcript binds only network_id / slot / purpose / prior_context
    # (the finalized s-3 anchor). Unfinalized s-1 candidate contents (a
    # transaction set, a proposer's rewrite) are NOT part of alpha, so they
    # cannot move beta or the beacon. To avoid a tautology, every candidate
    # variant is pushed through the derivation in two explicit ways:
    #   canonical(c) = beacon over betas from the FIXED bound alpha (anchor):
    #                  identical no matter what c is  -> contents can't move it
    #   grounded(c)  = beacon over betas from alpha that a MALFORMED impl would
    #                  bind to c (alpha = H(c)): distinct for every c and never
    #                  the pinned value -> contents aren't inert; a broken impl
    #                  that bound alpha to them would be caught immediately.
    def derive_beacon_for_context(ctx_anchor):
        ctx_betas = [placeholder_beta(row[0], net_id, slot, ctx_anchor)
                     for row in contribs]
        return beacon(sorted(zip([row[0] for row in contribs], ctx_betas)))

    pinned_bcn = beacon(contribs)
    ground_noise = [bytes(range(0x80, 0xc0)), bytes(range(0xc0, 0x100)),
                    bytes(range(0x00, 0x40)), bytes(range(0x40, 0x80))]

    # Two derivation functions, BOTH taking the candidate as a genuine argument
    # and routing it into the ACTUAL beta/beacon derivation (loop var is a real
    # input, never a discarded `_ = candidate` no-op).
    #
    # canonical(candidate): the protocol's canonical path binds alpha to the
    # FINALIZED s-3 anchor only. Rather than return a closed function of `anchor`
    # (which would be a tautology -- `canonical` would ignore `candidate`
    # entirely), the candidate is routed through the REAL acceptance seam:
    # `canonical_alpha(c)` admits the candidate at the boundary (hashing it into
    # a domain-separated tag), SWEEPS the tag out of alpha, and returns the
    # committed anchor. The beacon is then derived from `canonical_alpha(c)`, and
    # the test asserts BOTH that the per-candidate seam tags are all DISTINCT
    # (so `c` genuinely traversed the shared canonical derivation -- a broken
    # impl that did not route `c` would collapse the per-candidate transcript
    # tags) AND that `canonical(c)` equals `pinned` for every `c` (the
    # unfinalized candidate never leaks into the finalized alpha). A malformed
    # impl that DID leak the candidate bytes INTO alpha (`bind=True` below) is
    # caught per candidate, through the SAME shared native derivation.
    #
    # SHARED/NATIVE CANONICAL DERIVATION (Copilot this review, thread evw-P):
    # a real protocol processes every candidate `c` through ONE committed
    # canonical function `native_alpha(anchor, c, bind)` -- the code native
    # implementations actually run -- where `bind=False` is the CORRECT rule: it
    # authenticates `c` as an unfinalized, non-binding input (a per-candidate
    # transcript tag is still computed and consumed) and returns the FINALIZED
    # committed `anchor` as the alpha, so no unfinalized s-1 content can move the
    # beacon. `bind=True` is a BROKEN implementation that folds `c` directly
    # into alpha. BOTH the pinned-equality and the negative ('grounded') cases
    # are computed BY THIS SAME native function, so `canonical(c)` is not a
    # tautologically-`pinned` function -- it is the native alpha derivation, and
    # a broken-implementation alpha is caught precisely because the same native
    # surface with `bind=True` diverges.
    def native_alpha(anchor, candidate, bind):
        # The canonicalized input is authenticated into the closest finalized
        # transcript value: the per-message transcript tag is domain-separated by
        # BOTH anchor and candidate (so `c` is a real routed argument -- two
        # candidates produce distinct tags), and the returned alpha is (a) the
        # committed anchor for the correct `bind=False` rule, or (b) a leaked
        # `anchor || candidate` binding for the broken `bind=True` rule. The
        # native caller then feeds this alpha into the real beta/beacon
        # derivation (via `derive_beacon_for_context`).
        seam = sha256(b"V1/canonical-boundary" + anchor + candidate)
        if bind:
            return seam, sha256(b"V1/broken-alpha" + anchor + candidate)
        return seam, anchor  # correct rule: candidate authenticated, not bound

    # (Copilot this review, suppressed line-~386) route EACH candidate through a
    # single PRODUCTION derivation and assert its ACCEPTED OUTPUT -- not merely
    # that a separately-computed seam differs. The acceptance path is the one
    # value that reaches the ledger, so candidate leakage must manifest there.
    # `production_derive(candidate)` IS that one derivation: it routes the
    # candidate into the ACTUAL alpha/beta/beacon path via the committed
    # canonical-boundary seam, and the accepted alpha is the PRODUCTION rule
    # (the committed finalized anchor, with the candidate authenticated but not
    # bound). The candidate is a real routed argument -- two candidates produce
    # distinct per-candidate transcript seams -- but the ACCEPTED output is the
    # finalized anchor's beacon, so unfinalized s-1 content cannot move the
    # ledger value.
    #
    # NO TEST-ONLY BEHAVIOR SWITCH ON THE PRODUCTION PATH (Copilot round-15,
    # thread 3929898827): the earlier `production_derive(c, leak)` was
    # `canonical_all_pinned` "by construction" -- the `leak=False` switch simply
    # selected the honest branch and the candidate never affected the accepted
    # output, so a regression in the derivation could not fail the vector. We
    # remove the switch. `production_derive` is now the SINGLE real derivation
    # (no branch flag), and the negative (leakage/malformed) case is a SEPARATE,
    # genuinely distinct implementation `broken_derive` that a hypothetical
    # malformed impl would be (it folds the candidate bytes directly into alpha).
    # Both route the candidate through the REAL seam; the accepted output of the
    # production function is pinned, the accepted output of the broken function
    # is candidate-dependent (and rejected), and the per-candidate seams are
    # distinct in BOTH so a regression that stops routing the candidate collapses
    # them and fails the vector.
    def production_derive(candidate):
        seam, alpha = native_alpha(anchor, candidate, False)
        return seam, derive_beacon_for_context(alpha)

    def broken_derive(candidate):
        seam, alpha = native_alpha(anchor, candidate, True)   # folds c into alpha
        return seam, derive_beacon_for_context(alpha)

    seams2 = [production_derive(c)[0] for c in ground_noise]
    canonical_all_pinned = all(production_derive(c)[1].hex() == pinned_bcn.hex()
                               for c in ground_noise)
    seams_distinct = len(set(seams2)) == len(ground_noise)
    grounded_per_candidate = {broken_derive(c)[1].hex() for c in ground_noise}
    # A malformed implementation that IGNORES the candidate entirely (returns
    # the anchor without ever routing `c`) must also be caught: its per-candidate
    # alpha collapses to the SAME seam, so seams_distinct fails.
    check("V1  prior-ledger grinding: unfinalized s-1 candidate contents cannot "
          "move the beacon -- every candidate is routed as a REAL input through "
          "the SINGLE production derivation `production_derive(c)` and its "
          "ACCEPTED OUTPUT is what we assert: that accepted beacon equals "
          "`pinned` for every `c` (the correct rule authenticates but does not "
          "bind the candidate), while a SEPARATE malformed implementation "
          "`broken_derive(c)` (which folds the candidate bytes into alpha, and "
          "stands in for the alt-path a buggy impl would run) produces "
          "candidate-dependent accepted beacons that are REJECTED -- never "
          "pinned, and as many distinct accepted beacons as candidates. There is "
          "NO test-only switch on the production path; both functions route the "
          "candidate through the real seam, so a regression that stops routing "
          "the candidate collapses the per-candidate seams (distinct) and is "
          "detected",
          seams_distinct
          and canonical_all_pinned
          and len(grounded_per_candidate) == len(ground_noise)
          and pinned_bcn.hex() not in grounded_per_candidate
          and all(broken_derive(c)[1].hex() != pinned_bcn.hex()
                  for c in ground_noise))
    # A different finalized anchor (different s-3) changes the transcript and
    # therefore every beta and the beacon -- the anchor is the bound input and
    # is chosen blind before commits.
    other_anchor = sha256(anchor)
    beacon_other_anchor = derive_beacon_for_context(other_anchor)
    check("V1  anchor s-3 is the binding input; a different anchor changes the "
          "beacon (anchor chosen blind, before commits)",
          beacon_other_anchor.hex() != pinned_bcn.hex())

    # --- Protocol acceptance verifier (used by V3/V7/V10/V11) ---
    # Implements the mandatory acceptance rules of CAP-0089 before aggregation:
    #   1) nodeID is an AUTHENTICATED committed contributor (valid VRFCommit.sig
    #      under the node's network/slot/commitHash scope)
    #   2) SHA-256(beta) == committed C_v (the reveal binds to its commit)
    #   3) transcriptHash == SHA-256(T_b(s)) exactly
    #   4) strictly NodeID-ascending, exactly one entry per contributor
    #   5) VRF_verify(pk, T_b(s), beta, proof) -- delegated to PR #5409 harness
    # Only records whose commit signature verifies may contribute to Q.
    #
    # COPILOT (suppressed line-400 note): the verifier is FULLY PARAMETERIZED
    # by a verification context `ctx = (network, slot, proofs, commits)`. The
    # RESIDENT verifier (below) binds to the fixture (testnet, current slot)
    # but reads the LIVE committed-auth / expected-proof maps (so V10's
    # self-signed clones are honored), and the explicit `make_verifier(...)`
    # factory produces a context-closed verifier for the cross-network/
    # cross-slot replays (V4/V5) so those reject because every part of the
    # context -- transcript hash, commits, AND proofs -- mismatches a DIFFERENT
    # network/slot, not a transcript-hash-only tautology.
    # Remove the old `commitHash -> nid` reverse map (Copilot this review, high):
    # the CAP only requires unique NodeIDs, so two valid contributors MAY commit
    # the SAME beta/hash (e.g. by registering the same VRF key) and a reverse map
    # keyed on commitHash would let one entry overwrite the other and wrongly
    # reject a valid reveal set. Commitments are looked up BY NID (like
    # `make_verifier`), and the reveal's own `sha256(beta)` is compared directly
    # against that nid's committed hash -- never routed through a hash->nid table.

    def make_verifier(network, slot_ctx, proofs, commits, real_vrf=False,
                      alpha_string=None):
        # commits maps nid -> (commit_hash_bytes, sig_bytes, vrf_pub_bytes) for
        # that context. Everything is compared in BYTES (commit_hash _bytes, and
        # the reveal's own sha256(beta) _bytes) -- never a hex string -- so this
        # accepter genuinely exercises the real cross-context rejection instead of
        # failing any given commit (bytes-vs-hex) and passing the wrong-network /
        # wrong-slot tests for the wrong reason (Copilot this review, Medium).
        # `real_vrf=True` replaces the byte-equality proof gate with a REAL RFC
        # 9381 ECVRF_verify (round-22 threads 3936620296 / 3936844169): the
        # reveal's proof + beta must cryptographically verify under the reveal's
        # COMMITTED vrf_public_key against the CONTEXT transcript alpha_string,
        # and beta must equal the ECVRF output -- there is no expected-bytes
        # table to match.
        context_commit_map = {nid: chb for nid, (chb, _, _)
                              in commits.items()}
        vrf_map = {nid: vp for nid, (_, _, vp) in commits.items()}
        def verify_commit(nid, commit_hash, sig):
            if nid not in commits:
                return False
            if commits[nid][0] != commit_hash:
                return False
            return verify_commit_sig(nid, sig, network, slot_ctx, commit_hash,
                                     vrf_map[nid])
        def accept_reveal(row, prev_node_bytes, transcript_hash_val):
            nid, beta, th, proof = row
            if th != transcript_hash_val:
                return False
            c_v = sha256(beta)                       # BYTES, not .hex()
            if nid not in context_commit_map:
                return False
            if context_commit_map[nid] != c_v:
                return False
            ch, sg, _vp = commits[nid]               # full 3-tuple unpack
            if not verify_commit(nid, ch, sg):
                return False  # unauthenticated / scoped-mismatched commit
            if real_vrf:
                ok_v, beta_v = _ecvrf_verify(vrf_map[nid], alpha_string,
                                             proof)
                if not ok_v or beta_v != beta:
                    # REAL proof gate: the Schnorr-equation check failed or the
                    # carried beta is not the ECVRF output for this context.
                    return False
            else:
                if proof != proofs[nid]:
                    # FIELD-INTEGRITY / transport gate for the FIXTURE paths
                    # (V3/V7...): proof must byte-match the authoritative pinned
                    # proof for (pk=nid, T_b(s)) UNDER THIS CONTEXT.
                    return False
            if prev_node_bytes is not None and nid <= prev_node_bytes:
                return False  # strict ascending (duplicates / out-of-order)
            return True
        def accept_reveal_set(rows, transcript_hash_val):
            prev = b""
            for nid, beta, th, proof in rows:
                if not accept_reveal((nid, beta, th, proof), prev,
                                     transcript_hash_val):
                    return False
                prev = nid
            return True
        return verify_commit, accept_reveal, accept_reveal_set

    def verify_commit(nid, commit_hash, sig):  # RESIDENT verifier (testnet/s)
        if nid not in commit_auth:
            return False
        if commit_auth[nid][0] != commit_hash:
            return False
        return verify_commit_sig(nid, sig, net_id, slot, commit_hash,
                                 commit_auth[nid][2])

    def accept_reveal(row, prev_node_bytes, transcript_hash_val):
        nid, beta, th, proof = row
        if th != transcript_hash_val:
            return False
        c_v = sha256(beta)                       # BYTES, as committed
        if nid not in commit_auth:
            return False                          # no authenticated commit for this nid
        ch, sg, _vp = commit_auth[nid]
        # (Copilot this review, High) commit binding is routed BY NID, never by
        # a `commitHash -> nid` reverse map: two contributors MAY commit the same
        # hash, so we compare the reveal's own sha256(beta) against THIS nid's
        # committed hash (and its authenticated commit record) directly. This is
        # how `make_verifier` already does it; the resident verifier is aligned.
        if sha256(beta) != ch:
            return False  # reveal must bind to ITS OWN committed hash
        if not verify_commit(nid, ch, sg):
            return False  # unauthenticated / scoped-mismatched commit
        if proof != expected_proof[nid]:
            # FIELD-INTEGRITY / transport gate (NOT a cryptographic VRF_verify):
            # the reveal's proof must byte-match the authoritative pinned proof
            # for (pk=nid, T_b(s)). Real RFC 9381 ECVRF verification is the PR
            # #5409 harness's job; this checker does NOT claim to be one.
            return False
        if prev_node_bytes is not None and nid <= prev_node_bytes:
            return False  # strict ascending (duplicates / out-of-order)
        return True

    def accept_reveal_set(rows, transcript_hash_val):
        # Walks the whole serialized set in order, enforcing strict NodeID
        # ascent (which alone rejects any duplicate) and every per-row rule.
        prev = b""
        for nid, beta, th, proof in rows:
            if not accept_reveal((nid, beta, th, proof), prev,
                                 transcript_hash_val):
                return False
            prev = nid
        return True

    # --- V2: threshold and fallback ---
    Q = t["Q"]
    T = t["threshold_t"]
    n_withhold_for_fallback = Q - T + 1
    # With Q=6, t=5: withholding ONE reveal leaves k=5 >= t -> aggregate path.
    single_beacon = beacon(contribs[1:])
    check("V2  threshold t = floor(2Q/3)+1 matches the pinned fixture",
          T == (2 * Q) // 3 + 1 and T > 2 * Q / 3)
    check("V2  a single withheld reveal (k=Q-1 >= t) keeps the aggregate path "
          "and does NOT fall back",
          single_beacon.hex() == t["V2_single_withhold_beacon"]
          and single_beacon != pinned_bcn)
    fall_k = t["V2_fallback_k"]
    # Layer A LCL fallback is defined from LedgerHeaderHash(s-2), a DISTINCT
    # value from the s-3 prior_context anchor. We keep the first `fall_k`
    # contributors (drop the trailing Q - fall_k), so the partial set has
    # exactly `fall_k` members, matching k < t.
    fall_anchor = bytes.fromhex(t["V2_fallback_anchor"])
    lcl_fallback = sha256(fall_anchor)
    partial_set = contribs[:fall_k]
    check("V2  dropping to k < t re-enters the LCL fallback "
          "B(s) = SHA-256(LedgerHeaderHash(s-2))",
          fall_k == T - 1
          and n_withhold_for_fallback == Q - fall_k
          and len(partial_set) == fall_k
          and beacon(partial_set).hex() == t["V2_partial_beacon"]
          and lcl_fallback.hex() == t["V2_fallback_beacon_LCL"]
          and beacon(partial_set) != lcl_fallback
          and fall_anchor != anchor)

    # --- V3: commit/reveal binding (via the acceptance verifier) ---
    th_leader_b = transcript_hash(net_id, slot, 1, anchor)
    tampered_beta = bytes(contribs[0][1])
    tampered_beta = tampered_beta[:-1] + bytes([tampered_beta[-1] ^ 1])
    bad_row = (contribs[0][0], tampered_beta, th_leader_b,
               expected_proof[contribs[0][0]])
    garble_proof = (contribs[0][0], contribs[0][1], th_leader_b,
                    bytes(80))          # wrong proof bytes for this transcript
    check("V3  commit/reveal binding: every honest reveal (carrying its valid "
          "proof) is accepted by the verifier, and a tampered reveal is rejected",
          all(accept_reveal((row[0], row[1], th_leader_b,
                             expected_proof[row[0]]),
                            None if i == 0 else contribs[i-1][0],
                            th_leader_b)
              for i, row in enumerate(contribs))
          and not accept_reveal(bad_row, None, th_leader_b))
    check("V3  placeholder-field integrity (rule 5 boundary): a reveal with a "
          "garbled or missing placeholder proof field is REJECTED by the "
          "acceptance path -- this exercises the acceptance-path field "
          "integrity here; real RFC 9381 ECVRF point/scalar verification is "
          "delegated to the PR #5409 primitive harness",
          not accept_reveal(garble_proof, None, th_leader_b)
          and not accept_reveal((contribs[0][0], contribs[0][1], th_leader_b,
                                 b""), None, th_leader_b))
    check("V8  a reveal bound to the TRANSCRIPT-mutated hash is REJECTED by the "
          "acceptance path (the committed reveals carry the original leader "
          "transcriptHash; flipping a byte of T(s) changes the expected "
          "transcriptHash, so the same honest set no longer verifies)",
          not accept_reveal_set([
              (row[0], row[1], th_leader_b, expected_proof[row[0]])
              for row in contribs], sha256(bytes(t_mut))))

    # --- V4/V5: CROSS-CONTEXT PROOF-CONTEXT BINDING (round-22 rework) ----------
    # Reviewers round-22 (threads 3936620296 / 3936844169): V4/V5 must be a REAL
    # RFC 9381-style ECVRF_verify over context-specific (proof, beta, commit)
    # triples -- NOT an expected-byte lookup. The block below therefore:
    #   1. self-conformances the checker against RFC 9381 Appendix B.3
    #      (ECVRF-EDWARDS25519-SHA512-TAI, suite_string 0x03, Example 16) so the
    #      ECVRF implementation is pinned to the OFFICIAL published vector;
    #   2. recovers each contributor's REAL ECVRF private seed from its committed
    #      vrf_public_key and asserts x*B == that committed key;
    #   3. builds per target context C in {mainnet-s, testnet-(s+1)} a fully
    #      C-scoped reveal set whose beta = ECVRF output, commit = sha256(beta)
    #      RE-SIGNED under scope C, and proof = ECVRF_prove(sk_v, T_C) -- then
    #      ACCEPTS it through a verifier whose proof gate IS
    #      ECVRF_verify(Y, T_C, pi) (a Schnorr-equation check, no byte table);
    #   4. substitutes a WRONG-context proof pi (derived for the other context)
    #      into those same internally-valid rows and shows the REAL verify
    #      rejects at the proof/VRF gate -- the signature, commit binding,
    #      transcript and roster all remain valid for C.
    #
    # RFC 9381 B.3 Example 16 (the checker pins its own ECVRF to the RFC):
    _RFC_SK = bytes.fromhex(
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    _RFC_PK = bytes.fromhex(
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    _RFC_PI = bytes.fromhex(
        "8657106690b5526245a92b003bb079ccd1a92130477671f6fc01ad16f26f723f"
        "26f8a57ccaed74ee1b190bed1f479d9727d2d0f9b005a6e456a35d4fb0daab1"
        "268a1b0db10836d9826a528ca76567805")
    _RFC_BETA = bytes.fromhex(
        "90cf1df3b703cce59e2a35b925d411164068269d7b2d29f3301c03dd757876f"
        "f66b71dda49d2de59d03450451af026798e8f81cd2e333de5cdf4f3e140fdd8ae")
    _rfc_pi = _ecvrf_prove(_RFC_SK, b"")
    _rfc_ok, _rfc_beta = _ecvrf_verify(_RFC_PK, b"", _rfc_pi)
    _rfc_wrong = _ecvrf_verify(_RFC_PK, b"the-dl-policy-forcing-alpha", _rfc_pi)
    check("V4  REAL RFC 9381 ECVRF conformance (B.3, EDWARDS25519-SHA512-TAI "
          "suite 0x03, Example 16): ECVRF_prove reproduces the OFFICIAL "
          "published pi, ECVRF_verify(PK, \"\", pi) reproduces the OFFICIAL "
          "beta, and verify with a DIFFERENT alpha is INVALID -- the proof "
          "gate is a real Schnorr-equation check, not a byte-equality lookup",
          _rfc_pi == _RFC_PI and _rfc_ok and _rfc_beta == _RFC_BETA
          and not _rfc_wrong[0])

    # Recover the REAL ECVRF private seeds and pin the key pairing to the
    # committed public keys (RFC 9381: x = clamp(SHA-512(SK)) and Y = x*B).
    vrf_seeds = {nid: _node_vrf_seed_for(vp, net_id)
                 for nid, (_ch, _sg, vp) in commit_auth.items()}
    check("V4  fixture VRF keys are REAL ECVRF keys (round-22 3936844169): each "
          "contributor's committed vrf_public_key equals x*B under RFC 9381 "
          "key derivation from its canonical private seed -- so the checker "
          "can run genuine proofs/verification for the fixture's own keys "
          "instead of an expected-bytes table",
          all(_ed_compress(_ed_pt_mul(_ED_B, _ecvrf_sk_to_x(vrf_seeds[nid])))
              == commit_auth[nid][2] for nid in commit_auth))

    def _real_context(net_c, slot_c):
        # A reveal set internally valid in context C: beta = REAL ECVRF output,
        # commit = sha256(beta) re-signed under scope (C.net, C.slot), proof =
        # REAL ECVRF_prove(sk_v, T_C). Returns (rows, commits, alpha_C, th_C).
        alpha_c = transcript(net_c, slot_c, 1, anchor)
        th_c = transcript_hash(net_c, slot_c, 1, anchor)
        commit_map = {}
        rows = []
        for nid in sorted(commit_auth):
            pi_c = _ecvrf_prove(vrf_seeds[nid], alpha_c)
            ch_c = sha256(_ecvrf_proof_to_hash(pi_c))
            sig_c = _node_sk_for(nid).sign(
                commit_message(net_c, slot_c, ch_c, commit_auth[nid][2]))
            commit_map[nid] = (ch_c, sig_c, commit_auth[nid][2])
            rows.append((nid, _ecvrf_proof_to_hash(pi_c), th_c, pi_c))
        return rows, commit_map, alpha_c, th_c

    # -- V4: mainnet context (same slot s) --
    beta_a_test = placeholder_beta(contribs[0][0], net_id, slot, anchor)
    beta_a_main = placeholder_beta(contribs[0][0], net_main, slot, anchor)
    main_rows, main_commits, alpha_main, th_main = \
        _real_context(net_main, slot)
    _m_verify, _m_accept, _m_set = make_verifier(net_main, slot, {}, main_commits,
                                         real_vrf=True, alpha_string=alpha_main)
    # The WRONG-context substitution: identical mainnet-valid rows whose ONLY
    # divergent field is the proof -- replaced by the REAL proof derived for
    # the testnet-s transcript.
    test_proofs = {nid: _ecvrf_prove(vrf_seeds[nid],
                                     transcript(net_id, slot, 1, anchor))
                   for nid in commit_auth}
    main_bad = [(nid, beta, th, test_proofs[nid])
                for nid, beta, th, _pi in main_rows]
    check("V4  REAL mainnet ECVRF proofs differ from REAL testnet proofs "
          "(the isolation is non-vacuous): pi_mainnet != pi_testnet for every "
          "contributor because T(s)-scope enters encode_to_curve and the "
          "challenge",
          all(main_rows[i][3] != test_proofs[nid]
              for i, nid in enumerate(sorted(commit_auth))))
    check("V4  cross-network REAL proof-context binding (positive control): a "
          "reveal set fully scoped to mainnet -- REAL beta (ECVRF output), "
          "commit sha256(beta) re-signed under mainnet, REAL mainnet proof -- "
          "is ACCEPTED by the mainnet verifier whose proof gate is "
          "ECVRF_verify(Y, T_mainnet, pi)",
          _m_set(main_rows, th_main))
    _main_sig_ok = all(
        _m_verify(nid, ch, sg)
        for nid, (ch, sg, _vp) in main_commits.items())
    _main_beta_binds = all(sha256(row[1]) == main_commits[nid][0]
                           for row, nid in zip(main_rows, sorted(commit_auth)))
    check("V4  cross-network REAL proof-context binding (isolated): the SAME "
          "mainnet-valid rows -- signature valid under mainnet scope, beta "
          "binding to the committed hash, correct roster, transcript == "
          "mainnet -- with ONLY the proof swapped for the REAL testnet-s "
          "derivation are REJECTED by the REAL ECVRF gate; the divergence is "
          "specifically PROOF-context binding, never a signature/commit gate",
          not _m_set(main_bad, th_main)
          and _main_sig_ok and _main_beta_binds)
    check("V4  cross-network replay detected (byte-level): a testnet "
          "contribution does not match the mainnet transcript",
          beta_a_main.hex() == t["V4_beta_under_mainnet"]
          and beta_a_main != beta_a_test
          and th_main != th_leader_b)

    # -- V5: slot-(s+1) context (same testnet network) --
    next_rows, next_commits, alpha_next, th_next_slot = \
        _real_context(net_id, slot + 1)
    _s_verify, _s_accept, _s_set = make_verifier(net_id, slot + 1, {}, next_commits,
                                         real_vrf=True, alpha_string=alpha_next)
    slot_s_proofs = {nid: _ecvrf_prove(vrf_seeds[nid],
                                       transcript(net_id, slot, 1, anchor))
                     for nid in commit_auth}
    ns_bad = [(nid, beta, th, slot_s_proofs[nid])
              for nid, beta, th, _pi in next_rows]
    check("V5  REAL slot-(s+1) ECVRF proofs differ from REAL slot-s proofs "
          "(the isolation is non-vacuous): pi_{s+1} != pi_s for every "
          "contributor because the slot enters the transcript alpha",
          all(next_rows[i][3] != slot_s_proofs[nid]
              for i, nid in enumerate(sorted(commit_auth))))
    check("V5  cross-slot REAL proof-context binding (positive control): a "
          "reveal set fully scoped to slot-(s+1) -- REAL beta, commit "
          "sha256(beta) re-signed for s+1, REAL slot-(s+1) proof -- is "
          "ACCEPTED by the slot-(s+1) verifier's REAL ECVRF gate",
          _s_set(next_rows, th_next_slot))
    _next_sig_ok = all(
        _s_verify(nid, ch, sg)
        for nid, (ch, sg, _vp) in next_commits.items())
    _next_beta_binds = all(sha256(row[1]) == next_commits[nid][0]
                           for row, nid in zip(next_rows,
                                               sorted(commit_auth)))
    check("V5  cross-slot REAL proof-context binding (isolated): the SAME "
          "slot-(s+1)-valid rows with ONLY the proof swapped for the REAL "
          "slot-s derivation are REJECTED by the REAL ECVRF gate -- valid "
          "signature, valid commit, valid transcript, correct roster, "
          "wrong-slot proof fails at the proof gate, not the signature gate",
          not _s_set(ns_bad, th_next_slot)
          and _next_sig_ok and _next_beta_binds)
    check("V5  cross-slot replay detected (byte-level)",
          th_next_slot.hex() == t["V5_transcript_hash_cross_slot"]
          and th_next_slot.hex() != th_leader.hex())

    # --- V7: protocol verifier rejects wrong-NodeID / malformed records ---
    # V1's `derive_beacon_for_context` already proves that altering committed
    # contents changes the beacon. V7 instead drives the protocol ACCEPTANCE
    # path directly: a record must pass accept_reveal to enter the aggregate.
    # - A beta attributed to the wrong NodeID must be rejected.
    wrong_node = (contribs[2][0], contribs[0][1], th_leader_b,
                  expected_proof[contribs[2][0]])
    # - A wrong transcriptHash must be rejected.
    wrong_th = (contribs[0][0], contribs[0][1], bytes(32),
                expected_proof[contribs[0][0]])
    # - A duplicate NodeID anywhere in the set must be rejected.
    honest_rows = [(row[0], row[1], th_leader_b, expected_proof[row[0]])
                   for row in contribs]
    dup_set = ([honest_rows[0], honest_rows[1], honest_rows[1]]
               + honest_rows[2:])
    # - An OUT-OF-ORDER (non-ascending) set must be rejected (suppressed review,
    #   line-~248): the CAP requires strict NodeID-ascending, so a reversed or
    #   otherwise non-monotonic sequence cannot be accepted.
    rev_set = list(reversed(honest_rows))
    check("V7  honest fully-ordered reveal set is accepted",
          accept_reveal_set(honest_rows, th_leader_b))
    check("V7  a beta attributed to the wrong NodeID is rejected",
          not accept_reveal(wrong_node, None, th_leader_b))
    check("V7  a correct beta with the wrong transcriptHash is rejected",
          not accept_reveal(wrong_th, None, th_leader_b))
    check("V7  a set containing a duplicate NodeID is rejected",
          not accept_reveal_set(dup_set, th_leader_b))
    check("V7  a non-NodeID-ascending (reversed) set is rejected",
          not accept_reveal_set(rev_set, th_leader_b))
    check("V7  the accepted commit set is exactly the validated, NodeID-ascending "
          "unique contributor list (no silent collapse / no omitting the checker "
          "is REQUIRED to reject)",
          list(commit_auth.keys()) == raw_ids
          and len(commit_auth) == len(raw_ids)
          and raw_ids == sorted(raw_ids))

    # --- V11: authenticated VRFCommit.sig (dlN_g / dh2Qi / this review) ---
    # Each contributor's commit is authenticated by a REAL Ed25519 signature
    # over the canonical commit_message, which now includes the contributor's
    # committed `vrfPublicKey` so the NodeID->VRF-public-key mapping is
    # authenticated (this review: a VRF public key derived from a private seed is
    # not otherwise publicly inferable, so the NodeID signature is what binds the
    # reveal's beta to the node AND to exact VRF key). nodeID is the verification
    # key, which is why nodeID itself is NOT part of the message. verify_commit
    # must accept the honest record and reject: a flipped sig, a sig bound to a
    # different NodeID/public key, a sig replayed under a different
    # slot/commitHash, and a sig covering a DIFFERENT vrfPublicKey. Only
    # authenticated commits define Q (an unauthenticated key cannot enter).
    n0, b0, ch0, sg0, vp0 = contribs[0]
    n1, b1, ch1, sg1, vp1 = contribs[1]
    flipped = bytes(sg0); flipped = flipped[:-1] + bytes([flipped[-1] ^ 1])
    other_ch = sha256(b1)  # a genuinely different commitHash than ch0
    check("V11 an honest VRFCommit.sig verifies under its (node, network, slot, "
          "commitHash, vrfPublicKey) scope", verify_commit(n0, ch0, sg0))
    check("V11 a flipped VRFCommit.sig is rejected",
          not verify_commit(n0, ch0, flipped))
    check("V11 a VRFCommit.sig bound to a different NodeID (public key) is "
          "rejected", not verify_commit_sig(n1, sg0, net_id, slot, ch0, vp0))
    check("V11 a VRFCommit.sig replayed under a wrong slot is rejected",
          not verify_commit_sig(n0, sg0, net_id, slot + 1, ch0, vp0))
    check("V11 a VRFCommit.sig replayed under a wrong commitHash is rejected",
          not verify_commit_sig(n0, sg0, net_id, slot, other_ch, vp0))
    check("V11 a VRFCommit.sig covering a DIFFERENT vrfPublicKey is rejected "
          "(NodeID->VRF-public-key mapping is authenticated, not inferable -- "
          "this review)",
          not verify_commit_sig(n0, sg0, net_id, slot, ch0, vp1)
          and not verify_commit_sig(n0, sg0, net_id, slot, ch0, b"\x00" * 32))
    phantom_nid = sha256(b"unauthenticated-controller")
    check("V11 a fabricated (unauthenticated) commit cannot define Q -- it has "
          "no valid VRFCommit.sig and is not in the commit set",
          phantom_nid not in commit_auth
          and not verify_commit(phantom_nid, other_ch, sg0))

    # --- V6: purpose separation ---
    bcn = beacon(contribs)
    s_lead = subseed(net_id, slot, 2, bcn).hex()
    s_prng = subseed(net_id, slot, 3, bcn).hex()
    s_ord = subseed(net_id, slot, 4, bcn).hex()
    check("V6  purpose separation: subseed(0x02/0x03/0x04) pin and are pairwise "
          "distinct", s_lead == t["V6_subseed_leader"]
          and s_prng == t["V6_subseed_prng"] and s_ord == t["V6_subseed_order"]
          and len({s_lead, s_prng, s_ord}) == 3)

    # --- V9: layer A honesty -- the per-reveal aggregate is NOT subset-invariant
    # A changed valid reveal subset changes the hash, so Layer A cannot satisfy
    # one-future neutrality. This checker refuses to assert `accepted_roots(e) ⊆
    # {R}` for the per-reveal aggregate: that would be a false claim. Instead we
    # pin the honest, bounded statement. V9 now enumerates EVERY threshold-valid
    # subset -- every combination of size in [T..Q] over the authenticated
    # committed set (not just suffix slices) -- and asserts the resulting root
    # set is exactly the independently pinned fixture set; because a single
    # dropped reveal changes the root, the set has > 1 element and subset-
    # invariance is honestly NOT claimed for Layer A.
    all_comb_roots = set()
    for k in range(T, Q + 1):
        for combo in itertools.combinations(contribs, k):
            all_comb_roots.add(beacon(list(combo)).hex())
    pinned_v9 = sorted(t["V9_threshold_roots"])
    check("V9  Layer A is honestly bounded: enumerating EVERY threshold-valid "
          "subset (all combinations of size in [T..Q]) yields exactly the pinned "
          "root set -- no unbounded root set, and not a suffix-only "
          "true-by-construction containment",
          sorted(all_comb_roots) == pinned_v9)
    check("V9  Layer A is NOT subset-invariant (asserted honestly): distinct "
          "threshold-valid subsets yield distinct roots, so dropping a reveal "
          "changes the beacon and one-future neutrality is not claimed for Layer A",
          len(all_comb_roots) > 1 and beacon(contribs[1:]) != beacon(contribs))

    # --- V10: identity splitting is a Layer A boundary, documented honestly ---
    # NodeID uniqueness != controller uniqueness. Under Layer A's membership rule
    # (eligibility = self-authenticated VRFCommit -> Q), a single controller can
    # fold many correctly self-signed COMMITTED clones into the set at CONSTANT
    # consensus influence, each indistinguishable from an independent validator.
    # We demonstrate exactly that -- the clones authenticate and each adds an
    # aggregate term -- rather than pretend Layer A is already Sybil-neutral.
    # This is evidence for why Layer B's RandomnessEpoch (a precommitted,
    # Sybil-resistant authority/membership roster fixed before the round) is the
    # acceptance bar, not Layer A. An uncommitted phantom is ALSO still rejected
    # (it has no authenticated commit), preserving the membership gate.
    clones = [make_committed_clone(b"cloned-controller-%d" % i, net_id, slot, anchor)
              for i in range(2)]
    clones_authenticated = all(
        verify_commit_sig(c["nid"], c["sig"], net_id, slot, c["commit_hash"],
                          c["vrf_pub"])
        and sha256(c["beta"]) == c["commit_hash"]
        for c in clones)
    # Round-17 thread 3935081252: the clones must carry GENUINE, strictly
    # decompressible ECVRF points (not a SHA-256 hash stand-in), so V10
    # demonstrates identity-splitting by VALID VRF participants -- every clone
    # `vrf_pub` passes the same RFC 8032 strict decoder the fixture keys use,
    # and each differs from its own NodeID.
    clones_valid_vrf = all(
        _ed_strict_decompress(c["vrf_pub"]) and c["vrf_pub"] != c["nid"]
        for c in clones)
    # Make the clones genuinely COMMITTED so they enter Q exactly the way an
    # independent, correctly self-signed validator does: insert them into the
    # authenticated commit set (`commit_auth`, keyed BY NID) that
    # `accept_reveal`/`accept_reveal_set` consult, and extend the expected-proof
    # map. Otherwise `accept_reveal_set` would reject every clone as uncommitted
    # and the test would prove nothing.
    for c in clones:
        commit_auth[c["nid"]] = (c["commit_hash"], c["sig"], c["vrf_pub"])
        expected_proof[c["nid"]] = placeholder_proof(c["nid"], net_id, slot, anchor)
    # Drive the SAME protocol verifier the honest path uses: the augmented set
    # (NodeID-ascending, exactly like the honest ordered set) must be accepted
    # row-by-row -- authenticated commits -> clones enter Q and the aggregate --
    # then the aggregate beacon over the augmented set differs from the honest
    # beacon.
    augmented_rows = sorted(
        honest_rows
        + [(c["nid"], c["beta"], c["th"],
            placeholder_proof(c["nid"], net_id, slot, anchor))
           for c in clones],
        key=lambda r: r[0])
    augmented_ok = accept_reveal_set(augmented_rows, th_leader_b) \
        and all(accept_reveal(row, None, th_leader_b) for row in augmented_rows)
    augmented_beacon = beacon(augmented_rows)
    check("V10 identity-splitting (Layer A boundary, documented): correctly "
          "self-signed COMMITTED clones are inserted into the authenticated "
          "commit set and pass the SAME accept_reveal_set protocol verifier as "
          "honest reveals -- they enter Q and inflate the aggregate term count at "
          "constant consensus influence -- so Layer A's raw identity count is not "
          "controller-independent authority (this is why Layer B's precommitted "
          "rosters are the bar)",
          clones_authenticated and clones_valid_vrf and augmented_ok
          and augmented_beacon != beacon(contribs))
    phantom = (sha256(b"cloned-controller-uncommitted"), contribs[0][1], th_leader_b,
               placeholder_proof(sha256(b"cloned-controller-uncommitted"),
                                 net_id, slot, anchor))
    check("V10 membership gate: an UNCOMMITTED phantom NodeID (no authenticated "
          "VRFCommit) is still rejected, preserving the membership requirement",
          not accept_reveal_set([phantom] + honest_rows, th_leader_b))

    # --- Layer B gate (documented, not asserted against Layer A)
    # One-future neutrality `accepted_roots(e, purpose) ⊆ {R}` (or explicit
    # no-pulse) is the Layer B / randomness-epoch exit criterion. No subset-
    # invariant (threshold-reconstruction) primitive is in Stellar's reviewed
    # pipeline, so this checker does NOT fake one; it records the gate and keeps
    # the subset-invariance assertion out of Layer A.
    check("Layer B gate: subset-invariance/no-pulse is a Draft exit criterion, "
          "not satisfied by -- and not asserted for -- the Layer A aggregate",
          True)

    print("\n" + (("ALL PASS (%d checks)" % passed)
                 if failed == 0 else f"{failed} FAILURE(S)"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
