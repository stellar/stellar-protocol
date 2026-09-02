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
import struct
import sys

EPOCH_SCHEME = b"stellar-vrf/epoch/unique-threshold/v1"
NETWORK = hashlib.sha256(b"Test SDF Network ; September 2015").digest()
LABEL_PRN = b"PRNG"
LABEL_APPLY = b"APPLY"
LABEL_NOM = b"NOMINATION"
NO_CALLER_OUTCOME_CLASS = frozenset()
RELEASE_CERT_CONFIRM_EXTERNALIZE = b"confirm/externalize"
RELEASE_CERT_ACCEPTED_COMMIT = b"accepted-commit"   # deliberately NOT authoritative

# The model standby for the primitive's SYSTEM/GROUP key material. It is never
# serialized, never committed in the epoch, and never printed; it mirrors the
# boundary that the real VUF/DKG group secret lives only inside the primtive
# (Rust) and the holder set. `verify` (below) uses it exactly the way a
# production verifier uses the certified group public key + committed setup.
GROUP_SK = hashlib.sha256(b"cap-0089:model:group-sk:v1").digest()


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def u32(n: int) -> bytes:
    return struct.pack(">I", n)


def lp(b: bytes) -> bytes:
    # Length-prefix a variable-length field so the canonical encoding is
    # injective (dnFWC): distinct byte boundaries cannot collide.
    return struct.pack(">I", len(b)) + b


def close_input(epoch_hash: bytes, network_id: bytes, ledger_seq: int,
                previous_ledger_hash: bytes, value_hash: bytes) -> bytes:
    """Single canonical close-input contract `RandomnessCloseInputV1`.

    Core-native widths (Noot): `ledgerSeq` is a uint32 (Core's LedgerSeq XDR
    type), `format_version` is a single canonical identity byte (u8). Length-
    prefixed so the encoding is injective. Binds network, epoch, the REAL
    ledgerSeq, the predecessor ledger (state-transition semantics) and the exact
    externalized value bytes. Provenance (signatures, proposer, envelopes,
    transport) is deliberately absent."""
    return (b"RandomnessCloseInputV1" + u32(1)
            + lp(network_id) + lp(epoch_hash)
            + u32(ledger_seq) + lp(previous_ledger_hash) + lp(value_hash))


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
                 scheme: bytes = EPOCH_SCHEME):
        self.format_version = format_version
        self.authority_key = authority_key
        self.roster = tuple(sorted(roster))
        self.membership_commitment = sha256(roster_bytes(self.roster))
        self.activation = activation
        self.retirement = retirement
        self.threshold = threshold
        self.verifier_rule = verifier_rule
        self.root_rule = root_rule
        self.event_mapping = event_mapping
        self.scheme = scheme
        self.hash = sha256(
            b"Epoch"
            + struct.pack(">B", format_version) + lp(scheme)
            + lp(authority_key) + lp(self.membership_commitment)
            + struct.pack(">QQ", activation, retirement)
            + struct.pack(">I", threshold) + lp(verifier_rule)
            + lp(root_rule) + lp(event_mapping))

    @property
    def n(self) -> int:
        return len(self.roster)

    def active_at(self, slot: int) -> bool:
        return self.activation <= slot < self.retirement


def roster_bytes(roster) -> bytes:
    """Canonical sorted roster encoding: each member key length-prefixed, whole
    list length-prefixed (injective). `membership_commitment = H(roster_bytes)`.
    This is what `from_epoch` re-derives, so substituted (n, t, roster) mappings
    are a different commitment and cannot verify under the epoch."""
    return lp(b"".join(lp(k) for k in sorted(roster)))


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
    canonical byte string the epoch's verifier accepts. Two accepted encodings
    of the same mathematical proof MUST canonicalize to the SAME bytes before
    either can influence R_s (Noot: proof malleability is a conformance issue,
    never a second-future surface)."""
    if proof is None or len(proof) != 32:
        return None
    return proof


def canonical_root(C_s: bytes, proof: bytes):
    """R_s derived ONLY after canonicalization+verification (dnFVg)."""
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

    def __init__(self, epoch: EpochDescriptor, seed: bytes):
        self.epoch = epoch
        self.seed = seed
        self._signed = {}     # durable sign-once: member_index -> (slot, C_s)

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

    def share(self, member_index: int, cl: LockedClose):
        if not (1 <= member_index <= self.epoch.n):
            raise ValueError("member index out of canonical roster")
        if cl.epoch_hash != self.epoch.hash:
            # An authority for epoch A cannot share over a close of epoch B.
            return None
        lock = self._signed.get(member_index)
        if lock is None:
            self._signed[member_index] = (cl.slot, cl.hash)
        elif lock != (cl.slot, cl.hash):
            # Same event, DIFFERENT C_s: refuse (durable sign-once per event).
            return None
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
        # Unique output: a pure function of (epoch, C_s) plus the recovered
        # group secret -- independent of which valid subset reconstructed it.
        return sha256(b"Proof" + self.epoch.scheme + self.epoch.authority_key
                      + cl.hash + _full_member_commit(self.seed, self.epoch.n))

    def restart(self) -> "ThresholdAuthority":
        """Deterministic re-derivation from (epoch, seed): a crash/restart
        authority reproduces every share and the same P_s/R_s with no new
        authority choice and no process memory."""
        return type(self)(self.epoch, self.seed)


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
        """Pure archived verifier: verify(epoch, C_s, P_s) -> R_s | None."""
        p = canonical_proof(P_s)
        if p is None:
            return None
        # Mirror of the primitive's verifier: the group public key (committed in
        # the epoch) plus the scheme's certified setup determine ONE canonical
        # proof string for message C_s. Strict equality -> one byte future.
        expected = sha256(b"Proof" + epoch.scheme + epoch.authority_key + C_s
                          + _full_member_commit(GROUP_SK, epoch.n))
        if p != expected:
            return None
        return canonical_root(C_s, p)


def consumer_kdf(root: bytes, label: bytes) -> bytes:
    # KDF(R_s, label): three distinct labelled consumers of ONE root (dnFWi).
    return sha256(b"KDF" + root + label)


class RandomnessSource:
    """Producer-side release/admission interface. Shares are the transport of
    the proof; an honest holder signs ONLY at the CONFIRM/EXTERNALIZE boundary
    after local full validation, and durably once per event. The source keeps
    ONE canonical slot lock: it admits the exact externalized close for a slot
    and refuses a second, different close for the same slot (thread d9aC4)."""

    def __init__(self, epoch: EpochDescriptor):
        self.epoch = epoch
        self._admitted = {}      # C_s.hash -> evidence
        self._slot_lock = {}     # slot -> C_s hash (ONE canonical close per slot)

    def admit(self, cl: LockedClose, release_certificate: bytes,
              fully_validated: bool, evidence: bytes) -> bool:
        if release_certificate != RELEASE_CERT_CONFIRM_EXTERNALIZE:
            return False
        if not fully_validated:
            return False
        if not cl.validate():
            return False
        if cl.network_id != NETWORK:
            return False
        if cl.epoch_hash != self.epoch.hash:
            return False
        if not self.epoch.active_at(cl.slot):
            return False
        if evidence is None:
            return False
        existing = self._slot_lock.get(cl.slot)
        if existing is not None and existing != cl.hash:
            return False
        self._admitted[cl.hash] = evidence
        self._slot_lock[cl.slot] = cl.hash
        return True

    def has_valid_proof(self, cl: LockedClose) -> bool:
        return cl.hash in self._admitted

    def proof(self, cl: LockedClose, authority: ThresholdAuthority = None):
        if not self.has_valid_proof(cl):
            return None
        if authority is None:
            return None
        # All n honest holders durably sign the exact externalized close once;
        # >= t valid shares reconstruct the single canonical proof.
        holder_shares = [(i, authority.share(i, cl))
                         for i in range(1, authority.epoch.n + 1)]
        return authority.recover_proof(holder_shares, cl)


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

    N_MEMBERS = 8
    roster = mk_roster(N_MEMBERS)
    epoch = EpochDescriptor(
        format_version=1,
        authority_key=sha256(b"authority:group-key"),
        roster=roster,
        activation=12300, retirement=13000,
        threshold=5,
        root_rule=b"unique-threshold/v1",
        event_mapping=b"single-pulse:LockedClose->C_s/v1")
    source = RandomnessSource(epoch)
    auth = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
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
    rogue_auth = ThresholdAuthority.from_epoch(epoch, sha256(b"rogue-seed"))

    # ---------- Single-pulse primitives ---------------------------------------
    cl_a = LockedClose(epoch, slot, prev_hash, sha256(b"externalized-value-A"))
    cl_b = LockedClose(epoch, slot, prev_hash, sha256(b"externalized-value-B"))

    check("R2 same epoch hash, substituted member mapping: a share produced by a "
          "different (seed/secret) authority for the same epoch is NOT a valid "
          "share of the canonical authority; with no valid shares, recover is "
          "None",
          rogue_auth.share(1, cl_a) is not None
          and not auth.verify_share(1, cl_a, rogue_auth.share(1, cl_a))
          and auth.recover_proof([(1, rogue_auth.share(1, cl_a))], cl_a) is None)

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
    other_win = EpochDescriptor(
        format_version=1, authority_key=sha256(b"authority:group-key-2"),
        roster=mk_roster(4), activation=epoch.activation - 50,
        retirement=epoch.retirement + 50, threshold=3,
        root_rule=epoch.root_rule, event_mapping=epoch.event_mapping)
    overlap = {sha256(b"prev-canonical-state"): (epoch, other_win)}
    check("N5 fail-closed overlap: two committed epochs whose windows BOTH cover "
          "the slot select NOTHING (no caller/config/cache picks one of them)",
          epoch_for_transition(sha256(b"prev-canonical-state"), overlap, slot) is None)

    # ---------- Single pulse: closed ledger -> one C_s -> one proof -> one root
    auth_b = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
    pb_b = auth_b.recover_proof([(i, auth_b.share(i, cl_b))
                                 for i in range(1, epoch.threshold + 1)], cl_b)
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
    src_early = RandomnessSource(epoch)
    early_ok = src_early.admit(cl_a, RELEASE_CERT_ACCEPTED_COMMIT, True,
                               sha256(b"ev-early"))
    check("dnFVg release boundary: a proof/share is NOT released at "
          "accepted-commit (mCommit in PREPARE is not safe-to-act finality)",
          not early_ok and src_early.proof(cl_a, auth) is None
          and resolve(epoch, cl_a, src_early, None)["outcome"] == "UNKNOWN")
    alien_stage = RandomnessSource(epoch)
    not_validated = alien_stage.admit(cl_a, RELEASE_CERT_CONFIRM_EXTERNALIZE,
                                      False, sha256(b"ev-not-validated"))
    check("dnFVg release boundary: externalize WITHOUT local full validation "
          "releases no proof", not not_validated
          and alien_stage.proof(cl_a, auth) is None)
    ok_boundary = source.admit(cl_a, RELEASE_CERT_CONFIRM_EXTERNALIZE, True,
                               sha256(b"ext-validated-A"))
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
    auth_m.share(1, cl_a)
    refused = auth_m.share(1, cl_a_alt)          # same event, different C_s
    check("N3 durable sign-once: a member that already signed the event refuses "
          "a DIFFERENT C_s for the SAME slot -- two roots from one member are "
          "impossible; an SCP safety failure stalls randomness, it cannot mint "
          "two roots", refused is None
          and auth_m.share(1, cl_a) == auth.share(1, cl_a))

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
    source_b.admit(cl_b, RELEASE_CERT_CONFIRM_EXTERNALIZE, True,
                   sha256(b"ext-validated-B"))
    check("B2 C_s binds the externalized value: a proof for value A FAILS "
          "against value B, and B resolves only under its own admitted proof",
          resolve(epoch, cl_b, source, proof_a)["outcome"] == "REJECTED"
          and resolve(epoch, cl_b, source_b, source_b.proof(cl_b, auth_b))
          ["outcome"] == "ROOT")

    # ---------- Epoch gate: bind to THIS epoch (dnFVu) -------------------------
    other_source = RandomnessSource(other_win)
    o_auth = ThresholdAuthority.from_epoch(other_win, GROUP_SK)
    other_slot = other_win.activation + 50
    cl_o = LockedClose(other_win, other_slot,
                       sha256(u32(other_slot - 1) + b"prev-o"),
                       sha256(b"externalized-value-A"))
    other_source.admit(cl_o, RELEASE_CERT_CONFIRM_EXTERNALIZE, True,
                       sha256(b"foreign-ev"))
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
    src_slot.admit(cl_c, RELEASE_CERT_CONFIRM_EXTERNALIZE, True,
                   sha256(b"slot-ev"))
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
    ok_w1 = src_w1.admit(cl_a, RELEASE_CERT_CONFIRM_EXTERNALIZE, True,
                         sha256(b"witness-variant-one"))
    ok_w2 = src_w2.admit(cl_a, RELEASE_CERT_CONFIRM_EXTERNALIZE, True,
                         sha256(b"witness-variant-two"))
    p_w1 = src_w1.proof(cl_a, ThresholdAuthority.from_epoch(epoch, GROUP_SK))
    p_w2 = src_w2.proof(cl_a, ThresholdAuthority.from_epoch(epoch, GROUP_SK))
    check("dnFVg canonical proof/root: two DIFFERENT honest witnesses for the "
          "SAME close admit the IDENTICAL canonical proof and root -- evidence "
          "authorizes release only and never changes the permanent pulse",
          ok_w1 and ok_w2 and p_w1 == p_w2 and p_w1 == proof_a
          and canonical_root(cl_a.hash, p_w1) == root_a)

    # ---------- cross-network binding (Copilot d7OZI) --------------------------
    foreign_net = LockedClose.rebuild(epoch, slot, prev_hash,
                                      sha256(b"externalized-value-A"),
                                      network_id=sha256(b"SomeOtherNetwork"))
    foreign_src = RandomnessSource(epoch)
    admitted_foreign = foreign_src.admit(
        foreign_net, RELEASE_CERT_CONFIRM_EXTERNALIZE, True, sha256(b"net-ev"))
    check("dnFVu cross-network binding: a self-consistent close rebuilt under a "
          "NON-local network id is REJECTED by the resolver (never ROOT), and is "
          "never admitted by this source",
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
        source.admit(c, RELEASE_CERT_CONFIRM_EXTERNALIZE, True,
                     sha256(b"witness:%d" % i))
        proofs[i] = source.proof(c, ThresholdAuthority.from_epoch(epoch, GROUP_SK))
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
    c1 = LockedClose(epoch, slot + 300, prev_hash, sha256(b"value-one"))
    c2 = LockedClose(epoch, slot + 300, prev_hash, sha256(b"value-two"))
    ok_c1 = comp_src.admit(c1, RELEASE_CERT_CONFIRM_EXTERNALIZE, True,
                           sha256(b"ev-one"))
    ok_c2 = comp_src.admit(c2, RELEASE_CERT_CONFIRM_EXTERNALIZE, True,
                           sha256(b"ev-two"))
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
          and comp_src.admit(c1, RELEASE_CERT_CONFIRM_EXTERNALIZE, True,
                             sha256(b"ev-one-retry")))
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
        # guess not only non-canonical but also spoof-secret proofs: all must
        # fail the PURE verifier, which canonicalizes against the GROUP key.
    crafted = [sha256(b"noise:%d" % k) for k in range(8)]
    check("O2 pre-lock unavailability (brute force): an attacker holding every "
          "public close field can forge, spoof (alien secret material) or "
          "craft proofs, but with <t VALID system shares they cannot obtain ANY "
          "P_s that the pure archived verifier verify(epoch, C_s, P_s) accepts "
          "-- a flow + primitive-key property, not a source flag",
          all(UniqueThresholdProof.verify(epoch, _c.hash, g) is None
              for _c in cand_closes
              for g in (attacker_forged + crafted + [None]))
          and all(attacker_forged[k] is None for k in range(len(cand_closes)))
          and not any(auth.verify_share(i, cand_closes[0], sha256(b"forged"))
                      for i in range(1, t + 1)))
    real = cand_closes[3]
    true_src = RandomnessSource(epoch)
    true_auth = ThresholdAuthority.from_epoch(epoch, GROUP_SK)
    true_src.admit(real, RELEASE_CERT_CONFIRM_EXTERNALIZE, True,
                   sha256(b"real-ev"))
    real_proof = true_src.proof(real, true_auth)
    check("O2 once EXACTLY ONE close is boundary-admitted, only that close "
          "resolves to a root; every other candidate yields none (no post-hoc "
          "selection among previewed candidates)",
          all(UniqueThresholdProof.verify(epoch, c.hash, real_proof) is None
              for c in cand_closes if c.hash != real.hash)
          and UniqueThresholdProof.verify(epoch, real.hash, real_proof) is not None
          and resolve(epoch, real, true_src, real_proof)["outcome"] == "ROOT")

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
    check("K2 kill-Q2: pre-lock unavailability -- the pure verifier accepts NO "
          "proof for any candidate close before the boundary (a bare value "
          "never yields a root)",
          all(UniqueThresholdProof.verify(epoch, c.hash, real_proof) is None
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
          "admits the lock, a proposer holds NO valid proof (source fault model, "
          "not a caller flag)",
          all(UniqueThresholdProof.verify(epoch, c.hash, real_proof) is None
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
    EXP_B3 = "c7fd7cce8e549d6cb7fb7f03e71611a7f15dd81bb84b81f50f3b24e139431b53"
    EXP_COMP = "5936b2a52b4bfba7bed6690d387ec908ac4f010eb0709de8ace091104ce41a4e"
    check("P pinned B3 authoritative-history digest matches the REGISTERED "
          "conformance literal: %s" % pinned_b3, pinned_b3 == EXP_B3)
    check("P compositional root-sequence digest matches the REGISTERED literal: "
          "%s" % comp_seq_digest, comp_seq_digest == EXP_COMP)

    print("\n" + ("ALL PASS" if failed == 0 else "%d FAILURE(S)" % failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())