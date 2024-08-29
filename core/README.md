# Core Advancement Proposals (CAPs)

## CAP Status Terms

### Primary Workflow
* **Draft** — A CAP that is currently open for consideration and actively being discussed.
* **Awaiting Decision** — A mature and ready CAP that is ready for final deliberation by the CAP
  Core Team. After a maximum of three meetings, a vote will take place that will set the CAP's
  intended FCP disposition (**FCP: Acceptance/Rejection**) or go back into a **Draft** state.
* **FCP: [Acceptance/Rejection]** — A CAP that has entered a Final Comment Period (FCP) with an
  intended disposition. After one week has passed, during which any new concerns should be
  addressed, the CAP will head towards its intended disposition [**Acceptance/Rejection**] or go
  back into a Draft state.
* **Accepted** — A CAP that has been accepted on the merits of its idea pre-implementation, and is
  ready for implementation. It is still possible that the CAP may be rejected post-implementation
  due to the issues that may arise during an initial implementation.
* **Implemented** - A CAP that has been implemented with the protocol version specified in the CAP. It will graduate to
  **Final** when it has been formally accepted by a majority of validators (nodes) on the network.
* **Final** — A CAP that has been accepted by a majority of validators (nodes) on the network. A
  final CAP should only be updated to correct errata.

### Additional Statuses
* **Rejected** - A CAP that has been formally rejected by the CAP Core Team, and will not be
  implemented.
* **Superseded: [New Final CAP]** - A CAP that which was previously final but has been superseded
  by a new, final CAP. Both CAPs should reference each other.

## List of Proposals

| Number | Protocol Version | Title | Author | Status |
| ---- | --- | --- | --- | --- |
| [CAP-0001](cap-0001.md) | 10 | Bump Sequence | Nicolas Barry | Final |
| [CAP-0002](cap-0002.md) | 10 | Transaction level signature verification | Nicolas Barry | Final |
| [CAP-0003](cap-0003.md) | 10 | Asset-backed offers | Jonathan Jove | Final |
| [CAP-0004](cap-0004.md) | 10 | Improved Rounding for Cross Offer | Jonathan Jove | Final |
| [CAP-0005](cap-0005.md) | 11 | Throttling and transaction pricing improvements | Nicolas Barry | Final |
| [CAP-0006](cap-0006.md) | 11 | Add ManageBuyOffer Operation | Jonathan Jove | Final |
| [CAP-0015](cap-0015.md) | 13 | Fee Bump Transactions | OrbitLens | Final |
| [CAP-0017](cap-0017.md) | - | Update LastModifiedLedgerSeq If and Only If LedgerEntry is Modified | Jonathan Jove | Accepted |
| [CAP-0018](cap-0018.md) | 13 | Fine-Grained Control of Authorization | Jonathan Jove | Final |
| [CAP-0019](cap-0019.md) | 13 | Future-upgradable TransactionEnvelope type | David Mazières | Final |
| [CAP-0020](cap-0020.md) | 11 | Bucket Initial Entries | Graydon Hoare | Final |
| [CAP-0021](cap-0021.md) | 19 | Generalized transaction preconditions | David Mazières | Final |
| [CAP-0023](cap-0023.md) | 14 | Two-Part Payments with ClaimableBalanceEntry | Jonathan Jove | Final |
| [CAP-0024](cap-0024.md) | 12 | Make PathPayment Symmetrical | Jed McCaleb | Final |
| [CAP-0025](cap-0025.md) | 12 | Remove Bucket Shadowing | Marta Lokhava | Final |
| [CAP-0026](cap-0026.md) | 12 | Disable Inflation Mechanism | OrbitLens | Final |
| [CAP-0027](cap-0027.md) | 13 | First-class multiplexed accounts | David Mazières and Tomer Weller | Final |
| [CAP-0028](cap-0028.md) | 13 | Clear pre-auth transaction signer on failed transactions | Siddharth Suresh | Final |
| [CAP-0029](cap-0029.md) | 16 | AllowTrust when not AUTH_REQUIRED | Tomer Weller | Final |
| [CAP-0030](cap-0030.md) | 13 | Remove NO_ISSUER Operation Results | Siddharth Suresh | Final |
| [CAP-0033](cap-0033.md) | 14/15 | Sponsored Reserve with EphemeralSponsorshipEntry | Jonathan Jove | Final |
| [CAP-0034](cap-0034.md) | 14 | Preserve Transaction-Set/Close-Time Affinity During Nomination | Terence Rokop | Final |
| [CAP-0035](cap-0035.md) | 17 | Asset Clawback | Dan Doney | Final |
| [CAP-0038](cap-0038.md) | 18 | Automated Market Makers | Jonathan Jove | Final |
| [CAP-0040](cap-0040.md) | 19 | Ed25519 Signed Payload Signer for Transaction Signature Disclosure | Leigh McCulloch | Final |
| [CAP-0042](cap-0042.md) | - | Multi-Part Transaction Sets | Nicolas Barry | Final |
| [CAP-0046](cap-0046.md) | 20 |Soroban smart contract system overview | Graydon Hoare | Final |
| [CAP-0046-01 (formerly 0046)](cap-0046-01.md) | 20 | WebAssembly Smart Contract Runtime Environment | Graydon Hoare | Final |
| [CAP-0046-02 (formerly 0047)](cap-0046-02.md) | 20 | Smart Contract Lifecycle | Siddharth Suresh | Final |
| [CAP-0046-03 (formerly 0051)](cap-0046-03.md) | 20 | Smart Contract Host Functons | Jay Geng | Final |
| [CAP-0046-05 (formerly 0053)](cap-0046-05.md) | 20 | Smart Contract Data | Graydon Hoare | Final |
| [CAP-0046-06 (formerly 0054)](cap-0046-06.md) | 20 | Smart Contract Standardized Asset | Jonathan Jove | Final |
| [CAP-0046-07 (formerly 0055)](cap-0046-07.md) | 20 | Fee model in smart contracts | Nicolas Barry | Final |
| [CAP-0046-08 (formerly 0056)](cap-0046-08.md) | 20 |Smart Contract Logging | Siddharth Suresh | Final |
| [CAP-0046-09](cap-0046-09.md) | 20 | Network Configuration Ledger Entries | Dmytro Kozhevin | Final |
| [CAP-0046-10](cap-0046-10.md) | 20 | Smart Contract Budget Metering | Jay Geng | Final |
| [CAP-0046-11](cap-0046-11.md) | 20 | Soroban Authorization Framework | Dmytro Kozhevin | Final |
| [CAP-0046-12](cap-0046-12.md) | 20 | Soroban State Archival Interface | Garand Tyson | Final |
| [CAP-0051](cap-0051.md) | 21 | Smart Contract Host Functionality: Secp256r1 Verification | Leigh McCulloch | Final |
| [CAP-0053](cap-0053.md) | 21 | Separate host functions to extend the TTL for contract instance and contract code | Tommaso De Ponti | Final |
| [CAP-0054](cap-0054.md) | 21 | Soroban refined VM instantiation cost model | Graydon Hoare | Final |
| [CAP-0055](cap-0055.md) | 21 | Soroban streamlined linking | Graydon Hoare | Final |
| [CAP-0056](cap-0056.md) | 21 | Soroban intra-transaction module caching | Graydon Hoare | Final |

### Draft Proposals
| Number | Title | Author | Status |
| --- | --- | --- | --- |
| [CAP-0007](cap-0007.md) | Deterministic Account Creation | Jeremy Rubin | Draft |
| [CAP-0008](cap-0008.md) | Self Identified Pre-Auth Transaction | Jeremy Rubin | Draft |
| [CAP-0009](cap-0009.md) | Linear/Exterior Immutable Accounts | Jeremy Rubin | Draft |
| [CAP-0010](cap-0010.md) | Fee Bump Account | Jeremy Rubin | Draft |
| [CAP-0011](cap-0011.md) | Relative Account Freeze | Jeremy Rubin | Draft |
| [CAP-0012](cap-0012.md) | Deterministic accounts and creatorTxID | David Mazières | Draft |
| [CAP-0014](cap-0014.md) | Adversarial Transaction Set Ordering | Jeremy Rubin | Draft |
| [CAP-0022](cap-0022.md) | Invalid transactions must have no effects | David Mazières | Draft |
| [CAP-0032](cap-0032.md) | Trustline Preauthorization | Jonathan Jove | Draft |
| [CAP-0037](cap-0037.md) | Automated Market Makers | OrbitLens | Draft |
| [CAP-0041](cap-0041.md) | Concurrent Transactions | Leigh McCulloch, David Mazières | Draft |
| [CAP-0043](cap-0043.md) | ECDSA Signers with P-256 and secp256k1 Curves | Leigh McCulloch | Draft |
| [CAP-0044](cap-0044.md) | SPEEDEX - Configuration | Jonathan Jove | Draft |
| [CAP-0045](cap-0045.md) | SPEEDEX - Pricing | Jonathan Jove | Draft |
| [CAP-0057](cap-0057.md) | State Archival Persistent Entry Eviction | Garand Tyson | Draft |
| [CAP-0058](cap-0058.md) | Constructors for Soroban Contracts | Dmytro Kozhevin | Awaiting Decision |
| [CAP-0059](cap-0059.md) | Host functions for BLS12-381 | Jay Geng | Awaiting Decision |
| [CAP-0060](cap-0060.md) | Update to Wasmi register machine| Graydon Hoare | Awaiting Decision |

### Rejected Proposals
| Number | Title | Author | Status |
| --- | --- | --- | --- |
| [CAP-0013](cap-0013.md) | Change Trustlines to Balances | Dan Robinson | Rejected |
| [CAP-0016](cap-0016.md) | Cosigned assets: NopOp and COAUTHORIZED_FLAG | David Mazières | Rejected |
| [CAP-0031](cap-0031.md) | Sponsored Reserve | Jonathan Jove | Rejected |
| [CAP-0036](cap-0036.md) | Claimable Balance Clawback | Leigh McCulloch | Rejected |
| [CAP-0039](cap-0039.md) | Not Auth Revocable Trustlines | Leigh McCulloch | Rejected |
| [CAP-0048](cap-0048.md) | Smart Contract Asset Interoperability | Jonathan Jove | Rejected |
| [CAP-0049](cap-0049.md) | Smart Contract Asset Interoperability with Wrapper | Jonathan Jove | Rejected |
| [CAP-0050](cap-0050.md) | Smart Contract Interactions | Jonathan Jove | Rejected |
| [CAP-0052](cap-0052.md) | Smart Contract Host Functionality: Base64 Encoding/Decoding | Leigh McCulloch | Rejected |

# Contribution Process

The Stellar Protocol, like most software in the world, continues to evolve over time to meet the
needs of our network's participants and to drive technology forward into new territory. Given the
importance of the reliability and safety of the network, we ask that all of those who have ideas
towards pushing Stellar's protocol development forward adhere to the following:

- Consider your idea and how it serves the fundamental goals of the Stellar Network and aligns with
  values of the Stellar Protocol (which are listed below). If you cannot show how your proposal
  aligns with those goals and values, it's unlikely to ever be implemented.
- Gather feedback from discussion on the dev mailing list and other forums, and utilize it to begin
  a draft proposal, otherwise known as a CAP (Core Advancement Proposal).
- Follow the proposal process listed below.

## Stellar Network Goals
* **The Stellar Network should be secure and reliable, and should bias towards safety, simplicity,
  reliability, and performance over new functionality.**
* **The Stellar Network should run at scale and at low cost to all participants of the network.**
  * In support of this, the Stellar Network should support off-chain transactions, e.g. Starlight.
  * An explicit non-goal is limiting the hardware requirements of stellar-core to a personal
    computer.
* **The Stellar Network should facilitate simplicity and interoperability with other protocols and
  networks.**
  * In support of this, the Stellar Network should facilitate side-chain transactions to enable
    sub-networks.
* **The Stellar Network should enable cross-border payments, i.e. payments via exchange of assets,
  throughout the globe, enabling users to make payments between assets in a manner that is fast,
  cheap, and highly usable.**
    * In support of this, the Stellar Network should support an orderbook that values simplicity
      over functionality, and one that primarily serves to enable cross-border payments.
    * In support of this, the Stellar Network should facilitate liquidity as a means to enabling
    * cross-border payments.
    * In support of this, the Stellar Network should enable asset issuance, but as a means of
    * enabling cross-border payments.
* **The Stellar Network should support decentralization wherever possible, but not at the expense
  of the majority of its values.**
  * There should be no privileged actors — we should support egalitarianism and everyone
    participating on the same playing field.
* **The Stellar Network should enable users to easily exchange their non-Stellar based assets to
  Stellar-based assets, and vice versa.**
* **The Stellar Network should make it easy for developers of Stellar projects to create highly
  usable products.**

## Stellar Protocol Development Values
* **The Stellar Protocol should serve the goals of the Stellar Network.**
* **The Stellar Protocol should bias towards simplicity.**
  * When possible, solutions should be considered outside of core protocol changes such as via
    [SEPs (Stellar Ecosystem Proposals)](../ecosystem/readme.md) to minimize complexity in the
    Stellar protocol.
  * When possible, proposals should minimize the impact of changes to the smallest surface area and
    shallowest depth (i.e. sticking to the higher levels of the software) of the protocol
    architecture possible to make changes predictable and easier to test and reason about. Changes
    should be surgical, and minimal invasive. As a result, changes that affect lower levels of the
    implementation have a higher bar for acceptance.
  * In order from the lowest level to the highest level systems, the systems are:
    * Historical / Ledger XDR
    * Observable Transaction Semantics
    * Consensus XDR
    * DB State
    * Overlay XDR
    * Unobservable tx semantics (eg. performance or bug fixes)
    * Horizon semantics
    * Public APIs, Client Libraries/SDKs.
* **The Stellar Protocol should be clear, concise, and opinionated.**
  * New operations and functionality should be opinionated, and straightforward to use.
  * There should ideally be only one obvious way to accomplish a given task.
* **The Stellar Protocol should bias towards broad use cases, and bias against niche
    functionality.**
* **The Stellar Protocol should bias towards user safety.**

## CAP Process
These are the steps from [idea to deployment](https://www.youtube.com/watch?v=Otbml6WIQPo) on how
to create a Core Advancement Proposal (CAP).

### Pre-CAP (Initial Discussion)
Introduce your idea on the [stellar-dev mailing list](https://groups.google.com/forum/?utm_medium=email&utm_source=footer#!forum/stellar-dev).

* Make sure to gather feedback and alternative ideas — it's useful before putting together a
  formal draft!
* Consider contacting experts in a particular area for feedback while you're hashing out the
  details.

### Creating a CAP Draft
Draft a formal proposal using the [CAP Template](../cap-template.md), and submit a PR to this
repository. You should make sure to adhere to the following:

* Make sure to place the draft in the `core/` folder.
* Your CAP should be named `cap-TBD.md`
* If your CAP requires images or other supporting files, they should be included in a sub-directory
  of the `contents` folder for that CAP, such as `contents/cap-TBD/`. Links
  should be relative, for example a link to an image from your CAP would be
  `../contents/cap-TBD/image.png`.

Finally, submit a PR of your draft via your fork of this repository.

#### Additional Tips
* Use `TBD` for the protocol version. Don't assign a protocol version to the CAP — this will be
  established once the CAP has reached the state of *Final* and has been formally implemented.

### Draft: Merging & Further Iteration
From there, the following process will happen.

#### CAP gets merged
If you properly followed the steps above, your PR will get merged.

The CAP and associated files will get renamed based on the latest
CAP draft number before merging.

#### Assembling a working group

As your idea gets traction, you'll need to assemble a working group as
to increase the chances of success that this CAP proceeds through the stages.

For more information on this, review the [working group section](../cap-template.md#working-group) of the CAP template.

#### Iterating on the CAP

You should continue the discussion of the draft CAP on the mailing list
with an attempt at reaching consensus.

When opening PRs to modify the draft:
* changes have to either be submitted by one of the authors (Recommender or Owner) or
signed off by the authors
* avoid discussions in the PR itself as it makes it more difficult for future contributors to understand the rational for changes.
  * best is to always discuss in the mailing list.
  * alternatively, a recap of the discussion that happened in the PR could be posted in the mailing list (but it's easy to forget to do this).

### Draft -> Awaiting Decision

When your CAP received sufficient feedback from the community,
you'll need to present it to a subset of the CAP Core Team for review.

For that, when you're ready, you should submit a PR changing the status
in the draft to `Awaiting Decision`.

The CAP will be scheduled to be discussed at a protocol meeting.
As the owner of the CAP, you will be invited to share your CAP
and participate in discussion during the meeting.

You may invite any other members of your working group.

The protocol meetings will be used to decide on next step:
  * If the CAP has received support and general consensus, it is moved to `Awaiting Decision` ;
  * If the CAP requires some adjustments or needs to receive more feedback from the community, the meeting is adjourned ; 
  * If for any reason the CAP gets abandoned, it gets a status of `Rejected`.

### Awaiting Decision -> Final Comment Period (FCP)
* A vote will take place among the CAP Core Team.
  * A unanimous approval from the CAP Core Team will put the CAP in a `FCP: Accepted` status.
  * Otherwise, the CAP will be given feedback and head towards a `FCP: Rejected` status (if the
    majority of the CAP raises concerns) or a `Draft` status (if only a minority of the CAP
    raises concerns).
  * It can take upwards of 3 meetings before a disposition is reached.

### FCP -> Accepted/Rejected
* After a week of an Final Comment Period (FCP) where any major concerns that have not been
  previously addressed can be brought up, the CAP will head to its final disposition.
  * Concerns will be addressed on a case by case basis, and only major concerns that were not
    addressed earlier will move the CAP back to a `Draft` state.

### CAP Implementation

SDF will prioritize accepted CAPs among its priorities for a given year. However, if you want to
ensure your CAP is implemented in a timely manner, it is likely best for you to attempt to
implement it yourself.

Once a CAP is implemented, a PR should be submitted to update its status to **Implementation
Review**, along with the protocol version it was released in if applicable.

From here the proposal is brought up again before the protocol group for additional comment, where
it is possible that the proposal is rejected based on the issues that arise from its
implementation. If no issues arise, it will move to **Implemented** by a CAP team member.

### CAP Finalization

Once an implemented CAP has been released in a specified version, the CAP should be updated with
the protocol version that the implementation targets. From there, once a majority of validators on
the network have accepted the implementation, it will move to **Final**.

## CAP Team Members

**CAP Core Team**: Nicolas (SDF), Jed (SDF), David (SDF)
