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

`VRFCommit.sig` is a REAL Ed25519 signature (not a stand-in): each node's
`node_id` IS its Ed25519 verification key, and the signature is computed with
`cryptography` over the canonical, spec-defined message
`"stellar-vrf/commit" || 0x01 || network_id || u32_be(slot) || commitHash
 || vrfPublicKey`
(no `node_id` in the message; the key provides the binding, and the committed
`vrfPublicKey` makes the NodeID->VRF-key mapping authenticated -- this review).
A real fixture means the generator cannot silently share a stand-in bug with
the checker.
"""
import hashlib
import itertools
import json
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)


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
# "stellar-vrf/commit" | 0x01 | network_id | slot | commitHash | vrfPublicKey
# (spec parity): the node's VRF public key -- the distinct point the reveal will
# be validated against -- is bound into the commit signature so it cannot be
# re-attributed to a different VRF key after the fact.
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
#
# Each node_id IS a real Ed25519 verification key, deterministically derived so
# the fixture is reproducible. `node_keypair(name)` returns (private, public);
# the public key is the node's NodeID, and only that private key can produce a
# `VRFCommit.sig` that verifies under the NodeID (real cryptography, so the
# generator and checker cannot silently agree on the same stand-in bug).
NODE_KEY_LABEL = b"stellar-vrf/node-key"


def node_key(name: bytes) -> "tuple[Ed25519PrivateKey, bytes]":
    seed = sha512(NODE_KEY_LABEL + name)[0:32]
    sk = Ed25519PrivateKey.from_private_bytes(seed)
    pub = sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return sk, pub


# NODES: (private_key, node_id=public_key, name) — 6 deterministic validators.
_keypairs = [(node_key(b"validator:%s" % b))
             for b in (b"alpha", b"beta", b"gamma", b"delta", b"epsilon", b"zeta")]
NODES = [(sk, pub, name) for (sk, pub), name in zip(_keypairs, (
    b"validator:alpha", b"validator:beta", b"validator:gamma",
    b"validator:delta", b"validator:epsilon", b"validator:zeta"))]


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


def commit_message(net: bytes, slot: int, commit_hash: bytes,
                   vrf_pub: bytes = None) -> bytes:
    """Canonical signing preimage, exactly as the CAP/XDR specifies:
    `"stellar-vrf/commit" || 0x01 || network_id || u32_be(slot) || commitHash ||
    vrfPublicKey`. The `vrfPublicKey` is now part of the signed message so the
    NodeID->VRF-public-key mapping is authenticated by the consensus-recognized
    NodeID (this review); a value author cannot substitute a different VRF key
    for a contributor. `node_id` itself is deliberately NOT part of M_commit —
    the key provides the node binding (nodeID is the Ed25519 verification key).
    One function decides the bytes everywhere (V11 spec parity)."""
    return (COMMIT_SIG_LABEL + bytes([VER]) + net
            + slot.to_bytes(4, "big") + commit_hash
            + (vrf_pub or b""))


def vrf_public_key(node_id: bytes) -> bytes:
    """The contributor's ECVRF public key (VKF), a DISTINCT 32-byte value from
    the NodeID (the CAP's `vrfPublicKey` field). Deriving it from a private seed
    means it is NOT publicly inferable from the NodeID, so the CAP commits it in
    `VRFCommit` and has the NodeID signature bind it (this review: without the
    committed+authenticated mapping, `ECVRF_Verify(VKF, ...)` could not bind the
    reveal's beta to the node that committed it).

    COPILOT round-15 (thread 3929898654, High): a RAW 32-byte digest is NOT a
    valid ECVRF-Ed25519 public key -- roughly half of all 32-byte strings fail
    Edwards25519 point decompression, so the fixtures could not be replayed
    through the native VRF acceptance path. We therefore generate a GENUINE,
    valid Edwards25519 public point deterministically from the node seed: the
    domain-separated secret seed `s_v` is expanded (SHA-512) to 32 bytes, an
    Ed25519 keypair is derived from that exact seed, and the COMPRESSED public
    point (32 bytes, decomposable by the RFC 8032 point decoder) is returned.
    This is the ECVRF-Ed25519 key-derivation shape: `VKF = s_v * B` with
    `s_v = H(...)` clamped, and the compressed point is the valid ECVRF public
    key the native `ECVRF_Verify` accepts. The value remains deterministic per
    node (same node_id -> same seed -> same valid point) and still differs from
    the NodeID, and the NodeID signature still binds this exact key."""
    seed = sha512(NODE_KEY_LABEL + b"/vrf-public-key" + node_id)[:32]
    vk = Ed25519PrivateKey.from_private_bytes(seed).public_key()
    return vk.public_bytes(Encoding.Raw, PublicFormat.Raw)


def commit_signature(sk: Ed25519PrivateKey, net: bytes, slot: int,
                     commit_hash: bytes, vrf_pub: bytes) -> bytes:
    """Real Ed25519 signature over `commit_message(net, slot, commitHash,
    vrfPublicKey)` using the node's secret key (whose public key is its NodeID).
    Genuine cryptography, so the fixture cannot share a stand-in bug with the
    checker: the signature verifies under the NodeID's public key exactly as the
    CAP requires, and it binds BOTH the commit (to beta) AND the node's
    NodeID->VRF-public-key mapping (this review)."""
    return sk.sign(commit_message(net, slot, commit_hash, vrf_pub))


def contributors(net, slot, anchor):
    # Sorted by NodeID ascending; each entry is (node_id, vrf_public_key, beta,
    # commit_hash, sig).  node_id IS the Ed25519 public key; sig is the REAL
    # Ed25519 signature over the canonical commit message (which includes the
    # node's vrfPublicKey), made by that node's secret key.
    rows = sorted((pub for _, pub, _ in NODES))
    key_of = {pub: sk for sk, pub, _ in NODES}
    out = []
    for nid in rows:
        beta = placeholder_beta(nid, net, slot, anchor)
        ch = commit_hash_of(beta)
        vp = vrf_public_key(nid)
        sg = commit_signature(key_of[nid], net, slot, ch, vp)
        out.append((nid, vp, beta, ch, sg))
    return out


def beacon(contrib_rows) -> bytes:
    """B(s) = SHA-256( concat of verified betas ordered by NodeID, ascending )."""
    return sha256(b"".join(row[2] for row in contrib_rows))


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
            {"node_id": nid.hex(), "vrf_public_key": vp.hex(),
             "beta": beta.hex(), "commit_hash": ch.hex(), "sig": sg.hex()}
            for nid, vp, beta, ch, sg in contribs
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
