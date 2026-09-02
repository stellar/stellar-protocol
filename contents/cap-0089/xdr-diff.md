# CAP-0089 XDR changes

**Status: this diff is conformance/evidence only.** It records the Layer-A
trailing-field shape that CAP-0089 deliberately **never serializes in any
shipping protocol version** (see [`core/cap-0089.md`]
(../../core/cap-0089.md), "Status and the Layer A / Layer B deployment fork" and
the exit criteria): it exists so an implementer can audit and reproduce the
machine-checked evidence of CAP-0089's cryptographic claims. The protocol
randomness format that ships is the single runtime-discriminated Layer-B
representation, **not** the `#ifdef` trailing members shown below. Implementers
must not implement this file's shape as a deployable format.

This file records, as a canonical unified diff, the changes to the XDR in the
[stellar-xdr](https://github.com/stellar/stellar-xdr) repository required by
CAP-0089. The authoritative copy of this diff — which is machine-checked by the
`mddiffcheck` CI gate against commit
`03cbf40cec4d89f82171bf895ef7598458d83e1b` of `stellar-xdr` — is embedded in
[`core/cap-0089.md`](../../core/cap-0089.md) under the caption
`diff mddiffcheck.base=03cbf40cec4d89f82171bf895ef7598458d83e1b`.

The change is additive and gated by a **compile-time schema guard** — the
`VRF_RANDOMNESS` build-time guard selects whether the trailing field exists in
the generated schema; it is not a runtime version discriminator that would let a
single wire format flip behavior per connection. It adds a **new orthogonal
top-level field** to `struct StellarValue` rather than a new
arm of the `ext` union, so it coexists with CAP-0088's `MS_CLOSE_TIME` arms
(and the empty-tx-set arms) of that union. Its type is a `Hash`
(`opaque Hash[32]`), matching the `SHA-256` width used throughout CAP-0089.

## `Stellar-ledger.x` — add `VRFCommit`/`VRFReveal` and the three `StellarValue` fields

```diff
@@ -28,6 +28,32 @@ struct LedgerCloseValueSignature
     Signature signature; // nodeID's signature
 };
 
+#ifdef VRF_RANDOMNESS
+/* CAP-0089 VRF randomness. Commit/reveal records are consensus-visible and
+ * replayable so every node derives the identical per-slot beacon.
+ * MAX_VRF_CONTRIBUTORS bounds the contributions per slot so an oversized
+ * candidate cannot impose unbounded SCP bandwidth / verification work. */
+const MAX_VRF_CONTRIBUTORS = 100; // protocol maximum per slot
+
+struct VRFCommit
+{
+    NodeID nodeID;     // contributor public key (NodeID)
+    Hash commitHash;   // C_v = SHA-256(beta_v), hiding commit
+    // Ed25519 signature by nodeID's existing NodeID key over
+    //   "stellar-vrf/commit" | 0x01 | network_id | slot | commitHash
+    // so an entry attributed to nodeID cannot be forged by the value author.
+    Signature sig;
+};
+
+struct VRFReveal
+{
+    NodeID nodeID;        // contributor public key (NodeID)
+    opaque vrfBeta[64];   // ECVRF output beta_v, RFC 9381 (exact length)
+    opaque vrfProof[80];  // pi = Gamma || c || s (exact length)
+    Hash transcriptHash;  // SHA-256(T_b(s)) for the targeted slot
+};
+#endif // VRF_RANDOMNESS
+
 /* StellarValue is the value used by SCP to reach consensus on a given ledger
  */
 struct StellarValue
@@ -76,6 +94,21 @@ struct StellarValue
 #endif // MS_CLOSE_TIME
     }
     ext;
+
+#ifdef VRF_RANDOMNESS
+    // CAP-0089 randomness. Carried as orthogonal top-level fields (not `ext`
+    // arms) so they coexist with any MS_CLOSE_TIME / empty-tx-set arm of `ext`.
+    // Bounded by MAX_VRF_CONTRIBUTORS; each vector requires strict NodeID-
+    // ascending order with exactly one entry per contributor (duplicates MUST
+    // be rejected before aggregation).
+    //   vrfCommits   : commit set for slot L+2 (published during ledger L)
+    //   vrfReveals   : reveals for slot L+1 (published during ledger L)
+    //   vrfBeaconNext: aggregate beacon B(L+1) = SHA-256 over NodeID-ordered,
+    //                  verified betas accepted during L
+    VRFCommit vrfCommits<MAX_VRF_CONTRIBUTORS>;
+    VRFReveal vrfReveals<MAX_VRF_CONTRIBUTORS>;
+    Hash vrfBeaconNext;
+#endif // VRF_RANDOMNESS
 };
```

`vrfCommits` carries the hiding commit set for slot `L+2` (published during
ledger `L`); `vrfReveals` carries the verified reveals for slot `L+1`; and
`vrfBeaconNext` is the resulting 32-byte aggregate `B(L+1)`. All fixed-width
members are `Hash`/`opaque[64]`/`opaque[80]`, matching the `SHA-256` width used
throughout CAP-0089. `VRFCommit.sig` authenticates the entry to `nodeID`'s
existing NodeID key; both vectors are bounded by `MAX_VRF_CONTRIBUTORS`, and a
value that exceeds the cap, is not strictly `NodeID`-ascending, or contains a
duplicate `NodeID` is rejected before any per-reveal cryptographic verification.

## Unchanged

The `GeneralizedTransactionSet`, `TransactionSetV1`, and
`TransactionSetV1.phases` are **not** modified by this CAP. The existing `ext`
union and all of its `StellarValueType` arms (including the CAP-0088
`MS_CLOSE_TIME` arms and the empty-tx-set arms) are **not** modified and remain
fully selectable. The per-purpose sub-seeds are derived deterministically by
every node from the shared beacon, so no per-transaction or per-set inflation
is introduced.
