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
VER = 0x01
SLOT = 123456789
# Canonical anchor: the existing 32-byte LedgerHeader hash of ledger (s-3).
# prior_context(s) IS this hash; it is NOT re-hashed (avoids a double hash).
ANCHOR = bytes(range(32))

# Deterministic contributor set (validator public keys / NodeIDs). The
# aggregation order is by NodeID (lexicographic, ascending), per the CAP.
NODES = [
    (sha256(b"validator:alpha"), b"validator:alpha"),
    (sha256(b"validator:beta"), b"validator:beta"),
    (sha256(b"validator:gamma"), b"validator:gamma"),
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


def contributors(net, slot, anchor):
    # Sorted by NodeID ascending; each entry is (node_id, beta).
    rows = sorted((nid for nid, _ in NODES))
    by = {}
    for nid, _ in NODES:
        by[nid] = placeholder_beta(nid, net, slot, anchor)
    return [(nid, by[nid]) for nid in rows]


def beacon(contrib_rows) -> bytes:
    """B(s) = SHA-256( concat of verified betas ordered by NodeID, ascending )."""
    return sha256(b"".join(beta for _, beta in contrib_rows))


def subseed(net: bytes, slot: int, purpose: int, bcn: bytes) -> bytes:
    return sha512(SUB_DOMAIN + bytes([VER]) + net
                  + slot.to_bytes(4, "big") + bytes([purpose]) + bcn)[0:32]


def mutated_leader_transcript_hash(net, slot, anchor):
    t = bytearray(transcript(net, slot, 0x01, anchor))
    t[len(DOMAIN)] ^= 1
    return sha256(bytes(t))


contribs = sorted(contributors(NETWORK_ID_TESTNET, SLOT, ANCHOR), key=lambda r: r[0])
bcn = beacon(contribs)

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
        "purpose_leader": 1,
        "purpose_prng": 2,
        "purpose_order": 3,
        "network_id_testnet": NETWORK_ID_TESTNET.hex(),
        "network_id_mainnet": NETWORK_ID_MAINNET.hex(),
    },
    "testnet": {
        "network_id": NETWORK_ID_TESTNET.hex(),
        "slot": SLOT,
        "anchor_ledger_header_hash": ANCHOR.hex(),
        "contributors": [
            {"node_id": nid.hex(), "beta": beta.hex()} for nid, beta in contribs
        ],
        "beacon": bcn.hex(),
        "V1_transcript_hash_leader": transcript_hash(
            NETWORK_ID_TESTNET, SLOT, 1, ANCHOR).hex(),
        "V4_beta_under_mainnet": placeholder_beta(
            contribs[0][0], NETWORK_ID_MAINNET, SLOT, ANCHOR).hex(),
        "V5_transcript_hash_cross_slot": transcript_hash(
            NETWORK_ID_TESTNET, SLOT + 1, 1, ANCHOR).hex(),
        "V6_subseed_prng": subseed(NETWORK_ID_TESTNET, SLOT, 2, bcn).hex(),
        "V6_subseed_order": subseed(NETWORK_ID_TESTNET, SLOT, 3, bcn).hex(),
        "V8_transcript_hash_mutated": mutated_leader_transcript_hash(
            NETWORK_ID_TESTNET, SLOT, ANCHOR).hex(),
    },
}

body = (json.dumps(fixture, indent=2) + "\n").encode("utf-8")
sys.stdout.buffer.write(body)
