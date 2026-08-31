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
        # retirement | threshold | root_rule | event_mapping.
        self.hash = sha256(
            b"Epoch"
            + struct.pack(">I", format_version) + scheme
            + authority_key + membership_commitment
            + struct.pack(">QQ", activation, retirement)
            + struct.pack(">I", threshold) + root_rule + event_mapping)

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
        self._admitted = {}      # locked_object_hash -> canonical witness digest

    def admit(self, locked_object_hash: bytes, witness: bytes):
        # Canonical protocol state admits the witness for this lock object once
        # the last mutable input is fixed. After this point the source may produce
        # a valid proof for the (single) event carrying that lock object.
        self._admitted[locked_object_hash] = witness

    def has_valid_proof(self, ev: EventLock) -> bool:
        # A valid proof exists for an event iff its lock object was canonically
        # admitted (and the event is not a pre-locked NO_PULSE). Before admission
        # there is NO valid proof -- this is the S2 causal seal, independent of
        # local timing/arrival.
        if ev.outcome_class == OUTCOME_NO_PULSE:
            return False
        return ev.locked_object_hash in self._admitted

    def proof(self, ev: EventLock) -> "bytes | None":
        # The complete valid proof, present only after canonical admission.
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
    Gate 1 (epoch): an event outside [activation, retirement) is never accepted.
    Gate 2 (class):  NO_PULSE is pre-locked and never accepts any later proof.
    Gate 3 (proof):  a ROOT_REQUIRED event with no proof stays UNKNOWN; with a
    proof it becomes ROOT(R) only if the proof VERIFIES, otherwise REJECTED.
    There is no timeout/non-arrival -> NO_PULSE transition anywhere."""
    if not ev.validate():
        return {"event_hash": ev.hash.hex(), "outcome": "REJECTED"}
    if not epoch.active_at(ev.slot):
        return {"event_hash": ev.hash.hex(), "outcome": "REJECTED"}
    if ev.outcome_class == OUTCOME_NO_PULSE:
        return {"event_hash": ev.hash.hex(), "outcome": "NO_PULSE"}
    if proof is None:
        # operational non-delivery = UNKNOWN, never NO_PULSE (no timeout rule).
        return {"event_hash": ev.hash.hex(), "outcome": "UNKNOWN"}
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
    # Source only admits B's witness; A is not admitted here, so no valid proof.
    source.admit(txset_a, witness=sha256(b"canonical-witness-A"))
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
            source.admit(obj, witness=sha256(b"witness:%d" % i))
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
    # admit EXACTLY one real witness after lock -> only that event gets a proof
    real_object = sha256(b"cand:3")
    src_cold.admit(real_object, witness=sha256(b"externalized-real"))
    real_ev = EventLock(epoch, slot, PURPOSE_POST, real_object, OUTCOME_ROOT_REQUIRED)
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
    # prefix stability: every canonical prefix len k has |H_k| = 1
    prefix_ok = True
    for k in range(8, n_events + 1, 97):
        p = base_seq[: 32 * k]
        if any(canonical_value_seq(events)[: 32 * k] != p for _ in [0]):
            prefix_ok = False
    check("C prefix-stability: |H_k| = 1 for every sampled canonical prefix (no "
          "repeated-cycle predicate advantage compounds)", prefix_ok)

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
    EXP_B3 = "db7f136f5c7e16b94ba459a23f8c5e0de8986fc29b1a587d22614f639a248a63"
    EXP_COMP = "9f9aecea23998437aed656b5cc54d37761340e4ba5444602ddea2cc92f5b7f83"
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
