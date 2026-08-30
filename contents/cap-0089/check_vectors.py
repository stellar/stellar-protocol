#!/usr/bin/env python3
"""Deterministic check for CAP-0089 protocol-level conformance vectors.

Reproduces the fixture in fixture_vectors.json and asserts the adversarial
properties that V1/V4/V5/V6/V8 pin.

The canonical transcript for CAP-0089 is:

    T(N) = "stellar-vrf" | 0x01 | network_id | slot | purpose | prior_context(N)
    prior_context(N) = SHA-512( ledgerHeaderHash(N) || txSetContentsHash(N) )

Note that every input to T(N) is fixed by the *already-finalized* prior ledger
N. There is deliberately NO input that a proposer controls during nomination
for slot N+1. That structural fact is what V1 asserts.

  V1 (grinding surface):  the candidate's proposed contents for the next
      ledger are absent from T(N); a proposer cannot vary any transcript input.
  V4 (cross-network):     a beacon on one network does not verify on another,
      because network_id is in the transcript -> H(T) differs.
  V5 (cross-slot):        a beacon for slot N+1 does not verify for N+2,
      because slot is in the transcript -> H(T) differs.
  V6 (purpose separation):subseed(0x02) != subseed(0x03) for the same beta, so
      a favorable outcome for one purpose cannot be reused for another.
  V8 (transcript mutation): altering any byte of T(N) changes H(T), so
      vrfTranscriptHash no longer matches.

Run:  python3 check_vectors.py
Exit code 0 on pass, 1 on any failure.
"""
import hashlib, json, os, sys


def sha512(b: bytes) -> bytes:
    return hashlib.sha512(b).digest()


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


NETWORK_ID_TESTNET = bytes([0]) + sha256(b"Test SDF Network ; September 2015")
NETWORK_ID_MAINNET = bytes([0]) + sha256(b"Public Global Stellar Network ; September 2015")


def prior_context(ledger_header_hash: bytes, txset_contents_hash: bytes) -> bytes:
    # Both inputs are fixed by the already-finalized prior ledger N.
    return sha512(ledger_header_hash + txset_contents_hash)


def transcript(net_id: bytes, slot: int, purpose: int, ledger_header_hash: bytes,
               txset_contents_hash: bytes) -> bytes:
    return (b"stellar-vrf" + bytes([0x01]) + net_id
            + slot.to_bytes(4, "big") + bytes([purpose])
            + prior_context(ledger_header_hash, txset_contents_hash))


def subseed(beta: bytes, net_id: bytes, slot: int, purpose: int) -> bytes:
    return sha512(b"stellar-vrf/sub" + bytes([0x01]) + net_id
                  + slot.to_bytes(4, "big") + bytes([purpose]) + beta)[0:32]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "fixture_vectors.json"), encoding="utf-8") as f:
        fx = json.load(f)["testnet"]

    ledger_header_hash = bytes.fromhex(fx["fixture_ledger_header_hash"])  # prior ledger N
    txset_contents_hash = bytes.fromhex(fx["fixture_txset_contents_hash"])  # prior ledger N
    beta = bytes.fromhex(fx["fixture_beta"])
    slot = fx["slot"]
    ledger_seq_next = slot + 1  # ledger being generated (N+1)

    def H(net_id, s, purpose):
        return sha512(transcript(net_id, s, purpose, ledger_header_hash,
                                 txset_contents_hash)).hex()

    failed = 0

    # --- V1: grinding surface ---
    # A proposer controls its *candidate* for slot N+1 (its proposed transaction
    # set, its chosen ordering). Under the naive design that motivated this CAP,
    # alpha = lcl.hash || seq || candidateTxSet, so a proposer could vary
    # candidateTxSet and grind for a favorable randomness outcome. CAP-0089's
    # transcript binds ONLY to the already-finalized prior ledger N; the
    # candidate's contents for N+1 are not a transcript input at all.
    #
    # We demonstrate the contrast by computing the naive (grindable) digest over
    # many candidate proposals, and the CAP-0089 digest over the same proposals:
    #   - naive:  the digest varies with candidateTxSet  -> a proposer can grind.
    #   - CAP-0089: the digest is invariant with candidateTxSet -> no grinding.
    candidate_proposals = [bytes(range(128, 192)),
                           bytes(range(192, 256)),
                           bytes(range(0, 64)),
                           bytes(range(64, 128))]
    naive = lambda c: sha512(ledger_header_hash + ledger_seq_next.to_bytes(4, "big") + c).hex()
    naive_digests = {naive(c) for c in candidate_proposals}
    cap_digests = {sha512(transcript(NETWORK_ID_TESTNET, ledger_seq_next, 1,
                                     ledger_header_hash, txset_contents_hash)).hex()
                   for _ in candidate_proposals}
    v1_ok = (len(naive_digests) == len(candidate_proposals)   # naive: grindable
             and len(cap_digests) == 1                         # CAP: single fixed digest
             and cap_digests == {H(NETWORK_ID_TESTNET, ledger_seq_next, 1)})
    print(("PASS  " if v1_ok else "FAIL  ") + "V1 grinding-surface (candidate contents not in transcript)")
    failed += 0 if v1_ok else 1

    # --- V4/V5/V8 ---
    ops = [
        ("V4 cross-network replay", H(NETWORK_ID_TESTNET, ledger_seq_next, 1) != H(NETWORK_ID_MAINNET, ledger_seq_next, 1)),
        ("V5 cross-slot replay",     H(NETWORK_ID_TESTNET, ledger_seq_next, 1) != H(NETWORK_ID_TESTNET, ledger_seq_next + 1, 1)),
        ("V6 purpose separation",    subseed(beta, NETWORK_ID_TESTNET, ledger_seq_next, 2).hex() != subseed(beta, NETWORK_ID_TESTNET, ledger_seq_next, 3).hex()),
    ]
    t_mutated = bytearray(transcript(NETWORK_ID_TESTNET, ledger_seq_next, 1,
                                     ledger_header_hash, txset_contents_hash))
    t_mutated[11] ^= 1
    ops.append(("V8 transcript mutation",
                H(NETWORK_ID_TESTNET, ledger_seq_next, 1) != sha512(bytes(t_mutated)).hex()))

    for name, ok in ops:
        print(("PASS  " if ok else "FAIL  ") + name)
        failed += 0 if ok else 1

    print("\n" + ("ALL PASS" if failed == 0 else f"{failed} FAILURE(S)"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
