# Stellar Ecosystem Proposals (SEPs)
Stellar Ecosystem Proposals are open protocols that explain how to build interoperable infrastructure on top of the Stellar network. Each SEP addresses a specific problem, and walks through the motivation, specification, and design rationale for a suggested solution. By creating common standards and structures for implementation, SEPs allow broad interaction between ecosystem participants. 

## SEP Status Terms
* **Draft** - A proposal that is currently in discussion and undergoing revision.  Drafts remain as pull requests until approved.
* **Active** - A proposal intended for adoption by the entire ecosystem.  Before a SEP is marked active, there has to be a functioning prototype or reference implementation.
* **Deprecated** - A SEP that was previously Active, but is no longer suggested for use. 

## Active Proposals

| Number | Title | Author |
| --- | --- | --- |
| [SEP-0001](sep-0001.md) | stellar.toml specification | SDF |
| [SEP-0002](sep-0002.md) | Federation Protocol | SDF |
| [SEP-0004](sep-0004.md) | Tx Status Endpoint | SDF |
| [SEP-0005](sep-0005.md) | Key Derivation Methods for Stellar Accounts | SDF |
| [SEP-0007](sep-0007.md) | URI Scheme to facilitate delegated signing | Interstellar |
| [SEP-0008](sep-0008.md) | Regulated Assets | Interstellar |
| [SEP-0009](sep-0009.md) | Standard KYC / AML Fields | SDF |
| [SEP-0010](sep-0010.md) | Stellar Web Authentication | Sergey Nebolsin, Tom Quisel |
| [SEP-0011](sep-0011.md) | Txrep: Human-Readable Low-Level Representation of Stellar Transactions | David Mazières |
| [SEP-0012](sep-0012.md) | Anchor/Client Customer Info Transfer | Interstellar |
| [SEP-0018](sep-0018.md) | Data Entry Namespaces | Mister.Ticot |
| [SEP-0020](sep-0020.md) | Self-verification of validator nodes | Johan Stén |
| [SEP-0024](sep-0024.md) | Simplified Anchor/Client Interoperability | SDF |
| [SEP-0028](sep-0028.md) | XDR Base64 Encoding | SDF |
| [SEP-0029](sep-0029.md) | Account Memo Requirements | OrbitLens, Tomer Weller, Leigh McCulloch, David Mazières |

### Drafts
**Note: we'd need to figure out what to do with these: accept, deprecate, or somehow move back into PR**
| Number | Title | Author |
| --- | --- | --- |
| [SEP-0014](sep-0014.md) | Dynamic Asset Metadata | OrbitLens, Paul Tiplady |
| [SEP-0015](sep-0015.md) | Attachment Convention | Interstellar |
| [SEP-0016](sep-0016.md) | Account Transfer Permissionless Payment Protocol (@p2p) | Jeremy Rubin |
| [SEP-0017](sep-0017.md) | Issuer account funding protocol (CAP-13 Based) | Tom Quisel |
| [SEP-0019](sep-0019.md) | Bootstrapping Multisig Transaction Submission | Paul Selden, Nikhil Saraf |
| [SEP-0021](sep-0021.md) | On-chain signature & transaction sharing | Mister.Ticot |
| [SEP-0022](sep-0022.md) | IPFS Support | Samuel B. Sendelbach |
| [SEP-0023](sep-0023.md) | Augmented strkey format for multiplexed addresses | David Mazières and Tomer Weller |

### Deprecated Proposals

| Number | Title | Author |
| --- | --- | --- |
| [SEP-0003](sep-0003.md) | Compliance Protocol | SDF |
| [SEP-0006](sep-0006.md) | Anchor/Client Interoperability | SDF |
| [SEP-0013](sep-0013.md) | DEPOSIT_SERVER proposal | @no, @ant, @manran, @pacngfar |

## SEP Process
The process for creating and discussing SEPs is open—meaning anyone can participate in any part of it—and it’s designed to be nimble enough to keep up with the evolving needs of the ecosystem.  Unlike their cousins, Core Advancement Proposals (CAPs), SEPs do not require a change to the Stellar protocol itself, so the burden for acceptance is much lower.
 
That said, there are still clear stages and requirements, and a SEP needs to have a reference implementation before it’s accepted.  

### Overview of the SEP process
Gather feedback → Draft a PR → Broadcast to channels → Discuss and revise in PR → Build reference implementation →  Merge to Active

### Gather feedback (optional)
Before drafting a SEP, you may want to gather suggestions and insights from other ecosystem participants.  The best way to do that: create a Github issue in this repository that outlines the problem you’re planning to address and post a message on the [stellar-dev mailing list](https://groups.google.com/forum/?utm_medium=email&utm_source=footer#!forum/stellar-dev) linking to the issue and asking for feedback.

### Draft a PR
To begin the SEP process, draft a proposal using the [SEP Template](../sep-template.md), and submit a PR via your fork to this repository. 

When creating the draft, make sure to:

* Use the following format for the filename of your draft:
  `sep_{shorttitle}.md`, for example `sep_newaccountdeposit.md`
* Place your SEP in the `ecosystem/` folder.
* Include GitHub handles or emails for all authors listed.  GitHub handles are preferred.

### Broadcast to channels
Once you have filed a draft PR, notify the [stellar-dev mailing list](https://groups.google.com/forum/?utm_medium=email&utm_source=footer#!forum/stellar-dev) by posting a message linking to it.  The SEP team will help spread the word by mentioning the discussion on Keybase and in the Stellar Dev Digest. 

### Discuss the PR
To keep things simple, drafts of SEPs will persist as pull requests during the discussion period.  All discussion of the draft will happen in the PR itself.  As the discussion unfolds, make sure to answer questions and revise the PR to correct problems and incorporate suggestions.

When the discussion tapers off, the SEP team will send out a notification to the stellar dev mailing list asking for final comments. 

### Build Reference Implementation or Prototype
Before a SEP is merged and deemed active, someone has to create a prototype or reference implementation demonstrating its viability.  **Add more info here about what that means**

### Merge to Active 
Once the SEP team has reviewed and approved the draft and implementation, they will merge the SEP, add a one-word name to end of file name, assign a number, and add it to the readme table.  At this point, a SEP is ready for others to implement.

### Versioning
**Note: need to figure out how to handle versioning**

### Deprecation process
It is possible for a SEP to move from `Active` to `Deprecated` if it is never adopted, or is abandoned by the community.
**Note: add more about how that process works**


## SEP Team Members
**Note: replace names with Github handles**
**SEP Team**: Tomer (SDF), Nikhil (SDF) Tom Q. (SDF), Michael (SDF), Alex (SDF), orbitlens, David (SDF), Jed
(SDF)


