# CAP-0089 XDR changes

This file records, as a canonical unified diff, the changes to the XDR in the
[stellar-xdr](https://github.com/stellar/stellar-xdr) repository required by
CAP-0089. The authoritative copy of this diff — which is machine-checked by the
`mddiffcheck` CI gate against commit
`03cbf40cec4d89f82171bf895ef7598458d83e1b` of `stellar-xdr` — is embedded in
[`core/cap-0089.md`](../../core/cap-0089.md) under the caption
`diff mddiffcheck.base=03cbf40cec4d89f82171bf895ef7598458d83e1b`.

The change is additive and versioned behind the `VRF_RANDOMNESS` guard. It
adds a **new orthogonal top-level field** to `struct StellarValue` rather than a
new arm of the `ext` union, so it coexists with CAP-0088's `MS_CLOSE_TIME` arms
(and the empty-tx-set arms) of that union. The field is a 32-byte `Hash`
(`opaque Hash[32]`), matching the `SHA-256` width used throughout CAP-0089.

## `Stellar-ledger.x` — add `vrfBeaconNext` to `struct StellarValue`

```diff
@@ -76,6 +76,15 @@ struct StellarValue
 #endif // MS_CLOSE_TIME
     }
     ext;
+
+#ifdef VRF_RANDOMNESS
+    // CAP-0089: randomness beacon for the next slot. Aggregated from verified,
+    // delayed-reveal VRF contributions finalized at close of THIS ledger, so
+    // beacon(L) is public and immutable before slot L begins. Carried as an
+    // orthogonal top-level field (not an `ext` arm) so it can coexist with any
+    // MS_CLOSE_TIME / empty-tx-set arm of `ext` above.
+    Hash vrfBeaconNext; // 32-byte SHA-256 (see "Hash" in Stellar-types.x)
+#endif // VRF_RANDOMNESS
 };
```

`vrfBeaconNext` is the aggregate randomness beacon `B(s)` for the slot `s`
produced immediately after the ledger carrying it closes, computed from the
verified, delayed-reveal VRF contributions accepted during that ledger. Because
it is a plain 32-byte `Hash`, it serializes compactly and needs no variable
length.

## Unchanged

The `GeneralizedTransactionSet`, `TransactionSetV1`, and
`TransactionSetV1.phases` are **not** modified by this CAP. The existing `ext`
union and all of its `StellarValueType` arms (including the CAP-0088
`MS_CLOSE_TIME` arms and the empty-tx-set arms) are **not** modified and remain
fully selectable. The per-purpose sub-seeds are derived deterministically by
every node from the shared beacon, so no per-transaction or per-set inflation
is introduced.
