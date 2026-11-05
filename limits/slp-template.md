## Preamble

```
SLP: To Be Assigned
Title: <SLP title>
Working Group:
    Owner: <Person accountable for the SLP - name/email address/github alias>
    Authors: <List of comma separated name/email address/github alias>
    Consulted: <List of comma separated name/email address/github alias>
Status: Draft
Created: <date created on, in ISO 8601 (yyyy-mm-dd) format>
Discussion: <link to SLP discussion https://github.com/orgs/stellar/discussions/categories/stellar-limits-proposals>
Protocol version: TBD
```

## Simple Summary

A short, layman-accessible explanation of the proposed limit change(s): which resource(s) are being
adjusted and at a high level, why.


## Motivation

The increase in resources should generally be motivated by demand. However, the notion of demand
differs for ledger-wide and per-transaction limits. Note that 'demand' doesn't mean that a limit
will be increased, it's just a motivation to consider the increase at all.

- For ledger-wide limits, _the demand can be identified by sufficiently high surge pricing rate due
  to transactions not fitting into a certain limit_, or at least a significant percentage of
  ledgers being near the resource limit.
  - This is a reactive approach. There is a possibility that the Core team might need to take a
    proactive approach and increase the limits in preparation for launching a protocol that is
    expected to have high TPS (i.e. not in response to the existing network activity). This should
    rather be an exception though.
  - When the per-transaction limits are increased, it might be necessary to also increase the
    respective ledger-wide limits in order to maintain a high enough ratio between the limits.
- For per-transaction limits, the demand is based on the needs of the protocols that run on
  Soroban.
  - It's not realistic to support each and every possible protocol, but in general Soroban should
    provide the capabilities for implementing the majority of protocols that exist on the other
    blockchains, with as little exceptions as possible.
    - More specifically, we should first and foremost look for the protocols that align with the
      Stellar chain goals like any other permanent protocol changes (see CAP process).
  - Contract developers have some room for optimization. That said, it would be preferential to
    have optimization just impact the costs and not to be a hard requirement for doing more
    complex things on Soroban.

### Goals Alignment

Reference the [Stellar Network goals](../core/README.md#stellar-network-goals) that this proposal
advances. If the demand stems from a specific ecosystem use case, describe how that use case
aligns with those goals.

## Proposed Changes

Specify the resource(s) and the desired new limit value(s). For each affected limit, include:

- The current value, the source used to verify it, and the proposed new value.
- Whether the limit is per-transaction, ledger-wide, or both.
- If proposing a per-transaction limit increase, whether the corresponding ledger-wide limit also
  needs to be raised to maintain a healthy ledger/transaction ratio (see
  [Transactions per ledger ratio](slp-technical-evaluation.md#transactions-per-ledger-ratio)).

## Impact Assessment

To the extent possible, describe the expected impact of the change on the network and downstream
systems such as indexers, RPC providers, and block explorers. Authors are not required to perform
benchmarking; the Core team will complete the
[technical evaluation](slp-technical-evaluation.md) during the `Awaiting Evaluation` phase.


## Proposing restriction on ledger keys

If the proposal restricts ledger keys using the mechanism introduced in
[CAP-0077](../core/cap-0077.md), see the `LedgerKey` types that are in scope and whether the proposal preserves the CAP-0077 exclusions
  for pool share trustlines and issuer trustlines. Please specify:

- The reason for putting restrictions on the ledger keys. For example, To remediate data corruption, or, To Limit the blast radius of a security vulnerability exploit.
- Provide links to the [Github SLP Discussion](https://github.com/orgs/stellar/discussions/categories/stellar-limits-proposals) page where this is being discussed. 
- Whether the limit applies to `keysToFreeze`, `keysToUnfreeze`, or both.


## Process for proposing the new limits

Here are the steps you should follow to draft a SLP. More details on the SLP process is in the [SLP README](README.md).
**Step 1 \- Identify the resources in demand**  
There are a few options for this:

- Based on the ecosystem requests (may affect both per-transaction and ledger-wide  limits)
  - Ecosystem requests should demonstrate the necessity of the increase, specifically:  
    - How the protocol aligns with [Stellar Network goals](../core/README.md#stellar-network-goals) 
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
Based on the signal from step 1, you need to come up with the actual limits to adjust. If the demand is based on the network usage, you need to figure out the desired increase that should satisfy the needs. Even if there is a straightforward request (e.g. raise a certain per-transaction limit by 50%), you need to consider increasing the respective ledger limit in order to maintain a high enough ratio.  

Here are some basic rule ideas:

- For the ledger capacity (in case of resource causing surge pricing), we can go with as high value as technically feasible within e.g. 2x of the current limit  
- For the per transaction capacity, aim at making an increase that would make 95+% of transactions to have \<70% resource utilization  
- Maintain the ledger/transaction ratio high enough  
  - 5x is a reasonable lower bound  
  - Until the lower ratios from the initial launch haven’t been fixed, we should try to at least not reduce these further

**Step 3 \- Create a Pull Request with Draft status**  
Once you create a draft SLP, Core team will evaluate the proposal by setting the status to ["Awaiting Evaluation"](README.md). 


## Justification of the Proposed Numbers

Based on the demand identified in the Motivation section, explain how the specific values in
Proposed Changes were chosen. The Core team will evaluate the numbers using the following
guidelines; authors are encouraged to address them up front.

**Identifying the resources in demand**

There are a few options for justifying that a limit needs to change:

- Based on ecosystem requests (may affect both per-transaction and ledger-wide limits)
  - Ecosystem requests should demonstrate the necessity of the increase, specifically:
    - How the protocol aligns with Stellar goals (similar to CAP alignment section)
    - Why the existing limits are not sufficient (e.g. protocol requirements upper bound is clearly
      above the existing limit)
- For ledger-wide limits, based on the observed ledger utilization
  - E.g. the resource is at 90+% of capacity for 10+% of the ledgers
    - While it's intentional for some ledgers to be surge priced (especially in case of
      spam/arbitrage activity), it's important to analyze the network activity and scale up in
      case of actual organic growth (or to at least allow non-spammy traffic to be applied as
      well)
- For per-transaction limits, based on the network usage patterns
  - E.g. the resource is at 80+% of transaction limit for 10+% of transactions
    - Besides straightforward indication of the presence of more complex protocols on the network,
      we need to keep custom accounts in mind - using a protocol that's already 'on the edge' of
      the resource limit may be simply impossible for some custom accounts, which is why some
      leeway is necessary
- Based on Core protocol advancements
  - E.g. we should be able to 'fix' the write limit ratios with the full launch of State Archival

**Coming up with the desired numbers**

Even if there is a straightforward request (e.g. raise a certain per-transaction limit by 50%), we
need to consider increasing the respective ledger limit in order to maintain a high enough ratio.
Some basic rule ideas:

- For the ledger capacity (in case of resource causing surge pricing), we can go with as high a
  value as technically feasible within e.g. 2x of the current limit.
- For the per-transaction capacity, aim at making an increase that would make 95+% of transactions
  have <70% resource utilization.
- Maintain the ledger/transaction ratio high enough.
  - 5x is a reasonable lower bound.
  - Until the lower ratios from the initial launch have been fixed, we should try to at least not
    reduce these further.


## Technical Evaluation

The Core team fills in this section during the ["Awaiting Evaluation"](README.md) phase using the
[technical evaluation guide](slp-technical-evaluation.md). Authors may pre-populate any
benchmarking, modeling, or downstream-impact data they already have. The completed section should
record the methodology, findings, final recommended values, and any required downstream approvals.
The evaluation may have several outcomes:

- Everything is within the acceptable bounds, the proposal goes through unchanged.
- Limits can be increased only to a fraction of the desired number - modify the proposal
  respectively.
  - This often may still be a satisfactory outcome, given that in a lot of cases any increase
    should improve the situation (e.g. reduce the surge pricing rate or reduce the risk of custom
    account not being able to interact with a protocol).
- The limits can't be increased at all or can be moved just marginally - the proposal has to be
  rejected and reviewed again if/when Core is better suited to handle it.

## Security Concerns

Describe any security implications of the proposed change. If the change has no material new
security concerns, briefly explain why (for example, because resource accounting and metering
semantics are unchanged and only numeric ceilings are adjusted).
