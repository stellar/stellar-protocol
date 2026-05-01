# Stellar Limits Proposals (SLPs)

## Summary

This document introduces the proposal process for performing smart contract resource limit updates
(mostly increases), similar to the CAP/SEP processes.

The technical considerations that go into evaluating a limit change — what each resource impacts,
how to choose appropriate values, the ledger/transaction ratio, and how proposals are
benchmarked — live in [`slp-template.md`](../slp-template.md). Authors of an SLP should read the
template in full before drafting; this README focuses on process.

## Limits Overview

Smart contract execution on Stellar is guarded by various resource limits that ensure that:

- a transaction doesn't consume more resources than it requested
- a transaction can't request more resources than allowed by the protocol (per-transaction resource limit)
- cumulative resources in a given ledger don't exceed the value defined by the protocol (ledger-wide resource limit)

The resource and limit semantics are specified in detail in [CAP-46-07](../core/cap-0046-07.md).


## Contribution Process

Users of the network are encouraged to propose changes to Soroban resource limits through the Stellar
Limits Proposal (SLP) process. Unlike CAPs, SLPs are focused specifically on adjusting smart
contract resource limits (mostly increases) and follow a streamlined process tailored to that scope. 
The process to approve SLPs is a modified version of the [CAP-Process](../core/README.md#contribution-process).
From a technical standpoint, network settings are easier to understand than CAP changes but still require a well-balanced panel of reviewers and participants.
 
The Stellar Protocol, like most software in the world, continues to evolve over time to meet the
needs of our network's participants and to drive technology forward into new territory. Given the
importance of the reliability and safety of the network, we ask that all of those who have ideas
towards pushing Stellar's protocol development forward adhere to the following:
 
- Consider your idea and how it serves the fundamental [Stellar Network Goals](../core/README.md#stellar-network-goals) and aligns with
  [Stellar Protocol Values](../core/README.md#stellar-protocol-development-values). If you cannot show how your proposal
  aligns with those goals and values, it's unlikely to ever be implemented.
- Gather feedback from discussion on the dev mailing list and other forums, and utilize it to begin
  a draft SLP proposal.
- Follow the proposal process listed below.

## SLP Committee
Before limits get voted on by validators, an SLP needs to be signed-off by the SLP committee.
Committee members have the following roles and responsibilities:
* vote for/against an SLP, taking into account alignment to Stellar Network Goals, Protocol Development Values and critical parties such as validator operators and domain experts.
* review an SLP.
* provide feedback on SLP, especially when voting against a proposal.
 
Votes for/against should be recorded in a publicly accessible location.
 
This will be achieved by sending messages to the developer mailing list alongside feedback.
 
### SLP Committee Members
 
As the goal of the committee is to maximize the chances of success for proposals, members will be individuals representing each “tier 1” organization as calculated at the time of the decision.
 
Each organization will be represented by one individual during meetings and will identify themselves as such.
 
### SLP Committee consensus
The committee will reach decisions based on simple majority voting.
Note that while getting an SLP approved by the SLP committee increases the chance of it getting voted by the network, it does not guarantee its ratification when it comes to final vote performed by validators as that final vote depends on individual quorum configuration, and validator operator opinion on the SLP at the time of the vote.


## SLP Process
These are the steps from [idea to deployment](https://www.youtube.com/watch?v=Otbml6WIQPo) on how
to create a Stellar Limit Proposal (SLP).

### Pre-SLP (Initial Discussion)

Introduce your idea in one of
* [stellar-dev mailing list](https://groups.google.com/forum/?utm_medium=email&utm_source=footer#!forum/stellar-dev)
* [Stellar Protocol Discussion](https://github.com/stellar/stellar-protocol/discussions)

You should:
- Clearly describe which resource limit(s) you would like to see changed and why.
- Gather feedback from the community — others may have encountered the same limitation or have
  alternative suggestions.
- Consider contacting experts in a particular area for feedback while you're hashing out the
  details.

### Creating a SLP Draft
Draft a formal proposal and submit a PR to this repository. Your proposal should adhere to the following:
- Make sure to place the draft in the `limits/` folder.
- Your SLP should be named `slp-TBD.md` where TBD should be the next available SLP number.
- If your SLP requires images or other supporting files, they should be included in a sub-directory
  of the `contents` folder for that SLP, such as `contents/slp-TBD/`. Links
  should be relative, for example a link to an image from your SLP would be
  `../contents/slp-TBD/image.png`.
- **Motivation** — Demonstrate the necessity of the increase:
  - How the use case aligns with [Stellar Network goals](../core/README.md#stellar-network-goals).
  - Why the existing limits are not sufficient (e.g. your protocol's resource requirements clearly
    exceed the current limit).
- **Proposed Changes** — Specify the resource(s) and the desired new limit value(s). If you are
  proposing a per-transaction limit increase, consider whether the corresponding ledger-wide limit
  also needs to be raised to maintain a healthy ledger/transaction ratio (see
  [Transactions per ledger ratio](#transactions-per-ledger-ratio)).
- **Impact Assessment** — To the extent possible, describe the expected impact of the change on the
  network and downstream systems (indexers, RPC providers, block explorers, etc.). Refer to the
  [Key considerations for increasing the limits](#key-considerations-for-increasing-the-limits)
  section for guidance on what to consider.

Finally, submit a PR of your draft via your fork of this repository.

### Draft: Merging & Further Iteration

From there, the following process will happen.

#### SLP gets merged
If you properly followed the steps above and the PR meets the documented requirements, it can be merged after review by the appropriate maintainers.

#### Iterating on the SLP
 You should continue the discussion of the draft SLP at the location referenced from the “Discussion” contained in the SLP
with an attempt at reaching consensus.

When opening PRs to modify the draft:
- Changes have to either be submitted by one of the authors or signed off by the authors.
- Avoid discussions in the PR itself as it makes it more difficult for future contributors to understand the rationale for changes.
  - Best is to always discuss in the mailing list.
  - Alternatively, a recap of the discussion that happened in the PR could be posted in the mailing list (but it's easy to forget to do this).

### Draft -> Awaiting Evaluation
Once the proposal receives sufficient feedback from the community, the Core team will evaluate the proposed numbers against
the network's actual capabilities. This includes:

- Running apply-time benchmarks for ledger-wide limit changes.
- Assessing flooding and Supercluster test results for transaction size changes.
- Evaluating long-term impact on protocol development.
- Coordinating with downstream teams (indexers, RPC providers, etc.) if the changes significantly
  affect them.

The evaluation may result in the proposal being accepted as-is, accepted with modified numbers, or
rejected if the network cannot safely support the increase at this time.


### Awaiting Evaluation -> Awaiting Decision
 
When your SLP has undergone technical evaluation by the Core team,
you'll need to present it to the SLP Committee for review.
 
For that, when you're ready, you should
1. submit a PR changing the status in the draft to `Awaiting Decision`.
2. send an email to the developer mailing list with a subject line starting with “SLP TBD: Ready for review”
 
At this point the SLP committee will:
* review the SLP
* provide feedback
* optionally, schedule a discussion that will occur as a protocol meeting.
 
In the event of a live discussion being scheduled, as the owner of the SLP, you will be invited to share your SLP and participate in discussion during the meeting.
You may invite any other members of your working group.
 
At some point, the SLP committee:
* votes FOR the proposal, in which case its status is modified to “Accepted”. This signals validators to organize a vote to deploy changes to the public network.
* votes AGAINST the proposal, in which case its status is modified to “Rejected”. The SLP will not be discussed further by the committee.


### SLP Finalization: “Awaiting Decision -> Final”
Once an implemented SLP has been successfully ratified on the public network, it should be updated with a status of **Final** with the ledger number that corresponds to the vote.


### Additional Tips
- You do **not** need to perform benchmarking yourself. The Core team will handle benchmarking and
  technical evaluation of proposed limit changes as part of the review process (see Step 3 in
  [Process for increasing the limits](#process-for-increasing-the-limits)).
- Focus your proposal on clearly articulating the demand and justification — a well-motivated
  proposal with concrete data is more likely to move forward.
- If your proposal affects per-transaction limits, keep in mind that these increases are
  essentially irreversible (see [Reducing the limits](#reducing-the-limits)), so proposals should
  be well-justified.
