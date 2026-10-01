# SLP Technical Evaluation Guide

This guide describes the technical evaluation the Core team performs during the
[`Awaiting Evaluation`](README.md) phase. It complements the proposer-facing
[SLP template](slp-template.md). The Core team records the evaluation methods, findings, and
recommended values in the proposal's `Technical Evaluation` section.

## Impact Assessment

Using the proposal's impact assessment as input, evaluate the expected impact of the change on the
network and downstream systems such as indexers, RPC providers, and block explorers. Address the
factors below that apply to the resources being changed.


## Reducing the limits

While the focus of this document is limit increases, it’s important to mention when and why the limits can be decreased.

The reason for the decrease should be network-wide emergency (e.g. significant ledger close time slow-down or nodes getting out of sync). While ideally we’d like to avoid that and do benchmarking and testing, there is always a chance that the behavior in the real network differs from any test performed.

The ledger-wide limits technically can be reduced down to at least the respective per-transaction limit, but since the main reason for decrease is likely to be reverting an overly optimistic increase, these would mostly just be rollbacks. Another prominent reason for decreasing the ledger-wide limits is the potential for the ledger close latency decrease, i.e. if the network will close more ledgers per unit of time, but every ledger includes less transactions than before. In either scenario the proposal is likely to be exempt from the process described in this document.

The per-transaction limits should normally not be decreased at all, making ***per-transaction limit increases basically irreversible***. As a consequence, ***per-transaction limit increases must be done fairly conservatively and thoughtfully***. The reason for this is that after the per-transaction limit is increased, anyone can start sending larger transactions to the network and build protocols that rely on the increased limits. Thus reducing the limit will likely break a number of protocols, which is something that the network should try to avoid at all costs.

Reduction of the per-transaction limit should be viewed as the ‘last resort’ measure in case if it causes serious network issues that can’t be quickly resolved.

## Increasing the limits

### Why increase the limits?

The increase in resources should generally be motivated by demand. However, the notion of demand differs for ledger-wide and per-transaction limits. Note, that ‘demand’ doesn’t mean that a limit will be increased, it’s just a motivation to consider the increase at all.

- For ledger-wide limits, *the demand can be identified by sufficiently high surge pricing rate due to transactions not fitting into a certain limit*, or at least a significant percentage of ledgers being near the resource limit
  - This is a reactive approach. There is a possibility that Core team might need to take a proactive approach and increase the limits in preparation for launching a protocol that is expected to have high TPS (i.e. not in response to the existing network activity). This should rather be an exception though
  - When the per-transaction limits are increased, it might be necessary to also increase the respective ledger-wide limits in order to maintain a high enough ratio between the limits
- For per-transaction limits, the demand is based on the needs of the protocols that run on Soroban.
  - It’s not realistic to support each and every possible protocol, but in general Soroban should provide the capabilities for implementing the majority of protocols that exist on the other blockchains, with as little exceptions as possible
    - More specifically, we should first and foremost look for the protocols that align with the Stellar chain goals like any other permanent protocol changes (see CAP process)
  - Contract developers have some room for optimization. That said, it would be preferential to have optimization just impact the costs and not to be a hard requirement for doing more complex things on Soroban

### Limit upper bounds

When considering the increase of any given limit, we need to make sure it doesn’t exceed some upper bound. In order to determine that upper bound we need to consider both short and long term impact on the network health, protocol development, and downstream systems.

The nature of the impact is significantly different for ledger-wide and per-transaction limits.

Increasing ledger-wide limits has an immediate impact on the network health and downstream systems, but these are easy to reduce in case of emergency. Increasing per-transaction limits has almost no immediate impact on anything, as the overall amount of work done doesn’t change. However, it is almost impossible to reduce the per-transaction limits, so increasing these might have a potential long term impact on the future changes to the protocol.

Below is the per-resource breakdown of the potential impact factors.

**Instructions**

Ledger-wide

- (Immediate) Ledger close time increase
  - The ‘hard’ upper bound is limited by how much time we can dedicate applying the transactions and the minimum hardware requirements for a validator (mostly CPU-driven for the instructions)
- (Long-term, minor) Catchup time increase

Per-transaction

- (Long-term) Long-running transactions might hinder the development of more efficient scheduling algorithms.
  - For example, large transactions might be problematic if we want to introduce synchronization steps during parallel transaction application.
  - Another example would be reducing the interval between ledgers \- while it is possible to achieve higher overall TPS by applying less transactions more frequently, long running transactions may result in too high lower bound for the apply time

**Read entries**
Ledger-wide

- (Immediate) Ledger close time increase
  - This shares the ledger apply time upper bound with the instructions, but is mostly determined by IOPS


**Read KB**
Ledger-wide
- (Immediate, minor) Ledger close time increase
  - The intuition is that more random reads are more expensive than a single read of a bigger entry, i.e. ‘read entries’ limit has more impact than the overall data size (given a reasonably small ledger entry size limit)

**Write entries**
Ledger-wide
- (Immediate, minor) Ledger close time increase

**Write KB**
Ledger-wide
- (Immediate, minor) Ledger close time increase
- (Immediate & long term, downstream) Ledger close meta size increase
- (Short to long term) Increased speed of the ledger growth
  - This is bounded by the archival/temp entry eviction rate \- Core should be able to evict the data faster than it can be written

Per-transaction
- (Immediate & long term, downstream) Increase in per-transaction meta size \- might be problematic for indexing

**Tx size KB**
Ledger-wide

- (Immediate) Network bandwidth for flooding the transactions between the nodes
- (Immediate & long term, downstream) Ledger close meta size increase
- (Long term) History size increase

Per-transaction

- (Immediate) Potential issues with flooding larger transactions

**Events size**
There is currently no ledger-wide limit for the total size of events emitted, however the maximum total size of events per ledger is per-transaction limit times the number of transactions.
- (Immediate & long term, downstream) Ledger close meta size increase

#### Ledger-wide impact summary

As a quick summary of increasing most of the ledger-wide limits we can ‘transpose’ the per-resource paragraphs above and indicate the dependencies:

**Total ledger apply time**

```text
ledger_apply_time = io_time + tx_apply_time
io_time = read_time(ledger_read_entries, ledger_read_bytes) + write_time(ledger_write_entries, ledger_write_bytes) + meta_emit_time
tx_apply_time = tx_execution_time(ledger_instructions)
```

`read_time`, `write_time` and `execution_time` functions are proportional to the respective ledger-wide limits.
`meta_emit_time` has no ledger-wide limit and is proportional to the metadata size per ledger (see below).

**Total size of metadata per ledger**

```text
metadata_size = ledger_txs_size + entry_sizes_before_write + ledger_write_bytes + tx_events_size_bytes * num_txs
```

`entry_sizes_before_write` is technically limited by `ledger_read_bytes`, but that’s rather an upper bound and a more realistic estimate for this is `ledger_write_bytes`.

**Total history size per ledger**

```text
history_size = ledger_txs_size + result_size * num_txs
```

`result_size` is a small constant value.

### Transactions per ledger ratio

Besides the resource-specific direct impact of any limit increase, there is always a factor of the transaction prioritization and transaction set building.

Core prioritizes Soroban transactions using only the flat inclusion fee that is completely independent of the resources that the transaction demands. This approach makes the fee model simpler and keeps the fees reasonably low for more complex protocols. The downside is that transaction sets that the Core builds are not optimized for the maximum throughput TPS- and fee-wise (for example, Core might build a transaction set with 2 large transactions with 1001 stroops fee instead of a transaction set with 20 small transactions with 1000 stroops fee each). This issue is mostly alleviated by the high enough ratio between the ledger limit and transaction limit for every resource.

Basically, every per-transaction limit increase results in a decrease of the ratio with the ledger-wide limit. Thus most of the time we’ll need to consider increasing the ledger-wide limit together with increasing the per-transaction limit, even if there is no immediate need for that. For example, if the current ratio is 10 and the increase of per-transaction limit moves it down to 7 (that is still above the “target” of 5), we might be fine with changing only the transaction limit.

Limit values change as SLPs are ratified, so this guide does not reproduce a static table of current
values. Verify the limits active on the target network and the source cited by the proposal, then
calculate the current and proposed ledger/transaction ratios for every affected resource.


## Core Evaluation Checklist

The proposed numbers have to be thoroughly verified against the actual network capabilities. Note
that the whole limits-increase process assumes that the network doesn't operate at the full
potential capacity at the moment, e.g. due to performance optimizations or just due to conservative
current limits.

- Most of the ledger-wide limits can be evaluated via apply-time benchmarks.
  - Define and record the current timing target, metric, model-validator hardware profile, and Core
    build used for the evaluation. Historical targets must not be assumed to remain current.
    - 'Model validator' is a bit imprecise, but we can't benchmark every validator on one hand and
      expect them to have a proportional change in apply time on the other.
    - Note that the timing target might need to go _down_ together with the ledger-wide limits if we
      prioritize the ledger close latency over individual ledger throughput. The important
      implication is that this adds a potential future limit to maximum _per-transaction_ limits.
      This just reinforces the requirements around maintaining high enough ledger/transaction
      ratios, though in this case it's likely mostly relevant for the resources that impact the
      ledger close time the most (CPU instructions, read entries).
- Going forward we might also consider additional evaluations based on models (such as
  [this](https://github.com/stellar/stellar-core/blob/master/scripts/resource-calc.ipynb)), though
  this will likely only become relevant when we start getting closer to the hardware limits.
- The transaction size limits (both per-ledger and per-transaction) need to be exercised in
  Supercluster tests to ensure there is no significant flooding TPS degradation.
- In case of changes that impact the downstream teams significantly, come up with estimated impact
  and reach out to the affected parties for approval (such as indexers, RPC providers, block
  explorers, etc.).
- In case of less tangible long term impact, evaluate on a case-by-case basis.
  - For example, in case of instructions we need to care about the ratio between the _sequential_
    per-ledger instructions and per-transaction instructions and keep it high enough (say, at
    least 4x).
  - We also need to care about some known limitations of the future protocols, e.g. synchronization
    stages in the proposed parallelization approach introduce yet another limit on maximum
    per-transaction instructions.
    - Use benchmarks to ensure that per-transaction limits remain compatible with current
      stage-level timing and capacity assumptions. Record those assumptions in the evaluation
      rather than relying on historical values.
    - This doesn't mean though that we can't also work around these issues while designing the
      protocol changes.

Once the evaluation is complete, the Core team updates the SLP's `Technical Evaluation` section
with its methods, findings, recommended values, and any required downstream approvals.