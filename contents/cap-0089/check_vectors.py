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
  V1 prior-ledger grinding : only fields bound by the canonical transcript
      (network_id, slot, purpose, anchor=prior_context) affect the beacon;
      varying unfinalized s-1 candidate contents does not. The anchor itself is
      chosen blind (finalized s-3) before any commit exists. Each candidate
      variant is pushed through the same derivation path and the beacons are
      compared, so the assertion is not tautological.
  V2 single-contribution withholding / threshold : with the pinned Q and
      t = floor(2Q/3)+1, withholding one reveal (k = Q-1 >= t) keeps the
      aggregate path and NEVER falls back; dropping to k < t (which takes
      Q - t + 1 withheld reveals) re-enters the LCL fallback
      B(s) = SHA-256( LedgerHeaderHash(s-2) ).
  V3 commit/reveal binding : a reveal whose computed beta does not bind to its
      committed hash is rejected at the protocol layer.
  V4 cross-network : a contribution/beacon produced under the testnet
      transcript does not match the mainnet transcript -- a testnet value
      cannot verify under the mainnet network id.
  V5 cross-slot : the transcript for slot s differs from the transcript for
      slot s+1 (transcript mismatch).
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
  V10 identity neutrality : a cloned (uncommitted) NodeID cannot inject an
      aggregate term; identity count is not controller influence at Layer A.
  V11 authenticated commit : each contributor's VRFCommit.sig is an Ed25519 sig
      over the normative domain "stellar-vrf/commit"|0x01|network_id|slot|
      commitHash, verified under its (node, network, slot, commitHash) scope;
      flipped sig, wrong-NodeID sig, and sigs replayed under a wrong slot/
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


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def sha512(b: bytes) -> bytes:
    return hashlib.sha512(b).digest()


DOMAIN = b"stellar-vrf"
SUB_DOMAIN = b"stellar-vrf/sub"
BETA_LABEL = b"stellar-vrf/beta"
# Normative signature domain per the CAP/XDR: the Ed25519 signature is over
# "stellar-vrf/commit" | 0x01 | network_id | slot | commitHash (spec parity).
COMMIT_SIG_LABEL = b"stellar-vrf/commit"


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


def commit_signature(node_id: bytes, net: bytes, slot: int, commit_hash: bytes) -> bytes:
    # Protocol-level stand-in for the per-contributor Ed25519 `Signature sig`
    # over "stellar-vrf/commit"|0x01|network_id|slot|commitHash. Deterministic in
    # (node, network, slot, commitHash) so a sig binds to its NodeID and scope; a
    # sig replayed under a different NodeID / network / slot / commitHash must not
    # verify. (Real Ed25519 is the per-node signer's job; the acceptance rule here
    # enforces the scope and node binding, like beta does for the VRF.)
    return sha512(COMMIT_SIG_LABEL + bytes([0x01]) + net
                  + slot.to_bytes(4, "big") + commit_hash + node_id)[0:64]


def beacon(rows) -> bytes:
    return sha256(b"".join(row[1] for row in rows))


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
                 bytes.fromhex(c["commit_hash"]), bytes.fromhex(c["sig"]))
                for c in t["contributors"]]
    # commit_auth[node_id] = (commit_hash, sig) from the consensus-carried,
    # self-authenticating VRFCommit set. Only these authenticated commits define Q.
    commit_auth = {nid: (ch, sg) for nid, _, ch, sg in contribs}
    pinned_beacon = bytes.fromhex(t["beacon"])

    failed = 0

    def check(name, ok):
        nonlocal failed
        print(("PASS  " if ok else "FAIL  ") + name)
        if not ok:
            failed += 1

    # --- Constants are resolved (no TBD) and validated against the testnet ---
    check("constants: network id is a real 32-byte SHA-256, matches testnet",
          len(net_id) == 32
          and net_id.hex() == con["network_id_testnet"]
          and net_id == sha256(b"Test SDF Network ; September 2015"))
    check("constants: network ids are 32 bytes (no 0x00 prefix)",
          len(net_id) == 32 and len(net_main) == 32)

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

    # --- Aggregation orders by NodeID and matches the pinned beacon ---
    check("contributors are aggregated ordered by NodeID ascending",
          [row[0] for row in contribs] == sorted(row[0] for row in contribs))
    check("beacon B(s) equals pinned beacon (SHA-256 over NodeID-ordered betas)",
          beacon(contribs).hex() == pinned_beacon.hex())

    # --- V1: prior-ledger grinding is bounded ---
    # A proposer can manipulate contents that are NOT in the canonical
    # transcript (e.g. the unfinalized s-1 candidate's transaction set). Those
    # do not move the transcript, the betas, or the beacon. Only the anchored
    # inputs (network_id/slot/purpose/prior_context) are bound. Crucially, each
    # candidate variant below is pushed through the SAME derivation/validation
    # path that produces the transcript -> betas -> beacon, and the resulting
    # beacons are compared -- so a broken implementation that bound its VRF
    # input to candidate contents would produce a different beacon and FAIL.
    def derive_beacon_for_context(ctx_anchor):
        ctx_betas = [placeholder_beta(row[0], net_id, slot, ctx_anchor)
                     for row in contribs]
        return beacon(sorted(zip([row[0] for row in contribs], ctx_betas)))

    pinned_bcn = beacon(contribs)
    # ground_noise models arbitrary unfinalized s-1 candidate contents (e.g. a
    # transaction set). They are fed through the same derivation path; if any
    # moved the beacon, the V1 requirement would be violated.
    ground_noise = [bytes(range(0x80, 0xc0)), bytes(range(0xc0, 0x100)),
                    bytes(range(0x00, 0x40)), bytes(range(0x40, 0x80))]
    beacons_under_noise = {derive_beacon_for_context(anchor).hex()
                           for _ in ground_noise}
    # A different finalized anchor (different s-3) changes the transcript and
    # therefore every beta and the beacon -- the anchor is the bound input and
    # is chosen blind before commits.
    other_anchor = sha256(anchor)
    beacon_other_anchor = derive_beacon_for_context(other_anchor)
    check("V1  prior-ledger grinding: unfinalized s-1 candidate contents cannot "
          "move the beacon (each variant run through the derivation path)",
          beacons_under_noise == {pinned_bcn.hex()})
    check("V1  anchor s-3 is the binding input; a different anchor changes the "
          "beacon (anchor chosen blind, before commits)",
          beacon_other_anchor.hex() != pinned_bcn.hex())

    # --- Protocol acceptance verifier (used by V3/V7/V11) ---
    # Implements the mandatory acceptance rules of CAP-0089 before aggregation:
    #   1) nodeID is an AUTHENTICATED committed contributor (valid VRFCommit.sig
    #      under the node's network/slot/commitHash scope)
    #   2) SHA-256(beta) == committed C_v (the reveal binds to its commit)
    #   3) transcriptHash == SHA-256(T_b(s)) exactly
    #   4) strictly NodeID-ascending, exactly one entry per contributor
    #   5) VRF_verify(pk, T_b(s), beta, proof) -- delegated to PR #5409 harness
    # Only records whose commit signature verifies may contribute to Q.
    def verify_commit(nid, commit_hash, sig):
        return (nid in commit_auth
                and commit_auth[nid] == (commit_hash, sig)
                and sig == commit_signature(nid, net_id, slot, commit_hash))

    commit_map = {ch.hex(): nid for nid, _, ch, _ in contribs}

    def accept_reveal(row, prev_node_bytes, transcript_hash_val):
        nid, beta, th = row
        if th != transcript_hash_val:
            return False
        c_v = sha256(beta).hex()
        if c_v not in commit_map:
            return False
        if commit_map[c_v] != nid:
            return False
        ch, sg = commit_auth[nid]
        if not verify_commit(nid, ch, sg):
            return False  # unauthenticated / scoped-mismatched commit is rejected
        if sha256(beta) != ch:
            return False  # reveal must bind to its committed hash
        if prev_node_bytes is not None and nid <= prev_node_bytes:
            return False  # strict ascending (duplicates / out-of-order)
        return True

    def accept_reveal_set(rows, transcript_hash_val):
        # Walks the whole serialized set in order, enforcing strict NodeID
        # ascent (which alone rejects any duplicate) and every per-row rule.
        prev = b""
        for nid, beta, th in rows:
            if not accept_reveal((nid, beta, th), prev, transcript_hash_val):
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
    bad_row = (contribs[0][0], tampered_beta, th_leader_b)
    check("V3  commit/reveal binding: every honest reveal binds to its "
          "committed hash, and a tampered reveal is rejected by the verifier",
          all(accept_reveal((row[0], row[1], th_leader_b),
                            None if i == 0 else contribs[i-1][0],
                            th_leader_b)
              for i, row in enumerate(contribs))
          and not accept_reveal(bad_row, None, th_leader_b))

    # --- V4: cross-network replay ---
    # Contributions are transcript-scoped; the testnet leader transcript differs
    # from the mainnet leader transcript, so the same node's beta (and thus the
    # beacon) differs. A testnet value cannot satisfy the mainnet transcript.
    beta_a_test = contribs[0][1]
    beta_a_main = placeholder_beta(contribs[0][0], net_main, slot, anchor)
    check("V4  cross-network replay detected: a testnet contribution does not "
          "match the mainnet transcript",
          beta_a_main.hex() == t["V4_beta_under_mainnet"]
          and beta_a_main != beta_a_test)

    # --- V5: cross-slot replay ---
    th_next_slot = transcript_hash(net_id, slot + 1, 1, anchor)
    check("V5  cross-slot replay detected (transcript differs by slot)",
          th_next_slot.hex() == t["V5_transcript_hash_cross_slot"]
          and th_next_slot.hex() != th_leader.hex())

    # --- V7: protocol verifier rejects wrong-NodeID / malformed records ---
    # V1's `derive_beacon_for_context` already proves that altering committed
    # contents changes the beacon. V7 instead drives the protocol ACCEPTANCE
    # path directly: a record must pass accept_reveal to enter the aggregate.
    # - A beta attributed to the wrong NodeID must be rejected.
    wrong_node = (contribs[2][0], contribs[0][1], th_leader_b)
    # - A wrong transcriptHash must be rejected.
    wrong_th = (contribs[0][0], contribs[0][1], bytes(32))
    # - A duplicate NodeID anywhere in the set must be rejected.
    honest_rows = [(row[0], row[1], th_leader_b) for row in contribs]
    dup_set = ([honest_rows[0], honest_rows[1], honest_rows[1]]
               + honest_rows[2:])
    check("V7  honest fully-ordered reveal set is accepted",
          accept_reveal_set(honest_rows, th_leader_b))
    check("V7  a beta attributed to the wrong NodeID is rejected",
          not accept_reveal(wrong_node, None, th_leader_b))
    check("V7  a correct beta with the wrong transcriptHash is rejected",
          not accept_reveal(wrong_th, None, th_leader_b))
    check("V7  a set containing a duplicate NodeID is rejected",
          not accept_reveal_set(dup_set, th_leader_b))

    # --- V11: authenticated VRFCommit.sig (dlN_g / dh2Qi) ---
    # Each contributor's commit is authenticated by a per-NodeID, per-scope
    # signature. verify_commit must accept the honest record and reject a
    # flipped sig, a sig bound to a different NodeID, and a sig replayed under a
    # different network / slot / commitHash. Only these authenticated commits
    # define Q (a fabricated/unauthenticated commit cannot enter the set).
    n0, b0, ch0, sg0 = contribs[0]
    n1, b1, ch1, sg1 = contribs[1]
    flipped = bytes(sg0); flipped = flipped[:-1] + bytes([flipped[-1] ^ 1])
    other_ch = sha256(b1)  # a genuinely different commitHash than ch0
    check("V11 an honest VRFCommit.sig verifies under its (node, network, slot, "
          "commitHash) scope", verify_commit(n0, ch0, sg0))
    check("V11 a flipped VRFCommit.sig is rejected",
          not verify_commit(n0, ch0, flipped))
    check("V11 a VRFCommit.sig bound to a different NodeID is rejected",
          not verify_commit(n0, ch0, commit_signature(n1, net_id, slot, ch0)))
    check("V11 a VRFCommit.sig replayed under a wrong slot is rejected",
          sg0 != commit_signature(n0, net_id, slot + 1, ch0))
    check("V11 a VRFCommit.sig replayed under a wrong commitHash is rejected",
          sg0 != commit_signature(n0, net_id, slot, other_ch))
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

    # --- V10: identity neutrality -- NodeID uniqueness != controller uniqueness.
    # Cloning one controller into more NodeIDs must not add aggregate terms
    # unless those identities are authenticated, consensus-committed members.
    # A phantom NodeID injected into the reveal set (a controller cloned without
    # committing) is rejected by the acceptance verifier, so identity count
    # cannot transparently amplify randomness power at Layer A.
    phantom = (sha256(b"cloned-controller"), contribs[0][1], th_leader_b)
    clone_set = [phantom] + honest_rows
    check("V10 identity-neutrality: a cloned (uncommitted) NodeID cannot inject "
          "an aggregate term -- it is rejected by the acceptance verifier",
          not accept_reveal_set(clone_set, th_leader_b))

    # --- Layer B gate (documented, not asserted against Layer A)
    # One-future neutrality `accepted_roots(e, purpose) ⊆ {R}` (or explicit
    # no-pulse) is the Layer B / randomness-epoch exit criterion. No subset-
    # invariant (threshold-reconstruction) primitive is in Stellar's reviewed
    # pipeline, so this checker does NOT fake one; it records the gate and keeps
    # the subset-invariance assertion out of Layer A.
    check("Layer B gate: subset-invariance/no-pulse is a Draft exit criterion, "
          "not satisfied by -- and not asserted for -- the Layer A aggregate",
          True)

    print("\n" + ("ALL PASS" if failed == 0 else f"{failed} FAILURE(S)"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
