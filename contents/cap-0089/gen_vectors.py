import hashlib, json

def sha512(b): return hashlib.sha512(b).digest()
def sha256(b): return hashlib.sha256(b).digest()

NETWORK_ID_TESTNET = bytes([0]) + sha256(b"Test SDF Network ; September 2015")
NETWORK_ID_MAINNET = bytes([0]) + sha256(b"Public Global Stellar Network ; September 2015")

def transcript(net_id, slot, purpose, ledger_header_hash, txset_contents_hash):
    prior_context = sha512(ledger_header_hash + txset_contents_hash)
    return (b"stellar-vrf" + bytes([0x01]) + net_id
            + slot.to_bytes(4,"big") + bytes([purpose])
            + prior_context)

def subseed(beta, net_id, slot, purpose):
    return sha512(b"stellar-vrf/sub" + bytes([0x01]) + net_id
                  + slot.to_bytes(4,"big") + bytes([purpose]) + beta)[0:32]

lh = bytes(range(32))     # deterministic placeholder for ledgerHeaderHash(N) (real value in harness)
ts = bytes(range(32,64))  # placeholder for txSetContentsHash(N)
slot = 123_456_789
beta = bytes(range(1,65)) # RFC 9381 / PR#5409-verified beta (placeholder for fixture)

basis = {}
for name, net in [("testnet", NETWORK_ID_TESTNET), ("mainnet", NETWORK_ID_MAINNET)]:
    t_l = transcript(net, slot, 0x01, lh, ts)
    t_prng = transcript(net, slot, 0x02, lh, ts)
    t_ord = transcript(net, slot, 0x03, lh, ts)
    s_prng = subseed(beta, net, slot, 0x02)
    s_ord  = subseed(beta, net, slot, 0x03)
    t_badslot  = transcript(net, slot+1, 0x01, lh, ts)
    t_badnet   = transcript(NETWORK_ID_MAINNET if name=="testnet" else NETWORK_ID_TESTNET, slot, 0x01, lh, ts)
    t_badbyte  = bytearray(t_l); t_badbyte[11] ^= 1
    basis[name] = {
        "slot": slot,
        "network_id": net.hex(),
        "transcript_hash_leader": sha512(t_l).hex(),
        "transcript_hash_prng":   sha512(t_prng).hex(),
        "transcript_hash_order":  sha512(t_ord).hex(),
        "subseed_prng": s_prng.hex(),
        "subseed_order": s_ord.hex(),
        "transcript_hash_cross_slot": sha512(t_badslot).hex(),
        "transcript_hash_cross_network": sha512(t_badnet).hex(),
        "transcript_hash_mutated_byte": sha512(bytes(t_badbyte)).hex(),
    }

print(json.dumps(basis, indent=2))
