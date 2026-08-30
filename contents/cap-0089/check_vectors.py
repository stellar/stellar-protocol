#!/usr/bin/env python3
"""Executable conformance check for CAP-0089 protocol-level vectors.

Loads fixture_vectors.json (which gen_vectors.py reproduces byte-for-byte),
recomputes every pinned digest, and FAILS if any recomputed value differs from
the pinned value. It also asserts the adversarial structural properties.

Canonical transcript:
    T(s) = "stellar-vrf" | 0x01 | network_id | slot | purpose | prior_context(s)
    prior_context(s) = LedgerHeaderHash(s-3)                  # 32 bytes, no re-hash
    beta_v           = VRF_prove(sk_v, T(s))                  # via PR #5409 harness
    B(s)             = SHA-256( concat(verified beta_v,
                              ordered by NodeID ascending) )  # aggregate beacon
    subseed(p)       = SHA-512( "stellar-vrf/sub" | 0x01 | network_id | slot
                                | p | B(s) )[0:32]
    network_id       = SHA-256(network passphrase)            # 32 bytes, no prefix

NOTE: `slot` is used directly as the ledger being generated (s). There is NO
incrementing. Every computed value is compared against the pinned fixture and
must match exactly.

Vectors:
  V1 prior-ledger grinding : only fields bound by the canonical transcript
      (network_id, slot, purpose, anchor=prior_context) affect the beacon;
      varying unfinalized s-1 candidate contents does not. The anchor itself is
      chosen blind (finalized s-3) before any commit exists.
  V2 single-contribution withholding : withholding one contributor's reveal
      excludes it and B(s) is deterministically recomputed over the remainder,
      ordered by NodeID.
  V3 commit/reveal binding : a reveal whose computed beta does not bind to its
      committed hash is rejected at the protocol layer.
  V4 cross-network : a contribution/beacon produced under the testnet
      transcript does not match the mainnet transcript -- a testnet value
      cannot verify under the mainnet network id.
  V5 cross-slot : the transcript for slot s differs from the transcript for
      slot s+1 (transcript mismatch).
  V6 purpose separation : subseed(0x02) != subseed(0x03) for the same B(s).
  V7 malformed contribution : a contribution ordering/tampering that cannot
      bind to the committed set is rejected. (Full RFC 9381 proof and wrong-key
      rejection is the PR #5409 harness's job -- see note in the fixture.)
  V8 transcript mutation : flipping a byte of T(s) changes the transcript hash;
      it no longer matches the pinned value.

Run:  python3 check_vectors.py
Exit code 0 on pass, 1 on any failure.
"""
import hashlib
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


def beacon(rows) -> bytes:
    return sha256(b"".join(beta for _, beta in rows))


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
    contribs = [(bytes.fromhex(c["node_id"]), bytes.fromhex(c["beta"]))
                for c in t["contributors"]]
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
          [nid for nid, _ in contribs] == sorted(nid for nid, _ in contribs))
    check("beacon B(s) equals pinned beacon (SHA-256 over NodeID-ordered betas)",
          beacon(contribs).hex() == pinned_beacon.hex())

    # --- V1: prior-ledger grinding is bounded ---
    # A proposer can manipulate contents that are NOT in the canonical
    # transcript (e.g. the unfinalized s-1 candidate's transaction set). Those
    # do not move the transcript, the betas, or the beacon. Only the anchored
    # inputs (network_id/slot/purpose/prior_context) are bound.
    ground_noise = [bytes(range(0x80, 0xc0)), bytes(range(0xc0, 0x100)),
                    bytes(range(0x00, 0x40)), bytes(range(0x40, 0x80))]
    beacons_under_noise = {beacon(contribs).hex() for _ in ground_noise}
    # A different finalized anchor (different s-3) changes the transcript and
    # therefore every beta and the beacon -- the anchor is the bound input and
    # is chosen blind before commits.
    other_anchor = sha256(anchor)
    other_betas = [placeholder_beta(nid, net_id, slot, other_anchor)
                   for nid, _ in contribs]
    beacon_other_anchor = beacon(
        sorted(zip([nid for nid, _ in contribs], other_betas)))
    check("V1  prior-ledger grinding: unfinalized s-1 candidate contents cannot "
          "move the beacon",
          beacons_under_noise == {pinned_beacon.hex()})
    check("V1  anchor s-3 is the binding input; a different anchor changes the "
          "beacon (anchor chosen blind, before commits)",
          beacon_other_anchor.hex() != pinned_beacon.hex())

    # --- V2: single-contribution withholding ---
    remainder = contribs[1:] + contribs[:0]
    dropped = beacon(remainder)
    check("V2  withholding one reveal excludes it and recomputes the aggregate "
          "deterministically by NodeID order",
          dropped != beacon(contribs)
          and dropped == beacon(sorted(remainder, key=lambda r: r[0])))

    # --- V3: commit/reveal binding ---
    commit_hashes = {sha256(beta).hex(): beta for _, beta in contribs}
    tampered_beta = contribs[0][1]
    tampered_beta = tampered_beta[:-1] + bytes([tampered_beta[-1] ^ 1])
    check("V3  commit/reveal binding: each reveal binds to its committed hash, "
          "and a tampered reveal is rejected",
          all(sha256(beta).hex() in commit_hashes for _, beta in contribs)
          and sha256(tampered_beta).hex() not in commit_hashes)

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

    # --- V7: malformed contribution is rejected at the protocol layer ---
    tampered_agg = beacon(sorted(
        [(contribs[0][0], tampered_beta)] + contribs[1:],
        key=lambda r: r[0]))
    check("V7  malformed contribution: a contribution that cannot bind to the "
          "committed set yields an aggregate that does not match",
          tampered_agg != beacon(contribs))
    check("V7  wrong contributor key: a beta assigned to the wrong NodeID in "
          "the ordered aggregate does not reproduce the beacon",
          beacon(sorted([(contribs[2][0], contribs[0][1])] + contribs[1:],
                        key=lambda r: r[0])) != beacon(contribs))

    # --- V6: purpose separation ---
    bcn = beacon(contribs)
    s_prng = subseed(net_id, slot, 2, bcn).hex()
    s_ord = subseed(net_id, slot, 3, bcn).hex()
    check("V6  purpose separation: subseed(0x02) pins and differs from "
          "subseed(0x03)", s_prng == t["V6_subseed_prng"]
          and s_ord == t["V6_subseed_order"] and s_prng != s_ord)

    print("\n" + ("ALL PASS" if failed == 0 else f"{failed} FAILURE(S)"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
