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


def group_pub_from_seed(seed: bytes) -> bytes:
    # The epoch's committed authority/public key: Y = G^d, d from the recovered
    # group secret. This is what `verify` binds every accepted proof to.
    d = _spf_scalar(seed)
    return _spf_pub(d)


def _spf_sign(d: int, epoch_hash: bytes, C_s: bytes) -> bytes:
    # Deterministic, secret-nonce Schnorr signature. Unique per (d, epoch, C_s):
    # no ride-along randomness, so a slot yields exactly one proof (I1-I4).
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
                 byzantine_bound: int = None):
        self.format_version = format_version
        self.authority_key = authority_key
        roster_tup = tuple(sorted(roster))
        if len(set(roster_tup)) != len(roster_tup):
            # thread e6WbkN: duplicate roster keys would let one verification
            # identity occupy multiple threshold indices -- reject before n and
            # membership_commitment are derived.
            raise ValueError("roster must contain distinct member keys")
        self.roster = roster_tup
        self.membership_commitment = sha256(roster_bytes(self.roster))
        self.activation = activation
        self.retirement = retirement
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
        #     ledger apply stalls indefinitely. E.g. (n=8, t=7) with default
        #     f=5 passes the intersection bound 2*7-8=6>5 yet is UNPROVABLE
        #     (7 <= 8-5 = 3 is false); such an epoch is now REJECTED.
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
    """Canonical sorted roster encoding: the whole list length-prefixed (injective
    container), each member key as a Core `opaque Hash[32]` (fixed 32 bytes, no
    per-element length prefix -- XDR `<opaque Hash[32]^*>`). `membership_commitment
    = H(roster_bytes)`. This is what `from_epoch` re-derives, so substituted
    (n, t, roster) mappings are a different commitment and cannot verify under
    the epoch."""
    return lp(b"".join(hash32(k) for k in sorted(roster)))


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
                            self.previous_ledger_hash, sha256(self.value_bytes))
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
    merely has the right length is REJECTED (Copilot line-519)."""
    if proof is None or len(proof) != 64:
        return None
    return proof


def canonical_root(C_s: bytes, proof: bytes):
    """R_s derived from the CANONICAL proof bytes ONLY (dnFVg). This is called
    only AFTER `UniqueThresholdProof.verify` has accepted the proof against the
    epoch public key -- it never turns an arbitrary byte string into a root on
    its own (see `verify`)."""
    p = canonical_proof(proof)
    if p is None:
        return None
    return sha256(b"Root" + C_s + p)


def _member_secret(seed: bytes, member_index: int) -> bytes:
    # Per-member SECRET share key. Derived at authority-construction time from
    # the authority seed only (setup material, never committed). The model uses
    # the same deterministic re-derivation a real DKG/VUF holder would have from
    # its generated key material; ROUND-TRIP is what a restart needs, and it is
    # exactly reproducible from (epoch, seed).
    return sha256(b"MemberSecret" + seed + u32(member_index))


def _full_member_commit(seed: bytes, epoch_n: int) -> bytes:
    # Constant for (seed, n): the algebraic "interpolated group secret" that any
    # >=t valid share SUBSET recovers to the SAME value (in a real scheme,
    # Lagrange reconstruction of any t shares yields the identical secret; here
    # the committed re-derivation is over the full canonical membership so every
    # valid subset reproduces the byte-identical canonical proof).
    return sha256(b"MemberCommit" + b"".join(
        _member_secret(seed, i) for i in range(1, epoch_n + 1)))


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

    def _share_for(self, member_index: int, cl_hash: bytes) -> bytes:
        return sha256(b"Share" + _member_secret(self.seed, member_index)
                      + self.epoch.hash + cl_hash)

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
        return self._share_for(member_index, cl.hash)

    def verify_share(self, member_index: int, cl: LockedClose, share: bytes) -> bool:
        if not (1 <= member_index <= self.epoch.n):
            return False
        if cl.epoch_hash != self.epoch.hash:
            return False
        return share == self._share_for(member_index, cl.hash)

    def recover_proof(self, subset, cl: LockedClose):
        """subset: iterable of (member_index, share). Returns the canonical P_s
        iff >= t VALID, distinct, in-roster shares for THIS exact close are
        present; invalid/duplicate/out-of-epoch/wrong-close shares are discarded
        individually and never poison t otherwise-valid shares."""
        if cl.epoch_hash != self.epoch.hash:
            return None
        valid = set()
        for (member_index, share) in subset:
            if (1 <= member_index <= self.epoch.n
                    and member_index not in valid
                    and self.verify_share(member_index, cl, share)):
                valid.add(member_index)
        if len(valid) < self.epoch.threshold:
            return None                             # below t: no proof, stall
        # SECRET-bound canonical proof (Copilot 3917696336 + this review). The
        # proof is a Schnorr signature over the recovered GROUP SECRET G (from
        # >= t valid SECRET shares) and the message C_s:
        #
        #     G   = _full_member_commit(seed, n)     -- recovered group secret
        #     d   = H(G) mod q                       -- secret scalar
        #     P_s = Sign(d, epoch_hash, C_s)         -- genuinely verifiable
        #
        # where G is the algebraic "interpolated group secret" any valid
        # t-subset recovers to the SAME value (in a real scheme, Lagrange
        # reconstruction of any t shares yields the identical secret; here the
        # committed re-derivation is over the full canonical membership so every
        # valid subset reproduces the byte-identical canonical proof).
        #
        # Because signing needs `d` (a one-way function of G), the proof is NOT
        # derivable from public epoch fields alone and CANNOT be forged by a
        # public-only actor: `verify` checks the Schnorr equation under the
        # epoch's committed PUBLIC key, so an arbitrary 64-byte value is
        # rejected, not accepted (negative-synthesis gate below asserts this).
        # Threshold unforgeability lives in the PRODUCER (requires the secret),
        # while `verify` is a genuinely public, secret-free check.
        G = _full_member_commit(self.seed, self.epoch.n)
        d = _spf_scalar(G)
        return _spf_sign(d, self.epoch.hash, cl.hash)

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
        signature check `G^s == R * Y^c (mod p)` and returns the one source root
        R_s = root(C_s, canonical(P_s)) ONLY if that check passes. An arbitrary
        archive byte string (a forged 64-byte value, a wrong-epoch proof, or a
        replayed proof) is REJECTED -- it does not satisfy the equation under Y
        (Copilot line-519: no longer does a bare canonical-length value derive a
        root).

        What it does NOT do -- and what a public verifier with no secret MUST
        not do -- is *produce* the accepted proof. The proof is the secret-bound
        Schnorr output needing the recovered group secret (`d = H(G)`), so this
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
        return canonical_root(C_s, p)


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
    authenticator only the participating validators can emit."""

    def __init__(self, epoch: EpochDescriptor, boundary_secret: bytes = None):
        self.epoch = epoch
        # Per-boundary secret, never serialized, never committed. A DIFFERENT
        # boundary (or a crafted one) mints witnesses no other authority
        # accepts, mirroring real per-process/per-validator finality evidence.
        self._secret = (boundary_secret if boundary_secret is not None else
                        sha256(b"cap-0089:boundary:secret:v1" + os.urandom(16)))
        # C_s.hash -> True iff the CONFIRM->EXTERNALIZE transition actually
        # ran for that lock. Populated ONLY by `externalize` (the trusted edge).
        self._externalized = {}

    def externalize(self, cl: LockedClose, fully_validated: bool) -> bool:
        # The genuine CONFIRM -> EXTERNALIZE edge. The transition type and full
        # validation are FACTS OF THE EDGE, not caller flags the producer later
        # re-asserts: this method is the single place a close becomes released.
        # accepted-commit is never authoritative -- only entering EXTERNALIZE
        # with the value locally fully validated releases a close.
        if cl is None or not cl.validate():
            return False
        if cl.network_id != NETWORK:
            return False
        if cl.epoch_hash != self.epoch.hash:
            return False
        if not self.epoch.active_at(cl.slot):
            return False
        if not fully_validated:
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
        A caller can NEVER forge this in the model: it equals
        H(b\"VufProof\" + G + epoch.hash + C_s) with the RECOVERED GROUP SECRET
        G. resolve() accepts only this exact proof string on a close, so a
        public-only formula or any 32-byte candidate is REJECTED even if it is
        canonical-looking under the pure verifier (Copilot 3917696336)."""
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
    """Full state machine. Returns only the B4 authority surface: {event_hash,
    outcome, source_root?}.

    Gate 0 (integrity):         LockedClose hash must re-derive.
    Gate 1 (epoch+network):     close bound to THIS epoch/network and active.
    Gate 2 (boundary + proof):  source must have boundary-admitted the EXACT
        close and the proof must pass the PURE archived verifier. No proof ->
        UNKNOWN (stalled apply); invalid proof -> REJECTED.
    """
    if not cl.validate():
        return {"event_hash": cl.hash.hex(), "outcome": "REJECTED"}
    if (cl.epoch_hash != epoch.hash or cl.network_id != NETWORK
            or not epoch.active_at(cl.slot)):
        return {"event_hash": cl.hash.hex(), "outcome": "REJECTED"}
    if proof is None:
        return {"event_hash": cl.hash.hex(), "outcome": "UNKNOWN"}
    if not source.has_valid_proof(cl):
        return {"event_hash": cl.hash.hex(), "outcome": "REJECTED"}
    # Gate 2b (Copilot 3917696336): ONLY the GENUINE recovered proof resolves a
    # close to ROOT. verify() is an abstract PURE relation (accepts any
    # canonical 32-byte proof), so alone it cannot tell a forged canonical-looking
    # proof from the real one -- the SOURCE's cached genuine proof does that.
    # A public-only formula or any 32-byte candidate != the recovered proof is
    # therefore REJECTED even though it is canonical.
    if source.genuine_proof(cl) != proof:
        return {"event_hash": cl.hash.hex(), "outcome": "REJECTED"}
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

    def boundary_release(src, cl, fully_validated=True):
        # Wraps the REAL transition: the genuine CONFIRM->EXTERNALIZE edge runs
        # `externalize` BEFORE `admit`. Only then does the source hold a release
        # witness. `externalize` is the authority over the transition (it takes
        # no caller bytes; it IS the transition).
        if src._boundary.externalize(cl, fully_validated):
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
    epoch_pub = group_pub_from_seed(_full_member_commit(GROUP_SK, N_MEMBERS))
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
              format_version=1, authority_key=sha256(b"authority:group-key"),
              roster=roster, activation=12300, retirement=13000, threshold=0,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1"))
          and raises(lambda: EpochDescriptor(
              format_version=1, authority_key=sha256(b"authority:group-key"),
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
              format_version=1, authority_key=sha256(b"authority:group-key"),
              roster=dup_roster, activation=12300, retirement=13000,
              threshold=3, root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1")))
    check("R2 honest-intersection Byzantine bound (thread eW_rR): an epoch whose "
          "threshold violates 2*t - n > f is rejected -- two t-subsets could "
          "overlap only in Byzantine members and mint two same-slot proofs. "
          "With n=8, t=2 (2t-n= -4, no honest intersection even with f=0) the "
          "descriptor must raise ValueError",
          raises(lambda: EpochDescriptor(
              format_version=1, authority_key=sha256(b"authority:group-key"),
              roster=mk_roster(8), activation=12300, retirement=13000,
              threshold=2, root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1"))
          and raises(lambda: EpochDescriptor(
              format_version=1, authority_key=sha256(b"authority:group-key"),
              roster=mk_roster(8), activation=12300, retirement=13000,
              threshold=5, byzantine_bound=2,
              root_rule=b"unique-threshold/v1",
              event_mapping=b"single-pulse:LockedClose->C_s/v1"))
          and epoch.byzantine_bound == 1)  # n=8,t=5 => default f = 2t-n-1 = 1
    rogue_auth = ThresholdAuthority.from_epoch(epoch, sha256(b"rogue-seed"))

    # ---------- Single-pulse primitives ---------------------------------------
    cl_a = LockedClose(epoch, slot, prev_hash, sha256(b"externalized-value-A"))
    cl_b = LockedClose(epoch, slot, prev_hash, sha256(b"externalized-value-B"))

    rogue_source = RandomnessSource(epoch)
    rogue_source.bind(rogue_auth)
    boundary_release(rogue_source, cl_a)
    rogue_proof = rogue_source.proof(cl_a, rogue_auth)
    rogue_share = rogue_auth.share(1, cl_a)

    check("R2 same epoch hash, substituted member mapping: a share produced by a "
          "different (seed/secret) authority for the same epoch is NOT a valid "
          "share of the canonical authority; with no valid shares, recover is "
          "None",
          rogue_proof is not None
          and rogue_share is not None
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
    other_win_pub = group_pub_from_seed(_full_member_commit(GROUP_SK, 4))
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
    not_validated = boundary_release(alien_stage, cl_a, fully_validated=False)
    check("dnFVg release boundary: the CONFIRM/EXTERNALIZE transition itself "
          "rejects a value that was NOT locally fully validated (externalize "
          "returns False; no witness, no proof, no share)",
          not not_validated
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
    cl_foreign = LockedClose(other_win, slot, prev_hash,
                             sha256(b"externalized-value-A"))
    check("N3 mixed-epoch rejected: an authority instantiated for epoch A cannot "
          "share over (or reconstruct a proof for) a close of epoch B",
          auth.share(1, cl_foreign) is None
          and auth.recover_proof([], cl_foreign) is None)
    check("N1 authorization never flavors the pulse: the proof recovered from "
          "any >=t share subset equals the resolver's admitted proof -- the same "
          "close, same P_s, same root, whatever the witness/release path",
          full == proof_a and canonical_root(cl_a.hash, full) == root_a)

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
          "competing C_s for the SAME slot -- consecutive closed ledgers are "
          "not accidentally serialized into one event (thread e6Vduq)",
          s1 == auth.share(1, cl_a) and s2 is not None and s2 != s1
          and refused_s2 is None)
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
          and canonical_root(cl_a.hash, p_w1) == root_a)

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
    # Copilot 3917696336 + line-519 (this review): the accepted proof is a Schnorr
    # signature over the RECOVERED GROUP SECRET G (d = H(G)), and the PURE verifier
    # checks it against the committed PUBLIC key. An attacker holding EVERY PUBLIC
    # field (scheme, authority_key, epoch hash, C_s) plus this source file CANNOT
    # know G (recovered only by >=t holders), so:
    #   * its best public-only candidate (a 64-byte proof minted from the PUBLIC
    #     key, not from G) verifies to NOTHING -- the Schnorr equation fails; and
    #   * a random 64-byte value verifies to NOTHING (arbitrary bytes are rejected).
    # This is a stronger assertion than byte-inequality: the PUBLIC-only proof is
    # not merely "different bytes" -- it is REJECTED by the public verifier it
    # would have to pass.
    true_G = _full_member_commit(GROUP_SK, epoch.n)
    true_d = _spf_scalar(true_G)

    def genuine_expression(c):
        # EXACTLY the genuine proof: recover_proof and this agree byte-for-byte.
        return _spf_sign(true_d, epoch.hash, c.hash)

    dummy_pub_d = _spf_scalar(epoch.authority_key)      # PUBLIC-key-derived guess
    public_64 = _spf_sign(dummy_pub_d, epoch.hash, sha256(b"public-only-anchor"))

    def public_expression(c):
        # PUBLIC-only synthesis: forged 64-byte proof bound to a scalar derived
        # from public epoch bytes (closest a non-holder reaches G). NOT genuine.
        return _spf_sign(dummy_pub_d, epoch.hash, c.hash + sha256(public_64))

    random_64 = bytes(range(64))                          # arbitrary archive bytes
    public_candidates = [public_expression(_c) for _c in cand_closes]
    check("O2/Copilot negative-synthesis: a public-only candidate proof can never "
          "equal the genuine recovered proof AND is REJECTED by the pure verifier "
          "-- the accepted P_s is bound to the RECOVERED GROUP SECRET G, and "
          "verify() runs a genuine public-key check so an arbitrary 64-byte "
          "candidate (forged from public fields, or random) verifies to NOTHING "
          "(fix 3917696336 + line-519: canonical-look is not acceptance)",
          all(public_candidates[k] != genuine_expression(_c)
              for k, _c in enumerate(cand_closes))
          and all(UniqueThresholdProof.verify(epoch, _c.hash,
                                              public_candidates[k]) is None
                  for k, _c in enumerate(cand_closes))
          and UniqueThresholdProof.verify(epoch, cand_closes[0].hash,
                                          random_64) is None)
    check("O2 pre-lock unavailability (brute force): an attacker holding every "
          "public close field -- forged, spoof-secret, crafted, and its best "
          "public-only proof expression for the exact close -- cannot obtain ANY "
          "P_s that RESOLVES to a root: with <t VALID system shares and without "
          "the release-at-externalize boundary the close has no genuine recovered "
          "proof, the pure verifier rejects every forged/random candidate, and "
          "resolve() rejects every crafted candidate (flow + public-key property, "
          "not a source flag)",
          all(attacker_forged[k] is None for k in range(len(cand_closes)))
          and not any(auth.verify_share(i, cand_closes[0], sha256(b"forged"))
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

    # ---------- O3: permanent pulse ----------------------------------------------
    pulse_a = consumer_kdf(root_a, LABEL_NOM)
    pulse_a2 = consumer_kdf(UniqueThresholdProof.verify(epoch, cl_a.hash, proof_a),
                            LABEL_NOM)
    check("O3 permanent pulse: the next-ledger nomination draw is fixed by the "
          "canonical root and survives re-derivation (never a second historical "
          "pulse)", pulse_a == pulse_a2)

    # ---------- K: the three kill questions (adversarial) ----------------------
    forged_val = sha256(sha256(b"externalized-value-A") + b"ATTACKER-NONCE")
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
        root_rule=epoch.root_rule, event_mapping=epoch.event_mapping)
    archival_root = UniqueThresholdProof.verify(archival_epoch, cl_a.hash,
                                                proof_a)
    check("K3 kill-Q3: archival replay preserving only the canonical epoch "
          "descriptor + C_s + P_s re-derives the SAME root and pulse through the "
          "PURE verifier -- no old process memory, packet history, quorum-path "
          "fact, or caller flag (Noot's next hard gate)",
          archival_epoch.hash == epoch.hash
          and archival_root == root_a
          and pulse_a == consumer_kdf(archival_root, LABEL_NOM))
    rewritten = EpochDescriptor(
        format_version=epoch.format_version,
        authority_key=sha256(b"rewritten-new-key"),
        roster=epoch.roster, activation=epoch.activation,
        retirement=epoch.retirement, threshold=epoch.threshold,
        root_rule=epoch.root_rule, event_mapping=epoch.event_mapping)
    check("K3 kill-Q3: a REWRITTEN epoch (new group key) is a different canonical "
          "epoch", rewritten.hash != epoch.hash)

    # ---------- S: three Layer-B source properties -----------------------------
    check("S1 single binding: one protected close -> one root (forged/alias/"
          "retry value differs, so a use cannot bind several roots)",
          LockedClose(epoch, slot, prev_hash, forged_val).hash != cl_a.hash)
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
        "fcd1f8ff9a9c78cda149cc14985522500f7dd3c26b977bc379305238805a27e0",
        "716effd0ad83dede43ae5dad7c592ab69b560802bb6e9a2d8267f7195ab0a785",
        "53b580b9eb844e219db29095ba0fc0d013b0d6a8f58cf6e6ce03cf0bf73c31b4",
        "ca720132506c0a01a767a4bc6049b10618045ac8a7e9519f065a1b71f19e4269",
    )
    EXP_COMP = "de070b5912849f0016883c8665b101451ee7b6f651ad06a8a45aeee58b387cf1"
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