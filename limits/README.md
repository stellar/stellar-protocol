# Stellar Limits Proposals (SLPs)

## Summary

This document list the considerations that go into smart contract resource limit updates (mostly increases) and introduces a proposal process for performing the resource limit updates, similar to the CAP/SEP processes.

## Limits Overview

Smart contract execution on Stellar is guarded by various resource limits that ensure that:

- a transaction doesn't consume more resources than it requested
- a transaction can't request more resources than allowed by the protocol (per-transaction resource limit)
- cumulative resources in a given ledger don't exceed the value defined by the protocol (ledger-wide resource limit)

The resource and limit semantics are specified in detail in [CAP-46-07](../core/cap-0046-07.md).

## Reducing the limits

While the focus of this document is limit increases, it’s important to mention when and why the limits can be decreased.

The reason for the decrease should be network-wide emergency (e.g. significant ledger close time slow-down or nodes getting out of sync). While ideally we’d like to avoid that and do benchmarking and testing, there is always a chance that the behavior in the real network differs from any test performed.   

The ledger-wide limits technically can be reduced down to at least the respective per-transaction limit, but since the main reason for decrease is likely to be reverting an overly optimistic increase, these would mostly just be rollbacks. Another prominent reason for decreasing the ledger-wide limits is the potential for the ledger close latency decrease, i.e. if the network will close more ledgers per unit of time, but every ledger includes less transactions than before. In either scenario the proposal is likely to be exempt from the process described in this document.

The per-transaction limits should normally not be decreased at all, making ***per-transaction limit increases basically irreversible***. As a consequence, ***per-transaction limit increases must be done fairly conservatively and thoughtfully***. The reason for this is that after the per-transaction limit is increased, anyone can start sending larger transactions to the network and build protocols that rely on the increased limits. Thus reducing the limit will likely break a number of protocols, which is something that the network should try to avoid at all costs.

Reduction of the per-transaction limit should be viewed as the ‘last resort’ measure in case if it causes serious network issues that can’t be quickly resolved.

## Key considerations for increasing the limits

### Why increase the limits?

The increase in resources should generally be motivated by demand. However, the notion of demand differs for ledger-wide and per-transaction limits. Note, that ‘demand’ doesn’t mean that a limit will be increased, it’s just a motivation to consider the increase at all.

- For ledger-wide limits, *the demand can be identified by sufficiently high surge pricing rate due to transactions not fitting into a certain limit*, or at least a significant percentage of ledgers being near the resource limit
  - This is a reactive approach. There is a possibility that Core team might need to take a proactive approach and increase the limits in preparation for launching a protocol that is expected to have high TPS (i.e. not in response to the existing network activity). This should rather be an exception though  
  - When the per-transaction limits are increased, it might be necessary to also increase the respective ledger-wide limits in order to maintain a high enough ratio between the limits
- For per-transaction limits, the demand is based on the needs of the protocols that run on Soroban.  
  - It’s not realistic to support each and every possible protocol, but in general Soroban should provide the capabilities for implementing the majority of protocols that exist on the other blockchains, with as little exceptions as possible  
    - More specifically, we should first and foremost looks for the protocols that align with the Stellar chain goals like any other permanent protocol changes (see CAP process)  
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
`ledger_apply_time = io_time + tx_apply_time`, where   
`io_time = read_time(ledger_read_entries, ledger_read_bytes) + write_time(ledger_write_entries, ledger_write_bytes) + meta_emit_time`, and  
`tx_apply_time = tx_execution_time(ledger_instructions)`  
`read_time`, `write_time` and `execution_time` functions are proportional to the respective ledger-wide limits.  
`meta_emit_time` has no ledger-wide limit and is proportional to the metadata size per ledger (see below).  

**Total size of metadata per ledger**  
`metadata_size = ledger_txs_size + entry_sizes_before_write + ledger_write_bytes + tx_events_size_bytes * num_txs`  
`entry_sizes_before_write` is technically limited by `ledger_read_bytes`, but that’s rather an upper bound and a more realistic estimate for this is `ledger_write_bytes`.  

**Total history size per ledger**  
`history_size = ledger_txs_size + result_size * num_txs`, where `result_size` is a small constant value

### Transactions per ledger ratio

Besides the resource-specific direct impact of any limit increase, there is always a factor of the transaction prioritization and transaction set building.   

Core prioritizes Soroban transactions using only the flat inclusion fee that is completely independent of the resources that the transaction demands. This approach makes the fee model simpler and keeps the fees reasonably low for more complex protocols. The downside is that transaction sets that the Core builds are not optimized for the maximum throughput TPS- and fee-wise (for example, Core might build a transaction set with 2 large transactions with 1001 stroops fee instead of a transaction set with 20 small transactions with 1000 stroops fee each). This issue is mostly alleviated by the high enough ratio between the ledger limit and transaction limit for every resource.  

Basically, every per-transaction limit increase results in a decrease of the ratio with the ledger-wide limit. Thus most of the time we’ll need to consider increasing the ledger-wide limit together with increasing the per-transaction limit, even if there is no immediate need for that. For example, if the current ratio is 10 and the increase of per-transaction limit moves it down to 7 (that is still above the “target” of 5), we might be fine with changing only the transaction limit.   
For reference, here are the current (‘phase 5’) ratios between the per-transaction and ledger-wide limits:

| Resource | Per-ledger limit | Per-tx limit | Ratio (ledger/tx) |
| :---- | :---- | :---- | :---- |
| Instructions | 500M | 100M | 5 |
| Read entries | 200 | 40 | 5 |
| Write entries | 125 | 25 | 5 |
| Read KB | 500 KB | 200 KB | 2.5 |
| Write KB | 143 KB | 132 KB | 1.08 |
| Tx size KB | 133 KB | 132 KB | 1.007 |

The write KB and transaction size ratios are currently notably low due to technical limitations; this should be addressed eventually.

## Process for increasing the limits

*Note: initially, most of the process will be handled by the Core development team, as the tools and methodologies are still under development. Eventually the benchmarking tooling might become mature enough to allow for mostly 'self-service' proposals.*

*Note: the thresholds here are not final and are subject to change.*  

Based on the key considerations above, here is a sketch for the limit update process that will be documented in a dedicated document: Stellar Limits Proposal (SLP). The exact template is TBD.

**Step 1 \- Identify the resources in demand**  
There are a few options for this:

- Based on the ecosystem requests (may affect both per-transaction and ledger-wide  limits)
  - Ecosystem requests should demonstrate the necessity of the increase, specifically:  
    - How the protocol aligns with Stellar goals (similar to CAP alignment section)  
    - Why the existing limits are not sufficient (e.g. protocol requirements upper bound is clearly above the existing limit)  
- For ledger-wide limits, based on the observed ledger utilization  
  - E.g. The resource is at 90+% of capacity for 10+% of the ledgers  
    - While it’s intentional for some ledgers to be surge priced (especially in case of spam/arbitrage activity), it’s important to analyze the network activity and scale up in case of actual organic growth (or to at least allow non-spammy traffic to be applied as well)  
- For per-transaction limits, based on the network usage patterns  
  - E.g. The resource is at 80+% of transaction limit for 10+% of transactions  
    - Besides straightforward indication of the presence of more complex protocols on the network, we need to keep custom accounts in mind \- using the protocol that’s already ‘on the edge’ of the resource limit may be simply impossible for some custom accounts, which is why some leeway is necessary
- Based on Core protocol advancements  
  - E.g. we should be able to ‘fix’ the write limit ratios with the full launch of State Archival

**Step 2 \- Come up with the desired numbers**  
Based on the signal from step 1 we need to come up with the actual limits to adjust. If the demand is based on the network usage, we need to figure out the desired increase that should satisfy the needs. Even if there is a straightforward request (e.g. raise a certain per-transaction limit by 50%), we need to consider increasing the respective ledger limit in order to maintain a high enough ratio.  
Here are some basic rule ideas:

- For the ledger capacity (in case of resource causing surge pricing), we can go with as high value as technically feasible within e.g. 2x of the current limit  
- For the per transaction capacity, aim at making an increase that would make 95+% of transactions to have \<70% resource utilization  
- Maintain the ledger/transaction ratio high enough  
  - 5x is a reasonable lower bound  
  - Until the lower ratios from the initial launch haven’t been fixed, we should try to at least not reduce these further

**Step 3 \- Evaluate the proposed numbers**  
The proposed numbers have to be thoroughly verified against the actual network capabilities. Note, that the whole limits increase process assumes that the network doesn’t operate at the full potential capacity at the moment, e.g. due to performance optimizations or just due to conservative current limits.

- Most of the ledger-wide limits can be evaluated via apply-time benchmarks  
  - The goal is to be able to close 95+% of the ledgers within N ms on a model validator (where N is a moving target that is based on the available processing time for closing the ledgers). Currently the tentative value of N is 500 ms  
    - ‘Model validator’ is a bit imprecise, but we can’t benchmark every validator on one hand and expect them to have a proportional change in apply time on the other 
    - Note, that N might need to go *down* together with the ledger-wide limits in case if we prioritize the ledger close latency over individual ledger throughput. The important implication is that this adds a potential future limit to maximum *per-transaction* limits. This just reinforces the requirements around maintaining high enough ledger/transaction ratios, though in this case it’s likely mostly relevant for the resources that impact the ledger close time the most (CPU instructions, read entries)  
- Going forward we might also consider additional evaluations based on models (such as [this](https://github.com/stellar/stellar-core/blob/master/scripts/resource-calc.ipynb)), though this will likely only become relevant when we start getting closer to the hardware limits  
- The transaction size limits (both per-ledger and per-transaction) need to be exercised in Supercluster tests to ensure there is no significant flooding TPS degradation  
- In case of changes that impact the downstream teams significantly, come up with estimated impact and reach out to the affected parties for approval (such as indexers, RPC providers, block explorers etc.)
- In case of less tangible long term impact, evaluate on case-by-case basis  
  - For example, in case of instructions we need to care about the ratio between the *sequential* per-ledger instructions and per-transaction instructions and keep it high enough (say, at least 4x)  
  - We also need to care about some known limitations of the future protocols, e.g. synchronization stages in the proposed parallelization approach introduce yet another limit on maximum per-transaction instructions  
    - We should be able to use benchmarking capabilities to ensure that per transaction limits are compatible with future work. As of right now, we would be looking at a “stage” taking in the order of 125ms (with a stage having enough capacity for 2-3 transactions as to ensure a sane ratio at the ledger level). Benchmarks can be run using stage limits as ledger limits and ensure that timing goals are met.  
    - This doesn’t mean though that we can’t also work around these issues while designing the protocol changes

The evaluation may have several outcomes:

- Everything is within the acceptable bounds, the proposal goes through unchanged  
- Limits can be increased only to a fraction of the desired number \- modify the proposal respectively  
  - This often may still be a satisfactory outcome, given that in a lot of cases any increase should improve the situation (e.g. reduce the surge pricing rate or reduce the risk of custom account not being able to interact with a protocol)  
- The limits can’t be increased at all or can be moved just marginally \- the proposal has to be rejected and reviewed again if/when Core is better suited to handle it.

**Step 4 \- Nominate the proposal**  
In case if the proposal has gone through evaluation, it can be nominated for the vote by the validators. The nomination can be supported by the evaluation results summary.  
