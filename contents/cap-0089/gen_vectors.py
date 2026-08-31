#!/usr/bin/env python3
"""Regenerate fixture_vectors.json for CAP-0089.

This script is the single source of truth for the pinned protocol-level
digests. Run:

    python3 gen_vectors.py > fixture_vectors.json

It must reproduce the checked-in fixture_vectors.json byte-for-byte (LF line
endings), so a reviewer can regenerate and verify the pinned data. Any change
to the CAP's transcript, hashing, ordering, or network-ID encoding that alters
these digests must be reflected here AND in the checked-in fixture.

The placeholder `beta` here models the *protocol-relevant property* of the real
`beta_v = VRF_prove(sk_v, T_v(s))` (RFC 9381): determinism in the key and the
transcript `alpha`, and pseudorandomness/dependence on the transcript. The
real ECVRF outputs and proofs are exercised by the PR #5409 harness; this
fixture pins the protocol-level derivations (transcript, aggregation order,
beacon, sub-seeds) so V1/V2/V4/V5/V6/V8 are executable without the crypto.
"""
import hashlib
import itertools
import json
import sys


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def sha512(b: bytes) -> bytes:
    return hashlib.sha512(b).digest()


# The existing Stellar network id: Application::getNetworkID() ==
# SHA-256(network passphrase), exactly 32 bytes, with NO prefix.
NETWORK_ID_TESTNET = sha256(b"Test SDF Network ; September 2015")
NETWORK_ID_MAINNET = sha256(b"Public Global Stellar Network ; September 2015")

DOMAIN = b"stellar-vrf"
SUB_DOMAIN = b"stellar-vrf/sub"
BETA_LABEL = b"stellar-vrf/beta"
# Normative signature domain per the CAP/XDR: the Ed25519 signature is over
# "stellar-vrf/commit" | 0x01 | network_id | slot | commitHash (spec parity).
COMMIT_SIG_LABEL = b"stellar-vrf/commit"
VER = 0x01
SLOT = 123456789
# Canonical anchor: the existing 32-byte LedgerHeader hash of ledger (s-3).
# prior_context(s) IS this hash; it is NOT re-hashed (avoids a double hash).
ANCHOR = bytes(range(32))
# The LCL fallback (Layer A) is defined from a DISTINCT
# LedgerHeaderHash(s-2), never from the s-3 prior_context(s). Noot's catch:
# reusing ANCHOR (s-3) as the fallback input made V2 pin the wrong source.
FALLBACK_ANCHOR = sha256(ANCHOR)

# Deterministic contributor set (validator public keys / NodeIDs). The
# aggregation order is by NodeID (lexicographic, ascending), per the CAP.
# Six contributors give Q=6, so t = floor(2*6/3)+1 = 5: a single withheld reveal
# (k=5) still meets the beacon threshold and does NOT force the LCL fallback,
# which is the honest resilience property V2 must demonstrate. Only when a
# one-third coalition (Q - t + 1 = 2 nodes here) withholds do we reach k < t and
# re-enter the fallback.
NODES = [
    (sha256(b"validator:alpha"), b"validator:alpha"),
    (sha256(b"validator:beta"), b"validator:beta"),
    (sha256(b"validator:gamma"), b"validator:gamma"),
    (sha256(b"validator:delta"), b"validator:delta"),
    (sha256(b"validator:epsilon"), b"validator:epsilon"),
    (sha256(b"validator:zeta"), b"validator:zeta"),
]


def transcript(net: bytes, slot: int, purpose: int, anchor: bytes) -> bytes:
    return (DOMAIN + bytes([VER]) + net
            + slot.to_bytes(4, "big") + bytes([purpose]) + anchor)


def transcript_hash(net: bytes, slot: int, purpose: int, anchor: bytes) -> bytes:
    # 32-byte SHA-256, matching the XDR `Hash` type used throughout.
    return sha256(transcript(net, slot, purpose, anchor))


def placeholder_beta(node_id: bytes, net: bytes, slot: int, anchor: bytes) -> bytes:
    """Protocol-level stand-in for VRF_prove(sk_v, T_v(s)): deterministic in the
    node key and the leader transcript, so it depends on network/slot/anchor
    exactly as the real VRF output over `alpha = T_leader(s)` would."""
    t_leader = transcript(net, slot, 0x01, anchor)
    return sha512(BETA_LABEL + bytes([VER]) + node_id + t_leader)[0:64]


def commit_hash_of(beta: bytes) -> bytes:
    # The XDR `VRFCommit.commitHash` is the 32-byte commitment to beta.
    return sha256(beta)


def commit_signature(node_id: bytes, net: bytes, slot: int, commit_hash: bytes) -> bytes:
    """Protocol-level stand-in for the per-contributor Ed25519 `Signature sig`
    over `"stellar-vrf/commit"|0x01|network_id|slot|commitHash`. Deterministic
    in (node, network, slot, commitHash) so a sig binds to its NodeID and its
    scope; a sig replayed under a different NodeID / network / slot / commitHash
    must not verify. (Real Ed25519 is the signer's job; here we model the scope
    and node binding the acceptance rule enforces.)"""
    return sha512(COMMIT_SIG_LABEL + bytes([VER]) + net
                  + slot.to_bytes(4, "big") + commit_hash + node_id)[0:64]


def contributors(net, slot, anchor):
    # Sorted by NodeID ascending; each entry is (node_id, beta, commit_hash, sig).
    rows = sorted((nid for nid, _ in NODES))
    out = []
    for nid in rows:
        beta = placeholder_beta(nid, net, slot, anchor)
        ch = commit_hash_of(beta)
        sg = commit_signature(nid, net, slot, ch)
        out.append((nid, beta, ch, sg))
    return out


def beacon(contrib_rows) -> bytes:
    """B(s) = SHA-256( concat of verified betas ordered by NodeID, ascending )."""
    return sha256(b"".join(row[1] for row in contrib_rows))


def subseed(net: bytes, slot: int, purpose: int, bcn: bytes) -> bytes:
    return sha512(SUB_DOMAIN + bytes([VER]) + net
                  + slot.to_bytes(4, "big") + bytes([purpose]) + bcn)[0:32]


def mutated_leader_transcript_hash(net, slot, anchor):
    t = bytearray(transcript(net, slot, 0x01, anchor))
    t[len(DOMAIN)] ^= 1
    return sha256(bytes(t))


contribs = sorted(contributors(NETWORK_ID_TESTNET, SLOT, ANCHOR), key=lambda r: r[0])
bcn = beacon(contribs)

Q = len(contribs)
T = (2 * Q) // 3 + 1  # t = floor(2Q/3)+1, strictly more than two thirds


def fallback_beacon(anchor_prev: bytes) -> bytes:
    # B(s) = SHA-256( LedgerHeaderHash(s-2) ); status-quo LCL entropy.
    return sha256(anchor_prev)


# V2: with Q=6, t=5. Withholding ONE reveal leaves k=5 >= t -> aggregate path
# (never fallback). Dropping below t (k < t) requires Q - t + 1 = 2 withheld.
single_withhold = contribs[1:]  # k=5 (drop the first contributor)
single_beacon = beacon(single_withhold)
# Drop (Q - t + 1) = 2 reveals to reach k = t - 1 = 4 < 5. We KEEP the first
# `fallback_k` sorted contributors and drop the trailing 2, so the partial set
# has exactly `fallback_k` = 4 members (previously the suffix slice
# `contribs[fallback_k:]` kept only 2 and pinned the wrong scenario).
fallback_k = T - 1
partial_withhold = contribs[:fallback_k]  # keep first `fallback_k`, drop tail
partial_beacon = beacon(partial_withhold)
# Layer A LCL fallback uses the DISTINCT s-2 header hash, not the s-3 anchor.
bfbk = fallback_beacon(FALLBACK_ANCHOR)

# V9: every threshold-valid reveal subset (each combination of size in [T..Q]
# over the authenticated, NodeID-ordered committed set) -> a root. Pinned so the
# checker asserts the full bounded root set, not a suffix-only containment. The
# roots differ per subset, honestly documenting that Layer A is NOT
# subset-invariant (one-future neutrality is a Layer B / epoch property).
v9_roots = sorted({
    beacon(list(combo)).hex()
    for k in range(T, Q + 1)
    for combo in itertools.combinations(contribs, k)
})


fixture = {
    "cap": "CAP-0089",
    "title": "VRF-Based Protocol Randomness and Fair Leader Selection",
    "cryptographic_building_block": "ECVRF-EDWARDS25519-SHA512-TAI (RFC 9381)",
    "building_block_pr": "https://github.com/stellar/stellar-core/pull/5409",
    "note": (
        "Protocol-level conformance fixture. `network_id` is the real 32-byte "
        "Application::getNetworkID() = SHA-256(network passphrase), no prefix. "
        "`anchor_ledger_header_hash` is the canonical LedgerHeader hash of "
        "ledger (s-3) and is used directly (not re-hashed) as prior_context(s). "
        "Contributions are ordered by NodeID ascending per the CAP. The beta "
        "placeholders model VRF determinism-in-transcript; real RFC 9381 proofs "
        "are exercised by the PR #5409 harness."
    ),
    "constants": {
        "domain": "stellar-vrf",
        "transcript_version": 1,
        "sub_domain": "stellar-vrf/sub",
        "network_id_hash": "SHA-256",
        "anchor_hash": "LedgerHeaderHash (32 bytes, not re-hashed)",
        "beacon_hash": "SHA-256",
        "subseed_hash": "SHA-512[0:32]",
        "beta_label_hash": "SHA-512[0:64] (protocol placeholder)",
        "purpose_beacon": 1,
        "purpose_leader": 2,
        "purpose_prng": 3,
        "purpose_order": 4,
        "network_id_testnet": NETWORK_ID_TESTNET.hex(),
        "network_id_mainnet": NETWORK_ID_MAINNET.hex(),
    },
    "testnet": {
        "network_id": NETWORK_ID_TESTNET.hex(),
        "slot": SLOT,
        "anchor_ledger_header_hash": ANCHOR.hex(),
        "contributors": [
            {"node_id": nid.hex(), "beta": beta.hex(),
             "commit_hash": ch.hex(), "sig": sg.hex()}
            for nid, beta, ch, sg in contribs
        ],
        "beacon": bcn.hex(),
        "Q": Q,
        "threshold_t": T,
        "V2_single_withhold_beacon": single_beacon.hex(),
        "V2_fallback_k": fallback_k,
        "V2_fallback_anchor": FALLBACK_ANCHOR.hex(),
        "V2_partial_beacon": partial_beacon.hex(),
        "V2_fallback_beacon_LCL": bfbk.hex(),
        "V1_transcript_hash_leader": transcript_hash(
            NETWORK_ID_TESTNET, SLOT, 1, ANCHOR).hex(),
        "V4_beta_under_mainnet": placeholder_beta(
            contribs[0][0], NETWORK_ID_MAINNET, SLOT, ANCHOR).hex(),
        "V5_transcript_hash_cross_slot": transcript_hash(
            NETWORK_ID_TESTNET, SLOT + 1, 1, ANCHOR).hex(),
        "V6_subseed_leader": subseed(NETWORK_ID_TESTNET, SLOT, 2, bcn).hex(),
        "V6_subseed_prng": subseed(NETWORK_ID_TESTNET, SLOT, 3, bcn).hex(),
        "V6_subseed_order": subseed(NETWORK_ID_TESTNET, SLOT, 4, bcn).hex(),
        "V8_transcript_hash_mutated": mutated_leader_transcript_hash(
            NETWORK_ID_TESTNET, SLOT, ANCHOR).hex(),
        "V9_threshold_roots": v9_roots,
    },
}

body = (json.dumps(fixture, indent=2) + "\n").encode("utf-8")
sys.stdout.buffer.write(body)
