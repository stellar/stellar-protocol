# Core Advancement Proposals (CAPs)

## CAP Status Terms
* **Archived** - A CAP that did not head towards a disposition due to a lack of consensus _and_
  support. Generally open to revival with additional edits.
* **Draft** - A CAP that is currently open for consideration and actively being discussed.
* **Pending: [Acceptance/Rejection]** - A CAP that has entered a Final Comment Period (FCP) with an
  intended disposition. After one week has passed, during which any new concerns should be
  addressed, the SEP will head towards its intended disposition [**Accepted/Rejected**] or go
  back into a Draft state.
* **Accepted** - A CAP that has been formally accepted and is ready for implementation. It is
  expected to be included in a future version of the protocol.
* **Finalized** - A CAP that has been implemented in Stellar Core in the version specified.

## Proposals

| Number | Title | Author | Status |
| --- | --- | --- | --- |
| [CAP-0001](cap-0001.md) | Bump Sequence | Nicolas Barry | Finalized |
| [CAP-0002](cap-0002.md) | Transaction level signature verification | Nicolas Barry | Finalized |
| [CAP-0003](cap-0003.md) | Asset-backed offers | Jonathan Jove | Finalized |
| [CAP-0004](cap-0004.md) | Improved Rounding for Cross Offer | Jonathan Jove | Finalized |
| [CAP-0005](cap-0005.md) | Throttling and transaction pricing improvements | Nicolas Barry | Pending |
| [CAP-0006](cap-0006.md) | Add ManageBuyOffer Operation | Jonathan Jove | Pending |
| [CAP-0007](cap-0007.md) | Deterministic Account Creation | Jeremy Rubin | Draft |
| [CAP-0008](cap-0008.md) | Self Identified Pre-Auth Transaction | Jeremy Rubin | Draft |
| [CAP-0009](cap-0009.md) | Linear/Exterior Immutable Accounts | Jeremy Rubin | Draft |
| [CAP-0010](cap-0010.md) | Fee Bump Account | Jeremy Rubin | Draft |
| [CAP-0011](cap-0011.md) | Relative Account Freeze | Jeremy Rubin | Draft |
| [CAP-0013](cap-0013.md) | Change Trustlines to Balances | Dan Robinson | Draft |
| [CAP-0014](cap-0014.md) | Adversarial Transaction Set Ordering | Jeremy Rubin | Draft |
| [CAP-0015](cap-0015.md) | Bump Fee Transactions | OrbitLens | Draft |
| [CAP-0016](cap-0016.md) | Cosigned assets: NopOp and COAUTHORIZED_FLAG | David Mazières | Draft |
| [CAP-0017](cap-0017.md)| Update LastModifiedLedgerSeq If and Only If LedgerEntry is Modified | Jonathan Jove | Draft |
| [CAP-0018](cap-0018.md)| Fine-Grained Control of Authorization | Jonathan Jove | Pending |

# Contribution Process

## How the protocol changes

Software is never done. As the Stellar Protocol evolves we want to ensure that changes serve the values of the Stellar network. So as you are proposing protocol changes it is important to keep those in mind...

### Stellar Protocol Values
* The Stellar network should be secure and reliable, and should bias towards safety, simplicity, reliability and performance over new development.
* Simplicity towards the protocol - we should not over complicate the protocol itself, and the more outside of the core protocol, the better.
    * Embrace principle of modifying only the outermost layers possible, keeping innermost layers stable. Order of layers: historical / ledger XDR is innermost, then observable transaction semantics, then consensus XDR, then DB state, overlay XDR, unobservable tx semantics (eg. perf or bug fixes), Horizon semantics, public APIs, client libs.
    * Also embrace higher bar for acceptance as changes affect inner layers: implementation prototype, version migration logic, performance evaluation and testing needs go up the more intrusive a change. Don’t accept change proposals that are both intrusive and underdeveloped.
* Clarity of intent - new operations and functionality should be opinionated, and straightforward to use.
* User safety over additional functionality - minimize attack surface at the lowest levels.
* The Stellar network should run at scale and at low cost to all users.
    * In support of this, the Stellar network should support off-chain transactions, e.g. Starlight.
* The Stellar network should facilitate simplicity and interoperability with other protocols and networks.
    * In support of this, the Stellar network should facilitate side-chain transactions to enable sub-networks.
* The Stellar network should support decentralization wherever possible, but not at the expense of the majority of its values.
* It should be easy to develop projects using the Stellar Network
* The Stellar network should make it easy for developers of Stellar projects to create highly usable products
* The Stellar network should enable cross-border payments, i.e. payments via exchange of assets, throughout the globe, enabling users to make payments between assets in a manner that is fast, cheap, and highly usable.
    * In support of this, the Stellar network should support an orderbook that values simplicity over functionality, and one that primarily serves to enable cross-border payments.
    * In support of this, the Stellar network should facilitate liquidity as a means to enabling cross-border payments.
    * In support of this, the Stellar network should enable asset issuance, but as a means of enabling cross-border payments.
* The Stellar network should enable users to easily exchange their non-Stellar based assets to Stellar-based assets, and vice versa.



## CAP Process
These are the steps from [idea to deployment](https://www.youtube.com/watch?v=Otbml6WIQPo)
1. Idea is proposed on the core [mailing list](https://groups.google.com/forum/?utm_medium=email&utm_source=footer#!forum/stellar-dev)
2. Discussion on mailing list
3. Someone gathers and collates all the various proposals
4. Someone is picked to write a CAP for a given proposal. They then:
    * Fork the repository by clicking "Fork" in the top right.
    * Write the CAP in their fork of the repository. There is a [template CAP here](../cap-template.md). The first PR should be a first draft of the CAP. It must follow the template.
    * Add a link to the CAP proposal in this document, linking to the appropriate `/core/cap-XXXX.md`
    * If your CAP requires images or other supporting files, they should be included in a subdirectory of the `contents` folder for that CAP as follows: `contents/cap-X` (for CAP **X**). Links should be relative, for example a link to an image from CAP-X would be `../contents/cap-X/image.png`.
    * Drafts are numbered by the author but subject to change when made final
    * CAP is written and set as `Draft`
    * Submit a Pull Request to Stellar's [protocol repository](https://github.com/stellar/stellar-protocol).
5. Buddy is assigned (Jon, Graydon, Jeremy, Johnny, Orbitlens) and will merge your PR if you properly followed the steps above.
6. Discussion of the draft CAP will now take place on the mailing list. There should be some iteration between discussion and further PRs refining the CAP.
7. If the CAP is not receiving enough support the Buddy will mark as rejected and move it to the archive. Otherwise the CAP is moved to `Pending`. 
8. There is now one week for people to make final comments.
9. After that the CAP is discussed at the next protocol meeting.
10. Needs unanimous approval from (Nicolas, Jed, David) to become `Accepted` otherwise the CAP is `Rejected` or turned back to `Draft` with some comments.
11. Implementer is decided and that person starts implementing.
12. Once a CAP is implemented, a PR should be submitted to update its status to `Final`.



**CAP Key Members**: Nicolas, Jed, David

**CAP Buddies**: (Jon, Graydon, Jeremy, Johnny, Orbitlens)<BR>
Buddies are responsible for moving a CAP along the process. They should make sure the draft is either `Accepted` or `Rejected` in a timely manner.
