# CAP-0089 XDR changes

This file records, as a canonical unified diff, the changes to the XDR in the
[stellar-xdr](https://github.com/stellar/stellar-xdr) repository required by
CAP-0089. The authoritative copy of this diff — which is machine-checked by the
`mddiffcheck` CI gate against commit
`03cbf40cec4d89f82171bf895ef7598458d83e1b` of `stellar-xdr` — is embedded in
[`core/cap-0089.md`](../core/cap-0089.md) under the caption
`diff mddiffcheck.base=03cbf40cec4d89f82171bf895ef7598458d83e1b`.

The changes are additive and versioned behind the `VRF_RANDOMNESS` guard,
following the precedent set by CAP-0088's `MS_CLOSE_TIME` arms of the same
union.

## `Stellar-ledger.x`

### `StellarValueType` — add `STELLAR_VALUE_VRF`

Note that numeric values `3` and `4` are already taken by the CAP-0088
`MS_CLOSE_TIME` arms, so the new arm is `STELLAR_VALUE_VRF = 5`.

```diff
@@ -20,6 +20,10 @@ enum StellarValueType
     STELLAR_VALUE_SIGNED_MS = 3,
     STELLAR_VALUE_EMPTY_TX_SET_MS = 4
 #endif // MS_CLOSE_TIME
+#ifdef VRF_RANDOMNESS
+    ,
+    STELLAR_VALUE_VRF = 5
+#endif // VRF_RANDOMNESS
 };
```

### `StellarValue.ext` — add `vrfValue` arm

```diff
@@ -74,6 +78,19 @@ struct StellarValue
             LedgerCloseValueSignature lcValueSignature;
         } proposedMsValue;
 #endif // MS_CLOSE_TIME
+#ifdef VRF_RANDOMNESS
+    case STELLAR_VALUE_VRF:
+        struct
+        {
+            // the leader-elected beacon for this slot, verifiable by every node
+            opaque<64> vrfBeta;               // ECVRF output (beta), RFC 9381
+            opaque<80> vrfProof;              // pi = Gamma || c || s
+            NodeID vrfNodeID;                 // validating node that self-selected
+            uint32 vrfSlot;                   // ledger sequence the value applies to
+            Hash vrfTranscriptHash;           // H(T(N)) -- fixed prior-context transcript
+            LedgerCloseValueSignature lcValueSignature;
+        } vrfValue;
+#endif // VRF_RANDOMNESS
     }
     ext;
 };
```

### Unchanged

The `GeneralizedTransactionSet`, `TransactionSetV1`, and
`TransactionSetV1.phases` are **not** modified by this CAP. The beacon is
carried in `StellarValue.ext.vrfValue` (the consensus-critical value), and the
per-purpose sub-seeds are derived deterministically by every node from the
winner's committed `beta` and the fixed prior-context transcript, so no
per-transaction or per-set inflation is introduced.
