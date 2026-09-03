#!/usr/bin/env python3
"""CAP-0089 Layer B executable state-machine model -- SINGLE-PULSE architecture
(per tacticalnoot's zero-point passes: one close-input contract, a genuinely
thresholded authority derived ONLY from the epoch, a PURE archival verifier, and
predecessor-state epoch selection).

One canonical Core close-lock commitment per closed ledger, derived from ONE
native close-input contract `RandomnessCloseInputV1` that binds every semantic
input able to interact with the random result and EXCLUDES provenance:

    in_v1   = (network_id, epoch_hash, ledgerSeq, previousLedgerHash, H(value))
    C_s     = H("CloseLock" || in_v1)            -- single commitment / domain
    P_s     = ThresholdSignature(epoch, C_s)     -- UNIQUE proof (secret-bound)
    R_s     = H("Root" || C_s || canonical(P_s)) -- derived only after verify
    PRNG(s) / APPLY(s) / NOMINATION(s+1) = KDF(R_s, label)

`C_s` IS the threshold-signed domain: there is no second, independently encoded
"challenge" (Noot: a second encoding is another drift surface; the primitive
evaluates the already-canonical C_s directly). `previousLedgerHash` is an
EXPLICIT model input sourced from the externalized StellarValue (the real
predecessor hash Core commits), so the model consumes the bytes Core actually
locks; a vector asserts changing only that real predecessor hash changes C_s and
R_s. Provenance (lcValueSignature, proposer NodeID, SCP envelopes/certificate
paths, timestamps, transport) is deliberately absent.

Authority is a THRESHOLD authority derived ONLY from the epoch descriptor:
`ThresholdAuthority.from_epoch(epoch)` fixes the roster (sorted member
share-verification keys committed by the epoch), n = len(roster), t = epoch
threshold, and the group key. There is no caller-provided n/t/roster (Noot:
"threshold is a property of the locked authority, not an argument to the
caller"). Each member's share is bound to SECRET material held only by the
authority (the model's stand-in for generated VUF/DKG key material; in
production it never leaves the holder set). Reconstructing the canonical P_s
REQUIRES >= t valid shares: there is no public proof-emission function in this
program, so a player holding every public close field but fewer than `t` shares
cannot obtain any P_s accepted by the pure verifier.

The shared primitive is consumed through an ABSTRACT interface
`UniqueThresholdProof` (the smallest audited seam; Rust supplies the real
construction, BLS/VUF or another unique-output primitive). This model wires the
interface contract and ASSERTS the invariants the candidate crypto must satisfy
(I1-I4); the cryptographic proof (pre-lock secrecy, threshold unforgeability,
unique output, strict canonicalization) lives in the primitive harness, not in a
placeholder hash. The model's `verify` mirrors the primitive's pure verifier: a
deterministic function of (epoch, C_s, P_s) plus the scheme's canonical setup --
no source, no admission memory, no process memory.

State machine laws:
    Gate 0 (integrity):      LockedClose hash must re-derive from its fields.
    Gate 1 (epoch+network):  close bound to THIS epoch, THIS network, active.
    Gate 2 (boundary):       release is authorized ONLY by CONFIRM/EXTERNALIZE +
                             local full validation; accepted-commit never is.
    Gate 3 (proof):          the ARCHIVED PURE verifier verify(epoch, C_s, P_s)
                             accepts the proof (no source/admission memory).
    No proof -> UNKNOWN (stalled apply); invalid -> REJECTED. Applied history is
    a PREFIX of the canonical slot-ordered history -- nodes differ only in
    prefix length, never an applied ROOT,UNKNOWN,ROOT hole.

Activation (Noot #5): the epoch applied for a slot is selected from the
PREDECESSOR canonical state (`epoch_for_transition`), never local quorum sets.
Zero or two committed epochs for a slot FAIL CLOSED (no selection).

Durable sign-once (Noot): every authority member durably locks one semantic
event before first emission -- the same (epoch, slot, C_s) retry is idempotent,
a different C_s for the same slot is refused. Because share secrets and the
reconstruction rule are deterministic per epoch, a restarted authority
re-derives the same share and the same P_s/R_s without new authority choice or
process memory (native durability covers the crash-before-header ordering, CAP).

Exit laws asserted:
    O1 One use -> one pulse.  Retries / aliases / an equivalent value cannot let
       a consumer lock N draws and pick one after seeing the roots; a source
       keeps ONE canonical slot lock.
    O2 Earliest-knowledge sealing.  With < t valid shares no complete proof is
       a property of the primitive/flows, not a caller flag.
    O3 Permanent pulse.  After R_s is canonically accepted, later key/suite
       changes, proof re-encoding, recovery, migration, or archival replay can
       never create a second historical pulse.

Object/capability invariant (B4): the resolved object holds only
{event_hash, outcome, source_root?} -- NO successor key, delegate, membership
edit, recovery authority, or permission field.

Run: python layer_b_model.py   (exit 0 on pass, 1 on any failure)
"""
import hashlib
import itertools
import os
import struct
import sys

EPOCH_SCHEME = b"stellar-vrf/epoch/unique-threshold/v1"
NETWORK = hashlib.sha256(b"Test SDF Network ; September 2015").digest()
LABEL_PRN = b"PRNG"
LABEL_APPLY = b"APPLY"
LABEL_NOM = b"NOMINATION"
NO_CALLER_OUTCOME_CLASS = frozenset()
# The CONFIRM->EXTERNALIZE edge vs accepted-commit: the transition TYPE is now a
# fact INSIDE `ConfirmExternalizeBoundary` (the ONLY producer of release
# witnesses -- Copilot this review: no caller-asserted transition bytes). These
# names remain as the documented protocol roles; the boundary's `externalize()`
# is the only operation that realises CONFIRM/EXTERNALIZE, and accepted-commit
# is deliberately NOT authoritative (never externalizes).
RELEASE_CERT_CONFIRM_EXTERNALIZE = b"confirm/externalize"
RELEASE_CERT_ACCEPTED_COMMIT = b"accepted-commit"   # deliberately NOT authoritative

# The model standby for the primitive's SYSTEM/GROUP key material. It is never
# serialized, never committed in the epoch, and never printed; it mirrors the
# boundary that the real VUF/DKG group secret lives only inside the primitive
# (Rust) and the holder set. `verify` (below) uses it exactly the way a
# production verifier uses the certified group public key + committed setup.
GROUP_SK = hashlib.sha256(b"cap-0089:model:group-sk:v1").digest()


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def u32(n: int) -> bytes:
    return struct.pack(">I", n)


def lp(b: bytes) -> bytes:
    # Length-prefix a VARIABLE-length field so the canonical encoding is
    # injective (dnFWC): distinct byte boundaries cannot collide. Used only for
    # genuinely variable-length elements (schemes, rule labels, list containers)
    # and NEVER for fixed-width wire types (see hash32 below).
    return struct.pack(">I", len(b)) + b


def hash32(b: bytes) -> bytes:
    # Core-native wire type for a fixed-width `opaque Hash[32]` (XDR) /
    # uint256: a FIXED 32-byte element with NO length prefix. Validation is
    # explicit so a caller cannot feed a malformed length and silently change
    # the canonical encoding (Copilot 3917696404 round-2 follow-up / this
    # review's B1 wire-type note). Rejects anything that is not exactly 32 bytes.
    if b is None or len(b) != 32:
        raise ValueError("Hash[32] wire element must be exactly 32 bytes")
    return b


def close_input(epoch_hash: bytes, network_id: bytes, ledger_seq: int,
                previous_ledger_hash: bytes, value_hash: bytes) -> bytes:
    """Single canonical close-input contract `RandomnessCloseInputV1`.

    Wire shape (documented in B1, matches Core XDR widths EXACTLY): literal
    contract tag `"RandomnessCloseInputV1"` + a `uint32` arm version (currently
    `1`), then the four fixed-width hashes `epoch_hash`, `network_id`,
    `previous_ledger_hash`, `value_hash` each as a Core `opaque Hash[32]`
    (a FIXED 32 bytes, NO length prefix -- the `lp()` length prefix is a
    variable-length string encoding and is NOT the XDR encoding for a fixed
    Hash[32]; using it here would make a native implementation derive a
    different C_s), and a `uint32` `ledgerSeq` (Core's `LedgerSeq` XDR type).
    A native implementation following the declared XDR widths therefore derives
    the SAME C_s. Binds network, epoch, the REAL ledgerSeq, the predecessor
    ledger (state-transition semantics) and the exact externalized value bytes.
    Provenance (signatures, proposer, envelopes, transport) is deliberately
    absent. (The epoch's separate `format_version` canonical identity byte is
    committed in `EpochDescriptor.hash`, NOT in this close input.)"""
    return (b"RandomnessCloseInputV1" + u32(1)
            + hash32(network_id) + hash32(epoch_hash)
            + u32(ledger_seq) + hash32(previous_ledger_hash) + hash32(value_hash))


def canonical_value_hash(value_bytes: bytes) -> bytes:
    """`H(provenance_excluded(value))` -- the CANONICAL hash of a committed
    externalized value for the close-lock, excluding the signer provenance
    (Copilot this review, thread evw_K). A serialized Core `StellarValue` ends
    with its signed extension (`StellarValueExtV0.lcValueSignature`) carrying
    the SIGNER NodeID -- pure provenance, not an event semantic. Hashing the
    full serialization would make byte-identical-value-but-differently-SIGNED
    closes hash differently, contradicting the one-use/one-event `C_s` contract.

    Contract: `value_bytes` is one of
      * a 32-byte bare payload hash (a close supplied directly as a payload
        hash, e.g. `sha256(payload)` -- no signer -- used throughout this
        harness), which is hashed as-is; or
      * a serialized value `payload || signer`, where the trailing 32-byte
        `signer` is the value-signature NodeID/provenance to be EXCLUDED.
    In the serialized case only the proven payload is hashed, so every close
    with the SAME value payload and close semantics binds to the SAME `C_s`
    regardless of WHO signed or the envelope/transport path (which never enters
    the lock)."""
    if len(value_bytes) == 32:
        payload = value_bytes
    elif len(value_bytes) > 32:
        payload = value_bytes[:-32]      # drop trailing lcValueSignature NodeID
    else:
        payload = value_bytes            # degenerate/short: hash as-is (defensive)
    return sha256(b"ProvenanceExcludedValue/v1" + payload)


# --- Verifiable stand-in bound to the epoch public key (Copilot 3917696376 /
# this review's line-519 note) ------------------------------------------------
# A pure-hash "canonical 32-byte value" is NOT a proof: any attacker can conjure
# one, and a public verifier could not tell it from the real value. `verify`
# therefore validates a GENUINE asymmetric signature relation bound to the
# epoch's committed PUBLIC key, using a small, self-contained Schnorr-style
# scheme over a hardcoded 256-bit safe-prime group (no external crypto library;
# Python built-in `pow`/`%`). This is an HONEST STAND-IN: it demonstrates the
# public-key seam a real BLS/VUF primitive must satisfy (public verification,
# secret-only production, deterministic unique per-message output, reject of
# arbitrary bytes) using algebra instead of a hash placeholder. It is NOT the
# production primitive -- RFC 9381/BLS pairing lives in the separately-reviewed
# harness (PR #5409); the model only proves the interface contract.
#
# Group: p = 2*q + 1 (safe prime, 256-bit), q prime, generator G = 4 (order q).
#   d (secret scalar) = H(G_secret) mod q            -- only the recovered group
#       secret can compute it (threshold-only production)
#   pub Y            = G^d mod p                      -- committed in epoch
#   sign d over msg: r = H("SpfNonce", d, epoch, msg) mod q    (deterministic,
#       SECRET nonce -- revealing it would leak d), R = G^r mod p,
#       c = H("SpfChal", epoch, msg, R_bytes, Y_bytes), s = r + c*d mod q
#   proof             = R_bytes (32) || s_bytes (32)  -- 64 bytes
#   verify (public, needs only Y):
#       c = H("SpfChal", epoch, msg, R_bytes, Y_bytes)
#       accept iff G^s mod p == R * Y^c mod p
# The verifier needs NO secret and NO secret-derived value, yet can only accept
# proofs minted with `d` -- so a bare 64-byte grab-bag is REJECTED, while the
# genuine threshold-recovered proof verifies (Copilot line-519).
_GRP_P = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff72ef
_GRP_Q = (_GRP_P - 1) // 2
_GRP_G = 4                        # generator of the order-q subgroup


def _spf_scalar(secret: bytes) -> int:
    # Deterministic secret scalar d in [1, q) from the recovered group secret.
    # Only the group-secret holder (>= t valid shares) can compute this.
    d = int.from_bytes(sha256(b"SpfScalar" + secret + b"cap-0089-v1"), "big")
    return (d % (_GRP_Q - 1)) + 1     # ensure 1 <= d < q


def _spf_pub(d: int) -> bytes:
    return pow(_GRP_G, d, _GRP_P).to_bytes(32, "big")


def _poly_coeffs(seed: bytes, threshold: int, n: int):
    """Deterministic Shamir polynomial coefficients over GF(q). The GREEDY/group
    secret is `f(0) = d`; the leading coefficients are derived from the setup
    seed only (never from epoch/close bytes, so `d`, the epoch public key, and
    the polynomial are stable across restarts and independent of any single
    message). Reproducible from (seed, threshold, n) exactly as a real DKG
    would publish a committed polynomial (this review: reconstruction must come
    from the supplied shares, not a stored master)."""
    return [(_spf_scalar(b"PolyCoeff" + u32(k) + b"cap-0089-v1" + seed)
             % _GRP_Q) for k in range(threshold)]


def _poly_share(seed: bytes, threshold: int, n: int, member_index: int) -> int:
    """f(i) mod q -- the member's SECRET polynomial share (a Shamir share), the
    actual value `recover_proof` Lagrange-interpolates. Fixed per member and
    independent of the close (close-binding is enforced separately by the
    sign-once/authorization gates in `share`)."""
    coeffs = _poly_coeffs(seed, threshold, n)
    x = member_index % _GRP_Q
    acc = 0
    for k, a in enumerate(coeffs):
        acc = (acc + a * pow(x, k, _GRP_Q)) % _GRP_Q
    return acc


def _group_secret(seed: bytes, threshold: int, n: int) -> int:
    """d = f(0) -- the unique recovered group secret. Defined from the same
    polynomial the shares are evaluations of, so any t-subset Lagrange-
    interpolates to this EXACT value (one-future / byte-identical P_s)."""
    return _poly_coeffs(seed, threshold, n)[0]


def _feldman_commit(seed: bytes, threshold: int, n: int, member_index: int) -> bytes:
    """Public Feldman commitment C_i = G^{f(i)} (an order-q group element) for a
    member's long-lived secret share f(i). It is PUBLIC (never secret) and is
    used ONLY to verify a member's message-dependent FROST partial signature
    `s_i = n(i) + c*f(i)` via `G^{s_i} == N_i * C_i^c`, without ever revealing
    f(i). Committed into the epoch's membership surface so that partials are
    bound to the epoch's own roster (Copilot this review #3/#4)."""
    fi = _poly_share(seed, threshold, n, member_index) % _GRP_Q
    return pow(_GRP_G, fi, _GRP_P).to_bytes(32, "big")


def _frost_nonce_poly(nonce_seed: bytes, threshold: int, n: int) -> list:
    """Deterministic per-(epoch, C_s) nonce polynomial g (deg t-1) over GF(q).
    Its secret `r = g(0)` masks every partial so that the long-lived secret
    shares f(i) are never revealed and t partials from one close cannot be
    recombined for another close (message-dependent threshold shares, Copilot
    this review #3, High). Reproduction uses ONLY the nonce_seed (derived from
    the authority seed + epoch_hash + C_s), so restart/durable-sign-once
    re-derives the identical nonce with no process memory."""
    return [(_spf_scalar(b"FrostNoncePolyCoeff" + u32(k)
                         + b"cap-0089-v1" + nonce_seed) % _GRP_Q)
            for k in range(threshold)]


def _frost_share(nonce_coeffs: list, member_index: int) -> int:
    """n(i) -- the member's SECRET nonce share (an evaluation of the per-message
    nonce polynomial g). Fresh for every (epoch, C_s); never emitted raw. Its
    per-message secrecy is what makes partials `s_i = n(i) + c*f(i)` inert to
    cross-close recombination."""
    x = member_index % _GRP_Q
    acc = 0
    for k, a in enumerate(nonce_coeffs):
        acc = (acc + a * pow(x, k, _GRP_Q)) % _GRP_Q
    return acc % _GRP_Q


def _lagrange_recover(shares):
    """Reconstruct f(0) by Lagrange interpolation over GF(q) from >= t distinct
    (x_i, f(x_i)) pairs. `shares`: {member_index (as x): y}. Uses ONLY the
    supplied share values -- there is NO master secret on, or needed by, this
    path (Copilot this review). Returns the unique scalar `d = f(0)`."""
    xs = list(shares.keys())
    acc = 0
    for i in xs:
        xi = i % _GRP_Q
        yi = shares[i] % _GRP_Q
        num = 1
        den = 1
        for j in xs:
            if j == i:
                continue
            xj = j % _GRP_Q
            # L_i(0) = prod_{j!=i} (0 - xj) / (xi - xj)  over GF(q)
            num = (num * ((-xj) % _GRP_Q)) % _GRP_Q
            den = (den * ((xi - xj) % _GRP_Q)) % _GRP_Q
        li = (num * pow(den, _GRP_Q - 2, _GRP_Q)) % _GRP_Q
        acc = (acc + yi * li) % _GRP_Q
    return acc % _GRP_Q


def group_pub_from_seed(seed: bytes, threshold: int, n: int) -> bytes:
    # The epoch's committed authority/public key: Y = G^d, d = f(0) from the
    # same Shamir polynomial the n members hold shares of. `verify` binds every
    # accepted proof to this committed key.
    return _spf_pub(_group_secret(seed, threshold, n))


# ---------------------------------------------------------------------------
# HONEST HOLDER vs ATTACKER surface split (Copilot this review #1, High).
#
# `GROUP_SK` (line ~112) and the helpers `_poly_coeffs` / `_poly_share` /
# `_group_secret` / `_spf_sign` model the SEEDED GROUP SECRET and the signing
# path that ONLY the primitive (Rust) and its >= t holders may take. In this
# harness they are plain module functions so the honest-signing tests (N3/I3,
# the genuine threshold theorem) can be exercised from the authority's own
# signing path. They are NOT reachable from the attacker surface.
#
# `AttackerView` is the test's canonical ATTACKER: it is constructed with ONLY
# public committed material (epoch descriptor, authority_key, roster,
# membership_commitment, and the candidate closes) and exposes NO attribute or
# method to obtain shares, the seed, `_group_secret`, `_spf_sign`, or any other
# signing material. Every negative-synthesis / pre-lock unavailability check
# (O2, S2, K2) is driven through this façade, so the evidence the model offers
# is exactly "an attacker interface that cannot touch signing material cannot
# produce an accepted proof or a pre-lock root" -- not a claim that Python
# cannot be read. The truly cryptographic pre-lock secrecy (that < t shares are
# information-theoretically insufficient) is guaranteed by the real BLS/VUF
# primitive, which this harness consciously does not re-derive.
class AttackerView:
    def __init__(self, epoch, candidates):
        self.epoch = epoch
        self.authority_key = epoch.authority_key
        self.roster = epoch.roster
        self.membership_commitment = epoch.membership_commitment
        self.candidates = tuple(candidates)          # public candidate closes
        # Deliberately NO secret, shares, seed, _group_secret, or _spf_sign.

    def public_root_guess(self, c, p_guess):
        # A raw H("Root",...) over a GUESSED proof is not an accepted root;
        # it only reflects "a root could be computed for a specific proof". It
        # never runs the public-key check, so it is not `verify`.
        return sha256(b"Root" + self.authority_key + self.epoch.hash
                      + c.hash + p_guess)

    def __repr__(self):
        return ("AttackerView(public only: authority_key, roster, "
                "membership_commitment, %d candidate closes)" % len(self.candidates))


def _validator_confirm_sk(secret: bytes, member_index: int) -> int:
    """Per-member CONFIRM (SCP/externalization) signing key `k_i`, a genuinely
    MEMBER-HELD SECRET: it is derived from the authority's PRIVATE `secret`, NOT
    from any public data (Copilot this review: the old `_member_confirm` derived
    `k_i = H("ConfirmSubKey" || membership_commitment || i)` from PUBLILY-visible
    bytes, so any observer could mint a valid CONFIRM vote for every roster
    member -- it authenticated nothing). `k_i` is used ONLY to authenticate a
    member's CONFIRM->EXTERNALIZE vote to the boundary; never to sign/verify the
    randomness proof. An observer with only the epoch (public) cannot compute
    `k_i`: it requires the private group/DKG secret. The epoch commits ONLY the
    corresponding PUBLIC verification key (see `_validator_confirm_pub`)."""
    return _spf_scalar(sha256(b"NodeConfirmKey/v2" + hash32(secret)
                              + u32(member_index) + b"v1"))


def _validator_confirm_pub(secret: bytes, member_index: int) -> bytes:
    """Public verification key K_i = G^{k_i} for a member's CONFIRM vote. This is
    the ONLY per-member CONFIRM material an epoch commits/registers: the private
    key stays with the member (rev-w#7). Bound to the epoch's roster commitment
    through the `confirm_pub` the epoch registers."""
    return _spf_pub(_validator_confirm_sk(secret, member_index))


def _confirm_vote(k_i: int, epoch_hash: bytes, C_s: bytes) -> bytes:
    # Member CONFIRM vote = deterministic Schnorr signature over
    # ("CONFIRM", epoch_hash, C_s) under the member's PRIVATE subkey k_i. Sealed
    # and verifiable via the committed public K_i; an observer (lacking k_i,
    # which is not a public function) cannot mint one.
    r = _spf_scalar(sha256(b"ConfirmNonce" + k_i.to_bytes(32, "big")
                           + epoch_hash + C_s))
    R = pow(_GRP_G, r, _GRP_P)
    R_bytes = R.to_bytes(32, "big")
    K = pow(_GRP_G, k_i, _GRP_P)
    c = int.from_bytes(sha256(b"ConfirmChal" + epoch_hash + C_s
                              + R_bytes + K.to_bytes(32, "big") + b"v1"), "big") % _GRP_Q
    s = (r + c * k_i) % _GRP_Q
    return R_bytes + s.to_bytes(32, "big")


def _confirm_vote_verify(K_i_pub: bytes, epoch_hash: bytes, C_s: bytes,
                         vote: bytes) -> bool:
    if K_i_pub is None or len(K_i_pub) != 32 or vote is None or len(vote) != 64:
        return False
    K = int.from_bytes(K_i_pub, "big")
    if not (0 < K < _GRP_P):
        return False
    R_bytes, s_bytes = vote[:32], vote[32:]
    R = int.from_bytes(R_bytes, "big")
    s = int.from_bytes(s_bytes, "big")
    if not (0 < R < _GRP_P) or not (1 <= s < _GRP_Q):
        return False
    c = int.from_bytes(sha256(b"ConfirmChal" + epoch_hash + C_s
                              + R_bytes + K_i_pub + b"v1"), "big") % _GRP_Q
    return pow(_GRP_G, s, _GRP_P) == (R * pow(K, c, _GRP_P)) % _GRP_P


def _spf_sign(d: int, epoch_hash: bytes, C_s: bytes) -> bytes:
    # Deterministic, secret-nonce Schnorr signature (the model's CANONICAL
    # signature; RFC-6979-style). The model's own producer emits exactly one
    # byte-string per (d, epoch, C_s). NOTE: the accepted ROOT DOES depend on
    # these canonical proof bytes -- `R_s = H("Root", Y, epoch, C_s, P_s)` (see
    # `canonical_root` / UniqueThresholdProof.verify) -- and because the nonce is
    # deterministic and `d` is denied to every actor, only this ONE byte-identical
    # `P_s` can exist per close (N3/I3): alternate ENCODINGS canonicalize to the
    # same bytes, and a deviant `P_s` (which requires holding `d`) is never the
    # source's genuine proof, so no second root for the same close is reachable
    # (the one-future bound, Copilot this review).
    d_bytes = d.to_bytes(32, "big")
    r = _spf_scalar(sha256(b"SpfNonce" + d_bytes + epoch_hash + C_s))
    R = pow(_GRP_G, r, _GRP_P)
    R_bytes = R.to_bytes(32, "big")
    Y = pow(_GRP_G, d, _GRP_P)
    Y_bytes = Y.to_bytes(32, "big")
    c = int.from_bytes(sha256(b"SpfChal" + epoch_hash + C_s
                              + R_bytes + Y_bytes + b"cap-0089-v1"), "big")
    c %= _GRP_Q
    s = (r + c * d) % _GRP_Q
    return R_bytes + s.to_bytes(32, "big")


def _spf_verify(pub32: bytes, epoch_hash: bytes, C_s: bytes, proof: bytes) -> bool:
    # PURE public verification bound to the committed public key `pub32`.
    # Rejects anything that is not a valid signature under Y -- arbitrary bytes,
    # a wrong-epoch proof, a replayed cross-slot proof all fail here.
    if pub32 is None or len(pub32) != 32 or proof is None or len(proof) != 64:
        return False
    R_bytes, s_bytes = proof[:32], proof[32:]
    Y = int.from_bytes(pub32, "big")
    if not (0 < Y < _GRP_P):
        return False
    R = int.from_bytes(R_bytes, "big")
    if not (0 < R < _GRP_P):
        return False
    s = int.from_bytes(s_bytes, "big")
    if not (1 <= s < _GRP_Q):
        return False
    c = int.from_bytes(sha256(b"SpfChal" + epoch_hash + C_s
                              + R_bytes + pub32 + b"cap-0089-v1"), "big")
    c %= _GRP_Q
    # G^s == R * Y^c (mod p)
    return pow(_GRP_G, s, _GRP_P) == (R * pow(Y, c, _GRP_P)) % _GRP_P


class EpochDescriptor:
    """Inert verification material, canonicalized as ONE rule-hash so that any
    change to format/scheme/group key/roster/threshold/root-rule/event-mapping/
    verifier produces a NEW epoch (migration neutrality).

    The epoch COMMITS the full canonical threshold authority: a sorted roster of
    member share-verification keys (committed as `membership_commitment`), the
    group (`authority_key`), the threshold, and the verifier/root/encoding rules.
    n and t are DERIVED from this descriptor by `ThresholdAuthority.from_epoch`;
    they are never caller arguments."""

    def __init__(self, format_version: int, authority_key: bytes,
                 roster, activation: int, retirement: int, threshold: int,
                 root_rule: bytes, event_mapping: bytes,
                 verifier_rule: bytes = b"unique-threshold/v1",
                 scheme: bytes = EPOCH_SCHEME,
                 byzantine_bound: int = None,
                 confirm_pub=None,
                 feldman_pub=None):
        self.format_version = format_version
        # Commit the authority/group public key AFTER authenticating it as a
        # non-identity element of the order-q subgroup (Copilot this review #1,
        # High). An out-of-group / identity public key (e.g. Y = 1) would let
        # anyone choose s and satisfy `G^s == R * Y^c` with Y^c = 1, so forged
        # proofs could derive roots. We reject at construction: the committed
        # authority key must be a generator-subgroup element of order q.
        authority_key = hash32(authority_key)            # rejects wrong widths
        authority = int.from_bytes(authority_key, "big")
        if not (1 < authority < _GRP_P
                and pow(authority, _GRP_Q, _GRP_P) == 1):
            raise ValueError(
                "authority_key must be a non-identity order-q group element "
                "(1 < Y < p and Y^q == 1 mod p)")
        self.authority_key = authority_key
        roster_tup = tuple(sorted(roster))
        if len(set(roster_tup)) != len(roster_tup):
            # thread e6WbkN: duplicate roster keys would let one verification
            # identity occupy multiple threshold indices -- reject before n and
            # membership_commitment are derived.
            raise ValueError("roster must contain distinct member keys")
        self.roster = roster_tup
        self.membership_commitment = sha256(roster_bytes(self.roster))
        # Commit ONLY the per-member PUBLIC CONFIRM verification keys K_i
        # (Copilot this review: CONFIRM votes authenticate member-held SECRET
        # keys; the epoch registers/commits only the public verification keys).
        # `confirm_pub` is a tuple of n public keys K_i = G^{k_i}; the private
        # k_i is held only by the member/authority (never public, never here).
        self.confirm_pub = (
            tuple(confirm_pub) if confirm_pub is not None
            else tuple(_validator_confirm_pub(GROUP_SK, i)
                       for i in range(1, len(self.roster) + 1)))
        if len(self.confirm_pub) != len(self.roster):
            raise ValueError("confirm_pub must have one key per roster member")
        # Validate every committed CONFIRM verification key K_i as a NON-IDENTITY
        # element of the order-q subgroup (Copilot this review, High). If a K_i
        # were out-of-group or the identity (e.g. K_i = 1), an observer could
        # choose any valid s and set R = G^s so that K_i^c = 1 and the member's
        # CONFIRM vote verifies without that member ever signing -- minting votes
        # for keys the member never committed to. We reject at construction,
        # exactly as for `authority_key`.
        for _ki in self.confirm_pub:
            if len(_ki) != 32:
                raise ValueError("confirm_pub element must be 32 bytes")
            _k_int = int.from_bytes(_ki, "big")
            if not (1 < _k_int < _GRP_P
                    and pow(_k_int, _GRP_Q, _GRP_P) == 1):
                raise ValueError(
                    "confirmed CONFIRM key K_i must be a non-identity order-q "
                    "group element (1 < K_i < p and K_i^q == 1 mod p)")
        # COMMIT each member's PUBLIC Feldman commitment C_i = G^{f(i)} -- the
        # order-q public image of the member's long-lived polynomial share f(i)
        # (Copilot this review, thread evw9Z, High). These are PUBLIC (never
        # secret), but they MUST be committed into the epoch identity so that a
        # peer verifying a partial signature can MATCH the carrier-supplied C_i
        # against the epoch-committed value. Without committing them, a Byzan-
        # tine rostered sender could supply ANY subgroup element as C_i --
        # including the identity `C_i = 1`, which turns the partial check
        # `G^{s_i} == N_i * C_i^c` into `G^{s_i} == N_i` (no secret contribution,
        # satisfied by `(s_i=1, N_i=G)`) and poisons reconstruction. The epoch
        # commits exactly one C_i per roster member and the boundary rejects a
        # carrier whose C_i is not the epoch-committed one for that member.
        n_feld = len(self.roster)
        self.feldman_pub = (
            tuple(feldman_pub) if feldman_pub is not None
            else tuple(_feldman_commit(GROUP_SK, threshold, n_feld, i)
                       for i in range(1, n_feld + 1)))
        if len(self.feldman_pub) != len(self.roster):
            raise ValueError("feldman_pub must have one commitment per member")
        for _ci in self.feldman_pub:
            if len(_ci) != 32:
                raise ValueError("feldman_pub element must be 32 bytes")
            _c_int = int.from_bytes(_ci, "big")
            if not (1 < _c_int < _GRP_P
                    and pow(_c_int, _GRP_Q, _GRP_P) == 1):
                raise ValueError(
                    "committed Feldman commitment C_i must be a non-identity "
                    "order-q group element (1 < C_i < p and C_i^q == 1 mod p)")
        self.activation = activation
        self.retirement = retirement
        # Reject a malformed activation window at construction (Copilot this
        # review, thread evw-k): an empty (`activation == retirement`) or
        # reversed (`activation >= retirement`) window can never be active and
        # would fail closed indefinitely at transition. Fail fast here rather
        # than emitting a permanently-inactive committed epoch.
        if not (activation < retirement):
            raise ValueError(
                "activation window must satisfy activation < retirement "
                "(a non-empty, non-reversed active range)")
        if not (1 <= threshold <= len(self.roster)):
            # thread e6VduY: a malformed threshold (0 or > n) can never be a
            # sound epoch -- 0 would emit a proof with no shares, > n could
            # never resolve. Reject at construction.
            raise ValueError("threshold must satisfy 1 <= threshold <= n")
        self.threshold = threshold
        # Byzantine bound f and its TWO validity conditions, both committed into
        # the epoch identity.
        #
        # (1) HONEST-INTERSECTION (cross-message uniqueness, thread eW_rR):
        #     `2*t - n > f` guarantees any two size-t reconstructing subsets
        #     overlap in at least one HONEST member even with f Byzantine members
        #     anywhere -- so two conflicting same-slot proofs are impossible.
        # (2) AVAILABILITY (Copilot this review): `t <= n - f` guarantees the
        #     `n - f` honest members can actually gather `t` valid shares. If
        #     `t > n - f`, then with the f tolerated Byzantine members withholding
        #     (Layer B has NO fallback key), fewer than t honest shares exist and
        #     ledger apply stalls indefinitely.
        # The DEFAULT f is the largest value that satisfies BOTH bounds:
        #     f = min(2*t - n - 1, n - t).
        # For (n=8, t=7) the availability bound is binding -- n - t = 1 -- so the
        # default is f = 1 and the epoch is VALID and provable (7 <= 8-1 = 7).
        # A caller who FORCES a higher f (e.g. f = 5) gets it PRESERVED (never
        # silently re-clamped down) and then an honest FAIL-CLOSED rejection when
        # `t <= n - f` is violated (7 <= 3 is false). The clamp is applied to the
        # DEFAULT only, never to a configured/declared f (Copilot this review).
        n = len(self.roster)
        default_f = max(0, min(2 * threshold - n - 1, n - threshold))
        self.byzantine_bound = (default_f if byzantine_bound is None
                                else byzantine_bound)
        if not (0 <= self.byzantine_bound < threshold <= n):
            raise ValueError("byzantine bound must satisfy 0 <= f < t <= n")
        if not (2 * threshold - n > self.byzantine_bound):
            # Reject any (t, n, f) that does NOT guarantee an honest intersection
            # between every two threshold subsets (thread eW_rR).
            raise ValueError(
                "threshold must satisfy 2*t - n > f for honest-intersection "
                "(cross-message uniqueness)")
        if not (self.byzantine_bound <= n - threshold):
            # Reject any (t, n, f) whose honest members cannot gather t shares:
            # with f Byzantine members withholding, only n-f honest shares exist,
            # so we need t <= n-f for availability (no fallback key in Layer B).
            raise ValueError(
                "threshold must satisfy t <= n - f for AVAILABILITY "
                "(the n-f honest members must be able to gather t shares)")
        self.verifier_rule = verifier_rule
        self.root_rule = root_rule
        self.event_mapping = event_mapping
        self.scheme = scheme
        self.hash = sha256(
            b"Epoch"
            + struct.pack(">B", format_version) + lp(scheme)
            + hash32(authority_key) + hash32(self.membership_commitment)
            + hash32(sha256(roster_bytes(self.confirm_pub)))  # committed CONFIRM pubkeys
            + hash32(sha256(roster_bytes(self.feldman_pub)))  # committed Feldman C_i
            + struct.pack(">QQ", activation, retirement)
            + struct.pack(">I", threshold)
            + struct.pack(">I", self.byzantine_bound)
            + lp(verifier_rule)
            + lp(root_rule) + lp(event_mapping))

    @property
    def n(self) -> int:
        return len(self.roster)

    def active_at(self, slot: int) -> bool:
        return self.activation <= slot < self.retirement


def roster_bytes(roster) -> bytes:
    """Canonical sorted roster encoding as Core XDR `<opaque Hash[32]<>` (a
    variable-length array). XDR prefixes a variable-length array with the
    ELEMENT COUNT `n` (a uint32), not the byte length: the wire is `u32(n)`
    followed by `n` fixed-width 32-byte elements, each `Hash[32]` with no
    per-element length prefix. (A byte-length prefix of `32*n` would be the
    XDR encoding of a single `opaque<3968>` blob, NOT of `<Hash[32]>` -- a
    native implementation would derive a different membership commitment and
    epoch hash. Copilot this review.) `membership_commitment = H(roster_bytes)`.
    This is what `from_epoch` re-derives, so substituted (n, t, roster)
    mappings are a different commitment and cannot verify under the epoch."""
    ordered = sorted(roster)
    return struct.pack(">I", len(ordered)) + b"".join(hash32(k) for k in ordered)


class LockedClose:
    """Canonical Core close-lock commitment C_s for a closed ledger `slot`.
    Commits the externalized value bytes (via their SHA-256) with
    epoch/network/slot/previousLedgerHash -- every semantic input that can
    interact with the random result -- while excluding certificate/packet-path
    metadata (dnFWo / dnFWi). `previous_ledger_hash` is the REAL predecessor
    hash Core commits in StellarValue: an explicit input sourced from the
    externalized value, never synthesized."""

    __slots__ = ("epoch_hash", "network_id", "slot", "previous_ledger_hash",
                 "value_bytes", "hash")

    def __init__(self, epoch, slot: int, previous_ledger_hash: bytes,
                 value_bytes: bytes, network_id: bytes = NETWORK):
        self.epoch_hash = epoch.hash
        self.network_id = network_id
        self.slot = slot
        self.previous_ledger_hash = previous_ledger_hash
        self.value_bytes = value_bytes
        self.hash = self._commit()

    def _commit(self) -> bytes:
        in_v1 = close_input(self.epoch_hash, self.network_id, self.slot,
                            self.previous_ledger_hash,
                            canonical_value_hash(self.value_bytes))
        return sha256(b"CloseLock" + in_v1)

    def validate(self) -> bool:
        return self._commit() == self.hash

    @classmethod
    def rebuild(cls, epoch, slot: int, previous_ledger_hash: bytes,
                value_bytes: bytes, network_id: bytes = NETWORK) -> "LockedClose":
        """Self-consistent LockedClose under an ARBITRARY network id / explicit
        predecessor (used to prove the resolver rejects cross-network or wrong-
        predecessor closes, and that they never produce a root here)."""
        obj = cls.__new__(cls)
        obj.epoch_hash = epoch.hash
        obj.network_id = network_id
        obj.slot = slot
        obj.previous_ledger_hash = previous_ledger_hash
        obj.value_bytes = value_bytes
        obj.hash = obj._commit()
        return obj


def canonical_proof(proof: bytes):
    """Strict canonicalization: the proof is rejected unless it is the single
    canonical byte string the epoch's verifier accepts. The canonical shape of
    the model's Schnorr/VUF stand-in proof is EXACTLY 64 bytes of the form
    `R||s` (R is a 32-byte group element, s a 32-byte scalar). Two accepted
    encodings of the same mathematical proof MUST canonicalize to the SAME bytes
    before either can influence R_s (Noot: proof malleability is a conformance
    issue, never a second-future surface).

    NOTE: shape-canonicalization is NOT verification. `verify()` additionally
    checks the public-key Schnorr equation, so an arbitrary 64-byte value that
    merely has the right length is REJECTED (Copilot line-519). The canonical
    shape feeds authentication only; the ROOT is the proof-DEPENDENT unique
    function `R_s = H("Root", authority_key, epoch_hash, C_s, P_s)` of the
    committed authority key + the close + the canonical threshold proof (see
    `canonical_root`), so malleability of a valid signature's ENCODING cannot
    split the root: the byte-identical canonical P_s (N3/I3) gives the single,
    predictable root."""
    if proof is None or len(proof) != 64:
        return None
    return proof


def canonical_root(C_s: bytes, authority_key: bytes, epoch_hash: bytes,
                   P_s: bytes = None):
    """R_s -- the source root, derived from the UNPREDICTABLE canonical threshold
    proof: `R_s = H("Root", authority_key, epoch_hash, C_s, P_s)`.

    Anti-grinding (Copilot this review #2, High): the root MUST depend on the
    threshold PROOF `P_s`, not merely on public (authority_key, C_s). `P_s` is
    the deterministic-nonce output of the secret-bound threshold evaluation; it
    cannot be computed from public candidate data before the close is
    CONFIRM/EXTERNALIZE locked (it needs the recovered group secret `d`, which
    exists only among the >= t holders who sign AFTER externalization). So a
    proposer who could swap candidate C_s values to pick a favorable root cannot
    evaluate the root for any candidate in advance -- there is no favorable root
    to seek before the proof exists. This is `root(C_s, canonical(P_s))` as the
    CAP contract states.

    Uniqueness: `_spf_sign` uses a deterministic, RFC-6979-style nonce
    (a fixed function of (d, epoch, C_s)); there is NO message nonce an attacker
    can vary, so every >= t honest holder whose Lagrange reconstruction yields
    `d` emits the byte-IDENTICAL `P_s` (N3/I3 below). One close therefore mints
    exactly one proof byte-wise and one root. A deviant-nonce signature is
    possible only for a party that already holds `d` -- which the protocol
    denies to every actor (the secret lives only inside the signed primitive) --
    and is never the source's `genuine_proof`, so it cannot mint a second root.

    `verify` calls this ONLY after the public-key check has authenticated the
    proof; it never turns an arbitrary byte string into a root. `P_s` must be
    provided (it is not optional); a caller that omits it gets no root -- mirroring
    that no node can derive the root before it holds the valid proof."""
    if P_s is None:
        return None
    return sha256(b"Root" + authority_key + epoch_hash + C_s + P_s)


class ThresholdAuthority:
    """Genuinely thresholded release authority, derived ONLY from the epoch
    (Noot). `from_epoch(epoch)` fixes the roster / n / t / group; construction
    FAILS CLOSED if the caller tries to supply a differing n/t/roster. Each
    member holds a SECRET share key derived from the authority seed
    (setup/transport metadata -- never in the epoch hash).

    Rules:
      * share(i, cl): requires the close to belong to THIS epoch; durable
        sign-once per member per event -- the same (epoch, slot, C_s) retry is
        idempotent, a DIFFERENT C_s for the same slot is REFUSED (an SCP safety
        failure can stall randomness, never mint two roots).
      * verify_share / recover_proof: invalid, duplicate, out-of-epoch, or
        wrong-close shares are DISCARDED INDIVIDUALLY and never poison
        reconstruction -- if >= t other valid shares are present, the same
        canonical P_s is recovered anyway.
      * < t valid shares -> None (no proof at all). There is NO public
        proof-emission function: an actor with fewer than t valid shares cannot
        obtain any P_s accepted by the pure verifier."""

    def __init__(self, epoch: EpochDescriptor, seed: bytes,
                 signed: dict = None):
        self.epoch = epoch
        self.seed = seed
        # Durable sign-once per event: (member_index, slot) -> C_s. Each member
        # signs each ledger slot at most once; a competing C_s for the SAME slot
        # is refused. Distinct future slots are independent (threads e6Vduq,
        # e6Vdt1). `signed` is carried through restart() so a crash/restart
        # authority re-derives identical shares and still refuses equivocation.
        self._signed = signed if signed is not None else {}
        # Authorization gate (thread eW_rk / Copilot 3917696297): share() only
        # ever releases for a close that has been CONFIRM/EXTERNALIZE admitted
        # by the producer source -- never for an arbitrary pre-lock close.
        # `_released` maps C_s hash -> release witness; it is populated ONLY by
        # the private `_authorize_release()`, invoked exclusively from the
        # RandomnessSource boundary path. There is NO public `authorize_release`
        # an external holder of this object can call.
        self._released = {}
        # Bound boundary capability (set by RandomnessSource.bind): the image
        # commit H(b"CapCommit", cap) of the RELEASE capability derived from the
        # source's boundary secret. Without a genuine bound cap the authority
        # refuses every `_authorize_release` call, so an unpaired (attacker-held)
        # authority can authorize nothing.
        self._cap_check = None
        # PUBLISHED per-member per-close NONCE commitments N_i = G^{n_i}, maps
        # cl_hash -> {member_index: N_i_bytes}. These are PUBLIC (transported in
        # every share carrier) and are the ONLY nonce material `verify_share` /
        # `recover_proof` ever read: a peer-verifier needs NO master secret and
        # NO member nonce n_i, exactly as a distributed FROST protocol requires
        # (Copilot this review, High). The nonce SECRETS n_i live only in the
        # issuance path (`_share_for`); they are never stored here.
        self._published_nonces = {}

    @classmethod
    def from_epoch(cls, epoch: EpochDescriptor, seed: bytes,
                   n_members=None, threshold=None, roster=None) -> "ThresholdAuthority":
        """THE canonical constructor. n/t/roster come from the epoch; anything
        caller-supplied that disagrees fails closed."""
        if n_members is not None and n_members != epoch.n:
            raise ValueError("n_members must be derived from the epoch")
        if threshold is not None and threshold != epoch.threshold:
            raise ValueError("threshold must be derived from the epoch")
        if roster is not None and tuple(sorted(roster)) != epoch.roster:
            raise ValueError("roster must be derived from the epoch")
        return cls(epoch, seed)

    def _nonce_material(self, cl_hash: bytes):
        # Per-message (FROST-style) nonce machinery. The nonce is a fresh secret
        # per (epoch, C_s): a degree t-1 polynomial g whose constant term r=g(0)
        # is the aggregate nonce and whose evaluations n(i) are each member's
        # secret NONCE share. Derived deterministically from the authority seed +
        # epoch_hash + C_s so restart / durable sign-once re-derives the
        # identical R without process memory (Copilot this review #3, High).
        #
        # THIS is the SECRET-ISSUANCE path: it is the ONLY place the master seed
        # participates. The aggregate `R` and challenge `c` it yields are exactly
        # the values a public verifier re-derives from the transported nonce
        # commitments (see `_public_challenge`), so the final P_s is byte-
        # identical whether computed here or by an ordinary peer with no secret.
        nonce_seed = sha256(b"FrostNonce" + self.seed + self.epoch.hash + cl_hash)
        coeffs = _frost_nonce_poly(nonce_seed, self.epoch.threshold, self.epoch.n)
        r = coeffs[0]                       # g(0) -- aggregate secret nonce
        R = pow(_GRP_G, r, _GRP_P).to_bytes(32, "big")
        return coeffs, R

    def _public_aggregate(self, cl_hash: bytes, comms: dict) -> bytes:
        # PUBLIC per-close aggregate nonce commitment R = G^{g(0)}: the Lagrange
        # combination (in the EXPONENT, on the group) of any >= t transported
        # per-member nonce commitments N_i = G^{n_i}, where n_i = g(i). Because
        # every n_i lies on the SAME degree-(t-1) nonce polynomial g, the sum
        # `sum_j L_j(0) * n_j = g(0)` regardless of which t-subset is used, so R
        # (and therefore the bound P_s) is byte-identical for every subset while
        # being computable with NO master secret -- only public N_i commitments.
        xs = list(comms.keys())
        if len(xs) < 1:
            return None
        acc = 1
        for i in xs:
            xi = i % _GRP_Q
            Ni = int.from_bytes(comms[i], "big") % _GRP_P
            num = 1
            den = 1
            for j in xs:
                if j == i:
                    continue
                xj = j % _GRP_Q
                num = (num * ((-xj) % _GRP_Q)) % _GRP_Q
                den = (den * ((xi - xj) % _GRP_Q)) % _GRP_Q
            lam = (num * pow(den, _GRP_Q - 2, _GRP_Q)) % _GRP_Q
            # N_i^{lambda}: acc *= Ni^lam (mod p); lam may be negative -> invert.
            if lam < 0:
                lam += _GRP_Q
            acc = (acc * pow(Ni, lam, _GRP_P)) % _GRP_P
        return acc.to_bytes(32, "big")

    def _public_challenge(self, cl_hash: bytes, R: bytes) -> int:
        # Public Fiat-Shamir challenge c = H(epoch_hash, C_s, R, Y, tag) applied
        # mod q. Uses ONLY the (publicly derived) aggregate nonce commitment R
        # and the committed authority key Y -- never the master secret. An
        # ordinary peer can reproduce this exact value.
        Y_bytes = self.epoch.authority_key
        c = int.from_bytes(sha256(b"SpfChal" + self.epoch.hash + cl_hash
                                  + R + Y_bytes + b"cap-0089-v1"), "big")
        return c % _GRP_Q

    def _share_for(self, member_index: int, cl_hash: bytes):
        # The member's MESSAGE-DEPENDENT threshold partial signature
        # `s_i = n(i) + c*f(i) mod q` (32 bytes), the actual value `recover_proof`
        # Lagrange-combines into `s = r + c*d` (Copilot this review #3, High).
        # Unlike a raw long-lived Shamir share f(i), this partial is bound to the
        # specific cl_hash (via the fresh secret nonce n(i)), so gathering t
        # partials from one close yields NO usable value for any other close and
        # NEVER reveals f(i) or d -- combination produces only r+c*d for THIS
        # message. `recover_proof` is the only consumer of these partials.
        #
        # Returns a SHARE CARRIER `(s_i, N_i, C_i)` (Copilot this review, High):
        # the member's public nonce commitment N_i = G^{n_i} and public Feldman
        # commitment C_i = G^{f(i)} travel WITH the partial so a peer can verify
        # `G^{s_i} == N_i * C_i^c` without the master seed or any secret. The
        # nonce secret n_i (and the long-lived f_i) are derived in this secret
        # path and never leave it.
        coeffs, R = self._nonce_material(cl_hash)
        c = self._public_challenge(cl_hash, R)
        f_i = _poly_share(self.seed, self.epoch.threshold, self.epoch.n,
                          member_index) % _GRP_Q
        n_i = _frost_share(coeffs, member_index) % _GRP_Q
        s_i = (n_i + c * f_i) % _GRP_Q
        N_i = pow(_GRP_G, n_i, _GRP_P).to_bytes(32, "big")
        # The public Feldman commitment C_i = G^{f(i)} emitted in the carrier
        # MUST be the epoch-COMMITTED one for this member (Copilot this review,
        # thread evw9Z): `verify_share` matches the carrier's C_i against
        # `self.epoch.feldman_pub[i-1]`, so an honest carrier transports exactly
        # the committed value and a forged identity/subgroup C_i is rejected.
        C_i = self.epoch.feldman_pub[member_index - 1]
        return (s_i.to_bytes(32, "big"), N_i, C_i)

    def _set_boundary_cap(self, cap: bytes) -> None:
        """Bind a RELEASE capability derived from the source's boundary secret.
        Called only by RandomnessSource.bind() (never by an external caller).
        After binding, `_authorize_release` accepts a witness only if it was
        minted with this exact capability."""
        self._cap_check = sha256(b"CapCommit" + cap)

    def _authorize_release(self, cl_hash: bytes, witness: bytes, cap: bytes) -> bool:
        """PRIVATE release-authorization gate (Copilot 3917696297 + suppressed
        line-506 note). The ONLY writer to `_released`, and reachable only from
        RandomnessSource.proof() -- there is no public `authorize_release`.

        NON-FORGEABILITY: an external caller holding this authority object, but
        NOT the producer boundary, cannot conjure share eligibility. To pass,
        `cap` must be the genuine RELEASE capability derived from the boundary
        secret (its commit must match the bound `_cap_check`, so a fabricated
        `cap'` is rejected), AND `witness` must equal the boundary-minted release
        witness H(b"CEWitness", cap, epoch_hash, C_s). A caller who only holds
        the authority knows `_cap_check` = H(cap_real) but not `cap_real` (a
        preimage), so it cannot supply a matching (cap, witness) pair for its
        chosen pre-lock close. Unpaired authorities (no `_cap_check`) authorize
        nothing."""
        if self._cap_check is None:
            return False                       # unpaired: nothing can be released
        if sha256(b"CapCommit" + cap) != self._cap_check:
            return False                       # fabricated capability -> refuse
        if sha256(b"CEWitness" + cap + self.epoch.hash + cl_hash) != witness:
            return False                       # not the genuine boundary witness
        if self._released.get(cl_hash) is not None:
            return True                        # idempotent (durable once)
        self._released[cl_hash] = witness
        return True

    def share(self, member_index: int, cl: LockedClose):
        if not (1 <= member_index <= self.epoch.n):
            raise ValueError("member index out of canonical roster")
        if cl.epoch_hash != self.epoch.hash:
            # An authority for epoch A cannot share over a close of epoch B.
            return None
        if cl.hash not in self._released:
            # (thread eW_rk) share() is gated behind authorization: a close
            # that was never CONFIRM/EXTERNALIZE admitted cannot be shared,
            # so no pre-lock proof can be assembled by an external caller.
            return None
        key = (member_index, cl.slot)
        if key in self._signed:
            if self._signed[key] != cl.hash:
                # Same event slot, DIFFERENT C_s: refuse (durable sign-once).
                return None
        else:
            self._signed[key] = cl.hash
        carrier = self._share_for(member_index, cl.hash)
        # Publish the member's public nonce commitment N_i = G^{n_i} for this
        # close. Peers (and `verify_share`/`recover_proof`) read ONLY this public
        # commitment set to build R and c -- never the master seed.
        self._published_nonces.setdefault(cl.hash, {})[member_index] = carrier[1]
        return carrier

    def verify_share(self, member_index: int, cl: LockedClose,
                     share_carrier) -> bool:
        """Verify a member's MESSAGE-DEPENDENT partial without revealing f(i)
        and WITHOUT the master seed (Copilot this review, High):
        check `G^{s_i} == N_i * C_i^c (mod p)` using ONLY publicly transported
        values --
          * the member's public nonce commitment N_i = G^{n_i} (carrier[1]), and
          * the member's public Feldman commitment C_i = G^{f(i)} (carrier[2]),
        with the aggregate nonce commitment R and challenge c PUBLICLY derived
        from those commitments (`_public_aggregate`/`_public_challenge`). An
        ordinary peer who has NEVER seen the master secret can run this exactly;
        no secret, share, or nonce participates. `share_carrier` is a
        `(s_i, N_i, C_i)` triple, NOT a reusable long-lived Shamir share."""
        if not (1 <= member_index <= self.epoch.n):
            return False
        if cl.epoch_hash != self.epoch.hash:
            return False
        if share_carrier is None or not isinstance(share_carrier, tuple) \
                or len(share_carrier) != 3:
            return False
        s_i_b, N_i_b, C_i_b = share_carrier
        if s_i_b is None or len(s_i_b) != 32 or N_i_b is None or len(N_i_b) != 32 \
                or C_i_b is None or len(C_i_b) != 32:
            return False
        s_i = int.from_bytes(s_i_b, "big")
        N_i = int.from_bytes(N_i_b, "big")
        C_i = int.from_bytes(C_i_b, "big")
        if not (1 <= N_i < _GRP_P) or pow(N_i, _GRP_Q, _GRP_P) != 1:
            return False                                  # bad nonce commitment
        if not (1 <= C_i < _GRP_P) or pow(C_i, _GRP_Q, _GRP_P) != 1:
            return False                                # bad Feldman commitment
        # COMMITTED-C_i BINDING (Copilot this review, thread evw9Z, High): the
        # carrier-supplied C_i must byte-match the epoch-COMMITTED Feldman
        # commitment for THIS member (`epoch.feldman_pub[member_index-1]`).
        # A subgroup-valid but forged value -- in particular the identity
        # `C_i = 1`, which would reduce the partial equation to `G^{s_i} == N_i`
        # and count `(s_i=1, N_i=G)` as valid for ANY challenge -- is therefore
        # rejected. A Byzantine rostered sender can no longer poison reconstruc-
        # tion by transporting a C_i the epoch never committed for its index.
        if C_i_b != self.epoch.feldman_pub[member_index - 1]:
            return False                    # C_i not the epoch-committed one
        if not (1 <= s_i < _GRP_Q):
            return False
        # Public aggregate R from the published nonce commitments for this close
        # (fall back to this member's own commitment when none are published yet,
        # so a single-carrier smoke check still has a deterministic reference).
        comms = dict(self._published_nonces.get(cl.hash, {}))
        if member_index not in comms:
            comms[member_index] = N_i_b
        R_b = self._public_aggregate(cl.hash, comms)
        if R_b is None:
            return False
        c = self._public_challenge(cl.hash, R_b)
        # G^{s_i} == N_i * C_i^c (mod p)
        return pow(_GRP_G, s_i, _GRP_P) == (N_i * pow(C_i, c, _GRP_P)) % _GRP_P

    def recover_proof(self, subset, cl: LockedClose):
        """subset: iterable of (member_index, share_carrier). Returns the
        canonical P_s iff >= t VALID, distinct, in-roster message-dependent
        partials for THIS exact close are present; invalid/duplicate/out-of-
        epoch/wrong-close partials are discarded individually and never poison t
        otherwise-valid partials.

        GENUINE MESSAGE-DEPENDENT THRESHOLD RECONSTRUCTION, PEER-VERIFIABLE
        (Copilot this review, High): the combined signing scalar `s = r + c*d` is
        obtained by LAGRANGE-combining the supplied partials `s_i = n(i) + c*f(i)`
        over GF(q) -- `s = sum_i L_i(0)*s_i = r + c*d` -- WITHOUT ever recovering
        the long-lived group secret `d`, any member share `f(i)`, ANY nonce
        secret `n(i)`, or the master seed. The aggregate nonce commitment R and
        challenge c are derived PUBLICLY from the transported N_i commitments
        (`_public_aggregate`/`_public_challenge`), so an ordinary peer holding no
        secret reproduces the byte-identical P_s from any >= t valid partials.
        The partials are bound to cl_hash, so t partials collected from one close
        are REUSELESS for any other close and cannot be used to sign a pre-lock
        commitment. The final proof is `(R || s)` (64 bytes), byte-identical for
        every >= t subset (R = G^{g(0)} is invariant under the subset choice)."""
        if cl.epoch_hash != self.epoch.hash:
            return None
        t = self.epoch.threshold
        n = self.epoch.n
        valid = {}
        for (member_index, carrier) in subset:
            if (1 <= member_index <= n and member_index not in valid
                    and self.verify_share(member_index, cl, carrier)):
                valid[member_index] = carrier
        if len(valid) < t:
            return None                             # below t: no proof, stall
        # PUBLIC aggregate R from the accepted carriers' nonce commitments.
        comms = {i: carrier[1] for (i, carrier) in valid.items()}
        R_b = self._public_aggregate(cl.hash, comms)
        if R_b is None:
            return None
        s = 0
        xs = list(valid.keys())
        for i in xs:
            xi = i % _GRP_Q
            yi = int.from_bytes(valid[i][0], "big") % _GRP_Q
            num = 1
            den = 1
            for j in xs:
                if j == i:
                    continue
                xj = j % _GRP_Q
                num = (num * ((-xj) % _GRP_Q)) % _GRP_Q
                den = (den * ((xi - xj) % _GRP_Q)) % _GRP_Q
            li = (num * pow(den, _GRP_Q - 2, _GRP_Q)) % _GRP_Q
            s = (s + yi * li) % _GRP_Q
        s %= _GRP_Q
        return R_b + s.to_bytes(32, "big")

    def restart(self) -> "ThresholdAuthority":
        """Deterministic re-derivation from (epoch, seed) that CARRIES the
        durable sign-once decisions: a crash/restart authority reproduces every
        share and the same P_s/R_s with no new authority choice and no process
        memory, while still refusing a competing C_s for any slot it already
        signed (thread e6Vdt1 -- the crash window cannot mint an equivocation).
        `signed` is passed through (its references are per-(epoch,seed) and the
        re-derived authority stands in for the same device across restart)."""
        new_auth = type(self)(self.epoch, self.seed, signed=self._signed)
        new_auth._released = dict(self._released)
        new_auth._cap_check = self._cap_check
        return new_auth


class UniqueThresholdProof:
    """Abstract unique-threshold-proof interface -- the smallest audited Rust
    seam. `verify` is PURE and archived-stable: it takes ONLY (epoch, C_s, P_s)
    and returns the single canonical R_s or None. No source, no admission, no
    process memory, no quorum-path fact (a year-later catchup node needs only
    the descriptor + C_s + P_s). The candidate crypto (BLS/VUF) separately
    proves: <t shares produce no proof; every >=t valid subset/permutation
    recovers the byte-identical canonical P_s; strict verify/canonicalize ->
    exactly one root; pre-lock secrecy under <t adversarial shares. This file
    ASSERTS those contract invariants as executable checks (I1-I4) and never
    pretends a placeholder hash is cryptographic proof: the proof bytes below
    depend on the recovered group secret, which no public field can derive."""

    @staticmethod
    def verify(epoch: EpochDescriptor, C_s: bytes, P_s: bytes):
        """PUBLIC archival verifier: verify(epoch, C_s, P_s) -> R_s | None.

        The pure, archived-stable acceptance relation over the canonical proof.
        It takes ONLY (epoch, C_s, P_s) -- no source, no admission memory, no
        process memory, no quorum-path fact.

        It is a GENUINELY public verification bound to the epoch's committed
        PUBLIC key (`epoch.authority_key`): it runs the Schnorr stand-in
        signature check `G^s == R * Y^c (mod p)` and, only if that passes,
        returns the one UNIQUE source root `R_s = H("Root" || authority_key ||
        epoch_hash || C_s || P_s)`. An arbitrary archive byte string (a forged
        64-byte value, a wrong-epoch proof, or a replayed proof) is REJECTED --
        it does not satisfy the equation under Y (Copilot line-519: no longer
        does a bare canonical-length value derive a root).

        PROVENANCE-INDEPENDENT AUTHENTICATION + ANTI-GRINDING (Copilot this
        review #2): `verify` AUTHENTICATES the proof against the committed public
        key -- not against which authority produced it or whether THIS node
        cached it -- so a valid proof received from another authority, or loaded
        during catchup, resolves to the identical root (a fresh catchup node
        needs only the descriptor + C_s + P_s). But the ROOT itself is derived
        from the UNPREDICTABLE proof bytes `P_s`, so it is NOT computable from
        public (authority_key, epoch_hash, C_s) before the proof exists -- a
        proposer cannot grind candidate closes to pick a favorable seed. Because
        the honest `P_s` is the deterministic-nonce canonical output (unique per
        C_s, N3/I3), one close yields one byte-identical proof and one root
        (one-future), while no attacker that lacks the group secret can mint an
        accepted proof to steer the root.

        What it does NOT do -- and what a public verifier with no secret MUST
        not do -- is *produce* the accepted proof. The proof is the secret-bound
        Schnorr output needing the recovered group secret (`d = f(0)`), so this
        verifier cannot and does not regenerate or forge it from public inputs
        (Copilot 3917696336). In production the primitive's public-key check
        (BLS pairing / RFC 9381 VUF equation) is the real math; the model's
        Schnorr stand-in below is an honest, self-contained surrogate for that
        seam (see the group-scheme note)."""
        p = canonical_proof(P_s)
        if p is None:
            return None
        if not _spf_verify(epoch.authority_key, epoch.hash, C_s, p):
            return None
        return canonical_root(C_s, epoch.authority_key, epoch.hash, p)


def consumer_kdf(root: bytes, label: bytes) -> bytes:
    # KDF(R_s, label): three distinct labelled consumers of ONE root (dnFWi).
    return sha256(b"KDF" + root + label)


class ConfirmExternalizeBoundary:
    """Modeled CONFIRM -> EXTERNALIZE transition -- the **sole producer** of a
    release witness (Copilot 3917696297 + suppressed line-506 note + this
    review's "caller-asserted boundary" note at the source).

    The boundary is the AUTHORITY over the release edge: only the genuine
    CONFIRM -> EXTERNALIZE transition makes `externalize()` mark a close as
    released, and `has_externalized()` is the ONLY predicate `RandomnessSource`
    consults for admission. A caller cannot assert it: `admit` takes no
    caller-supplied `release_certificate` or `fully_validated` flag -- the fact
    lives inside the boundary. In production this boundary is the real Core
    CONFIRM->EXTERNALIZE edge; `boundary_secret` is the model's stand-in for the
    authenticator only the participating validators can emit.

    COPILOT THIS REVIEW #5 (High): the `>= t` distinct CONFIRM votes are the
    RANDOMNESS-ROSTER RECONSTRUCTION THRESHOLD -- they guarantee that >= t of
    the random-authority's rostered shareholders genuinely reached CONFIRM and
    can therefore produce shares for this value. They are **NOT** a claim of
    SCP quorum topology (FBA quorum is a block of quorum-sets, not a numeric
    committee). WHICH value externalizes is decided by Core's trusted local
    CONFIRM->EXTERNALIZE transition on the actual saved SCP envelopes /
    quorum-sets; the model represents that as this edge (the votes are the >= t
    *rostered* members Core observed reach CONFIRM with full local validation).
    So the numeric threshold independently guards the randomness
    reconstruction, and SCP quorum membership is validated by Core -- the two
    guarantees are deliberately separate, exactly as the reviewer requires."""

    def __init__(self, epoch: EpochDescriptor, boundary_secret: bytes = None):
        self.epoch = epoch
        # Per-boundary secret, never serialized, never committed. A DIFFERENT
        # boundary (or a crafted one) mints witnesses no other authority
        # accepts, mirroring real per-process/per-validator finality evidence.
        self._secret = (boundary_secret if boundary_secret is not None else
                        sha256(b"cap-0089:boundary:secret:v1" + os.urandom(16)))
        # PUBLIC per-member CONFIRM verification keys K_i (the epoch REGISTERS
        # only these; the private k_i stays member-held). These are AUTHENTICATION
        # keys for the CONFIRM->EXTERNALIZE edge only; they are never secrets and
        # are registered here (like Core validators exchanging verification keys),
        # so the boundary verifies a CONFIRM cert WITHOUT holding any member
        # sub-secret and WITHOUT assuming an SCP quorum topology. An observer
        # cannot mint a vote: it cannot compute any private k_i from K_i.
        self._confirm_pub = {
            i: self.epoch.confirm_pub[i - 1] for i in range(1, self.epoch.n + 1)}
        # C_s.hash -> True iff the CONFIRM->EXTERNALIZE transition actually
        # ran for that lock. Populated ONLY by `externalize` (the trusted Core
        # edge; it never answers "which value is an SCP quorum", only "Core
        # locally externalized THIS value behind >= t rostered CONFIRM votes").
        self._externalized = {}

    def externalize(self, cl: LockedClose, confirm_cert: dict) -> bool:
        # The genuine CONFIRM -> EXTERNALIZE edge. The transition type and full
        # validation are FACTS OF THE EDGE, not caller flags the producer later
        # re-asserts (Copilot this review #2). The CONFIRM cert here records the
        # >= t DISTINCT, VALID ROSTERED member votes that Core observed reach
        # CONFIRM with local full validation; each is verified under the
        # member's public subkey K_i (committed to the epoch, #4). The SCP
        # QUORUM that picked the externalized value is Core's trusted local
        # transition on the real envelopes/quorum-sets -- NOT this numeric
        # roster threshold, and NOT a caller-asserted flag (this review #5). A
        # close becomes released ONLY when the trusted edge ran for that exact
        # C_s; a bare boolean, votes that do not authenticate, or fewer than t
        # distinct valid votes are REJECTED. accepted-commit is never
        # authoritative; only entering EXTERNALIZE behind the trusted edge
        # (with >= t rostered CONFIRMers able to reconstruct) releases a close.
        if cl is None or not cl.validate():
            return False
        if cl.network_id != NETWORK:
            return False
        if cl.epoch_hash != self.epoch.hash:
            return False
        if not self.epoch.active_at(cl.slot):
            return False
        if not isinstance(confirm_cert, dict):
            return False
        valid = 0
        seen = set()
        for idx, vote in confirm_cert.items():
            if not isinstance(idx, int) or not (1 <= idx <= self.epoch.n):
                continue
            if idx in seen:
                continue
            seen.add(idx)
            K_i = self._confirm_pub.get(idx)
            if K_i is None:
                continue
            if _confirm_vote_verify(K_i, cl.epoch_hash, cl.hash, vote):
                valid += 1
        if valid < self.epoch.threshold:
            return False
        self._externalized[cl.hash] = True
        return True

    def has_externalized(self, cl: LockedClose) -> bool:
        # Boundary-ENFORCED admission predicate. The source never accepts a
        # caller-asserted boolean here; only the boundary knows whether this
        # close really reached the CONFIRM->EXTERNALIZE edge.
        return cl is not None and self._externalized.get(cl.hash, False)

    def _cap(self) -> bytes:
        # RELEASE capability derived from the boundary secret + epoch. It is the
        # SAME capability RandomnessSource.bind installs (commit) and proof()
        # presents, so the witness the boundary mints and the witness the
        # authority validates are derived from one key shared through the
        # boundary secret -- unforgeable by an external caller.
        return sha256(b"ReleaseCap" + self._secret + self.epoch.hash)

    def witness(self, cl: LockedClose) -> bytes:
        # UNFORGEABLE release witness: bound to the boundary capability, the
        # epoch and the exact close. Requires KNOWING the boundary secret; an
        # external caller holding only the authority sees its commit check but
        # cannot preimage the capability/witness, and a fabricated byte string
        # cannot equal this genuine witness (the source gate keeps only these).
        return sha256(b"CEWitness" + self._cap() + cl.epoch_hash + cl.hash)


class RandomnessSource:
    """Producer-side release/admission interface. Shares are the transport of
    the proof; an honest holder signs ONLY at the CONFIRM/EXTERNALIZE boundary
    after local full validation, and durably once per event. The source keeps
    ONE canonical slot lock: it admits the exact externalized close for a slot
    and refuses a second, different close for the same slot (thread d9aC4).

    Release authorization is an UNFORGEABLE capability produced ONLY by the
    boundary path (Copilot 3917696297): `admit` is boundary-ENFORCED (it takes
    NO caller-supplied `release_certificate`/`fully_validated` -- those were the
    forgeable, caller-asserted inputs; the fact lives in `ConfirmExternalizeBoundary.
    has_externalized`), `proof` is the ONLY place a close is recorded as
    authorized on an authority, and `proof` no longer AUTO-BINDS whatever
    authority a caller hands it -- an unbound (or mismatched) authority is simply
    refused, so an attacker who pairs their own source+authority (but lacks the
    genuine source-boundary pairing) can release nothing."""

    def __init__(self, epoch: EpochDescriptor, boundary: ConfirmExternalizeBoundary = None):
        self.epoch = epoch
        self._boundary = boundary if boundary is not None \
            else ConfirmExternalizeBoundary(epoch)
        self._admitted = {}      # C_s.hash -> release witness (boundary-minted)
        self._slot_lock = {}     # slot -> C_s hash (ONE canonical close per slot)
        self._genuine = {}       # C_s.hash -> GENUINE recovered proof (cached
                                 # by proof()); resolve() accepts ONLY this one

    def admit(self, cl: LockedClose) -> bool:
        # BOUNDARY-ENFORCED admission (Copilot this review). No caller-supplied
        # transition type or validation flag is accepted: admission is granted
        # IFF the boundary genuinely performed the CONFIRM->EXTERNALIZE edge for
        # this exact close. A caller-asserted `release_certificate==...`+
        # `fully_validated=True` could previously be conjured by anyone holding
        # RandomnessSource; now `admit(cl)` literally does nothing unless
        # `boundary.has_externalized(cl)`.
        if not self._boundary.has_externalized(cl):
            return False
        if not cl.validate():
            return False
        if cl.network_id != NETWORK:
            return False
        if cl.epoch_hash != self.epoch.hash:
            return False
        if not self.epoch.active_at(cl.slot):
            return False
        existing = self._slot_lock.get(cl.slot)
        if existing is not None and existing != cl.hash:
            return False
        # ONLY the boundary can mint this witness (it needs the secret).
        self._admitted[cl.hash] = self._boundary.witness(cl)
        self._slot_lock[cl.slot] = cl.hash
        return True

    def has_valid_proof(self, cl: LockedClose) -> bool:
        return cl.hash in self._admitted

    def genuine_proof(self, cl: LockedClose):
        """The GENUINE recovered proof for an admitted close (cached by proof()).
        In the PROTOCOL an attacker cannot forge this: it requires the recovered
        group secret, which is produced only by the >= t holders at the
        CONFIRM/EXTERNALIZE boundary, and the attestation is enforced through the
        harness's ATTACKER SURFACE (see `AttackerView`), not claimed against
        arbitrary Python source reading. The model itself documents this is a
        structural harness: `< t` shares reconstruct nothing (the real secrecy is
        the BLS/VUF primitive's), and `resolve()` authenticates proofs against the
        committed public key, so a public-only formula or any non-canonical/forged
        byte candidate is REJECTED even if it is canonical-looking (Copilot
        3917696336)."""
        return self._genuine.get(cl.hash)

    def bind(self, authority: "ThresholdAuthority") -> None:
        """Pair this source's boundary capability to an authority. Derives the
        RELEASE capability from the boundary secret and installs its commit on
        the authority. An external caller cannot do this: it needs the boundary
        secret. Called once before a source produces proofs."""
        cap = self._boundary._cap()
        authority._set_boundary_cap(cap)
    def proof(self, cl: LockedClose, authority: ThresholdAuthority = None):
        if not self.has_valid_proof(cl):
            return None
        if authority is None:
            return None
        cap = self._boundary._cap()
        # (Copilot this review / 3917696297) NO auto-bind: an unpaired authority
        # is refused rather than silently paired on the caller's say-so. The
        # source's capability commit must ALREADY be installed on `authority`
        # (via an explicit `bind()`, which needs the boundary secret). An
        # attacker who independently constructs their OWN source+authority is
        # therefore bound to a capability the boundary secret did not mint:
        # `_authorize_release` compares `sha256(CapCommit+cap)` against the
        # authority's `_cap_check` and refuses.
        if authority._cap_check is None:
            return None
        # (thread eW_rk / Copilot 3917696297) The source authorizes release on
        # the boundary-admitted close -- the ONLY release-authorization path --
        # THEN all n honest holders durably sign it; >= t valid shares
        # reconstruct the single canonical proof. A close that was never
        # admitted can neither be authorized nor shared.
        if not authority._authorize_release(cl.hash, self._admitted[cl.hash], cap):
            return None
        holder_shares = [(i, authority.share(i, cl))
                         for i in range(1, authority.epoch.n + 1)]
        recovered = authority.recover_proof(holder_shares, cl)
        if recovered is not None:
            self._genuine[cl.hash] = recovered
        return recovered


def resolve(epoch: EpochDescriptor, cl: LockedClose, source: RandomnessSource,
            proof) -> dict:
    """Full state machine (LIVE release admission + provenance-independent
    archival resolution). Returns only the B4 authority surface: {event_hash,
    outcome, source_root?}.

    Gate 0 (integrity):         LockedClose hash must re-derive.
    Gate 1 (epoch+network):     close bound to THIS epoch/network and active.
    Gate 2 (boundary + proof):  source must have boundary-admitted the EXACT
        close AND the proof must pass the PURE archived verifier. No proof ->
        UNKNOWN (stalled apply); invalid proof -> REJECTED.

    The `source` argument is the LIVE producer: it supplies the boundary-
    admitted release fact (whether this close really reached the CONFIRM->
    EXTERNALIZE edge through the genuine boundary path). A catchup / archival
    replayer that only holds {epoch, C_s, P_s} MUST NOT be forced to re-execute
    that live boundary -- it uses `resolve_archival` (provenance-independent),
    which applies the SAME pure verifier without consulting any source state
    (Copilot this review, thread evw-0)."""
    if not cl.validate():
        return {"event_hash": cl.hash.hex(), "outcome": "REJECTED"}
    if (cl.epoch_hash != epoch.hash or cl.network_id != NETWORK
            or not epoch.active_at(cl.slot)):
        return {"event_hash": cl.hash.hex(), "outcome": "REJECTED"}
    if proof is None:
        return {"event_hash": cl.hash.hex(), "outcome": "UNKNOWN"}
    if not source.has_valid_proof(cl):
        return {"event_hash": cl.hash.hex(), "outcome": "REJECTED"}
    return resolve_archival(epoch, cl, proof)


def resolve_archival(epoch: EpochDescriptor, cl: LockedClose, proof) -> dict:
    """PROVENANCE-INDEPENDENT archival resolution (Copilot this review, thread
    evw-0): a catchup / historical node holding ONLY {epoch, C_s, P_s} from the
    ledger -- and never having executed the live CONFIRM->EXTERNALIZE boundary,
    so it has NO transient `_admitted` release record -- resolves the close
    exactly like the live `resolve`. It applies ONLY the pure, archived-stable
    public verifier (`UniqueThresholdProof.verify`: authenticate P_s against the
    committed `epoch.authority_key`, return the unique root), which never reads
    any source/admission/process memory. Live release ADMISSION (whether this
    particular close was boundary-released) is a SEPARATE fact that lives only
    on the live producer path; it is not part of resolving an already-recorded
    proof, so an archival replayer is never wrongly rejected just because the
    transient `_admitted` entry does not exist in its fresh process. Same gates
    (integrity / epoch+network / pure proof verification) as `resolve`."""
    if not cl.validate():
        return {"event_hash": cl.hash.hex(), "outcome": "REJECTED"}
    if (cl.epoch_hash != epoch.hash or cl.network_id != NETWORK
            or not epoch.active_at(cl.slot)):
        return {"event_hash": cl.hash.hex(), "outcome": "REJECTED"}
    if proof is None or not isinstance(proof, (bytes, bytearray)):
        return {"event_hash": cl.hash.hex(), "outcome": "UNKNOWN"}
    # Gate 2: PROVENANCE-INDEPENDENT authentication. The pure archival verifier
    # needs only (epoch, C_s, P_s): it authenticates P_s against the committed
    # `authority_key` (public Schnorr equation) and returns the unique root
    # H("Root", authority_key, epoch_hash, C_s). A proof produced by ANOTHER
    # authority, or loaded during catchup (never cached by THIS node as
    # `genuine_proof`), is accepted -- a non-producing consumer can derive the
    # root -- while a forged/public-only/random proof still fails the equation
    # and is REJECTED (negative-synthesis gate). As with the live path, a
    # missing proof is UNKNOWN (stalled apply).
    root = UniqueThresholdProof.verify(epoch, cl.hash, proof)
    if root is None:
        return {"event_hash": cl.hash.hex(), "outcome": "REJECTED"}
    return {"event_hash": cl.hash.hex(), "outcome": "ROOT",
            "source_root": root.hex()}


def epoch_for_transition(predecessor_state: bytes,
                         committed: dict, slot: int):
    """Noot #5: the epoch applied for a slot is a pure function of the
    PREDECESSOR canonical state -- committed[predecessor_state] is the exact
    epoch window set frozen in that predecessor's ledger. Exactly one committed
    epoch active at `slot` is selected; ZERO or TWO (overlap) FAIL CLOSED
    (None). Never reads local quorum sets or membership bookkeeping."""
    cands = [e for e in committed.get(predecessor_state, ()) if e.active_at(slot)]
    if len(cands) == 1:
        return cands[0]
    return None


def main():
    failed = 0

    def check(name, ok):
        nonlocal failed
        print(("PASS  " if ok else "FAIL  ") + name)
        if not ok:
            failed += 1

    def mk_roster(n):
        return [sha256(b"member-verify:%d" % i) for i in range(1, n + 1)]

    def boundary_release(src, cl, n_votes=None):
        # Wraps the REAL transition: the genuine CONFIRM->EXTERNALIZE edge runs
        # `externalize` BEFORE `admit`. Only then does the source hold a release
        # witness. `externalize` is the authority over the transition: it takes a
        # QUORUM-CERT of >= t signed member CONFIRM votes (each verified under a
        # per-member public subkey K_i committed to the epoch's roster) -- THERE
        # IS NO caller-asserted boolean (Copilot this review #2/#4). By default
        # the helper emits a FULL threshold of genuine votes for the SOURCE's own
        # epoch (the honest validators who reached CONFIRM); passing n_votes <
        # threshold yields an incomplete cert and the boundary REJECTS (mirrors a
        # close that did not actually reach the externalize quorum).
        src_epoch = src.epoch
        n_votes = src_epoch.threshold if n_votes is None else n_votes
        cert = {i: _confirm_vote(_validator_confirm_sk(GROUP_SK, i),
                                 cl.epoch_hash, cl.hash)
                for i in range(1, n_votes + 1)}
        if src._boundary.externalize(cl, cert):
            return src.admit(cl)
        return False

    def eval_unbound(attacker_src, attacker_auth, cl, adversary_pub_proof=None):
        # O2/non-commitment red test with the boundary ENFORCED: an attacker who
        # holds ONLY (epoch, a source, an authority) -- but never the genuine
        # source-boundary pairing -- can admit nothing and obtain NO proof. If an
        # adversary_pub_proof is supplied it must fail the pure verifier.
        admitted = attacker_src.admit(cl)            # boundary-enforced: no fact
        pr = attacker_src.proof(cl, attacker_auth)   # unbound -> refused (None)
        if adversary_pub_proof is not None:
            rejected = UniqueThresholdProof.verify(epoch, cl.hash,
                                                   adversary_pub_proof) is None
        else:
            rejected = True
        return (not admitted) and (pr is None) and rejected

    N_MEMBERS = 8
    roster = mk_roster(N_MEMBERS)
    # The epoch's committed authority/public key is the Schnorr stand-in public
    # key Y = G^d mod p derived from the recovered GROUP SECRET G. `verify`
    # binds every accepted proof to this committed key, so the genuine
    # threshold-recovered proofs verify and arbitrary bytes are rejected.
    epoch_pub = group_pub_from_seed(GROUP_SK, 5, N_MEMBERS)
    # A canonical VALID authority key for construction tests that must SUCCEED:
    # a non-identity order-q subgroup element (Copilot this review #1, High). A
    # raw 32-byte hash is only ~1/2 likely to be in the subgroup, so tests that
    # expect construction to succeed must pass a genuine group key, not a hash.
    vkey = group_pub_from_seed(GROUP_SK, 5, N_MEMBERS)
    epoch = EpochDescriptor(
        format_version=1,
        authority_key=epoch_pub,
        roster=roster,
        activation=12300, retirement=13000,
        threshold=5,
        root_rule=b"unique-threshold/v1",
        event_mapping=b"single-pulse:LockedClose->C_s/v1")
    source = RandomnessSource(epoch)
    auth = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
    source.bind(auth)
    slot = epoch.activation + 1
    prev_hash = sha256(u32(slot - 1) + b"real-predecessor-committed-core")

    # ---------- R1: epoch rule hash binds every rule -------------------------
    epoch_v2 = EpochDescriptor(
        format_version=1, authority_key=epoch.authority_key,
        roster=epoch.roster, activation=epoch.activation,
        retirement=epoch.retirement, threshold=epoch.threshold + 1,
        root_rule=epoch.root_rule, event_mapping=epoch.event_mapping)
    check("R1 epoch rule-hash: changing ANY rule (here threshold) yields a NEW "
          "epoch hash", epoch_v2.hash != epoch.hash)
    check("R1 epoch rule-hash: a re-derived epoch from the SAME canonical bytes "
          "re-derives the IDENTICAL hash (archival replay is stable)",
          EpochDescriptor(format_version=epoch.format_version,
                          authority_key=epoch.authority_key,
                          roster=epoch.roster, activation=epoch.activation,
                          retirement=epoch.retirement, threshold=epoch.threshold,
                          root_rule=epoch.root_rule,
                          event_mapping=epoch.event_mapping).hash == epoch.hash)
    check("R1 the roster is COMMITTED by the epoch: a substituted roster is a "
          "DIFFERENT epoch (freeze-the-team-before-the-draw, in the hash)",
          EpochDescriptor(format_version=epoch.format_version,
                          authority_key=epoch.authority_key,
                          roster=mk_roster(N_MEMBERS + 1),
                          activation=epoch.activation,
                          retirement=epoch.retirement, threshold=epoch.threshold,
                          root_rule=epoch.root_rule,
                          event_mapping=epoch.event_mapping).hash != epoch.hash)

    # ---------- R2: ThresholdAuthority is epoch-bound (no caller n/t/roster) --
    def raises(fn):
        try:
            fn()
            return False
        except ValueError:
            return True

    check("R2 ThresholdAuthority::from_epoch fails CLOSED on caller-supplied "
          "n/t/roster that disagrees with the epoch (threshold is a property of "
          "the locked authority, not an argument to the caller)",
          raises(lambda: ThresholdAuthority.from_epoch(epoch, GROUP_SK, n_members=3))
          and raises(lambda: ThresholdAuthority.from_epoch(epoch, GROUP_SK,
                                                           threshold=1))
          and raises(lambda: ThresholdAuthority.from_epoch(epoch, GROUP_SK,
                                                           roster=mk_roster(5))))
    check("R2 malformed thresholds are rejected at epoch construction (thread "
          "e6VduY): threshold=0 would emit a proof with zero shares and "
          "threshold>n could never resolve -- both are unsound epochs and raise",
          raises(lambda: EpochDescriptor(
              format_version=1, authority_key=vkey,
              roster=roster, activation=12300, retirement=13000, threshold=0,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1"))
          and raises(lambda: EpochDescriptor(
              format_version=1, authority_key=vkey,
              roster=roster, activation=12300, retirement=13000,
              threshold=len(roster) + 1,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1")))
    dup_roster = [roster[0], roster[0]] + [sha256(b"member-verify:dup")] * 3
    check("R2 duplicate roster keys are rejected at epoch construction (thread "
          "e6WbkN): one verification identity would occupy multiple threshold "
          "indices, violating 1:1 membership -- such a roster raises ValueError "
          "before n / membership_commitment are derived",
          raises(lambda: EpochDescriptor(
              format_version=1, authority_key=vkey,
              roster=dup_roster, activation=12300, retirement=13000,
              threshold=3, root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1")))
    # Copilot this review #1 (High): the committed authority key must be a
    # non-identity order-q subgroup element. Y=1 would let anyone satisfy
    # G^s == R*Y^c with Y^c=1 and forge proofs; an out-of-subgroup key is
    # malformed. Both must raise at construction -- the subgroup check is a
    # FIRST-CLASS soundness gate, and a raw random 32-byte hash is not
    # automatically in-subgroup.
    identity_key = (1).to_bytes(32, "big")
    out_of_group = (_GRP_P + 1).to_bytes(32, "big")        # >= p: not a residue
    non_residue = None
    # find a 32-byte value that is NOT in the order-q subgroup (pow(v,q,p)!=1):
    for probe in range(0x10000):
        cand = probe.to_bytes(32, "big")
        value = int.from_bytes(cand, "big")
        if 1 < value < _GRP_P and pow(value, _GRP_Q, _GRP_P) != 1:
            non_residue = cand
            break
    check("R2 authority_key subgroup validation (Copilot this review #1, High): "
          "an identity key (Y=1), an out-of-group value (>= p), or a NON-"
          "residue (Y^q != 1 mod p -- not in the order-q subgroup) is REJECTED "
          "at construction, so Y=1 cannot be used to forge proofs (G^s==R*Y^c "
          "with Y^c=1) and malformed keys can never be committed as a valid "
          "authority",
          raises(lambda: EpochDescriptor(
              format_version=1, authority_key=identity_key,
              roster=roster, activation=12300, retirement=13000, threshold=5,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1"))
          and raises(lambda: EpochDescriptor(
              format_version=1, authority_key=out_of_group,
              roster=roster, activation=12300, retirement=13000, threshold=5,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1"))
          and raises(lambda: EpochDescriptor(
              format_version=1, authority_key=non_residue,
              roster=roster, activation=12300, retirement=13000, threshold=5,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1"))
          and EpochDescriptor(
              format_version=1, authority_key=vkey,
              roster=roster, activation=12300, retirement=13000, threshold=5,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1").authority_key
          is not None)
    # Copilot this review #1 (High): the committed per-member CONFIRM
    # verification keys must ALSO be non-identity order-q subgroup elements. A
    # K_i = 1 (or out-of-group K_i) would let an observer choose any valid s and
    # set R = G^s so that K_i^c = 1 and the member's CONFIRM vote verifies
    # without that member ever signing -- minting votes for members who never
    # reached CONFIRM. Both the default-derived keys and any caller-supplied
    # confirm_pub go through the same gate.
    good_confirm_pub = tuple(_validator_confirm_pub(GROUP_SK, i)
                             for i in range(1, N_MEMBERS + 1))
    bad_confirm_identity = (1).to_bytes(32, "big")
    bad_confirm_out = (_GRP_P + 1).to_bytes(32, "big")
    check("R2 confirm_pub subgroup validation (Copilot this review #1, High): "
          "a per-member CONFIRM key that is the identity (K_i=1), out-of-group "
          "(>= p), or a NON-residue (K_i^q != 1 mod p) is REJECTED at epoch "
          "construction, so an observer cannot forge a member's CONFIRM vote via "
          "K_i^c = 1, and the committed order-q keys pass",
          raises(lambda: EpochDescriptor(
              format_version=1, authority_key=vkey,
              roster=roster, activation=12300, retirement=13000, threshold=5,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1",
              confirm_pub=(identity_key,) + good_confirm_pub[1:]))
          and raises(lambda: EpochDescriptor(
              format_version=1, authority_key=vkey,
              roster=roster, activation=12300, retirement=13000, threshold=5,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1",
              confirm_pub=(out_of_group,) + good_confirm_pub[1:]))
          and raises(lambda: EpochDescriptor(
              format_version=1, authority_key=vkey,
              roster=roster, activation=12300, retirement=13000, threshold=5,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1",
              confirm_pub=(non_residue,) + good_confirm_pub[1:]))
          and EpochDescriptor(
              format_version=1, authority_key=vkey,
              roster=roster, activation=12300, retirement=13000, threshold=5,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1",
              confirm_pub=good_confirm_pub).confirm_pub == good_confirm_pub)
    check("R2 honest-intersection Byzantine bound (thread eW_rR): an epoch whose "
          "threshold violates 2*t - n > f is rejected -- two t-subsets could "
          "overlap only in Byzantine members and mint two same-slot proofs. "
          "With n=8, t=2 (2t-n= -4, no honest intersection even with f=0) the "
          "descriptor must raise ValueError",
          raises(lambda: EpochDescriptor(
              format_version=1, authority_key=vkey,
              roster=mk_roster(8), activation=12300, retirement=13000,
              threshold=2, root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1"))
          and raises(lambda: EpochDescriptor(
              format_version=1, authority_key=vkey,
              roster=mk_roster(8), activation=12300, retirement=13000,
              threshold=5, byzantine_bound=2,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1"))
          # AVAILABILITY fail-closed (Copilot this review): a caller-forced f is
          # PRESERVED (never re-clamped down) and then rejected when t <= n-f is
          # violated. n=8, t=7 with a forced f=5 must REJECT (7 <= 3 is false),
          # while the DEFAULT f = n - t = 1 is valid and provable.
          and raises(lambda: EpochDescriptor(
              format_version=1, authority_key=vkey,
              roster=mk_roster(8), activation=12300, retirement=13000,
              threshold=7, byzantine_bound=5,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1"))
          and EpochDescriptor(
              format_version=1, authority_key=vkey,
              roster=mk_roster(8), activation=12300, retirement=13000,
              threshold=7, root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1").byzantine_bound == 1
          and epoch.byzantine_bound == 1)  # n=8,t=5 => default f = 2t-n-1 = 1
    rogue_auth = ThresholdAuthority.from_epoch(epoch, sha256(b"rogue-seed"))

    # ---------- Single-pulse primitives ---------------------------------------
    cl_a = LockedClose(epoch, slot, prev_hash, sha256(b"externalized-value-A"))
    cl_b = LockedClose(epoch, slot, prev_hash, sha256(b"externalized-value-B"))

    rogue_source = RandomnessSource(epoch)
    rogue_source.bind(rogue_auth)
    boundary_release(rogue_source, cl_a)
    # `proof()` is called on the rogue path so `_released` is populated and
    # `share` becomes reachable for that rogue authority; the check below then
    # shows the rogue-produced carrier (different polynomial) is NOT a valid
    # share under the canonical authority, and the committed-C_i binding
    # (thread evw9Z) means the rogue authority can no longer emit ANY proof for
    # this epoch.
    rogue_proof = rogue_source.proof(cl_a, rogue_auth)
    rogue_share = rogue_auth.share(1, cl_a)

    check("R2 same epoch hash, substituted member mapping: a share produced by a "
          "different (seed/secret) authority for the same epoch is NOT a valid "
          "share of the canonical authority; with no valid shares, recover is "
          "None; and (thread evw9Z) the committed-C_i binding means the "
          "rogue-seed authority cannot produce ANY proof for this epoch",
          rogue_share is not None
          and rogue_proof is None
          and not auth.verify_share(1, cl_a, rogue_share)
          and auth.recover_proof([(1, rogue_share)], cl_a) is None)

    # ---------- R3 / Noot #5: predecessor-state epoch selection --------------
    wrong_prev = sha256(u32(slot - 1) + b"an-alien-predecessor")
    cl_wrong_prev = LockedClose(epoch, slot, wrong_prev,
                                sha256(b"externalized-value-A"))
    check("R3 previousLedgerHash is the REAL Core predecessor hash: changing "
          "ONLY that committed predecessor changes C_s and therefore the "
          "canonical proof/root (a vector Noot asked for; no cross-reorg "
          "randomness)",
          cl_wrong_prev.hash != cl_a.hash and prev_hash != wrong_prev)

    committed = {sha256(b"prev-canonical-state"): (epoch,)}
    selected = epoch_for_transition(sha256(b"prev-canonical-state"), committed,
                                    epoch.activation + 1)
    check("N5 epoch-for-slot is a pure function of the PREDECESSOR canonical "
          "state: exactly one committed epoch window matching -> the epoch is "
          "selected; never local qsets or membership bookkeeping",
          selected is epoch
          and epoch_for_transition(sha256(b"prev-canonical-state"), committed,
                                   slot) is epoch)
    check("N5 fail-closed selection: a DIFFERENT predecessor (no committed "
          "epoch window) yields NO selection, and a slot outside every window "
          "also yields none -- zero or two candidates both fail closed",
          epoch_for_transition(sha256(b"some-other-predecessor"), committed,
                               slot) is None
          and epoch_for_transition(sha256(b"prev-canonical-state"), committed,
                                   epoch.retirement + 1) is None)
    other_win_pub = group_pub_from_seed(GROUP_SK, 3, 4)
    other_win = EpochDescriptor(
        format_version=1, authority_key=other_win_pub,
        roster=mk_roster(4), activation=epoch.activation - 50,
        retirement=epoch.retirement + 50, threshold=3,
        root_rule=epoch.root_rule, event_mapping=epoch.event_mapping)
    overlap = {sha256(b"prev-canonical-state"): (epoch, other_win)}
    check("N5 fail-closed overlap: two committed epochs whose windows BOTH cover "
          "the slot select NOTHING (no caller/config/cache picks one of them)",
          epoch_for_transition(sha256(b"prev-canonical-state"), overlap, slot) is None)

    # ---------- Single pulse: closed ledger -> one C_s -> one proof -> one root
    auth_b = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
    src_b = RandomnessSource(epoch)
    src_b.bind(auth_b)
    boundary_release(src_b, cl_b)
    pb_b = src_b.proof(cl_b, auth_b)
    check("single-pulse binding: different externalized bytes -> distinct C_s "
          "as well as distinct proof/root under the same epoch+network+predecessor",
          cl_a.hash != cl_b.hash
          and UniqueThresholdProof.verify(epoch, cl_b.hash, pb_b)
          != UniqueThresholdProof.verify(epoch, cl_a.hash, pb_b)
          and pb_b is not None)
    check("dnFV6 no undefined outcome class: C_s is EXACTLY "
          "H(CloseLock||RandomnessCloseInputV1(in_v1)); there is NO second "
          "independently encoded challenge -- the primitive evaluates the "
          "already-canonical C_s directly (no caller byte can mint an "
          "undefined-outcome draw)",
          cl_a.validate() and not hasattr(cl_a, "challenge")
          and NO_CALLER_OUTCOME_CLASS == frozenset())

    # ---------- Release boundary: CONFIRM/EXTERNALIZE + fully validated ------
    # Copilot (this review): the release fact is NOT caller-asserted. A source
    # admits a close only when its boundary GENUINELY ran CONFIRM->EXTERNALIZE;
    # there is no public way to stamp a close released. accepted-commit /
    # "fully_validated" are no longer caller booleans -- they live inside the
    # transition.
    src_early = RandomnessSource(epoch)          # boundary never ran for cl_a
    early_ok = src_early.admit(cl_a)             # boundary-enforced -> False
    check("dnFVg release boundary: no CONFIRM/EXTERNALIZE for a close means "
          "nothing can be admitted -- in particular an accepted-commit/prepared "
          "close (which is not the externalize edge) cannot authorize a proof or "
          "share, and the close stays UNKNOWN (stalled apply)",
          not early_ok
          and not src_early._boundary.has_externalized(cl_a)
          and src_early.proof(cl_a, auth) is None
          and resolve(epoch, cl_a, src_early, None)["outcome"] == "UNKNOWN")
    alien_stage = RandomnessSource(epoch)
    # A bare/incomplete CONFIRM cert (< t votes) is REJECTED by the edge: there
    # is no caller boolean, only a quorum-cert that must authenticate and reach
    # the threshold (Copilot this review #2).
    stage_boundary = alien_stage._boundary
    weak_cert = {i: _confirm_vote(_validator_confirm_sk(GROUP_SK, i),
                                  cl_a.epoch_hash, cl_a.hash)
                 for i in range(1, epoch.threshold)}        # t-1 votes only
    bogus_cert = {1: b"\x00" * 64}                          # unauthenticated
    not_validated = (not stage_boundary.externalize(cl_a, weak_cert)
                     and not stage_boundary.externalize(cl_a, bogus_cert)
                     and not stage_boundary.has_externalized(cl_a)
                     and not boundary_release(alien_stage, cl_a, n_votes=0))
    check("dnFVg release boundary: the CONFIRM/EXTERNALIZE transition itself "
          "rejects a value whose quorum-cert is absent, INCOMPLETE (< t distinct "
          "valid votes) or unauthenticated (externalize returns False; no "
          "witness, no proof, no share) -- there is NO caller-asserted "
          "`fully_validated` boolean",
          not_validated
          and not alien_stage._boundary.has_externalized(cl_a)
          and alien_stage.proof(cl_a, auth) is None)
    ok_boundary = boundary_release(source, cl_a)
    proof_a = source.proof(cl_a, auth)
    root_a = UniqueThresholdProof.verify(epoch, cl_a.hash, proof_a)
    check("dnFVg release boundary + proof/root split: after CONFIRM/EXTERNALIZE "
          "with full local validation a proof is reconstructed from >=t shares, "
          "and that proof is a distinct authenticator -- NOT the root",
          ok_boundary and proof_a is not None
          and proof_a != root_a and root_a is not None)
    check("dnFVg an UNadmitted close is REJECTED, never ROOT",
          resolve(epoch, cl_b, source, pb_b)
          == {"event_hash": cl_b.hash.hex(), "outcome": "REJECTED"})

    # ---------- Noot #3: genuine threshold theorem ----------------------------
    t = epoch.threshold
    full_shares = [(i, auth.share(i, cl_a)) for i in range(1, N_MEMBERS + 1)]
    below = auth.recover_proof(full_shares[:t - 1], cl_a)
    check("N3 threshold: t-1 valid shares recover NO proof (nothing below t can "
          "reconstruct the canonical P_s)", below is None)
    recovered = {}
    all_same = True
    for combo in itertools.combinations(range(1, N_MEMBERS + 1), t):
        sub = [(i, auth.share(i, cl_a)) for i in combo]
        p = auth.recover_proof(sub, cl_a)
        recovered[frozenset(combo)] = p
        if p != proof_a:
            all_same = False
    check("N3 threshold: every one of %d distinct valid t-subsets (and any "
          "permutation) recovers the SAME canonical P_s -- byte-identical; no "
          "subset flavors the proof" % len(recovered),
          len(recovered) == len(list(itertools.combinations(
              range(1, N_MEMBERS + 1), t))) and all_same and len(recovered) >= 2)
    plus = auth.recover_proof(full_shares[:t + 1], cl_a)
    full = auth.recover_proof(full_shares, cl_a)
    check("N3 threshold: t+1 and full sets ALSO recover the identical canonical "
          "P_s", plus == proof_a and full == proof_a)
    junk = [(3, auth.share(3, cl_a))]                        # duplicate member 3
    junk += [(N_MEMBERS + 9, sha256(b"out-of-roster"))]      # out of roster
    junk += [(6, auth.share(6, cl_b))]                       # wrong close
    junk += [(2, sha256(b"waste:2"))]                        # invalid share
    mixed_epoch = [(i, auth.share(i, cl_a)) for i in range(1, t + 1)] + junk
    check("N3 threshold: invalid/duplicate/out-of-roster/wrong-close shares are "
          "DISCARDED individually and never poison t otherwise valid shares -- "
          "same canonical P_s with junk present",
          auth.recover_proof(mixed_epoch, cl_a) == proof_a
          and auth.recover_proof(junk, cl_a) is None)
    check("N3 threshold: a t-subset of a DIFFERENT close's shares cannot forge "
          "cl_a's proof (share is close-bound)",
          auth.recover_proof([(i, auth.share(i, cl_b)) for i in range(1, t + 1)],
                             cl_a) is None)
    # ======== Distributed FROST: verify/recover run WITHOUT the master secret
    # (Copilot this review, High - evMSO). A verifier-only authority constructed
    # from the SAME epoch but a SHAM seed (it holds NO group secret, NO share,
    # NO nonce) must verify honest carriers and reconstruct the byte-identical
    # canonical proof purely from the PUBLICLY broadcast nonce-commitment set
    # {i -> N_i} and the N_i / C_i carried in each share -- contacting none of
    # `self.seed`, `f(i)`, or `n(i)`. In a real distributed FROST the nonce
    # commitments are broadcast up front, so the verifier legitimately holds
    # that public set.
    verifier_only = ThresholdAuthority.from_epoch(epoch, sha256(b"peer-verifier-only"))
    public_nonces = {i: c[1] for (i, c) in full_shares}   # public broadcast set
    verifier_only._published_nonces[cl_a.hash] = dict(public_nonces)
    peer_accepted = all(verifier_only.verify_share(i, cl_a, carrier)
                        for (i, carrier) in full_shares)
    peer_proof = verifier_only.recover_proof(full_shares, cl_a)
    check("N3/threshold distributed-FROST peer verifiability (Copilot this "
          "review, High): an authority holding NO master seed -- the same epoch, "
          "a SHAM seed -- verifies every honest public N_i/C_i carrier and "
          "reconstructs the byte-identical canonical P_s, so verification is "
          "authentically distributed (public commitments only, no secret)",
          peer_accepted and peer_proof == proof_a)
    check("N3/threshold distributed-FROST forged carriers (Copilot this review, "
          "High): a replayed/wrong-owner carrier is REJECTED by the secret-free "
          "verifier -- including the identity-Feldman attack `C_i = 1` (which "
          "would reduce the partial equation to `G^{s_i} == N_i` and count "
          "`(s_i=1, N_i=G)` as valid for any challenge) and any C_i that is NOT "
          "the epoch-committed one -- so a Byzantine rostered sender cannot "
          "poison reconstruction, and the accepted set stays clean",
          not verifier_only.verify_share(1, cl_a, (full_shares[0][1][0],
                                                   full_shares[0][1][1],
                                                     (1).to_bytes(32, "big")))
          and not verifier_only.verify_share(1, cl_a, (full_shares[0][1][0],
                                                       full_shares[0][1][1],
                                                       sha256(b"wrong-feldman")))
          and not verifier_only.verify_share(1, cl_a, (full_shares[0][1][0],
                                                       sha256(b"wrong-nonce"),
                                                       full_shares[0][1][2]))
          and not verifier_only.verify_share(
              1, cl_a, (sha256(b"forged-s"), public_nonces[1],
                        full_shares[0][1][2])))
    cl_foreign = LockedClose(other_win, slot, prev_hash,
                             sha256(b"externalized-value-A"))
    check("N3 mixed-epoch rejected: an authority instantiated for epoch A cannot "
          "share over (or reconstruct a proof for) a close of epoch B",
          auth.share(1, cl_foreign) is None
          and auth.recover_proof([], cl_foreign) is None)
    check("N1 authorization never flavors the pulse: the proof recovered from "
          "any >=t share subset equals the resolver's admitted proof -- the same "
          "close, same P_s, same root, whatever the witness/release path",
          full == proof_a and canonical_root(cl_a.hash, epoch.authority_key,
                                             epoch.hash, full) == root_a)

    # ---------- Durable sign-once per event (Noot) ----------------------------
    auth2 = auth.restart()
    again2 = auth2.share(1, cl_a)
    check("N3 durable sign-once: the same (epoch, slot, C_s) retry is IDEMPOTENT "
          "-- a restarted authority re-derives the SAME share and reconstructs "
          "the SAME canonical P_s/R_s with no new authority choice",
          again2 == auth.share(1, cl_a)
          and auth2.recover_proof([(i, auth2.share(i, cl_a))
                                   for i in range(1, t + 1)], cl_a) == proof_a)
    cl_a_alt = LockedClose(epoch, slot, prev_hash,
                           sha256(b"externalized-value-ALT"))
    auth_m = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
    # Release-closer for the authority is ONLY the source boundary path, so
    # admit via a source bound to auth_m; a competing same-slot close needs its
    # own source (slot-lock: one canonical close per slot) but SHARES the same
    # authority's durable `_signed`/`_released` state.
    src_m = RandomnessSource(epoch)
    src_m.bind(auth_m)
    boundary_release(src_m, cl_a)
    src_m.proof(cl_a, auth_m)
    alt_src_m = RandomnessSource(epoch)
    alt_src_m.bind(auth_m)
    boundary_release(alt_src_m, cl_a_alt)
    alt_src_m.proof(cl_a_alt, auth_m)
    auth_m.share(1, cl_a)
    refused = auth_m.share(1, cl_a_alt)          # same event, different C_s
    check("N3 durable sign-once: a member that already signed the event refuses "
          "a DIFFERENT C_s for the SAME slot -- two roots from one member are "
          "impossible; an SCP safety failure stalls randomness, it cannot mint "
          "two roots", refused is None
          and auth_m.share(1, cl_a) == auth.share(1, cl_a))
    # e6Vduq: sign-once is keyed by (member, slot) -> C_s, so ONE durable
    # authority can sign DISTINCT future slots (a normal ledger sequence) and
    # refuses only competing C_s for the SAME slot.
    cl_s2 = LockedClose(epoch, slot + 1, sha256(b"next-prev"),
                        sha256(b"externalized-value-B"))
    auth_f = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
    src_f1 = RandomnessSource(epoch)
    src_f1.bind(auth_f)
    boundary_release(src_f1, cl_a)
    src_f1.proof(cl_a, auth_f)
    src_f2 = RandomnessSource(epoch)
    src_f2.bind(auth_f)
    boundary_release(src_f2, cl_s2)
    src_f2.proof(cl_s2, auth_f)
    auth_f.share(1, cl_a)
    s1 = auth_f.share(1, cl_a)
    s2 = auth_f.share(1, cl_s2)                   # different slot is allowed
    refused_s2 = auth_f.share(1, LockedClose(
        epoch, slot + 1, sha256(b"next-prev"),
        sha256(b"externalized-value-B-ALT")))
    check("N3 durable sign-once keyed by (member, slot): one authority signs "
          "DISTINCT future slots (a real ledger sequence) and refuses only a "
          "competing C_s for the SAME already-signed slot -- consecutive closed "
          "ledgers are not accidentally serialized into one event (thread "
          "e6Vduq). The SHARE is MESSAGE-DEPENDENT (FROST/Feldman: a partial "
          "s_i = n(i) + c*f(i) is bound to its cl_hash by a fresh secret nonce), "
          "so s1 != s2 and neither is reusable for the other close -- a peer "
          "holding t partials from one slot cannot forge the next slot's "
          "pre-lock proof (Copilot this review #3, High) -- while the same-close "
          "re-emission is idempotent (s1 reproducible) and the durable _signed "
          "lock still refuses a competing C_s at a signed slot",
          s1 == auth_f.share(1, cl_a) and s2 is not None and s1 != s2
          and refused_s2 is None
          and auth_f.recover_proof([(1, s1)], cl_s2) is None)
    # e6Vdt1: restart CARRIES the durable sign-once locks, so a crash window
    # cannot equivocate -- after restart the member still refuses the alternate
    # C_s for any slot it already signed.
    auth_r = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
    src_r = RandomnessSource(epoch)
    src_r.bind(auth_r)
    boundary_release(src_r, cl_a)
    src_r.proof(cl_a, auth_r)
    alt_src_r = RandomnessSource(epoch)
    alt_src_r.bind(auth_r)
    boundary_release(alt_src_r, cl_a_alt)
    alt_src_r.proof(cl_a_alt, auth_r)
    auth_r.share(1, cl_a)                         # sign before crash
    auth_rb = auth_r.restart()                     # crash + deterministic restart
    post_crash_ok = auth_rb.share(1, cl_a)         # same event: idempotent
    post_crash_refused = auth_rb.share(1, cl_a_alt)  # opposite event: refused
    check("N3 crash-window sign-once: restart() carries the durable locks -- "
          "the SAME event re-signs idempotently after a crash and a DIFFERENT "
          "C_s for an already-signed slot is still refused, so an authority "
          "cannot restart to mint an equivocation (thread e6Vdt1)",
          post_crash_ok == s1 and post_crash_refused is None)

    # ---------- B2: C_s binds the EXACT value bytes --------------------------
    prng_a, appl_a, nom_a = (consumer_kdf(root_a, LABEL_PRN),
                             consumer_kdf(root_a, LABEL_APPLY),
                             consumer_kdf(root_a, LABEL_NOM))
    check("dnFWi single pulse, three labelled consumers: PRNG/APPLY/(next) "
          "NOMINATION are distinct KDF labels over ONE root -- not three "
          "independent draws",
          len({prng_a, appl_a, nom_a}) == 3
          and consumer_kdf(root_a, LABEL_PRN) == prng_a)
    source_b = RandomnessSource(epoch)
    b_auth = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
    source_b.bind(b_auth)
    boundary_release(source_b, cl_b)
    check("B2 C_s binds the externalized value: a proof for value A FAILS "
          "against value B, and B resolves only under its own admitted proof",
          resolve(epoch, cl_b, source, proof_a)["outcome"] == "REJECTED"
          and resolve(epoch, cl_b, source_b, source_b.proof(cl_b, b_auth))
          ["outcome"] == "ROOT")

    # ---------- Epoch gate: bind to THIS epoch (dnFVu) -------------------------
    other_source = RandomnessSource(other_win)
    o_auth = ThresholdAuthority.from_epoch(other_win, GROUP_SK)
    other_source.bind(o_auth)
    other_slot = other_win.activation + 50
    cl_o = LockedClose(other_win, other_slot,
                       sha256(u32(other_slot - 1) + b"prev-o"),
                       sha256(b"externalized-value-A"))
    boundary_release(other_source, cl_o)
    check("dnFVu epoch binding: a close derived under a DIFFERENT epoch is "
          "REJECTED under the calling epoch; it resolves only under its own "
          "epoch+source",
          other_win.hash != epoch.hash
          and cl_o.epoch_hash != epoch.hash
          and resolve(other_win, cl_o, other_source,
                      other_source.proof(cl_o, o_auth))["outcome"] == "ROOT"
          and resolve(epoch, cl_o, source, other_source.proof(cl_o, o_auth))
          == {"event_hash": cl_o.hash.hex(), "outcome": "REJECTED"})

    # ---------- Admission keyed by the EXACT close (dnFWo) ---------------------
    cl_c = LockedClose(epoch, slot + 5,
                       sha256(u32(slot + 4) + b"real-predecessor-committed-core"),
                       sha256(b"externalized-value-A"))
    src_slot = RandomnessSource(epoch)
    boundary_release(src_slot, cl_c)
    sl_auth = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
    check("dnFWo admission by the exact close: admitting one close (value+slot) "
          "does NOT stock a valid proof for a DIFFERENT close sharing only the "
          "value bytes -- cl_a's proof is absent and its stale try is UNKNOWN",
          src_slot.has_valid_proof(cl_c)
          and cl_c.hash != cl_a.hash
          and not src_slot.has_valid_proof(cl_a)
          and resolve(epoch, cl_a, src_slot, src_slot.proof(cl_a, sl_auth))
          == {"event_hash": cl_a.hash.hex(), "outcome": "UNKNOWN"})

    # ---------- dnFWC: length-prefixed epoch preimage is injective -------------
    pair1 = EpochDescriptor(format_version=epoch.format_version,
                            authority_key=epoch.authority_key,
                            roster=epoch.roster, activation=epoch.activation,
                            retirement=epoch.retirement, threshold=epoch.threshold,
                            root_rule=b"a", event_mapping=b"bc")
    pair2 = EpochDescriptor(format_version=epoch.format_version,
                            authority_key=epoch.authority_key,
                            roster=epoch.roster, activation=epoch.activation,
                            retirement=epoch.retirement, threshold=epoch.threshold,
                            root_rule=b"ab", event_mapping=b"c")
    check("dnFWC epoch preimage is injective (length-prefixed): "
          "(root_rule=b'a',event_mapping=b'bc') vs (root_rule=b'ab',event_mapping"
          "=b'c') yields DIFFERENT epoch hashes", pair1.hash != pair2.hash)

    # ---------- dnFV1: the proof verifier/encoding is canonicalized in the -----
    # ---------- epoch identity (Copilot d7OY2) --------------------------------
    verif_change = EpochDescriptor(format_version=epoch.format_version,
                                   authority_key=epoch.authority_key,
                                   roster=epoch.roster,
                                   activation=epoch.activation,
                                   retirement=epoch.retirement,
                                   threshold=epoch.threshold,
                                   root_rule=epoch.root_rule,
                                   event_mapping=epoch.event_mapping,
                                   verifier_rule=b"unique-threshold/v2-alt")
    check("dnFV1 the proof verifier/encoding is a canonical member of the epoch "
          "rule-hash: a verifier/encoding change alone produces a NEW epoch "
          "identity (single-interpretation + permanent-pulse invariant)",
          verif_change.hash != epoch.hash
          and verif_change.verifier_rule != epoch.verifier_rule)

    # ---------- Proof canonicalization (Noot: one proof = one byte future) ----
    check("P-CANON proof malleability: a non-canonical byte string "
          "(trailing padding, alternate group-element/scalar encoding) is NOT "
          "accepted by the pure verifier and can never produce a different R_s; "
          "any two accepted encodings canonicalize to the SAME bytes before "
          "influencing the root",
          UniqueThresholdProof.verify(epoch, cl_a.hash, proof_a + b"\x00") is None
          and UniqueThresholdProof.verify(epoch, cl_a.hash, proof_a + b"\x00\x00")
          is None
          and canonical_proof(proof_a) == proof_a)

    # ---------- canonical proof is NOT a function of caller evidence ----------
    src_w1 = RandomnessSource(epoch)
    src_w2 = RandomnessSource(epoch)
    a_w1 = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
    a_w2 = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
    src_w1.bind(a_w1)
    src_w2.bind(a_w2)
    ok_w1 = boundary_release(src_w1, cl_a)
    ok_w2 = boundary_release(src_w2, cl_a)
    p_w1 = src_w1.proof(cl_a, a_w1)
    p_w2 = src_w2.proof(cl_a, a_w2)
    check("dnFVg canonical proof/root: two DIFFERENT honest release boundaries "
          "for the SAME close admit the IDENTICAL canonical proof and root -- "
          "the boundary witness authorizes release only and never changes the "
          "permanent pulse",
          ok_w1 and ok_w2 and p_w1 == p_w2 and p_w1 == proof_a
          and canonical_root(cl_a.hash, epoch.authority_key, epoch.hash,
                             proof_a) == root_a)

    # ---------- cross-network binding (Copilot d7OZI) --------------------------
    foreign_net = LockedClose.rebuild(epoch, slot, prev_hash,
                                      sha256(b"externalized-value-A"),
                                      network_id=sha256(b"SomeOtherNetwork"))
    foreign_src = RandomnessSource(epoch)
    admitted_foreign = boundary_release(foreign_src, foreign_net)
    check("dnFVu cross-network binding: a self-consistent close rebuilt under a "
          "NON-local network id is REJECTED by the resolver (never ROOT), and is "
          "never admitted by this source -- the boundary transition itself "
          "refuses an out-of-network close",
          not admitted_foreign
          and resolve(epoch, foreign_net, foreign_src, proof_a)
          == {"event_hash": foreign_net.hash.hex(), "outcome": "REJECTED"})

    # ---------- B3: transport/replay composition (schedule-driven) -------------
    n_events = 601
    evs, proofs = [], {}
    for i in range(n_events):
        s = epoch.activation + 2 + i               # distinct, in-window, != slot
        prev = sha256(u32(s - 1) + b"real-predecessor-%d" % s)
        c = LockedClose(epoch, s, prev, sha256(b"protect:%d" % i))
        evs.append(c)
        boundary_release(source, c)
        proofs[i] = source.proof(c, auth)
    schedules = [
        lambda i: True,
        lambda i: i % 2 == 0,
        lambda i: i % 3 != 1,
        lambda i: i % 4 in (0, 3),
    ]
    wire_orders = [
        list(range(n_events)),
        list(reversed(range(n_events))),
        [i for i in range(n_events) if i % 2 == 1]
        + [i for i in range(n_events) if i % 2 == 0],
        list(range(n_events // 2)) + list(range(n_events // 2, n_events)),
    ]

    def history_digest(rows):
        canon = b"".join(
            d["event_hash"].encode() + d["outcome"].encode()
            + d.get("source_root", "").encode() for d in rows)
        return sha256(canon).hex()

    canon_map = {evs[i].slot: i for i in range(n_events)}

    def slot_order_root(rows_by_slot):
        return b"".join(
            (bytes.fromhex(rows_by_slot[evs[i].slot]["source_root"])
             if rows_by_slot[evs[i].slot]["outcome"] == "ROOT" else b"UNKNOWN")
            for i in sorted(range(n_events), key=lambda j: evs[j].slot))

    transient_digests, route_confluent = set(), True
    for sched in schedules:
        per_sched = None
        for wire in wire_orders:
            seen = {}
            for idx in wire:
                seen[evs[idx].slot] = resolve(
                    epoch, evs[idx], source, proofs[idx] if sched(idx) else None)
            seq = tuple((seen[evs[i].slot]["outcome"],
                         seen[evs[i].slot].get("source_root", ""))
                        for i in sorted(range(n_events),
                                        key=lambda j: evs[j].slot))
            transient_digests.add(history_digest(
                [seen[evs[i].slot] for i in range(n_events)]))
            if per_sched is None:
                per_sched = seq
            elif seq != per_sched:
                route_confluent = False
    all_root_vals = []
    for i in range(n_events):
        d = resolve(epoch, evs[i], source, proofs[i])
        all_root_vals.append(d["source_root"])
    tr_unique = len(set(all_root_vals)) == n_events
    flushed_digest = history_digest([
        resolve(epoch, evs[i], source, proofs[i]) for i in range(n_events)])
    # Copilot 3917696376: every schedule is a PER-EVENT DELIVERY SEQUENCE (each
    # event delivers either its genuine proof or nothing), which we FLUSH
    # (observe the terminal steady state after applying each delivered payload).
    # We pin the TERMINAL history digest of EVERY schedule against a registered
    # literal -- not just the full-delivery case.
    terminal_digests = [
        history_digest([resolve(epoch, evs[i], source,
                                proofs[i] if sched(i) else None)
                        for i in range(n_events)])
        for sched in schedules
    ]
    check("C realizations genuinely differ: distinct (schedule x wire-order) "
          "profiles yield distinct transient partial-observation histories",
          len(transient_digests) > 1)
    check("C compositional one-future: for a FIXED schedule the final per-slot "
          "outcome map is IDENTICAL across every wire order (resolve()-state "
          "transitions are confluent), and every delivered close yields a "
          "DISTINCT canonical root -- no 2^n fan-out, no order-dependent roots",
          route_confluent and tr_unique and flushed_digest == history_digest(
              [resolve(epoch, evs[i], source, proofs[i])
               for i in range(n_events)]))

    # ---------- Noot #3: applied history is a PREFIX of one canonical history ---
    canon_roots = [bytes.fromhex(all_root_vals[i])
                   for i in sorted(range(n_events), key=lambda j: evs[j].slot)]
    prefix_ok = True
    for sched in schedules:
        applied, stalled = [], False
        for i in sorted(range(n_events), key=lambda j: evs[j].slot):
            if stalled:
                continue
            d = resolve(epoch, evs[i], source, proofs[i] if sched(i) else None)
            if d["outcome"] == "ROOT":
                applied.append(bytes.fromhex(d["source_root"]))
            elif d["outcome"] == "UNKNOWN":
                stalled = True
        if applied != canon_roots[:len(applied)]:
            prefix_ok = False
    check("N3 ledger-realistic applied history: under every delivery schedule "
          "the APPLIED root sequence is a PREFIX of the canonical slot-ordered "
          "history -- nodes cache future proofs but their applied view stalls at "
          "the first gap, so nodes differ only in prefix length, never an applied "
          "ROOT,UNKNOWN,ROOT hole", prefix_ok)

    # e6Vdu_: explicit UNKNOWN -> ROOT transition for the SAME close. Delaying
    # the proof (a `[none, proof]`-style schedule for THAT event) must first
    # yield UNKNOWN (apply stalls) and later the identical ROOT once the proof
    # arrives -- a per-event delivery sequence, not proof-permanently-present.
    mid = evs[n_events // 2]
    res_first = resolve(epoch, mid, source, None)
    res_after = resolve(epoch, mid, source, source.proof(mid, auth))
    check("B3 per-event UNKNOWN -> ROOT: an event whose proof arrives LATE "
          "(a `[none, proof]`-style schedule) first resolves UNKNOWN (apply "
          "stalls, never a substitute entropy branch) and then, on the proof "
          "delivery, resolves the IDENTICAL canonical path root -- the same "
          "close, one proven root, availability-only difference (thread e6Vdu_)",
          res_first == {"event_hash": mid.hash.hex(), "outcome": "UNKNOWN"}
          and res_after["outcome"] == "ROOT"
          and res_after["source_root"] == bytes.fromhex(all_root_vals[
              [i for i in range(n_events) if evs[i].slot == mid.slot][0]]
          ).hex() and res_after["source_root"]
          == UniqueThresholdProof.verify(epoch, mid.hash,
                                         source.proof(mid, auth)).hex())

    # ---------- B4: authority surface -------------------------------------------
    resolved = resolve(epoch, cl_a, source, proof_a)
    permitted = {"event_hash", "outcome", "source_root"}
    check("B4 authority surface: the resolved object holds ONLY "
          "{event_hash, outcome, source_root?} -- no successor/delegate/"
          "membership-edit/recovery/permission field",
          set(resolved.keys()) == permitted
          and not hasattr(epoch, "successor")
          and not hasattr(epoch, "delegate"))

    # ---------- O1: one use -> one pulse (competing same-slot admissions) ------
    comp_src = RandomnessSource(epoch)
    comp_auth = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
    comp_src.bind(comp_auth)
    c1 = LockedClose(epoch, slot + 300, prev_hash, sha256(b"value-one"))
    c2 = LockedClose(epoch, slot + 300, prev_hash, sha256(b"value-two"))
    ok_c1 = boundary_release(comp_src, c1)
    ok_c2 = boundary_release(comp_src, c2)
    check("O1 competing same-slot admission: the source keeps ONE canonical slot "
          "lock -- the first admitted close for the slot stays, a SECOND "
          "different value for the SAME slot is REFUSED and can never resolve to "
          "a root (retries may change availability, never the root)",
          ok_c1 and not ok_c2
          and comp_src.proof(c2, comp_auth) is None
          and resolve(epoch, c1, comp_src, comp_src.proof(c1, comp_auth))
          ["outcome"] == "ROOT"
          and resolve(epoch, c2, comp_src, comp_src.proof(c2, comp_auth))
          ["outcome"] == "UNKNOWN"
          and boundary_release(comp_src, c1))
    cand_vals = [
        (slot, sha256(b"externalized-value-A"), proof_a),
        (slot, sha256(b"externalized-value-B"), None),
        (slot + 5, sha256(b"externalized-value-A"), None),
        (slot, sha256(sha256(b"externalized-value-A") + b"alias"), None),
    ]
    drawn_root_set = set()
    for (sl, val, pfx) in cand_vals:
        c = LockedClose(epoch, sl, prev_hash, val)
        if pfx is not None:
            r = resolve(epoch, c, source, pfx)
            if r["outcome"] == "ROOT":
                drawn_root_set.add(r["source_root"])
    check("O1 one use -> one pulse: exactly ONE distinct root is drawn for the "
          "canonical close; value/slot/value-nonce candidates are distinct "
          "closes that are never valid draws -- a consumer cannot lock N draws "
          "and pick one after seeing roots",
          drawn_root_set == {root_a.hex()}
          and len({LockedClose(epoch, sl, prev_hash, val).hash
                   for (sl, val, _) in cand_vals}) >= 3)

    # ---------- O2: earliest-knowledge sealing (the brutal red test) ----------
    cand_closes = [LockedClose(epoch, epoch.activation + 2 + c,
                               sha256(u32(epoch.activation + 1 + c)
                                      + b"pre-lock-prev"),
                               sha256(b"cand:%d" % c)) for c in range(8)]
    spoof = ThresholdAuthority.from_epoch(epoch, sha256(b"spoof-seed"))
    attacker_forged = []
    for _c in cand_closes:
        attacker_forged.append(spoof.recover_proof(
            [(i, spoof.share(i, _c)) for i in range(1, t)], _c))
        # A spoof-secret (different seed) authority is never boundary-released,
        # so its shares are None and it recovers no proof at all.
    # Copilot this review #1 (High): the negative-synthesis evidence is driven
    # ONLY through the `AttackerView` façade -- an attacker object that is
    # constructed with PUBLIC material (authority_key, roster, membership
    # commitment, candidate closes) and exposes NO shares, seed, _group_secret,
    # or _spf_sign. The honest (admitted) proof, when it exists, is produced
    # exclusively through the ThresholdAuthority / RandomnessSource signing
    # path. This is what separates "the attacker interface cannot sign" from a
    # naive "read the file" reading of the harness. The model documents that the
    # information-theoretic <t-share secrecy itself is the primitive's guarantee
    # (BLS/VUF), not re-derived here.
    attacker = AttackerView(epoch, cand_closes)
    assert attacker.authority_key == epoch.authority_key
    # PUBLIC-only synthesized proofs: a scalar guessed from the committed public
    # key is an attacker's closest public estimate of d -- it is NOT d, and the
    # Schnorr public-key check rejects it (negative synthesis).
    dummy_pub_d = _spf_scalar(attacker.authority_key)
    public_candidates = [_spf_sign(dummy_pub_d, epoch.hash, _c.hash)
                         for _c in cand_closes]
    random_64 = bytes(range(64))                          # arbitrary archive bytes
    # The GENUINE proof for the same close is obtained ONLY via the honest
    # authority's sign-once/recover path (never a public-only formula), proving
    # the attacker's public candidates are all distinct from it byte-wise.
    check("O2/Copilot negative-synthesis (AttackerView): an attacker whose "
          "interface holds ONLY public committed material (authority_key, "
          "roster, membership commitment, candidate closes) and CANNOT touch "
          "signing material (no shares, no _group_secret, no _spf_sign on the "
          "façade) cannot forge an accepted proof: every public-only candidate "
          "differs from the honest recovered proof and is REJECTED by the pure "
          "public-key verifier, and an arbitrary/random byte string is rejected "
          "(fix 3917696336 + line-519: canonical-look is not acceptance)",
          not hasattr(attacker, "_group_secret") and not hasattr(attacker, "_spf_sign")
          and not hasattr(attacker, "GROUP_SK")
          and all(UniqueThresholdProof.verify(epoch, _c.hash,
                                              public_candidates[k]) is None
                  for k, _c in enumerate(cand_closes))
          and UniqueThresholdProof.verify(epoch, cand_closes[0].hash,
                                          random_64) is None)
    check("O2 pre-lock unavailability (brute force, AttackerView surface): an "
          "attacker whose interface holds only public close/epoch fields -- "
          "forged, spoof-secret, crafted, and its best public-only proof "
          "expression for the exact close -- cannot obtain ANY P_s that RESOLVES "
          "to a root: with <t VALID system shares and without the "
          "release-at-externalize boundary the close has no genuine recovered "
          "proof, the pure verifier rejects every forged/random candidate, and "
          "resolve() rejects every crafted candidate (flow + public-key property, "
          "not a source flag)",
          all(attacker_forged[k] is None for k in range(len(cand_closes)))
          and not any(auth.verify_share(
              i, cand_closes[0],
              (sha256(b"forged"), sha256(b"not-a-real-nonce"),
               sha256(b"not-a-real-feldman")))
              for i in range(1, t + 1))
          and all(source.genuine_proof(_c) is None for _c in cand_closes)
          and all(resolve(epoch, _c, source, public_candidates[k])["outcome"]
                  != "ROOT" for k, _c in enumerate(cand_closes))
          and all(not source.has_valid_proof(_c) for _c in cand_closes))
    real = cand_closes[3]
    true_src = RandomnessSource(epoch)
    true_auth = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
    true_src.bind(true_auth)
    boundary_release(true_src, real)
    real_proof = true_src.proof(real, true_auth)
    check("O2 once EXACTLY ONE close is boundary-admitted, only that close "
          "resolves to a root; every other candidate yields none (no post-hoc "
          "selection among previewed candidates)",
          true_src.genuine_proof(real) == real_proof
          and UniqueThresholdProof.verify(epoch, real.hash, real_proof) is not None
          and all(true_src.genuine_proof(c) is None
                  for c in cand_closes if c.hash != real.hash)
          and resolve(epoch, real, true_src, real_proof)["outcome"] == "ROOT"
          and all(resolve(epoch, c, true_src, real_proof)["outcome"] != "ROOT"
                  for c in cand_closes if c.hash != real.hash))

    # ---------- I1-I4: UniqueThresholdProof interface contract ---------------
    I1 = not hasattr(ThresholdAuthority, "emit") \
        and not hasattr(ThresholdAuthority, "sign_public")
    I2 = auth.recover_proof(full_shares[:t - 1], cl_a) is None
    I3 = (len(recovered) > 1
          and all(p == proof_a for p in recovered.values()))
    I4 = (UniqueThresholdProof.verify(epoch, cl_a.hash, proof_a)
          == UniqueThresholdProof.verify(epoch, cl_a.hash, proof_a)
          == root_a)
    check("I1-I4 UniqueThresholdProof interface contract: nothing in the program "
          "emits a proof from public close bytes alone (I1); <t valid shares "
          "produce no proof (I2); every >=t valid subset/permutation recovers "
          "the byte-identical canonical proof (I3); verify(epoch, C_s, P_s) is "
          "PURE and archived-stable -- same triple, same root, every time (I4)",
          I1 and I2 and I3 and I4)

    # Copilot this review #2 (High) + #1 (High): the source root is bound to the
    # UNPREDICTABLE canonical threshold proof `P_s`, so it is not a public
    # function of C_s (no proposer grinding) AND it is byte-unique per close.
    #
    # ONE-FUTURE / ALTERNATE-VALID-PROOF (Copilot this review #2): Schnorr per se
    # permits multiple valid same-message signatures under different nonces, so a
    # model that CONJURED an alternate signature would split the pulse. With the
    # FROST/Feldman message-dependent construction (this review #3) this is
    # structurally impossible for every actor the threshold denies: a second
    # valid proof for (Y, C_s) must be signed under the group secret `d`, but NO
    # actor below t collusion ever holds `d` -- the partials `s_i=n(i)+c*f(i)`
    # combine only into `s=r+c*d` for THIS message, and the fresh per-message
    # nonce `r` (masking every partial) is never revealed. So there is exactly
    # ONE obtainable canonical `P_s` per close, hence one root (one-future), and
    # the honest path itself is deterministic (`_spf_sign`/`recover_proof` emit
    # the byte-identical P_s). An ALTERNATE-VALID-PROOF probe that tries to mint
    # a second signature for the same (Y, C_s) -- whether by a crafted/different
    # nonce, a replayed/cross-close partial, or a public-only guess -- either
    # fails the public-key check (REJECTED) or, being byte-different, can only be
    # produced with `d`, which the attacker surface lacks. We assert:
    #   (a) the canonical proof is deterministic (every >=t subset -> proof_a);
    #   (b) an alternate valid proof does NOT exist below the secret: every
    #       alternate candidate (crafted 64-byte, cross-close partials, and the
    #       attacker's best public-only proof) is REJECTED by verify -> None;
    #   (c) the attacker surface cannot touch signing material / recover `d`, so
    #       no pre-lock root is obtainable.
    c_e = cl_a.hash
    crafted = sha256(b"non-canonical:" + proof_a)[:32] + proof_a[32:]
    check("I4/O2 unique-root & alternate-valid-proof (Copilot #2/#1): the "
          "accepted root is a strict deterministic function of the UNPREDICTABLE "
          "canonical proof -- H(Root || Y || epoch || C_s || P_s), byte-unique "
          "across every >=t reconstruction (I3). One-future is structural: an "
          "ALTERNATE valid proof is impossible below `d` (FROST message-dependent "
          "shares, #3), so a byte-different 'proof' (any crafted 64-byte string), "
          "cross-close partials, and the attacker's public guesses are ALL "
          "REJECTED -- yielding no second root, and no pre-lock root is derivable",
          all(p == proof_a for p in recovered.values())
          and UniqueThresholdProof.verify(epoch, c_e, proof_a) == root_a
          and UniqueThresholdProof.verify(epoch, c_e, crafted) is None
          and all(UniqueThresholdProof.verify(epoch, c_e, alt_src)
                  is None for alt_src in public_candidates)
          and canonical_root(c_e, epoch.authority_key, epoch.hash, proof_a)
          == root_a
          and not hasattr(attacker, "_spf_sign")
          and all(attacker.public_root_guess(_c, public_candidates[k])
                  != root_a
                  for k, _c in enumerate(cand_closes)))

    # ---------- O3: permanent pulse ----------------------------------------------
    pulse_a = consumer_kdf(root_a, LABEL_NOM)
    pulse_a2 = consumer_kdf(UniqueThresholdProof.verify(epoch, cl_a.hash, proof_a),
                            LABEL_NOM)
    check("O3 permanent pulse: the next-ledger nomination draw is fixed by the "
          "canonical root and survives re-derivation (never a second historical "
          "pulse)", pulse_a == pulse_a2)

    # ---------- K: the three kill questions (adversarial) ----------------------
    forged_val = sha256(sha256(b"externalized-value-A") + b"ATTACKER-NONCE")
    payload_v = sha256(b"externalized-value-A")   # a >0 s.sub event payload
    check("K1 kill-Q1: no caller nonce/alias can mint a second equivalent event "
          "for the same protected close (forged value -> distinct close)",
          LockedClose(epoch, slot, prev_hash, forged_val).hash != cl_a.hash)
    check("K2 kill-Q2: pre-lock unavailability -- only the exact boundary-admitted "
          "close has a genuine recovered proof; every other candidate close "
          "resolves to NO root (a bare value never yields a root)",
          true_src.genuine_proof(real) == real_proof
          and all(resolve(epoch, c, true_src, real_proof)["outcome"] != "ROOT"
                  for c in cand_closes if c.hash != real.hash))
    # year-later catchup: fresh node with ONLY canonical history (descriptor +
    # C_s + P_s), no source, no memory, no quorum-path fact -> same R_s.
    archival_epoch = EpochDescriptor(
        format_version=epoch.format_version, authority_key=epoch.authority_key,
        roster=epoch.roster, activation=epoch.activation,
        retirement=epoch.retirement, threshold=epoch.threshold,
        root_rule=epoch.root_rule, event_mapping=epoch.event_mapping,
        scheme=epoch.scheme, verifier_rule=epoch.verifier_rule,
        byzantine_bound=epoch.byzantine_bound,
        confirm_pub=epoch.confirm_pub,
        feldman_pub=epoch.feldman_pub)
    archival_root = UniqueThresholdProof.verify(archival_epoch, cl_a.hash,
                                                proof_a)
    check("K3 kill-Q3: archival replay preserving only the canonical epoch "
          "descriptor + C_s + P_s re-derives the SAME root and pulse through the "
          "PURE verifier -- no old process memory, packet history, quorum-path "
          "fact, or caller flag (Noot's next hard gate)",
          archival_epoch.hash == epoch.hash
          and archival_root == root_a
          and pulse_a == consumer_kdf(archival_root, LABEL_NOM))
    check("K3 kill-Q3 / thread evw-0: PROVENANCE-INDEPENDENT archival resolution "
          "-- a fresh catchup node holding ONLY {epoch, C_s, P_s} (and NO "
          "transient `_admitted` release record, because it never ran the live "
          "boundary) resolves the same close to the same ROOT via "
          "`resolve_archival`, and it is NOT wrongly rejected just because its "
          "process lacks the live admission entry",
          resolve_archival(archival_epoch, cl_a, proof_a)["outcome"] == "ROOT"
          and resolve_archival(archival_epoch, cl_a, proof_a)["source_root"]
          == root_a.hex()
          and resolve_archival(archival_epoch, cl_a, sha256(b"forged-archive"))
          ["outcome"] == "REJECTED")
    rewritten = EpochDescriptor(
        format_version=epoch.format_version,
        authority_key=group_pub_from_seed(sha256(b"rewritten-key-seed-v7"), 5, 8),
        roster=epoch.roster, activation=epoch.activation,
        retirement=epoch.retirement, threshold=epoch.threshold,
        root_rule=epoch.root_rule, event_mapping=epoch.event_mapping)
    check("K3 kill-Q3: a REWRITTEN epoch (new group key) is a different canonical "
          "epoch", rewritten.hash != epoch.hash)

    # ---------- S: three Layer-B source properties -----------------------------
    check("S1 single binding: one protected close -> one root (forged/alias/"
          "retry value differs, so a use cannot bind several roots)",
          LockedClose(epoch, slot, prev_hash, forged_val).hash != cl_a.hash)
    check("S1 / thread evw_K: C_s is a one-use/one-event mapping INDEPENDENT of "
          "the signer provenance. Two serialized values with the SAME payload "
          "but DIFFERENT trailing lcValueSignature NodeIDs hash -- via "
          "`canonical_value_hash`, which strips the signer -- to the SAME "
          "canonical value hash and therefore the SAME C_s, so differently-"
          "SIGNED but semantically-identical closes do NOT diverge, while a "
          "GENUINELY different value payload yields a different C_s",
          canonical_value_hash(payload_v + sha256(b"signer-A")) ==
          canonical_value_hash(payload_v + sha256(b"signer-B"))
          and LockedClose(epoch, slot, prev_hash,
                          payload_v + sha256(b"signer-A")).hash ==
          LockedClose(epoch, slot, prev_hash,
                      payload_v + sha256(b"signer-B")).hash
          and LockedClose(epoch, slot, prev_hash, payload_v).hash !=
          LockedClose(epoch, slot, prev_hash,
                      sha256(b"different-payload")).hash)
    check("S2 pre-lock unavailability: before the CONFIRM/EXTERNALIZE boundary "
          "admits the lock, a proposer holds NO valid proof -- no genuine "
          "recovered proof exists and no candidate resolves to a root (source "
          "fault model, not a caller flag)",
          all(source.genuine_proof(c) is None for c in cand_closes)
          and all(resolve(epoch, c, source, real_proof)["outcome"] != "ROOT"
                  for c in cand_closes if c.hash != real.hash))
    roots_seen = [UniqueThresholdProof.verify(epoch, evs[i].hash, proofs[i])
                  for i in range(n_events)]
    s3_ok = all(r is not None for r in roots_seen) \
        and len(roots_seen) == len(set(roots_seen))
    for i in range(n_events):
        wrong = proofs[(i + 1) % n_events]
        if resolve(epoch, evs[i], source, wrong)["outcome"] != "REJECTED":
            s3_ok = False
    check("S3 unique resolution: every valid boundary-authorized proof path "
          "collapses to exactly one canonical R and an invalid proof is always "
          "REJECTED, never a second root", s3_ok)

    # ---------- P: pinned model vectors (fixed registered literals) -------------
    pinned_b3 = flushed_digest
    comp_seq_digest = sha256(b"".join(canon_roots)).hex()
    EXP_B3 = (
        "21426ca05e8e5d1b3685cbd3555a07d647aaf62b49cddbd4313fa82f83f251b9",
        "96b916781f8444fee60dce11d2efb6032156ed7f6a5ffc66ecd9b752d2e28fb2",
        "13b31a3952926dc3cdb083df8d10992935e076be80c533192d23f0825c4b8987",
        "1a6f142fabd9080f7ab2ea625e12b4c16e9cfac083951301ce35a2facbb6f3cd",
    )
    EXP_COMP = "2c2c1c51668848e6cb025e4c51e5dc0cd067a10a3ee9f556ba06f759f6dcd084"
    check("P pinned B3 authoritative-history digest matches the REGISTERED "
          "conformance literals (one per delivery sequence): %s"
          % (tuple(terminal_digests),),
          tuple(terminal_digests) == EXP_B3)
    check("P compositional root-sequence digest matches the REGISTERED literal: "
          "%s" % comp_seq_digest, comp_seq_digest == EXP_COMP)

    print("\n" + ("ALL PASS" if failed == 0 else "%d FAILURE(S)" % failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())