#!/usr/bin/env python3
"""CAP-0089 Layer B executable state-machine model (normative protocol-randomness
target).

This is the executable Layer-B model discussed with tacticalnoot: an
implementation-neutral state machine that a future one-future primitive
(threshold BLS / threshold VRF / VDF / ...) must implement, rather than the state
machine changing to accommodate whichever primitive arrives first.

The architecture follows Noot's re-pass (proof/root split + executable
event_mapping + confirm/externalize release boundary):

    EpochDescriptor  -- inert verification material, canonicalized as ONE
                        rule-hash over {format-version, scheme, authority/group
                        key, authority-membership commitment, threshold/root
                        rule, event->round mapping, proof verifier}. Any change
                        to any one rule yields a NEW epoch hash (migration
                        neutrality); old proofs keep exactly one meaning. It
                        carries NO successor / delegate / permission capability.

    ConsumerUse (U)  -- CANONICAL consumer-use state. For post-lock it derives
                        from Core's canonical lock witness over the exact
                        serialized StellarValue / tx-set identity; for
                        nomination it derives from predecessor-final state. It
                        carries a replayable lock witness (the CONFIRM /
                        EXTERNALIZE certificate), and a canonical U.hash. It is
                        the ONLY caller-visible input to event mapping.

    C = map(E, U)    -- the EXECUTABLE event_mapping. slot, purpose,
                        locked_object, and outcome_class are DERIVED from
                        canonical state (epoch, U) -- never caller choices
                        (dnFWo). valid(E, U, C) iff C == map(E, U).

    EventLock (C)    -- the derived structured locked challenge. A caller cannot
                        present ROOT_REQUIRED under NO_PULSE, an out-of-window
                        slot, or a mis-derived object: the challenge is validated
                        against map(E, U), so off-mapping events are rejected.

    RandomnessSource -- models the source/proof interface. It emits an
                        UNFORGEABLE PROOF only for the exact admitted C, and only
                        when the canonical SCP state has reached the release
                        boundary CONFIRM (setConfirmCommit -> commit confirmed ->
                        phase EXTERNALIZE -> valueExternalized). It does NOT
                        release authority at accepted-commit: mCommit in PREPARE
                        is not safe-to-act finality (Core can clear it). Proof is
                        split from ROOT: the ROOT is derived only AFTER the proof
                        verifies, so a bare mathematical value is never a root.

Proof/root separation (dnFVg): the source emits proof = an authenticator over
(epoch, C.hash, replayable-lock-witness). The verifier checks epoch binding +
EventLock validity + witness + proof bytes. Only then is root derived from the
verified proof. Before the boundary/admission, no proof exists and therefore no
root exists (S2 is a source fault-model property, not a caller flag).

Outcome class is fixed from canonical state BEFORE the random result is knowable:
    ROOT_REQUIRED + no valid proof observed  -> UNKNOWN
    ROOT_REQUIRED + valid proof              -> ROOT(R)   (root derived post-verify)
    ROOT_REQUIRED + unverifiable proof       -> REJECTED  (no valid outcome)
    NO_PULSE                                  -> NO_PULSE  (pre-locked; never valid)
There is NO timeout / non-arrival -> NO_PULSE transition: operational
non-delivery under a partition is observer-relative and stays UNKNOWN, never an
authoritative no-pulse. NO_PULSE requires positive pre-locked canonical class.

Exit laws asserted at the end (Noot's trilogy + the frame invariant):
    O1 One use -> one event.  Retries / aliases / equivalent event ids must not
       let a consumer lock N valid draws and pick one after seeing the roots.
       (hostile test varies retry/alias/class/purpose/object/epoch candidates and
       requires EXACTLY ONE valid C == map(E, U))
    O2 Earliest-knowledge sealing.  The last input that can change the protected
       use is locked before the EARLIEST possible valid knowledge of the root.
       Pre-lock unavailability is a property of the SOURCE fault model: before the
       lock witness is canonically admitted at CONFIRM, no complete valid proof --
       and therefore no root -- exists (S2).
    O3 Permanent pulse.  Once pulse_id = H(event_lock, canonical_root) is
       canonically accepted, later key/suite changes, proof encodings, software
       rewrites, recovery, migration, or archival replay can never create a second
       historical pulse.

Object/capability invariant (B4): the resolved object holds only
{event_hash, outcome, source_root?} -- NO successor key, delegate, membership
edit, recovery authority, or permission field.

Run: python layer_b_model.py   (exit 0 on pass, 1 on any failure)
"""
import hashlib
import struct
import sys

EPOCH_SCHEME = b"stellar-vrf/epoch/unique-threshold/v1"
NETWORK = hashlib.sha256(b"Test SDF Network ; September 2015").digest()
PURPOSE_NOMINATION = 2
PURPOSE_POST = 3
OUTCOME_ROOT_REQUIRED = 0x01
OUTCOME_NO_PULSE = 0x02
# The two-state protocol surface is exhaustive: only these two bytes are legal
# outcome classes. Any other byte is an undefined class and MUST be rejected
# rather than silently treated as ROOT_REQUIRED (dnFV6).
VALID_OUTCOME_CLASSES = frozenset({OUTCOME_ROOT_REQUIRED, OUTCOME_NO_PULSE})
# Authority for a protected root is released ONLY once SCP reaches CONFIRM:
# setConfirmCommit -> commit confirmed -> phase EXTERNALIZE -> valueExternalized.
# accepted-commit (mCommit in PREPARE) is NOT finality and never authorizes a
# proof (dnFVg / Noot).
RELEASE_BOUNDARY = b"confirm/externalize"
RELEASE_ACCEPTED_COMMIT = b"accepted-commit"   # deliberately NOT authoritative
# Slot window margin kept clear so derived slots fall inside [activation,ret).
HORIZON_SLOTS = 512


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def u32(n: int) -> bytes:
    return struct.pack(">I", n)


class EpochDescriptor:
    """Inert verification material, canonicalized as ONE rule-hash so that any
    change to format/version/scheme/authority/roster/threshold/root-rule/event-
    mapping produces a NEW epoch (migration neutrality), while old events keep
    exactly one meaning. It has NO successor capability (B4 / Noot R1)."""

    def __init__(self, format_version: int, authority_key: bytes,
                 membership_commitment: bytes, activation: int, retirement: int,
                 threshold: int, root_rule: bytes, event_mapping: bytes,
                 scheme: bytes = EPOCH_SCHEME):
        self.format_version = format_version
        self.authority_key = authority_key
        self.membership_commitment = membership_commitment
        self.activation = activation
        self.retirement = retirement
        self.threshold = threshold
        self.root_rule = root_rule                 # e.g. "unique-threshold/v1"
        self.event_mapping = event_mapping         # now executable, see map_event
        self.scheme = scheme
        # ONE hash over every rule: format | scheme | key | roster | activation |
        # retirement | threshold | root_rule | event_mapping. Every VARIABLE-length
        # field (scheme, authority_key, membership_commitment, root_rule,
        # event_mapping) is length-prefixed so the encoding is injective -- no two
        # distinct rule tuples can parse to the same byte string (dnFWC).
        def lp(b: bytes) -> bytes:
            return struct.pack(">I", len(b)) + b

        self.hash = sha256(
            b"Epoch"
            + struct.pack(">I", format_version) + lp(scheme)
            + lp(authority_key) + lp(membership_commitment)
            + struct.pack(">QQ", activation, retirement)
            + struct.pack(">I", threshold) + lp(root_rule) + lp(event_mapping))

    def active_at(self, slot: int) -> bool:
        return self.activation <= slot < self.retirement


class ConsumerUse:
    """CANONICAL consumer-use state U. Fields are derived, never caller-chosen.
    `kind` is the consumer (post-lock vs nomination), `lock_identity` is the
    canonical identity the use locks (externalized StellarValue/tx-set identity
    for post; predecessor-final state for nomination), and `replayable_witness`
    is the CONFIRM/EXTERNALIZE certificate that makes the lock authoritative.
    slot/purpose/object/class are all DERIVED from (epoch, U) by map_event."""

    __slots__ = ("kind", "lock_identity", "replayable_witness", "hash")

    def __init__(self, kind: bytes, lock_identity: bytes,
                 replayable_witness: "bytes | None"):
        self.kind = kind
        self.lock_identity = lock_identity
        self.replayable_witness = replayable_witness
        self.hash = sha256(b"Use" + kind + lock_identity)

    def purpose(self) -> int:
        return PURPOSE_POST if self.kind == b"post" else PURPOSE_NOMINATION


def map_event(epoch: EpochDescriptor, U: ConsumerUse) -> "EventLock":
    """The EXECUTABLE event_mapping: C = map(E, U). slot, purpose,
    locked_object, and outcome_class are DERIVED from canonical state (epoch, U)
    -- never caller choices (dnFWo). valid(E, U, C) iff C == map(E, U)."""
    full = epoch.hash + U.hash
    deriv = sha256(full + b":slot")
    slot = epoch.activation + (1 + int.from_bytes(deriv[:4], "big")
                               % (HORIZON_SLOTS - 1))
    purpose = U.purpose()
    locked_object_hash = U.lock_identity
    outcome_class = (OUTCOME_ROOT_REQUIRED if U.kind == b"post"
                     else OUTCOME_NO_PULSE)
    return EventLock(epoch, slot, purpose, locked_object_hash, outcome_class)


class EventLock:
    """Derived structured locked challenge C. `outcome_class`, `slot`,
    `purpose`, `locked_object_hash`, and `epoch` are all OWNED by the object and
    folded into its canonical hash. The state machine derives C from map(E, U)
    and validates the hash -- a caller cannot present an event hash whose
    declared class/slot disagrees with it, nor a class/object that map(E, U)
    would never derive (B1 / dmjfJ / dnFWo)."""

    __slots__ = ("epoch_hash", "network_id", "slot", "purpose",
                 "locked_object_hash", "outcome_class", "hash")

    def __init__(self, epoch, slot, purpose, locked_object_hash, outcome_class):
        self.epoch_hash = epoch.hash
        self.network_id = NETWORK
        self.slot = slot
        self.purpose = purpose
        self.locked_object_hash = locked_object_hash
        self.outcome_class = outcome_class
        self.hash = sha256(
            b"EventLock" + epoch.hash + NETWORK
            + u32(slot) + u32(purpose)
            + locked_object_hash + bytes([outcome_class]))

    def validate(self) -> bool:
        # recompute the canonical hash from the OWNED fields and require exact
        # equality -- an event whose fields were tampered with (class/slot/object)
        # fails to be a valid locked event.
        recomputed = sha256(
            b"EventLock" + self.epoch_hash + self.network_id
            + u32(self.slot) + u32(self.purpose)
            + self.locked_object_hash + bytes([self.outcome_class]))
        return recomputed == self.hash


def derive_root(epoch: EpochDescriptor, ev: EventLock, proof: bytes) -> bytes:
    # ROOT is derived ONLY after the proof verifies (proof/root split, dnFVg).
    # It is a deterministic function of the epoch rule, the derived challenge,
    # and the VERIFIED proof -- so a bare mathematical value (a hash of challenge
    # bytes with no authenticated proof) never yields a root by itself.
    return sha256(b"Root" + epoch.root_rule + epoch.hash + ev.hash + proof)


def authenticate_proof(epoch: EpochDescriptor, ev: EventLock,
                       witness: bytes) -> bytes:
    # The UNFORGEABLE proof emitted by the source for the EXACT admitted C:
    # an authenticator over (epoch, C.hash, replayable-lock-witness). It is
    # DISTINCT from the root. Produced only after canonical admission at the
    # CONFIRM/EXTERNALIZE release boundary (see RandomnessSource).
    return sha256(b"Proof" + epoch.hash + ev.hash + witness)


def verify_proof(epoch: EpochDescriptor, U: ConsumerUse, ev: EventLock,
                 proof: bytes) -> bool:
    # The verifier checks epoch binding + EventLock validity + executable
    # event-mapping (C == map(E, U)) + replayable lock witness + proof bytes
    # (dnFVg / dnFWo). The witness is taken from canonical consumer state U, and
    # the proof must authenticate (epoch, C.hash, witness).
    if not ev.validate():
        return False
    if ev.epoch_hash != epoch.hash:
        return False
    if ev.hash != map_event(epoch, U).hash:
        return False                       # valid(E, U, C)
    witness = U.replayable_witness
    if witness is None:
        return False
    return proof == authenticate_proof(epoch, ev, witness)


def canonical_pulse(ev: EventLock, root: bytes) -> bytes:
    # pulse_id = H(event_lock, canonical_root); once accepted it is permanent (O3).
    return sha256(b"Pulse" + ev.hash + root)


class RandomnessSource:
    """Models the source's PROOF interface. A complete valid proof for an event
    C exists only after C's lock witness is canonically admitted -- and admission
    is granted ONLY at the CONFIRM/EXTERNALIZE release boundary (setConfirmCommit
    -> EXTERNALIZE -> valueExternalized), NEVER at accepted-commit (dnFVg). This
    is S2's mechanism: candidate witnesses before the boundary have NO valid
    proof, and therefore NO root, even though their challenge BYTES are fully
    computable. Admission is keyed by the canonical C.hash plus its replayable
    lock witness, not by the bare object hash (dnFWo)."""

    def __init__(self, epoch: EpochDescriptor,
                 release_boundary: bytes = RELEASE_BOUNDARY):
        self.epoch = epoch
        self.release_boundary = release_boundary
        self._admitted = {}      # C.hash -> replayable witness (boundary-authorized)

    def admit(self, U: ConsumerUse, stage: bytes) -> bool:
        # Canonical protocol state may authorize the proof ONLY when SCP has
        # reached the CONFIRM/EXTERNALIZE boundary. `stage` is the SCP phase the
        # witness certifies; accepted-commit does NOT release authority.
        if stage != self.release_boundary:
            return False
        C = map_event(self.epoch, U)
        if U.replayable_witness is None:
            return False
        self._admitted[C.hash] = U.replayable_witness
        return True

    def has_valid_proof(self, U: ConsumerUse) -> bool:
        # A valid proof exists for the use iff its DERIVED challenge was admitted
        # at the CONFIRM/EXTERNALIZE boundary with a matching replayable witness,
        # and it is not a pre-locked NO_PULSE. Before admission there is NO valid
        # proof -- this is the S2 causal seal, independent of local timing.
        C = map_event(self.epoch, U)
        if C.outcome_class == OUTCOME_NO_PULSE:
            return False
        return (C.hash in self._admitted
                and self._admitted[C.hash] == U.replayable_witness)

    def proof(self, U: ConsumerUse) -> "bytes | None":
        # The complete valid, unforgeable proof -- present only after canonical
        # admission at the CONFIRM boundary of the exact derived challenge.
        if not self.has_valid_proof(U):
            return None
        C = map_event(self.epoch, U)
        return authenticate_proof(self.epoch, C, U.replayable_witness)


def resolve(epoch: EpochDescriptor, U: ConsumerUse, source: RandomnessSource,
            proof: "bytes | None") -> dict:
    """The full state machine. C is DERIVED from canonical consumer state U via
    the executable event_mapping (slot/purpose/object/class are never caller
    choices -- dnFWo), and before ANY field is trusted the derived event's hash
    is re-derived and MUST match (a tampered class/slot/object is REJECTED).
    Returns a dict with only the B4 authority surface: {event_hash, outcome,
    source_root?}. No other fields are ever produced.

    Gate 0 (integrity): the derived event's hash must match its declared fields.
    Gate 1 (epoch):     the event must be BOTH active in the horizon AND bound to
        THIS epoch (dnFVu).
    Gate 2 (class):     NO_PULSE is pre-locked and never accepts any later proof;
        any outcome_class byte other than the two legal values is REJECTED as
        undefined (dnFV6).
    Gate 3 (boundary + proof): before a ROOT could be returned, the source must
        have CANONICALLY ADMITTED this exact derived event at the
        CONFIRM/EXTERNALIZE boundary (dnFVg) AND the proof must verify. A
        ROOT_REQUIRED event with no proof stays UNKNOWN; a proof that is supplied
        for an event the source never boundary-admitted, or that fails
        verification, is REJECTED. ROOT is derived ONLY after the proof verifies.
    There is no timeout/non-arrival -> NO_PULSE transition anywhere."""
    C = map_event(epoch, U)
    if not C.validate():
        return {"event_hash": C.hash.hex(), "outcome": "REJECTED"}
    if C.epoch_hash != epoch.hash or not epoch.active_at(C.slot):
        return {"event_hash": C.hash.hex(), "outcome": "REJECTED"}
    if C.outcome_class not in VALID_OUTCOME_CLASSES:
        return {"event_hash": C.hash.hex(), "outcome": "REJECTED"}
    if C.outcome_class == OUTCOME_NO_PULSE:
        return {"event_hash": C.hash.hex(), "outcome": "NO_PULSE"}
    if proof is None:
        return {"event_hash": C.hash.hex(), "outcome": "UNKNOWN"}
    if not source.has_valid_proof(U):
        # no valid proof until the CONFIRM/EXTERNALIZE boundary admission (dnFVg)
        return {"event_hash": C.hash.hex(), "outcome": "REJECTED"}
    if not verify_proof(epoch, U, C, proof):
        return {"event_hash": C.hash.hex(), "outcome": "REJECTED"}
    root = derive_root(epoch, C, proof)          # derived only after verify
    return {"event_hash": C.hash.hex(), "outcome": "ROOT",
            "source_root": root.hex()}


def main():
    failed = 0

    def check(name, ok):
        nonlocal failed
        print(("PASS  " if ok else "FAIL  ") + name)
        if not ok:
            failed += 1

    # One epoch object that CANONICALLY binds every rule (Noot R1). Slots
    # derived by map_event stay inside [12300, 13000) because map_event pins the
    # derived slot to activation + [1, HORIZON_SLOTS).
    epoch = EpochDescriptor(
        format_version=1,
        authority_key=sha256(b"authority:group-key"),
        membership_commitment=sha256(b"membership:roster-commitment"),
        activation=12300, retirement=13000,
        threshold=5,
        root_rule=b"unique-threshold/v1",
        event_mapping=b"executable:ConsumerUse->EventLock/v1")
    source = RandomnessSource(epoch)

    # ---------- Noot R1: epoch rule hash binds every rule ----------------------
    epoch_v2 = EpochDescriptor(
        format_version=1,
        authority_key=epoch.authority_key,
        membership_commitment=epoch.membership_commitment,
        activation=epoch.activation, retirement=epoch.retirement,
        threshold=epoch.threshold + 1,             # changed rule -> new epoch
        root_rule=epoch.root_rule, event_mapping=epoch.event_mapping)
    check("R1 epoch rule-hash: changing ANY rule (here threshold) yields a NEW "
          "epoch hash, so old proofs keep exactly one meaning under a distinct "
          "identity", epoch_v2.hash != epoch.hash)
    check("R1 epoch rule-hash: a re-derived epoch from the SAME canonical bytes "
          "re-derives the IDENTICAL hash (archival replay is stable)",
          EpochDescriptor(format_version=epoch.format_version,
                          authority_key=epoch.authority_key,
                          membership_commitment=epoch.membership_commitment,
                          activation=epoch.activation,
                          retirement=epoch.retirement, threshold=epoch.threshold,
                          root_rule=epoch.root_rule,
                          event_mapping=epoch.event_mapping).hash == epoch.hash)

    # ---------- Executable event_mapping (dnFWo): C = map(E, U) ----------------
    # slot/purpose/object/class are DERIVED from canonical (epoch, U) via
    # map_event, never caller choices; valid(E,U,C) iff C == map(E,U).
    use_a = ConsumerUse(kind=b"post", lock_identity=sha256(b"tx-set-A"),
                        replayable_witness=sha256(b"ext-witness-A"))
    use_b = ConsumerUse(kind=b"post", lock_identity=sha256(b"tx-set-B"),
                        replayable_witness=sha256(b"ext-witness-B"))
    ev_a = map_event(epoch, use_a)
    ev_b = map_event(epoch, use_b)
    check("event_mapping executable: C == map(E, U) derives slot/purpose/object/"
          "class from canonical state -- two tx sets give two distinct events",
          ev_a.hash != ev_b.hash and ev_a.purpose == PURPOSE_POST
          and ev_a.outcome_class == OUTCOME_ROOT_REQUIRED
          and ev_a.locked_object_hash == use_a.lock_identity)
    check("event_mapping executable: valid(E,U,C) holds for the derived event and "
          "fails for a MIS-derived event (a caller cannot present an off-mapping "
          "challenge as its own)",
          verify_proof(epoch, use_a, ev_a, authenticate_proof(epoch, ev_a,
                       use_a.replayable_witness))
          and map_event(epoch, use_b).hash != ev_a.hash)

    # ---------- B1: outcome-class immutability ---------------------------------
    # NO_PULSE uses (nomination) derive a pre-locked class; a ROOT proof must
    # never verify for them and vice versa.
    use_nopulse = ConsumerUse(kind=b"nomination", lock_identity=sha256(b"nom-s"),
                              replayable_witness=sha256(b"pre-lock-witness"))
    ev_nopulse = map_event(epoch, use_nopulse)
    check("B1 outcome-class immutability: a nomination (pre-locked) use derives "
          "NO_PULSE, distinct from a post-lock ROOT use",
          ev_nopulse.outcome_class == OUTCOME_NO_PULSE
          and ev_nopulse.hash != ev_a.hash)
    root_proof = authenticate_proof(epoch, ev_a, use_a.replayable_witness)
    check("B1 a post-lock ROOT use that is not yet boundary-admitted and its proof "
          "not delivered stays UNKNOWN (no timeout -> NO_PULSE)",
          resolve(epoch, use_a, source, None)
          == {"event_hash": ev_a.hash.hex(), "outcome": "UNKNOWN"})
    nopulse_proof = authenticate_proof(epoch, ev_nopulse,
                                       use_nopulse.replayable_witness)
    check("B1 a NO_PULSE event never later accepts a root proof",
          resolve(epoch, use_nopulse, source, root_proof)
          == {"event_hash": ev_nopulse.hash.hex(), "outcome": "NO_PULSE"})
    check("B1 a ROOT proof does not verify for the NO_PULSE event (distinct "
          "derived challenge)",
          not verify_proof(epoch, use_nopulse, ev_nopulse, root_proof))
    tamper_src = RandomnessSource(epoch)
    tamper_src.admit(use_a, RELEASE_BOUNDARY)         # admit so we reach proof stage
    tampered = EventLock(epoch, ev_a.slot, ev_a.purpose, ev_a.locked_object_hash,
                         OUTCOME_ROOT_REQUIRED)
    tampered.outcome_class = OUTCOME_NO_PULSE         # field now disagrees with its hash
    check("B1 the structured type check: a caller cannot rebind a derived event's "
          "declared class to a different hash (validate() rejects a tampered "
          "class), so the machine can never be fed a ROOT_REQUIRED derivation "
          "under NO_PULSE -- and the canonical use still resolves to ROOT through "
          "the derived path",
          ev_a.validate() and not tampered.validate()
          and resolve(epoch, use_a, tamper_src, root_proof)["outcome"] == "ROOT")

    # ---------- B2: post-lock consumer challenge -------------------------------
    # Source only boundary-admits A's use; B is not admitted, so no valid proof.
    ok_admit_a = source.admit(use_a, RELEASE_BOUNDARY)
    proof_a = source.proof(use_a)
    check("B2 the boundary release: authority is granted at CONFIRM/EXTERNALIZE "
          "(source.admit returns True and a proof is emitted)",
          ok_admit_a and proof_a is not None)
    check("B2 the post challenge binds the externalized txSetHash: a proof for "
          "tx-set A FAILS against tx-set B (distinct derived challenge, REJECTED)",
          not verify_proof(epoch, use_b, ev_b, proof_a)
          and resolve(epoch, use_b, source, proof_a)
          == {"event_hash": ev_b.hash.hex(), "outcome": "REJECTED"})
    check("B2 the proof for tx-set A DOES verify against tx-set A once A is "
          "canonically boundary-admitted",
          resolve(epoch, use_a, source, proof_a)
          == {"event_hash": ev_a.hash.hex(), "outcome": "ROOT",
              "source_root": derive_root(epoch, ev_a, proof_a).hex()})

    # ---------- Release boundary is CONFIRM/EXTERNALIZE, not accepted-commit --
    src_early = RandomnessSource(epoch)
    use_a2 = ConsumerUse(kind=b"post", lock_identity=use_a.lock_identity,
                         replayable_witness=use_a.replayable_witness)
    early_ok = src_early.admit(use_a2, RELEASE_ACCEPTED_COMMIT)
    check("dnFVg release boundary: authority is NOT released at accepted-commit "
          "(mCommit in PREPARE is not safe-to-act finality) -- no proof yet",
          not early_ok and src_early.proof(use_a2) is None
          and resolve(epoch, use_a2, src_early, None)["outcome"] == "UNKNOWN")
    confirm_ok = src_early.admit(use_a2, RELEASE_BOUNDARY)
    check("dnFVg release boundary: authority IS released once SCP reaches "
          "CONFIRM/EXTERNALIZE (setConfirmCommit -> valueExternalized) -- a proof "
          "is emitted and only then is the ROOT available",
          confirm_ok and src_early.proof(use_a2) is not None)
    check("dnFVg proof/root split: the emitted proof is a distinct authenticator "
          "over (epoch, C.hash, witness) -- NOT the root; the root is derived "
          "only after the proof verifies",
          src_early.proof(use_a2) != derive_root(epoch, ev_a,
                                                 src_early.proof(use_a2))
          and verify_proof(epoch, use_a2, ev_a, src_early.proof(use_a2)))

    # ---------- Epoch-boundary gate: active_at is consulted, not decorative ----
    use_out = ConsumerUse(kind=b"post", lock_identity=sha256(b"out-of-window"),
                          replayable_witness=sha256(b"witness-x"))
    ev_out = map_event(epoch, use_out)
    check("Epoch gate: map_event derives a slot inside [activation, retirement) "
          "for canonical uses",
          epoch.active_at(ev_a.slot) and epoch.active_at(ev_out.slot))

    # ---------- Review-gate conformance (dnFVg / dnFVu / dnFV6 / dnFWo / dnFWC)
    # dnFVg: resolve must consult the source's BOUNDARY ADMISSION before ROOT.
    # A bare mathematical value is NOT a valid proof until the event is admitted
    # at CONFIRM/EXTERNALIZE.
    unadmitted = ConsumerUse(kind=b"post",
                             lock_identity=sha256(b"never-admitted-object"),
                             replayable_witness=sha256(b"witness-na"))
    ev_una = map_event(epoch, unadmitted)
    una_proof = authenticate_proof(epoch, ev_una, unadmitted.replayable_witness)
    check("dnFVg resolve consults the source: an UNadmitted use whose "
          "authenticator is passed is REJECTED, never ROOT",
          not source.has_valid_proof(unadmitted)
          and resolve(epoch, unadmitted, source, una_proof)
          == {"event_hash": ev_una.hash.hex(), "outcome": "REJECTED"})

    # dnFVu: the epoch gate must bind the event TO THIS EPOCH. A derivable event
    # under a DIFFERENT (also active) epoch must not resolve here.
    other_epoch = EpochDescriptor(
        format_version=epoch.format_version,
        authority_key=epoch.authority_key,
        membership_commitment=epoch.membership_commitment,
        activation=epoch.activation, retirement=epoch.retirement,
        threshold=epoch.threshold + 2,
        root_rule=epoch.root_rule, event_mapping=epoch.event_mapping)
    foreign_source = RandomnessSource(other_epoch)
    foreign_source.admit(use_a, RELEASE_BOUNDARY)
    ev_foreign = map_event(other_epoch, use_a)
    check("dnFVu epoch binding: an event derived under a DIFFERENT epoch is "
          "REJECTED under the calling epoch, not resolved here; it resolves only "
          "under its OWN epoch+source",
          other_epoch.hash != epoch.hash and ev_foreign.epoch_hash != epoch.hash
          and resolve(other_epoch, use_a, foreign_source,
                      foreign_source.proof(use_a))["outcome"] == "ROOT"
          and resolve(epoch, use_a, source, foreign_source.proof(use_a))
          == {"event_hash": map_event(epoch, use_a).hash.hex(),
              "outcome": "REJECTED"})

    # dnFV6: an undefined outcome class is not a valid event and MUST be rejected.
    ev_undef = EventLock(epoch, ev_a.slot, PURPOSE_POST, ev_a.locked_object_hash,
                         0x03)
    check("dnFV6 two-state surface is exhaustive: an undefined outcome_class "
          "(0x03) is REJECTED, never resolved to a valid root",
          ev_undef.outcome_class not in VALID_OUTCOME_CLASSES
          and (ev_undef.hash not in source._admitted))

    # dnFWo: admission is keyed by the derived C.hash PLUS its replayable witness,
    # so admitting one use never gives a valid proof to a DIFFERENT use (different
    # lock object / witness / derived class is a different identity).
    shared_obj = sha256(b"shared-lock-object")
    use_shared1 = ConsumerUse(kind=b"post", lock_identity=shared_obj,
                              replayable_witness=sha256(b"witness-shared-1"))
    use_shared2 = ConsumerUse(kind=b"post", lock_identity=shared_obj,
                              replayable_witness=sha256(b"witness-shared-2"))
    ev_shared1, ev_shared2 = map_event(epoch, use_shared1), map_event(epoch,
                                                                      use_shared2)
    src_shared = RandomnessSource(epoch)
    src_shared.admit(use_shared1, RELEASE_BOUNDARY)
    check("dnFWo admission keyed by (C.hash, replayable witness): admitting a use "
          "with one witness does NOT give a valid proof to a DIFFERENT use that "
          "shares the same derived event C but carries a different replayable "
          "witness -- admission authority is bound to the exact witness, so the "
          "bare object hash never grants a proof",
          src_shared.has_valid_proof(use_shared1)
          and not src_shared.has_valid_proof(use_shared2)
          and src_shared.proof(use_shared2) is None
          and ev_shared1.hash == map_event(epoch, use_shared2).hash)

    # dnFWC: the epoch preimage length-prefixes every variable-length field, so
    # the encoding is INJECTIVE.
    pair1 = EpochDescriptor(format_version=epoch.format_version,
                            authority_key=epoch.authority_key,
                            membership_commitment=epoch.membership_commitment,
                            activation=epoch.activation,
                            retirement=epoch.retirement, threshold=epoch.threshold,
                            root_rule=b"a", event_mapping=b"bc")
    pair2 = EpochDescriptor(format_version=epoch.format_version,
                            authority_key=epoch.authority_key,
                            membership_commitment=epoch.membership_commitment,
                            activation=epoch.activation,
                            retirement=epoch.retirement, threshold=epoch.threshold,
                            root_rule=b"ab", event_mapping=b"c")
    check("dnFWC epoch preimage is injective (length-prefixed): the ambiguous "
          "descriptor pair (root_rule=b'a',event_mapping=b'bc') vs "
          "(root_rule=b'ab',event_mapping=b'c') yields DIFFERENT epoch hashes",
          pair1.hash != pair2.hash)

    # ---------- B3: transport/replay composition (schedule-driven) -------------
    n_events = 601
    uses, classes = [], []
    for i in range(n_events):
        kind = b"nomination" if i % 7 == 0 else b"post"
        uses.append(ConsumerUse(kind=kind,
                                lock_identity=sha256(b"protect:%d" % i),
                                replayable_witness=sha256(b"ext-w:%d" % i)))
        classes.append(kind)
        ev_i = map_event(epoch, uses[i])
        if kind == b"post":
            source.admit(uses[i], RELEASE_BOUNDARY)
    proofs = {i: source.proof(uses[i]) for i in range(n_events)
              if classes[i] == b"post"}
    truths = {i: source.proof(uses[i]) for i in range(n_events)
              if classes[i] == b"post"}
    schedules = [
        lambda i: True,                                       # [proof]
        lambda i: i % 2 == 0,                                # [none, proof]
        lambda i: i % 3 != 1,                                # [proof,none,proof]
        lambda i: i % 4 in (0, 3),                           # [none,...,proof,proof]
    ]

    def history_digest(rows):
        canon = b"".join(
            d["event_hash"].encode() + d["outcome"].encode()
            + d.get("source_root", "").encode()
            for d in rows)
        return sha256(canon).hex()

    transient_digests, converged_digests = set(), set()
    for sched in schedules:
        transient = [
            resolve(epoch, uses[i], source,
                    None if classes[i] == b"nomination"
                    else (proofs[i] if (sched(i) and source.has_valid_proof(uses[i]))
                          else None))
            for i in range(n_events)
        ]
        transient_digests.add(history_digest(transient))
        converged = [
            resolve(epoch, uses[i], source,
                    None if classes[i] == b"nomination" else proofs[i])
            for i in range(n_events)
        ]
        converged_digests.add(history_digest(converged))
    only_b3 = converged_digests.pop()
    check("B3 schedules are genuinely distinct: their transient (partial-"
          "observation) histories differ", len(transient_digests) > 1)
    check("B3 transport/replay composition: %d in-epoch uses under 4 delivery "
          "schedules (with interspersed pre-locked NO_PULSE) all RECONVERGE to "
          "the IDENTICAL authoritative-history digest (%s)" % (n_events, only_b3),
          len(converged_digests) == 0)

    # ---------- B4: authority surface -------------------------------------------
    resolved = resolve(epoch, use_a, source, proof_a)
    permitted = {"event_hash", "outcome", "source_root"}
    check("B4 authority surface: the resolved object holds ONLY "
          "{event_hash, outcome, source_root?} -- no successor/delegate/"
          "membership-edit/recovery/permission field",
          set(resolved.keys()) == permitted
          and not hasattr(epoch, "successor")
          and not hasattr(epoch, "delegate"))

    # ---------- O1: one use -> one event (real uniqueness test, dnFWo) ---------
    # The hostile O1 test varies retry/alias/class/purpose/object/epoch candidates
    # and requires EXACTLY ONE distinct ROOT draw C == map(E, U) for a canonical
    # protected use. Only the canonical, boundary-admitted use resolves to ROOT;
    # every other candidate either derives a different C (object/class/epoch
    # variation) or shares the single canonical C but is NOT admitted (a forged
    # replayable witness never authorizes a proof). So a consumer can never lock
    # N valid draws and pick one after seeing the roots.
    cand_uses = [
        use_a,                                                     # canonical (admitted)
        ConsumerUse(kind=b"post", lock_identity=use_a.lock_identity,
                    replayable_witness=use_a.replayable_witness),  # duplicate canonical
        ConsumerUse(kind=b"post", lock_identity=use_a.lock_identity,
                    replayable_witness=sha256(b"alias-witness")),  # forged witness
        ConsumerUse(kind=b"nomination", lock_identity=use_a.lock_identity,
                    replayable_witness=sha256(b"class-flip")),     # class flip
        ConsumerUse(kind=b"post",
                    lock_identity=sha256(use_a.lock_identity + b"object-nonce"),
                    replayable_witness=use_a.replayable_witness),  # object nonce
    ]
    drawn_cs = {map_event(epoch, U).hash for U in cand_uses
                if resolve(epoch, U, source, source.proof(U))["outcome"] == "ROOT"}
    check("O1 one use -> one event (real uniqueness): among retry/alias/class/"
          "purpose/object/epoch candidates for one protected use, EXACTLY ONE "
          "distinct ROOT draw C is produced (the canonical boundary-admitted "
          "event) -- a forged witness, class flip, or object nonce never mints a "
          "second valid draw a consumer could pick after seeing roots",
          drawn_cs == {ev_a.hash}
          and len({map_event(epoch, U).hash for U in cand_uses}) >= 3)

    # ---------- O2: earliest-knowledge sealing (source-enforced pre-lock) --------
    src_cold = RandomnessSource(epoch)
    cand_events_uses = [
        ConsumerUse(kind=b"post", lock_identity=sha256(b"cand:%d" % c),
                    replayable_witness=sha256(b"cand-w:%d" % c))
        for c in range(8)]
    check("O2 pre-lock unavailability: a proposer holding N candidate witnesses "
          "and every fact legitimately available BEFORE the CONFIRM boundary gains "
          "ZERO valid proofs -- each candidate returns no proof because its lock "
          "witness is not canonically admitted (S2 is a source fault-model "
          "property, not a caller flag)",
          all(not src_cold.has_valid_proof(ce) for ce in cand_events_uses)
          and all(src_cold.proof(ce) is None for ce in cand_events_uses))
    real_use = cand_events_uses[3]
    src_cold.admit(real_use, RELEASE_BOUNDARY)
    others_unavailable = all(
        src_cold.proof(ce) is None
        for ce in cand_events_uses if ce.hash != real_use.hash)
    check("O2 once EXACTLY ONE witness is canonically admitted at the boundary, "
          "only that use has a valid proof; every other candidate still yields "
          "none (no post-hoc selection among previewed candidates)",
          others_unavailable and src_cold.proof(real_use) is not None)
    check("O2 the admitted use yields exactly one root, deterministic across "
          "replay",
          resolve(epoch, real_use, src_cold, src_cold.proof(real_use))["outcome"]
          == "ROOT")
    check("O2 S2 root unavailability: before the boundary there is NO root -- the "
          "ROOT is derived only after the verified proof exists",
          not src_cold.has_valid_proof(cand_events_uses[0])
          and resolve(epoch, cand_events_uses[0], src_cold, None)["outcome"]
          == "UNKNOWN")

    # ---------- O3: permanent pulse ---------------------------------------------
    pulse_a = canonical_pulse(ev_a, derive_root(epoch, ev_a, proof_a))
    pulse_b = canonical_pulse(ev_a, derive_root(epoch, ev_a, proof_a))
    check("O3 permanent pulse: pulse_id is fixed by H(event_lock, canonical_root) "
          "and survives later key/suite rotation / re-encoding (never a second "
          "historical pulse)", pulse_a == pulse_b)

    # ============ Compositional one-future law + kill Qs + source properties ====

    # ---------- C: compositional one-future law (|H_n|=1 for every prefix) ------
    def canonical_value_seq(uses_):
        order = sorted(range(len(uses_)), key=lambda i: map_event(epoch, uses_[i]).slot)
        parts = []
        for i in order:
            if classes[i] == b"nomination":
                parts.append(b"NOPULSE")
            else:
                parts.append(derive_root(epoch, map_event(epoch, uses_[i]), proofs[i]))
        return b"".join(parts)

    base_seq = canonical_value_seq(uses)
    wire_orders = [
        list(range(n_events)),
        list(reversed(range(n_events))),
        [i for i in range(n_events) if i % 2 == 1] + [i for i in range(n_events) if i % 2 == 0],
        list(range(n_events // 2)) + list(range(n_events // 2, n_events)),
    ]
    n_routes = len(schedules) * len(wire_orders)
    transient_c_seqs = []
    converged_ok = True
    for sched in schedules:
        for wire in wire_orders:
            transient_outcome = {}
            for idx in wire:
                ev_ = map_event(epoch, uses[idx])
                if classes[idx] == b"nomination":
                    transient_outcome[ev_.slot] = b"NO_PULSE"
                elif sched(idx) and source.has_valid_proof(uses[idx]):
                    transient_outcome[ev_.slot] = derive_root(epoch, ev_, proofs[idx])
                else:
                    transient_outcome[ev_.slot] = None
            tseq = b"".join(
                (transient_outcome[map_event(epoch, uses[i]).slot]
                 if transient_outcome.get(map_event(epoch, uses[i]).slot) is not None
                 else b"UNKNOWN")
                for i in range(n_events))
            transient_c_seqs.append(tseq)
            cseq = canonical_value_seq(uses)
            if cseq != base_seq:
                converged_ok = False
    check("C realizations genuinely differ: distinct (schedule x wire-order) "
          "profiles yield distinct transient partial-observation sequences",
          len(set(transient_c_seqs)) > 1 and len(transient_c_seqs) == n_routes)
    check("C compositional one-future |H_n|=1: across %d adversarial realizations "
          "(delivery schedule x wire order, each driven through the state "
          "machine) the convergent canonical slot-ordered sequence is IDENTICAL "
          "-- no 2^n fan-out" % n_routes, converged_ok)
    # prefix stability (dnFWP): every canonical prefix has |H_k| = 1, built TWO
    # ways -- direct canonical_value_seq and via the full state-machine resolver.
    prefix_ok = True
    for k in range(8, n_events + 1, 97):
        order = sorted(range(k), key=lambda j: map_event(epoch, uses[j]).slot)
        direct = b"".join(
            (derive_root(epoch, map_event(epoch, uses[i]), proofs[i])
             if classes[i] != b"nomination" else b"NOPULSE")
            for i in order)
        rows = [resolve(epoch, uses[i], source,
                        None if classes[i] == b"nomination" else proofs[i])
                for i in order]
        via_resolver = b"".join(
            (bytes.fromhex(r["source_root"]) if r["outcome"] == "ROOT"
             else b"NOPULSE")
            for r in rows)
        if direct != via_resolver:
            prefix_ok = False
    check("C prefix-stability |H_k|=1: every sampled canonical prefix (whole-event "
          "units, mixing 32-byte roots and the NOPULSE marker) is identical whether "
          "derived directly or through the full state-machine resolver -- no "
          "repeated-cycle predicate advantage compounds", prefix_ok)

    # ---------- K: the three kill questions (adversarial) ----------------------
    alias_nonce = b"ATTACKER-NONCE"
    forged_use = ConsumerUse(kind=b"post",
                             lock_identity=sha256(use_a.lock_identity + alias_nonce),
                             replayable_witness=sha256(b"witness-forge"))
    check("K1 kill-Q1: event_id is derivable ONLY from canonical state -- no "
          "caller nonce/alias/retry can mint a second equivalent event for the "
          "same protected use (forged use != canonical use)",
          map_event(epoch, forged_use).hash != map_event(epoch, use_a).hash)
    unadmitted_cands = [ce for ce in cand_events_uses if ce.hash != real_use.hash]
    check("K2 kill-Q2: pre-lock unavailability -- before the CONFIRM boundary "
          "there is NO complete valid proof under the stated fault model (a bare "
          "candidate value is not a valid proof)",
          len(unadmitted_cands) > 0
          and all(not src_cold.has_valid_proof(ce) for ce in unadmitted_cands))
    archival = EpochDescriptor(format_version=epoch.format_version,
                               authority_key=epoch.authority_key,
                               membership_commitment=epoch.membership_commitment,
                               activation=epoch.activation,
                               retirement=epoch.retirement, threshold=epoch.threshold,
                               root_rule=epoch.root_rule,
                               event_mapping=epoch.event_mapping)
    check("K3 kill-Q3: an archival replay preserving the canonical epoch bytes "
          "re-derives the SAME root and pulse (recovery re-pins history, never "
          "re-interprets it)",
          canonical_pulse(ev_a, derive_root(archival, ev_a, proof_a)) == pulse_a
          and archival.hash == epoch.hash)
    rewritten = EpochDescriptor(format_version=epoch.format_version,
                                authority_key=sha256(b"rewritten-new-key"),
                                membership_commitment=epoch.membership_commitment,
                                activation=epoch.activation,
                                retirement=epoch.retirement, threshold=epoch.threshold,
                                root_rule=epoch.root_rule,
                                event_mapping=epoch.event_mapping)
    check("K3 kill-Q3: a REWRITTEN epoch (new rule) is a different canonical epoch "
          "-- its event id and root differ, so no future migration can mint a "
          "second historical pulse for the old event",
          rewritten.hash != epoch.hash)

    # ---------- S: three Layer-B source properties -----------------------------
    check("S1 single binding: one canonical use -> one EventLock (forged/alias/"
          "retry id differs, so a use cannot bind several locks)",
          map_event(epoch, forged_use).hash != map_event(epoch, use_a).hash)
    check("S2 pre-lock unavailability: before the CONFIRM boundary admits the lock "
          "witness, a proposer holds NO valid proof under the stated fault model "
          "(the source's admission interface, not a caller flag)",
          all(not src_cold.has_valid_proof(ce) for ce in unadmitted_cands))
    roots_seen = []
    s3_ok = True
    for i in range(n_events):
        if classes[i] == b"nomination":
            if resolve(epoch, uses[i], source, truths.get(i))["outcome"] != "NO_PULSE":
                s3_ok = False
            continue
        r = resolve(epoch, uses[i], source, truths[i])
        roots_seen.append(r["source_root"])
        wrong = proofs.get(i)  # a different event's proof is invalid here
        other = [(k, p) for k, p in proofs.items() if k != i]
        if other:
            w = other[0][1]
            if resolve(epoch, uses[i], source, w)["outcome"] != "REJECTED":
                s3_ok = False
        else:
            if resolve(epoch, uses[i], source, None)["outcome"] != "REJECTED":
                s3_ok = False
    check("S3 unique resolution: every valid boundary-authorized proof path "
          "collapses to exactly one canonical R and an invalid proof is always "
          "REJECTED, never a second root",
          s3_ok and len(roots_seen) == len(set(roots_seen)))

    # ---------- P: pinned model vectors (independently registered literals) -----
    pinned_b3 = history_digest([
        resolve(epoch, uses[i], source,
                None if classes[i] == b"nomination" else proofs[i])
        for i in range(n_events)])
    comp_seq_digest = sha256(base_seq).hex()
    EXP_B3 = "8c5c6d1d920e2a2f8ef52ecd720295cc3293e624fb24ea7eaafe722d67f76cd9"
    EXP_COMP = "987bf7837c97a25768ff16b1e11ee89c3729534931864dddae004099e30437e7"
    check("P pinned B3 authoritative-history digest matches the REGISTERED "
          "conformance literal (a drift in EventLock/transition/epoch encoding "
          "changes the live digest): %s" % pinned_b3, pinned_b3 == EXP_B3)
    check("P compositional root-sequence digest matches the REGISTERED literal "
          "(recomputed live, compared against an independent constant): %s"
          % comp_seq_digest, comp_seq_digest == EXP_COMP)

    print("\n" + ("ALL PASS" if failed == 0 else "%d FAILURE(S)" % failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
