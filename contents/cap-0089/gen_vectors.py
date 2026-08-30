#!/usr/bin/env python3
"""Regenerate fixture_vectors.json for CAP-0089.

This script is the single source of truth for the pinned protocol-level
digests. Run:

    python3 gen_vectors.py > fixture_vectors.json

It must reproduce the checked-in fixture_vectors.json byte-for-byte, so a
reviewer can regenerate and verify the pinned data. Any change to the CAP's
transcript, hashing, or network-ID encoding that alters these digests must be
reflected here AND in the checked-in fixture.
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
VER = 0x01
SLOT = 123456789
ANCHOR = bytes(range(32))  # LedgerHeader(s-3); canonical anchor, fixed here
# Deterministic public per-validator contributions (VRF betas) for slot SLOT.
# Their RFC 9381 proofs are exercised by the PR #5409 harness; the protocol
# layer only pins the aggregation and the derived beacon/sub-seeds.
CONTRIBUTIONS = [bytes(range(1, 65)), bytes(range(65, 129)), bytes(range(129, 193))]


def prior_context(anchor: bytes) -> bytes:
    """Canonical 32-byte anchor hash for slot s: SHA-256(LedgerHeader(s-3))."""
    return sha256(anchor)


def transcript(net: bytes, slot: int, purpose: int, anchor: bytes) -> bytes:
    return (DOMAIN + bytes([VER]) + net
            + slot.to_bytes(4, "big") + bytes([purpose])
            + prior_context(anchor))


def transcript_hash(net: bytes, slot: int, purpose: int, anchor: bytes) -> bytes:
    # 32-byte SHA-256, matching the XDR `Hash` type carried in vrfBeaconNext
    # context and the `Hash` type used throughout the protocol.
    return sha256(transcript(net, slot, purpose, anchor))


def beacon(slot: int, contribs) -> bytes:
    """Aggregate beacon B(s) = SHA-256( concat of verified betas, sorted )."""
    return sha256(b"".join(sorted(contribs)))


def subseed(net: bytes, slot: int, purpose: int, bcn: bytes) -> bytes:
    """32-byte labeled sub-seed derived from the shared beacon B(s)."""
    return sha512(SUB_DOMAIN + bytes([VER]) + net
                  + slot.to_bytes(4, "big") + bytes([purpose]) + bcn)[0:32]


def mutated_leader_transcript_hash(net, slot, purpose, anchor):
    t = bytearray(transcript(net, slot, purpose, anchor))
    t[len(DOMAIN)] ^= 1  # flip the first byte after the domain label
    return sha256(bytes(t))


bcn = beacon(SLOT, CONTRIBUTIONS)

fixture = {
    "cap": "CAP-0089",
    "title": "VRF-Based Protocol Randomness and Fair Leader Selection",
    "cryptographic_building_block": "ECVRF-EDWARDS25519-SHA512-TAI (RFC 9381)",
    "building_block_pr": "https://github.com/stellar/stellar-core/pull/5409",
    "note": (
        "Protocol-level conformance fixture. `network_id` is the real 32-byte "
        "Application::getNetworkID() = SHA-256(network passphrase), with no "
        "prefix. Public `contributions` are deterministic placeholders whose "
        "RFC 9381 proofs are exercised by the PR #5409 harness; the beacon and "
        "sub-seeds below are the protocol-level derivations pinned by this CAP."
    ),
    "constants": {
        "domain": "stellar-vrf",
        "transcript_version": 1,
        "sub_domain": "stellar-vrf/sub",
        "network_id_hash": "SHA-256",
        "anchor_hash": "SHA-256",
        "beacon_hash": "SHA-256",
        "subseed_hash": "SHA-512[0:32]",
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
        "contributions": [c.hex() for c in CONTRIBUTIONS],
        "beacon": bcn.hex(),
        "V1_transcript_hash_leader": transcript_hash(
            NETWORK_ID_TESTNET, SLOT, 1, ANCHOR).hex(),
        "V4_transcript_hash_cross_network": transcript_hash(
            NETWORK_ID_MAINNET, SLOT, 1, ANCHOR).hex(),
        "V5_transcript_hash_cross_slot": transcript_hash(
            NETWORK_ID_TESTNET, SLOT + 1, 1, ANCHOR).hex(),
        "V6_subseed_prng": subseed(NETWORK_ID_TESTNET, SLOT, 2, bcn).hex(),
        "V6_subseed_order": subseed(NETWORK_ID_TESTNET, SLOT, 3, bcn).hex(),
        "V8_transcript_hash_mutated": mutated_leader_transcript_hash(
            NETWORK_ID_TESTNET, SLOT, 1, ANCHOR).hex(),
    },
}

# Emit bytes with LF line endings so regeneration is byte-for-byte identical
# on every platform (avoids Python's platform-specific print() newline).
body = (json.dumps(fixture, indent=2) + "\n").encode("utf-8")
sys.stdout.buffer.write(body)
