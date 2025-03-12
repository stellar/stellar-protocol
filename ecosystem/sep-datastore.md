## Preamble

```
SEP: To Be Assigned
Title: Ledger Metadata Storage
Author: Tamir Sen <@tamirms>
Status: Draft
Created: 2025-03-11
Version: 0.1.0
```

## Simple Summary

A standard for how [`LedgerCloseMeta`](https://github.com/stellar/stellar-xdr/blob/v22.0/Stellar-ledger.x#L539-L545)
objects should be stored so that ledgers can be easily and efficiently ingested by downstream systems.

## Dependencies

None.

## Motivation

[galexie](https://github.com/stellar/go/tree/master/services/galexie) is a service which publishes
[`LedgerCloseMeta`](https://github.com/stellar/stellar-xdr/blob/v22.0/Stellar-ledger.x#L539-L545) XDR objects to a GCS
(Google Cloud Storage) bucket. However, the data format and layout of the XDR objects are not formally documented. This
SEP aims to provide a comprehensive specification for storing LedgerCloseMeta objects, enabling third-party developers
to build compatible data stores and clients for retrieving ledger metadata.

## Specification

The data store is a key-value store where:

- **Keys** are strings following a specific hierarchical format.
- **Values** are binary blobs representing compressed `LedgerCloseMetaBatch` XDR values.

The key-value store must support:

- Efficient random access lookups on arbitrary keys.
- Listing keys in lexicographic order, optionally filtered by a prefix.

Examples of compatible key-value stores include Google Cloud Storage (GCS) and Amazon S3.

---

### Value Format

Each value in the key-value store is the compressed binary encoding of the following XDR structure:

```c++
// Batch of ledgers along with their transaction metadata
struct LedgerCloseMetaBatch
{
    // starting ledger sequence number in the batch
    uint32 startSequence;

    // ending ledger sequence number in the batch
    uint32 endSequence;

    // Ledger close meta for each ledger within the batch
    LedgerCloseMeta ledgerCloseMetas<>;
};
```

- A LedgerCloseMetaBatch represents a contiguous range of one or more consecutive ledgers.

- All batches in a data store instance contain the same number of ledgers.

---

### Key Format

Keys follow a hierarchical directory structure. The root directory is `/ledgers`, and subdirectories represent
partitions. Each partition contains a fixed number of batches:

```
/ledgers/<partition>/<batch>.xdr
```

If the partition size is 1, the partition is omitted, resulting in:

```
/ledgers/<batch>.xdr
```

#### Partition Format:

```go
fmt.Sprintf("%08X--%d-%d/", math.MaxUint32-partitionStartLedgerSequence, partitionStartLedgerSequence, partitionEndLedgerSequence)
```

#### Batch Format:

```go
 fmt.Sprintf("%08X--%d-%d.xdr", math.MaxUint32-batchStartLedgerSequence, batchStartLedgerSequence, batchEndLedgerSequence)
```

If the batch size is 1, the format simplifies to:

```go
 fmt.Sprintf("%08X--%d.xdr", math.MaxUint32-batchStartLedgerSequence, batchStartLedgerSequence)
```

---

### Configuration File

The data store includes a configuration JSON object stored under the key `/config.json`. This file contains the
following properties:

- `networkPassphrase` - (string) the passphrase for the Stellar network associated with the ledgers.
- `compression` - (string) the compression algorithm used to compress ledger objects (currently only
  [`zstd`]([https://facebook.github.io/zstd/) is supported).
- `ledgersPerBatch` - (integer) the number of ledgers bundled into each `LedgerCloseMetaBatch`.
- `batchesPerPartition` - (integer) the number of batches in a partition.

#### Example Configuration:

```json
{
  "networkPassphrase": "Public Global Stellar Network ; September 2015",
  "compression": "zstd",
  "ledgersPerBatch": 2,
  "batchesPerPartition": 8
}
```

---

### Example Key Structure

Below is an example list of keys for ledger batches based on the configuration above:

```
/ledgers/FFFFFFEF--16-31/FFFFFFED--18-19.xdr
/ledgers/FFFFFFEF--16-31/FFFFFFEF--16-17.xdr
/ledgers/FFFFFFFF--0-15/FFFFFFF1--14-15.xdr
/ledgers/FFFFFFFF--0-15/FFFFFFF3--12-13.xdr
/ledgers/FFFFFFFF--0-15/FFFFFFF5--10-11.xdr
/ledgers/FFFFFFFF--0-15/FFFFFFF7--8-9.xdr
/ledgers/FFFFFFFF--0-15/FFFFFFF9--6-7.xdr
/ledgers/FFFFFFFF--0-15/FFFFFFFB--4-5.xdr
/ledgers/FFFFFFFF--0-15/FFFFFFFD--2-3.xdr
```

[![](https://mermaid.ink/img/pako:eNpl0U2LgzAQBuC_InPurJva1uphYa3rYb8_emr1EJpUC2okVdil9L_vrBpwSQ4h4X3IDJkLHJSQEEKueVM42zitHVr3e7eUIpf67GYO4p0T7ZN-PSSIbIUec7NR9vFmjBOKb5EtTTrsUW8ezRMxPbFGFtx8C51NxdP_IsyfiGHf9O7ZVGPkFlRu4gbxYoRHYo7Ms8SrEUsS1DKzxJsRPuIaAyt_N3mAuELfyj9MHiEu0O7x0-T0H3McOoQZVFJX_CRoJJc_nUJbyEqmENJRyCPvyjaFtL4S5V2rvn7qA4St7uQMtOryAsIjL8906xrBWxmfOI22MqTh9U6pakTXX0nQih8?type=png)](https://mermaid-js.github.io/mermaid-live-editor/edit#pako:eNpl0U2LgzAQBuC_InPurJva1uphYa3rYb8_emr1EJpUC2okVdil9L_vrBpwSQ4h4X3IDJkLHJSQEEKueVM42zitHVr3e7eUIpf67GYO4p0T7ZN-PSSIbIUec7NR9vFmjBOKb5EtTTrsUW8ezRMxPbFGFtx8C51NxdP_IsyfiGHf9O7ZVGPkFlRu4gbxYoRHYo7Ms8SrEUsS1DKzxJsRPuIaAyt_N3mAuELfyj9MHiEu0O7x0-T0H3McOoQZVFJX_CRoJJc_nUJbyEqmENJRyCPvyjaFtL4S5V2rvn7qA4St7uQMtOryAsIjL8906xrBWxmfOI22MqTh9U6pakTXX0nQih8)

**Note:** The genesis ledger starts at sequence number 2, so the oldest batch must have a `batchStartLedgerSequence`
of 2.

## Design Rationale

### Key Encoding (Reversed Ledger Sequence)

- **Lexicographic Order**: Many key-value stores (e.g., GCS, S3) optimize for listing keys in lexicographic order. By
  encoding the most recent ledgers first, clients can efficiently retrieve the latest data without scanning the entire
  dataset.
- **Reversed Sequence**: Using `math.MaxUint32 - startLedger` ensures that newer ledgers (with higher sequence numbers)
  appear before older ones when sorted lexicographically. This avoids the need for additional metadata or indexes to
  determine the latest ledger.

### Compression Algorithm

- `zstd` was chosen after evaluating `zstd`, `lz4`, and `gzip`. It provides the best balance between compression ratio
  and decompression speed.

## Security Concerns

Verifying the validity of the ledgers contained within the data store is outside the scope of this SEP. In otherwords,
this SEP does not provide any mechanism for validating that the ledgers obtained from a data store have not been
altered.

## Changelog

- `v0.1.0`: Initial draft
