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

| Number | Title | Author | Status |
| ---- | --- | --- | --- |
| [CAP-0001](cap-0001.md) | Bump Sequence | Nicolas Barry | Final |
| [CAP-0002](cap-0002.md) | Transaction level signature verification | Nicolas Barry | Final |
| [CAP-0003](cap-0003.md) | Asset-backed offers | Jonathan Jove | Final |
| [CAP-0004](cap-0004.md) | Improved Rounding for Cross Offer | Jonathan Jove | Final |
| [CAP-0005](cap-0005.md) | Throttling and transaction pricing improvements | Nicolas Barry | Final |
| [CAP-0006](cap-0006.md) | Add ManageBuyOffer Operation | Jonathan Jove | Final |
| [CAP-0015](cap-0015.md) | Bump Fee Transactions | OrbitLens | Implemented |
| [CAP-0017](cap-0017.md) | Update LastModifiedLedgerSeq If and Only If LedgerEntry is Modified | Jonathan Jove | Accepted |
| [CAP-0018](cap-0018.md) | Fine-Grained Control of Authorization | Jonathan Jove | Accepted |
| [CAP-0019](cap-0019.md) | Future-upgradable TransactionEnvelope type | David Mazières | Accepted |
| [CAP-0020](cap-0020.md) | Bucket Initial Entries | Graydon Hoare | Final |
| [CAP-0024](cap-0024.md) | Make PathPayment Symmetrical | Jed McCaleb | Final |
| [CAP-0025](cap-0025.md) | Remove Bucket Shadowing | Marta Lokhava | Final |
| [CAP-0026](cap-0026.md) | Disable Inflation Mechanism | OrbitLens | Final |
| [CAP-0027](cap-0027.md) | First-class multiplexed accounts | David Mazières and Tomer Weller | Accepted |
| [CAP-0028](cap-0028.md) | Clear pre-auth transaction signer on failed transactions | Siddharth Suresh | Accepted |
| [CAP-0030](cap-0030.md) | Remove NO_ISSUER Operation Results | Siddharth Suresh | Accepted |

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
| [CAP-0021](cap-0021.md) | Generalized transaction preconditions | David Mazières | Draft |
| [CAP-0022](cap-0022.md) | Invalid transactions must have no effects | David Mazières | Draft |
| [CAP-0023](cap-0023.md) | Two-Part Payments with PreparedTrustLineEntry and ClaimableBalanceEntry | Jonathan Jove | Draft |
| [CAP-0029](cap-0029.md) | AllowTrust when not AUTH_REQUIRED | Tomer Weller | Draft |

### Rejected Proposals
| Number | Title | Author | Status |
| --- | --- | --- | --- |
| [CAP-0016](cap-0016.md) | Cosigned assets: NopOp and COAUTHORIZED_FLAG | David Mazières | Rejected |
| [CAP-0013](cap-0013.md) | Change Trustlines to Balances | Dan Robinson | Rejected |

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
- Follow the proposal process listed below. If you're having difficulty moving the proposal
  forward, talk to the buddy that's assigned the CAP; they'll often have guidance on how to move
  things forward, as well as feedback regarding feasibility and how the proposal does or does not
  align with the Stellar protocol's goals and values.

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

* Use the following format for the filename of your draft: `cap_{github_username}_{shortsha256sum}.md`
  * `shortsha256sum` is defined as the first 8 characters of the SHA-256 checksum.
  * For example, a CAP by Github user `cryptocarnage` with a SHA-256 checksum of `a200f73c`
    would be titled `cap_cryptocarnage_a200f73c.md`.
* Make sure to place the draft in the `core/` folder.

Finally, submit a PR of your draft via your fork of this repository.

#### Additional Tips
* Use `TBD` for the protocol version. Don't assign a protocol version to the CAP — this will be
  established once the CAP has reached the state of *Final* and has been formally implemented.
* If your CAP requires images or other supporting files, they should be included in a sub-directory
  of the `contents` folder for that CAP, such as `contents/cap_cryptocarnage_a200f73/`. Links
  should be relative, for example a link to an image from your CAP would be
  `../contents/cap_cryptocarnage_a200f73/image.png`.

### Draft: Merging & Further Iteration
From there, the following process will happen:
* A CAP buddy is assigned and will merge your PR if you properly followed the steps above.
  * They'll rename the above files to the latest CAP draft number before merging in the PR.
  * They'll provide initial feedback, and help pull in any subject matter experts that will help in
    pushing the CAP towards a final disposition.
* You should continue the discussion of the draft CAP on the mailing list with an attempt at
  reaching consensus. We welcome any additional PRs that iterate on the draft.

### Draft -> Awaiting Decision
* When you're ready, you should submit a PR changing the status in the draft to `Awaiting Decision`.
* Your buddy will continue to help provide guidance on the CAP throughout the discussion — and will
  ultimately be responsible for deciding the CAP's next state:
  * If the CAP hasn't been sufficiently commented on by the community, your buddy will not change
    the status until its received enough discussion within the Stellar community.
  * If the CAP has not received enough support as a draft despite multiple iterations, your buddy
    can decide to mark the CAP as `Rejected` instead of moving forward to the rest of the core
    team.
  * If the CAP has received support and general consensus, it is moved to `Awaiting Decision`.
* The CAP will be scheduled to be discussed at the next protocol meeting. As the author of the
  proposal, you'll be invited to share your CAP and participate in discussion during the meeting.

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

**CAP Buddies**: Jon (SDF), Graydon (SDF), Orbitlens
