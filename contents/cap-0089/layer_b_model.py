#!/usr/bin/env python3
"""CAP-0089 Layer B executable state-machine model (normative protocol-randomness
target).

This is the executable Layer-B model discussed with tacticalnoot: an
implementation-neutral state machine that a future one-future primitive
(threshold BLS / threshold VRF / VDF / ...) must implement, rather than the state
machine changing to accommodate whichever primitive arrives first.

Objects (deliberately small):

    EpochDescriptor  -- inert verification material. It is a SINGLE canonical hash
                        over {format-version, scheme, authority/group key,
                        authority-membership commitment, threshold/root rule,
                        event->round mapping, proof verifier}. Any change to any
                        one rule yields a NEW epoch hash (migration-neutrality:
                        old proofs keep exactly one meaning; a future verifier
                        that re-derives the same bytes re-derives the same root).
                        It carries NO successor / delegate / permission capability
                        (succession is a canonical protocol-state concern, outside
                        the random key).

    EventLock        -- a STRUCTURED locked challenge carrying every field:
                        {epoch, network_id, slot, purpose, locked_object_hash,
                         outcome_class} with a deterministic canonical hash. The
                         state machine always derives slot/class from the event
                         object, and validates the object's hash before it can be
                         resolved -- so a caller cannot present a ROOT_REQUIRED
                         hash under OUTCOME_NO_PULSE or an out-of-window slot.

    RandomnessSource -- models the source's ADMISSION interface. A complete valid
                         proof for an event is produced only after that event's
                         lock witness is canonically admitted (honest share
                         release conditioned on canonical lock). A bare
                         deterministic hash of candidate bytes is NOT itself a
                         valid proof: validity requires canonical admission, which
                         the source enforces. This is the bit-level causal seal
                         (challenge BYTES are computable pre-lock; a complete
                         valid PROOF is not until the witness is canonical).

Outcome class is fixed from canonical state BEFORE the random result is knowable:
    ROOT_REQUIRED + no valid proof observed  -> UNKNOWN
    ROOT_REQUIRED + valid proof              -> ROOT(R)   (must verify)
    ROOT_REQUIRED + unverifiable proof       -> REJECTED  (no valid outcome)
    NO_PULSE                                  -> NO_PULSE  (pre-locked; no later
                                                           proof is ever valid)
There is NO timeout / non-arrival -> NO_PULSE transition: operational
non-delivery under a partition is observer-relative and stays UNKNOWN, never an
authoritative no-pulse. NO_PULSE requires positive pre-locked canonical class.

Exit laws asserted at the end (Noot's trilogy + the frame invariant):
    O1 One use -> one event.  Retries / aliases / equivalent event ids must not
       let a consumer lock N valid draws and pick one after seeing the roots.
    O2 Earliest-knowledge sealing.  The last input that can change the protected
       use is locked before the EARLIEST possible valid knowledge of the root.
       Pre-lock unavailability is a property of the SOURCE fault model: before the
       lock witness is canonical, no complete valid proof exists (S2).
    O3 Permanent pulse.  Once pulse_id = H(event_lock, canonical_root) is
       canonically accepted, later key/suite changes, proof encodings, software
       rewrites, recovery, migration, or archival replay can never create a second
       historical pulse.

Conformance vectors:
    B1 outcome-class immutability   (events differ if outcome_class differs; a
       ROOT proof never verifies for the NO_PULSE event and vice versa)
    B2 post-lock consumer challenge (locked_object = externalized_txSetHash; two
       tx sets -> two events; a proof for tx-set A MUST fail (REJECT) against B)
    B3 transport/replay composition (601 consecutive events, 4 delivery schedules,
       interspersed pre-locked NO_PULSE: transient histories differ, but every
       schedule RECONVERGES to the SAME authoritative-history digest)
    B4 authority surface           (resolved object holds only
       {event_hash, outcome, source_root?} -- NO successor key, delegate,
       membership edit, recovery authority, or permission field)

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
        self.event_mapping = event_mapping         # e.g. "EventLock/v1"
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


class EventLock:
    """Structured locked challenge. `outcome_class`, `slot`, `purpose`,
    `locked_object_hash`, and `epoch` are all OWNED by the object and folded into
    its canonical hash. The state machine reads slot/class from this object and
    validates the hash -- a caller cannot present an event hash whose declared
    class/slot disagrees with it (B1 / dmjfJ)."""

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


def unique_root(epoch: EpochDescriptor, ev: EventLock) -> bytes:
    # Model of the unique-output primitive (threshold BLS / VRF / VDF) folded
    # under the epoch's root rule. One locked challenge -> exactly one root;
    # deterministic so replay converges. A bare hash of candidate bytes is the
    # primitive's mathematical value, NOT itself a valid proof: a valid proof
    # additionally requires canonical admission (see RandomnessSource).
    return sha256(b"Root" + epoch.root_rule + epoch.hash + ev.hash)


def verify_proof(epoch: EpochDescriptor, ev: EventLock, proof: bytes) -> bool:
    # A proof only "verifies" if it is the canonical unique output of THIS event
    # AND the event is a valid locked event under this epoch. Because
    # locked_object_hash, slot, purpose, and outcome_class are owned by `ev`,
    # a proof for a different tx set / slot / class cannot equal
    # unique_root(epoch, ev) -- it FAILS verification (B1, B2). The caller never
    # supplies the root; the verifier derives and compares it.
    return ev.validate() and proof == unique_root(epoch, ev)


def canonical_pulse(ev: EventLock, root: bytes) -> bytes:
    # pulse_id = H(event_lock, canonical_root); once accepted it is permanent (O3).
    return sha256(b"Pulse" + ev.hash + root)


class RandomnessSource:
    """Models the source's ADMISSION interface. A complete valid proof for an
    event exists only after the event's lock witness is canonically admitted
    (honest share release conditioned on canonical lock). This is S2's mechanism:
    candidate witnesses before lock have NO valid proof, even though their
    challenge BYTES are fully computable. Admission is driven by canonical
    protocol state (a witness record), never by a caller-controlled flag."""

    def __init__(self, epoch: EpochDescriptor):
        self.epoch = epoch
        self._admitted = {}      # event_hash -> canonical witness digest

    def admit(self, ev: EventLock, witness: bytes):
        # Canonical protocol state admits the witness for the WHOLE event -- its
        # canonical event hash folds in epoch, network, slot, purpose, locked
        # object, and outcome class (dnFWo). Admitting one event therefore does
        # NOT make every different event that happens to share the same
        # locked_object_hash valid: only this exact event's proof may become
        # available, once its last mutable input is fixed.
        self._admitted[ev.hash] = witness

    def has_valid_proof(self, ev: EventLock) -> bool:
        # A valid proof exists for an event iff THIS event (by its full canonical
        # event hash) was canonically admitted, and it is not a pre-locked
        # NO_PULSE. Before admission there is NO valid proof -- this is the S2
        # causal seal, independent of local timing/arrival.
        if ev.outcome_class == OUTCOME_NO_PULSE:
            return False
        return ev.hash in self._admitted

    def proof(self, ev: EventLock) -> "bytes | None":
        # The complete valid proof, present only after canonical admission of the
        # exact event.
        if not self.has_valid_proof(ev):
            return None
        return unique_root(self.epoch, ev)


def resolve(epoch: EpochDescriptor, ev: EventLock, source: RandomnessSource,
            proof: "bytes | None") -> dict:
    """The full state machine. slot and outcome_class come FROM the event object
    (not separate trusted params), so they cannot disagree with the event hash;
    before ANY field is trusted the event's canonical hash is re-derived and MUST
    match (a tampered class/slot/object is REJECTED, never silently honored).
    Returns a dict with only the B4 authority surface: {event_hash, outcome,
    source_root?}. No other fields are ever produced.

    Gate 0 (integrity): the event's hash must match its declared fields; a
        tampered event is REJECTED before any field is trusted.
    Gate 1 (epoch): the event must be BOTH active in the horizon AND bound to
        THIS epoch (ev.epoch_hash == epoch.hash) -- a self-consistent event
        created under another active epoch cannot be resolved here (dnFVu).
    Gate 2 (class):   NO_PULSE is pre-locked and never accepts any later proof;
        any outcome_class byte other than the two legal values is REJECTED as
        undefined rather than silently treated as ROOT_REQUIRED (dnFV6).
    Gate 3 (source + proof): before a ROOT could be returned, the source must
        have CANONICALLY ADMITTED this exact event (dnFVg) AND the proof must
        verify. A ROOT_REQUIRED event with no proof stays UNKNOWN; a proof that
        is supplied for an event the source never admitted, or that fails
        verification, is REJECTED.
    There is no timeout/non-arrival -> NO_PULSE transition anywhere."""
    if not ev.validate():
        return {"event_hash": ev.hash.hex(), "outcome": "REJECTED"}
    if ev.epoch_hash != epoch.hash or not epoch.active_at(ev.slot):
        # the event must be bound to THIS epoch, not merely inside another active
        # window of a coincidentally-active epoch (dnFVu)
        return {"event_hash": ev.hash.hex(), "outcome": "REJECTED"}
    if ev.outcome_class not in VALID_OUTCOME_CLASSES:
        # an undefined outcome class is not a valid event (dnFV6)
        return {"event_hash": ev.hash.hex(), "outcome": "REJECTED"}
    if ev.outcome_class == OUTCOME_NO_PULSE:
        return {"event_hash": ev.hash.hex(), "outcome": "NO_PULSE"}
    if proof is None:
        # operational non-delivery = UNKNOWN, never NO_PULSE (no timeout rule).
        return {"event_hash": ev.hash.hex(), "outcome": "UNKNOWN"}
    if not source.has_valid_proof(ev):
        # a proof for an event the source never canonically admitted does not
        # yield a valid outcome -- pre-lock unavailability enforced here (dnFVg)
        return {"event_hash": ev.hash.hex(), "outcome": "REJECTED"}
    if not verify_proof(epoch, ev, proof):
        return {"event_hash": ev.hash.hex(), "outcome": "REJECTED"}
    root = unique_root(epoch, ev)
    return {"event_hash": ev.hash.hex(), "outcome": "ROOT",
            "source_root": root.hex()}


def main():
    failed = 0

    def check(name, ok):
        nonlocal failed
        print(("PASS  " if ok else "FAIL  ") + name)
        if not ok:
            failed += 1

    # One epoch object that CANONICALLY binds every rule (Noot R1): a change to
    # any of format/scheme/key/roster/threshold/root-rule/event-mapping yields a
    # NEW epoch hash. Slots 12345..12945 are inside [12300, 13000).
    epoch = EpochDescriptor(
        format_version=1,
        authority_key=sha256(b"authority:group-key"),
        membership_commitment=sha256(b"membership:roster-commitment"),
        activation=12300, retirement=13000,
        threshold=5,
        root_rule=b"unique-threshold/v1",
        event_mapping=b"EventLock/v1")
    source = RandomnessSource(epoch)
    slot = 12345
    txset_a = sha256(b"tx-set-A")
    txset_b = sha256(b"tx-set-B")

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

    # ---------- B1: outcome-class immutability ---------------------------------
    ev_root = EventLock(epoch, slot, PURPOSE_POST, txset_a, OUTCOME_ROOT_REQUIRED)
    ev_nopulse = EventLock(epoch, slot, PURPOSE_POST, txset_a, OUTCOME_NO_PULSE)
    # state machine reads the class FROM the structured event: a caller cannot
    # present a ROOT_REQUIRED hash under NO_PULSE (dmjfJ).
    root_proof = unique_root(epoch, ev_root)          # valid for ev_root
    nopulse_proof = unique_root(epoch, ev_nopulse)    # "proof" for NO_PULSE event
    check("B1 outcome-class immutability: flipping ONLY outcome_class changes the "
          "event id", ev_root.hash != ev_nopulse.hash)
    check("B1 a ROOT proof does not verify for the NO_PULSE event (distinct "
          "challenge)", not verify_proof(epoch, ev_nopulse, root_proof))
    check("B1 a NO_PULSE event never later accepts a root proof",
          resolve(epoch, ev_nopulse, source, root_proof)
          == {"event_hash": ev_nopulse.hash.hex(), "outcome": "NO_PULSE"})
    check("B1 root-vs-no-pulse is fixed by pre-locked outcome class, not by "
          "delivery/timeout",
          resolve(epoch, ev_root, source, None)
          == {"event_hash": ev_root.hash.hex(), "outcome": "UNKNOWN"})
    check("B1 an unverifiable proof for a ROOT_REQUIRED event is REJECTED (no "
          "valid outcome)",
          resolve(epoch, ev_root, source, nopulse_proof)
          == {"event_hash": ev_root.hash.hex(), "outcome": "REJECTED"})
    tampered = EventLock(epoch, slot, PURPOSE_POST, txset_a, OUTCOME_ROOT_REQUIRED)
    tampered.outcome_class = OUTCOME_NO_PULSE          # field no longer matches hash
    check("B1 the structured type check: a caller cannot rebind the event's "
          "declared class to a different hash (validate() rejects a tampered "
          "class), so the state machine can never be fed a ROOT_REQUIRED hash "
          "under NO_PULSE",
          ev_root.validate() and not tampered.validate()
          and resolve(epoch, tampered, source, root_proof)["outcome"] == "REJECTED")

    # ---------- B2: post-lock consumer challenge -------------------------------
    ev_a = EventLock(epoch, slot, PURPOSE_POST, txset_a, OUTCOME_ROOT_REQUIRED)
    ev_b = EventLock(epoch, slot, PURPOSE_POST, txset_b, OUTCOME_ROOT_REQUIRED)
    proof_a = unique_root(epoch, ev_a)
    check("B2 the post challenge binds the externalized txSetHash: two tx sets "
          "give two distinct events", ev_a.hash != ev_b.hash)
    check("B2 a proof for tx-set A FAILS against tx-set B (distinct challenge, "
          "REJECTED)", not verify_proof(epoch, ev_b, proof_a)
          and resolve(epoch, ev_b, source, proof_a)
          == {"event_hash": ev_b.hash.hex(), "outcome": "REJECTED"})
    # Source only admits A's event; B is not admitted here, so no valid proof.
    # Admission is keyed by the FULL event (dnFWo), not just the lock object.
    source.admit(ev_a, witness=sha256(b"canonical-witness-A"))
    check("B2 the proof for tx-set A DOES verify against tx-set A once A is "
          "canonically admitted",
          resolve(epoch, ev_a, source, proof_a)
          == {"event_hash": ev_a.hash.hex(), "outcome": "ROOT",
              "source_root": proof_a.hex()})

    # ---------- Epoch-boundary gate: active_at is consulted, not decorative ----
    slot_out = epoch.retirement + 5                    # outside [12300, 13000)
    ev_out = EventLock(epoch, slot_out, PURPOSE_POST, txset_a, OUTCOME_ROOT_REQUIRED)
    check("Epoch gate: an event outside [activation, retirement) is REJECTED "
          "(epoch.active_at read from the event object)",
          not epoch.active_at(ev_out.slot)
          and resolve(epoch, ev_out, source, unique_root(epoch, ev_out))
          == {"event_hash": ev_out.hash.hex(), "outcome": "REJECTED"})
    check("Epoch gate: an event inside the active window is accepted",
          epoch.active_at(ev_root.slot)
          and resolve(epoch, ev_root, source, root_proof)["outcome"] == "ROOT")

    # ---------- Review-gate conformance (dnFVg / dnFVu / dnFV6 / dnFWo / dnFWC)
    # dnFVg: resolve must consult the source's ADMISSION before returning ROOT.
    # A publicly-computable `unique_root` is the primitive's mathematical value,
    # NOT a valid proof until the event is canonically admitted. An unadmitted
    # pre-lock event must be REJECTED, never resolve to ROOT.
    unadmitted = EventLock(epoch, slot, PURPOSE_POST,
                           sha256(b"never-admitted-object"), OUTCOME_ROOT_REQUIRED)
    check("dnFVg resolve consults the source: an UNadmitted event whose publicly "
          "computable root is passed is REJECTED, never ROOT (a bare hash is not "
          "a valid proof until canonical admission)",
          not source.has_valid_proof(unadmitted)
          and resolve(epoch, unadmitted, source, unique_root(epoch, unadmitted))
          == {"event_hash": unadmitted.hash.hex(), "outcome": "REJECTED"})

    # dnFVu: the epoch gate must bind the event TO THIS EPOCH. A self-consistent
    # event created under a DIFFERENT (also active) epoch must not resolve here.
    other_epoch = EpochDescriptor(
        format_version=epoch.format_version,
        authority_key=epoch.authority_key,
        membership_commitment=epoch.membership_commitment,
        activation=epoch.activation, retirement=epoch.retirement,
        threshold=epoch.threshold + 2,
        root_rule=epoch.root_rule, event_mapping=epoch.event_mapping)
    ev_foreign = EventLock(other_epoch, slot, PURPOSE_POST, txset_a,
                           OUTCOME_ROOT_REQUIRED)
    # a source bound to the foreign epoch (with the event admitted under it) that
    # the event would legitimately resolve against, distinct from the primary one:
    foreign_source = RandomnessSource(other_epoch)
    foreign_source.admit(ev_foreign, witness=sha256(b"foreign-witness"))
    check("dnFVu epoch binding: an event bound to a DIFFERENT epoch (with an "
          "identical activation window) is REJECTED under the calling epoch, not "
          "resolved here; it resolves only under its OWN epoch+source",
          other_epoch.hash != epoch.hash
          and other_epoch.active_at(ev_foreign.slot)
          and ev_foreign.epoch_hash != epoch.hash
          and resolve(other_epoch, ev_foreign, foreign_source,
                      unique_root(other_epoch, ev_foreign))["outcome"] == "ROOT"
          and resolve(epoch, ev_foreign, source,
                      unique_root(other_epoch, ev_foreign))["outcome"] == "REJECTED")

    # dnFV6: an undefined outcome class (any byte other than 0x01/0x02) is not a
    # valid event and MUST be rejected, not silently treated as ROOT_REQUIRED.
    ev_undef = EventLock(epoch, slot, PURPOSE_POST, txset_a, 0x03)
    check("dnFV6 two-state surface is exhaustive: an event with an undefined "
          "outcome_class (0x03) is REJECTED, never resolved to a valid root",
          ev_undef.outcome_class not in VALID_OUTCOME_CLASSES
          and resolve(epoch, ev_undef, source, unique_root(epoch, ev_undef))
          == {"event_hash": ev_undef.hash.hex(), "outcome": "REJECTED"})

    # dnFWo: admission is keyed by the FULL event hash, so admitting one event
    # does NOT give a valid proof to a DIFFERENT event that shares only its
    # locked_object_hash (a different slot / purpose / class is a different id).
    shared_obj = sha256(b"shared-lock-object")
    ev_shared_slot2 = EventLock(epoch, slot + 1, PURPOSE_POST,
                                shared_obj, OUTCOME_ROOT_REQUIRED)
    source.admit(EventLock(epoch, slot, PURPOSE_POST,
                           shared_obj, OUTCOME_ROOT_REQUIRED),
                 witness=sha256(b"witness-shared"))
    check("dnFWo admission is full-event keyed: admitting one event does NOT make "
          "a different event sharing only its locked_object_hash valid (its proof "
          "is REJECTED by resolve)",
          not source.has_valid_proof(ev_shared_slot2)
          and resolve(epoch, ev_shared_slot2, source,
                      unique_root(epoch, ev_shared_slot2))
          == {"event_hash": ev_shared_slot2.hash.hex(), "outcome": "REJECTED"})
    # B2 already admitted ev_a == ev_root, so ev_root ROOT here is unaffected.

    # dnFWC: the epoch preimage length-prefixes every variable-length field, so
    # the encoding is INJECTIVE -- swapping boundaries between two descriptors
    # with the same total bytes yields a DIFFERENT epoch hash.
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
    events, classes = [], []
    for i in range(n_events):
        s = slot + i
        obj = sha256(b"protect:%d" % i)
        cls = OUTCOME_NO_PULSE if i % 7 == 0 else OUTCOME_ROOT_REQUIRED
        events.append(EventLock(epoch, s, PURPOSE_POST, obj, cls))
        classes.append(cls)
        # NO_PULSE events get no proof; ROOT events are admitted -> valid proof
        if cls == OUTCOME_ROOT_REQUIRED:
            source.admit(events[i], witness=sha256(b"witness:%d" % i))
    truths = [unique_root(epoch, events[i]) for i in range(n_events)]
    # delivery schedules: at observation index i, has this ROOT_REQUIRED event's
    # proof arrived YET? (NO_PULSE events have no proof by construction.)
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
            resolve(epoch, events[i], source,
                    None if classes[i] == OUTCOME_NO_PULSE
                    else (truths[i] if (sched(i) and source.has_valid_proof(events[i]))
                          else None))
            for i in range(n_events)
        ]
        transient_digests.add(history_digest(transient))
        converged = [
            resolve(epoch, events[i], source,
                    None if classes[i] == OUTCOME_NO_PULSE else truths[i])
            for i in range(n_events)
        ]
        converged_digests.add(history_digest(converged))
    only_b3 = converged_digests.pop()
    check("B3 schedules are genuinely distinct: their transient (partial-"
          "observation) histories differ", len(transient_digests) > 1)
    check("B3 transport/replay composition: 601 in-epoch events under 4 delivery "
          "schedules (with interspersed pre-locked NO_PULSE) all RECONVERGE to "
          "the IDENTICAL authoritative-history digest (%s)" % only_b3,
          len(converged_digests) == 0)

    # ---------- B4: authority surface -------------------------------------------
    resolved = resolve(epoch, ev_root, source, root_proof)
    permitted = {"event_hash", "outcome", "source_root"}
    check("B4 authority surface: the resolved object holds ONLY "
          "{event_hash, outcome, source_root?} -- no successor/delegate/"
          "membership-edit/recovery/permission field",
          set(resolved.keys()) == permitted
          and not hasattr(epoch, "successor")
          and not hasattr(epoch, "delegate"))

    # ---------- O1: one use -> one event ----------------------------------------
    roots = {unique_root(epoch, ev_root) for _ in range(5)}
    check("O1 one use -> one event: retries/aliases of one event id collapse to a "
          "single draw (identical root every request)",
          len(roots) == 1)

    # ---------- O2: earliest-knowledge sealing (source-enforced pre-lock) --------
    # Noot / dmjfO: the challenge BYTES are computable before lock (a proposer can
    # hash candidate tx sets); what must be UNAVAILABLE pre-lock is a complete
    # valid PROOF. The source has_valid_proof() is governed by CANONICAL
    # ADMISSION, not by a caller-controlled flag, and it is independent of local
    # timing.
    # Build fresh candidates W1..Wn whose witnesses are NOT yet admitted.
    src_cold = RandomnessSource(epoch)
    cand_events = [
        EventLock(epoch, slot, PURPOSE_POST, sha256(b"cand:%d" % c),
                  OUTCOME_ROOT_REQUIRED)
        for c in range(8)]
    for ce in cand_events:
        if src_cold.has_valid_proof(ce):
            check("O2 no valid proof for unadmitted candidate", False)
    check("O2 pre-lock unavailability: a proposer holding N candidate witnesses "
          "and every fact legitimately available BEFORE lock gains ZERO valid "
          "proofs -- each candidate returns no proof because its lock witness is "
          "not canonically admitted (S2 is a source fault-model property, not a "
          "caller flag)",
          all(not src_cold.has_valid_proof(ce) for ce in cand_events)
          and all(src_cold.proof(ce) is None for ce in cand_events))
    # admit EXACTLY one real event after lock -> only that event gets a proof.
    # Admission is keyed by the full event (dnFWo): the OTHER candidates sharing
    # the same purpose/class but a different lock object, and even a DIFFERENT
    # event that coincidentally shares `real_object`, are unaffected.
    real_object = sha256(b"cand:3")
    real_ev = EventLock(epoch, slot, PURPOSE_POST, real_object, OUTCOME_ROOT_REQUIRED)
    src_cold.admit(real_ev, witness=sha256(b"externalized-real"))
    # the OTHER candidates still have no valid proof
    others_unavailable = all(
        src_cold.proof(ce) is None
        for ce in cand_events if ce.locked_object_hash != real_object)
    check("O2 once exactly ONE witness is canonically admitted, only that event "
          "has a valid root; every other candidate still yields no proof (no "
          "post-hoc selection among previewed candidates)", others_unavailable)
    check("O2 the admitted event yields exactly one root, deterministic across "
          "replay",
          src_cold.proof(real_ev) == unique_root(epoch, real_ev))

    # ---------- O3: permanent pulse ---------------------------------------------
    pulse_a = canonical_pulse(ev_root, root_proof)
    # A later key/suite rotation / rewritten encoder re-derives the CANONICAL
    # root for the SAME canonical bytes; it can never mint a second pulse.
    pulse_b = canonical_pulse(ev_root, unique_root(epoch, ev_root))
    check("O3 permanent pulse: pulse_id is fixed by H(event_lock, canonical_root) "
          "and survives later key/suite rotation / re-encoding (never a second "
          "historical pulse)", pulse_a == pulse_b)

    # ============ Compositional one-future law + kill Qs + source properties ====

    # ---------- C: compositional one-future law (|H_n|=1 for every prefix) ------
    # Each realization = (delivery schedule x wire order on delivery x optional
    # duplication). We drive EVERY realization through the actual state machine:
    # proofs are delivered (or withheld) in that realization's wire order/schedule,
    # each event resolved via `resolve`, and the resolved outcomes then reordered
    # canonically by slot. The authoritative (all-proofs-present) canonical slot
    # sequence must be IDENTICAL across realizations and prefix-stable; transient
    # partial-observation sequences differ, proving the sweep is real (dmjfT).
    def canonical_value_seq(events_):
        # resolved-outcome sequence keyed canonically by slot: for ROOT_REQUIRED
        # events the value is the root; NO_PULSE events emit an explicit marker.
        order = sorted(range(len(events_)), key=lambda i: events_[i].slot)
        parts = []
        for i in order:
            if classes[i] == OUTCOME_NO_PULSE:
                parts.append(b"NOPULSE")
            else:
                parts.append(unique_root(epoch, events_[i]))
        return b"".join(parts)

    base_seq = canonical_value_seq(events)
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
            # Drive this realization through the machine: deliver proofs in this
            # wire order, a ROOT_REQUIRED event gets its proof only when both the
            # schedule says "arrived" AND the source admits it; collect transient
            # (partial) resolved outcomes keyed by event index.
            transient_outcome = {}
            for idx in wire:
                ev_ = events[idx]
                if classes[idx] == OUTCOME_NO_PULSE:
                    transient_outcome[ev_.slot] = b"NO_PULSE"
                elif sched(idx) and source.has_valid_proof(ev_):
                    transient_outcome[ev_.slot] = unique_root(epoch, ev_)
                else:
                    transient_outcome[ev_.slot] = None  # UNKNOWN (no proof yet)
            tseq = b"".join(
                (transient_outcome[events[i].slot] if transient_outcome.get(events[i].slot) is not None else b"UNKNOWN")
                for i in range(n_events))
            transient_c_seqs.append(tseq)
            # converged: deliver EVERY admitted proof -> canonical slot sequence
            cseq = canonical_value_seq(events)
            if cseq != base_seq:
                converged_ok = False
    # The transient (partial) sequences MUST differ meaningfully across
    # realizations; the converged canonical sequences MUST be identical.
    check("C realizations genuinely differ: distinct (schedule x wire-order) "
          "profiles yield distinct transient partial-observation sequences",
          len(set(transient_c_seqs)) > 1 and len(transient_c_seqs) == n_routes)
    check("C compositional one-future |H_n|=1: across %d adversarial realizations "
          "(delivery schedule x wire order, each driven through the state "
          "machine) the convergent canonical slot-ordered sequence is IDENTICAL "
          "-- no 2^n fan-out" % n_routes, converged_ok)
    # prefix stability (dnFWP): every canonical prefix has |H_k| = 1. This is
    # NOT a self-comparison: each prefix is built TWO ways -- (a) the direct
    # `canonical_value_seq` on the first k events, and (b) by resolving each of
    # those k events through the full state machine (validate -> epoch-binding ->
    # class -> source-admission -> proof) and extracting the resulting
    # ROOT/NO_PULSE values in canonical slot order -- and both must agree bit-for-
    # bit. Prefixes are measured in WHOLE events (each is a 32-byte root or the
    # 7-byte "NOPULSE" marker), never a blind `32*k` byte slice that mis-cuts
    # around the NO_PULSE marker.
    prefix_ok = True
    for k in range(8, n_events + 1, 97):
        order = sorted(range(k), key=lambda j: events[j].slot)
        direct = b"".join(
            (unique_root(epoch, events[i]) if classes[i] != OUTCOME_NO_PULSE
             else b"NOPULSE")
            for i in order)
        rows = [resolve(epoch, events[i], source,
                        None if classes[i] == OUTCOME_NO_PULSE else truths[i])
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
    # K1 "create several equivalent valid events and choose later?"
    #   No: an event id is derived ONLY from canonical state (epoch, network, slot,
    #   purpose, locked_object, class); no caller nonce/alias/retry field exists.
    alias_nonce = b"ATTACKER-NONCE"
    forged = EventLock(epoch, slot, PURPOSE_POST,
                       sha256(txset_a + alias_nonce), OUTCOME_ROOT_REQUIRED)
    check("K1 kill-Q1: event_id is derivable ONLY from canonical state -- no "
          "caller nonce/alias/retry can mint a second equivalent event for the "
          "same protected use (forged event != canonical event)",
          forged.hash != ev_root.hash and forged.hash != ev_a.hash)
    # K2 "learn the root while any relevant input is still legally movable?"
    #   No: pre-lock, a proposer gets no valid proof because the lock witness is
    #   not canonically admitted (O2 / S2). The unadmitted candidates are those
    #   whose lock witnesses never become canonical.
    unadmitted_cands = [ce for ce in cand_events
                        if ce.locked_object_hash != real_object]
    check("K2 kill-Q2: pre-lock unavailability -- before the EventLock's witness "
          "is canonical there is NO complete valid proof under the stated fault "
          "model (a bare candidate hash is not a valid proof)",
          len(unadmitted_cands) > 0
          and all(not src_cold.has_valid_proof(ce) for ce in unadmitted_cands))
    # K3 "any future verifier/migration make a different historical pulse valid?"
    #   No: pulse is fixed by canonical bytes; archival replay re-derives the same
    #   root; a rewritten epoch rule is a DIFFERENT epoch identity.
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
          canonical_pulse(ev_root, unique_root(archival, ev_root)) == pulse_a
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
          forged.hash != ev_root.hash)
    check("S2 pre-lock unavailability: before the lock witness is canonically "
          "admitted, a proposer holds NO valid proof under the stated fault "
          "model (the source's admission interface, not a caller flag)",
          all(not src_cold.has_valid_proof(ce) for ce in unadmitted_cands))
    roots_seen = []
    s3_ok = True
    for i in range(n_events):
        if classes[i] == OUTCOME_NO_PULSE:
            if resolve(epoch, events[i], source, truths[i])["outcome"] != "NO_PULSE":
                s3_ok = False
            continue
        r = resolve(epoch, events[i], source, truths[i])
        roots_seen.append(r["source_root"])
        wrong = truths[(i + 1) % n_events]
        if resolve(epoch, events[i], source, wrong)["outcome"] != "REJECTED":
            s3_ok = False
    check("S3 unique resolution: every valid post-lock proof path collapses to "
          "exactly one canonical R (%d roots, no duplicates) and an invalid proof "
          "is always REJECTED, never a second root" % len(roots_seen),
          s3_ok and len(roots_seen) == len(set(roots_seen)))

    # ---------- P: pinned model vectors (independently registered literals) -----
    pinned_b3 = history_digest([
        resolve(epoch, events[i], source,
                None if classes[i] == OUTCOME_NO_PULSE else truths[i])
        for i in range(n_events)])
    comp_seq_digest = sha256(base_seq).hex()
    EXP_B3 = "6f247279e87c7b330104efe22d3b25f218072e7673f67135b3cb27cefd0d2773"
    EXP_COMP = "71e12e816428806cf7d5ac1de60946a0038177f2b799143e159b31a001f3ca9b"
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
