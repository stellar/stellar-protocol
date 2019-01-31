# Stellar Ecosystem Proposals (SEPs)

## SEP Track Terms
* **Informational** — A SEP on the `Informational` track is one that is open to adoption by the
  ecosystem, but has not been formally standardized by SDF, and is not endorsed by SDF for
  adoption. Typically a SEP can start as `Informational` to gain traction within the ecosystem
  before moving to the `Standards` track.
* **Standard** — A SEP on the `Standards` track is one that aims for formal standardization and
  endorsement by SDF for adoption. Typically a Standard has a higher bar towards acceptance, and it
  requires approval by 2 SDF members of the SEP Team.

## SEP Status Terms
* **Archived** - A SEP that did not head towards a disposition due to a lack of consensus _and_
  support. Generally open to revival with additional edits.
* **Draft** - A SEP that is currently open to discussion and feedback.
* **FCP** - A SEP that has entered the Final Comment Period (FCP), and has one week remaining
  for final feedback before being accepted.
* **Accepted** - A SEP that is intended for immediate adoption by the entire ecosystem.

## Accepted Proposals

| Number | Title | Author | Track |
| --- | --- | --- | --- |
| [SEP-0001](sep-0001.md) | stellar.toml specification | SDF | Standard |
| [SEP-0002](sep-0002.md) | Federation Protocol | SDF | Standard |
| [SEP-0003](sep-0003.md) | Compliance Protocol | SDF | Standard |
| [SEP-0004](sep-0004.md) | Tx Status Endpoint | SDF | Standard |
| [SEP-0005](sep-0005.md) | Key Derivation Methods for Stellar Accounts | SDF | Standard |
| [SEP-0006](sep-0006.md) | Anchor/Client Interoperability | SDF | Standard |
| [SEP-0007](sep-0007.md) | URI Scheme to facilitate delegated signing | Interstellar | Standard |
| [SEP-0008](sep-0008.md) | Regulated Assets | Interstellar | Standard |
| [SEP-0009](sep-0009.md) | Standard KYC / AML Fields | SDF | Standard |
| [SEP-0010](sep-0010.md) | Stellar Web Authentication | Sergey Nebolsin, Tom Quisel | Standard |
| [SEP-0011](sep-0011.md) | Txrep: Human-Readable Low-Level Representation of Stellar Transactions | David Mazières | Standard |
| [SEP-0012](sep-0012.md) | Anchor/Client Customer Info Transfer | Interstellar | Standard |

# Contribution Process

The Stellar Ecosystem, like most software ecosystems in the world, continues to evolve over time to
meet the needs of our network's participants and to drive technology forward into new territory.

Unlike Stellar's Core development (CAPs), Stellar's Ecosystem Proposals are intended to be a more
dynamic way of introducing standards, protocols utilized in the ecosystem that are built on top of
the Stellar Network. It attempts to take a more lightweight process for approval, and much of its
process is inspired by the [IETF][ietf].

Before contributing, consider the following:

- Choose a track to propose your idea on. The bar for accepting an `Informational` SEP is much
  lower than one for a `Standard`, and allows you to promote the SEP independently to gain feedback
  and traction before creating a Standard out of it. However, you should feel free to 
- Gather feedback from discussion on the dev mailing list and other forums, and utilize it to begin
  a draft proposal.
- Follow the proposal process listed below. If you're having difficulty moving the proposal
  forward, talk to the buddy that's assigned the SEP; they'll often have guidance on how to move
  things forward, as well as feedback regarding feasibility and how the proposal does or does not
  align with the Stellar Network's goals.

## SEP Process
### Pre-SEP (Initial Discussion)
Introduce your idea on the [stellar-dev mailing list](https://groups.google.com/forum/?utm_medium=email&utm_source=footer#!forum/stellar-dev)
and other community forums dedicated to Stellar.

- Make sure to gather feedback and alternative ideas — it's useful before putting together a
  formal draft!
- Consider contacting experts in a particular area for feedback while you're hashing out the
  details.

### Creating a SEP Draft
Draft a formal proposal using the [SEP Template](../sep-template.md), and submit a PR to this
repository. You should make sure to adhere to the following:

* Use two unique words separated by a hyphen for your SEP number from the
  [BIP-0039 wordlist][wordlist]. For example, "amazing-crystal". Don't assign a number to the SEP
  — this will be established once the SEP has reached the state of `Accepted`.
* Add a link to the SEP proposal to the proposals table in this document.
* If your SEP requires images or other supporting files, they should be included in a subdirectory
  of the `contents` folder for that SEP, such as `contents/sep-amazing-crystal` (for SEP
  **amazing-crystal**). Links should be relative, for example a link to an image from SEP-X would
  be `../contents/cap-X/image.png`. *Once accepted, the folders will be renamed.*

Finally, submit a PR of your draft via your fork of this repository.

### Reaching SEP Approval
* A SEP buddy is assigned from the SEP team. They'll also provide initial feedback, and help pull
  in any subject matter experts that will help in pushing the SEP towards a final disposition.
  * For the Informational Track, the SEP enters FCP when 2 members of the SEP Team approve the pull
    request.
  * For the Standards Track, the SEP enters FCP when 3 members of the SEP team approve the pull
    request, 2 of whom must be representatives of SDF.
  * The SEP buddy (the PR assignee) is responsible for including members of the SEP team who are
    subject experts on the SEP being discussed; however, you are free to pull in feedback without
    going through your buddy. The SEP buddy may also bring it up at an upcoming protocol meeting.
  * If any SEP has major concerns (typically around security) from a SEP Team or CAP Core Team
    member, the concerns must be addressed before moving it forward; otherwise, it moves towards
    rejection.
* Once a SEP has been approved, it goes into FCP which is broadcast to the protocol meeting members
  along with the mailing list.
* If no major concerns are brought up, the SEP is Accepted.
* Regardless of disposition, the SEP buddy is responsible for the following for closing the pull
  request:
  * If the SEP is `Accepted`, they need to mark it as `Accepted` and update all SEP numbers to the
    next available number on the pull request before merging it in. **If you can, offer to help!**
  * If the SEP is `Archived`, they will mark it as archived in the proposal and move it to the
    `ecosystem/archive` folder before merging in the pull request.
  * Regardless, all pull requests are merged in to keep a record of the archive in the repository.

## SEP Team Members

**SEP Team**: Tomer (SDF), Nikhil (SDF) Tom Q. (SDF), Jeremy, Johnny (SDF), orbitlens, David (SDF),
Jed (SDF)

[wordlist]: https://github.com/bitcoin/bips/blob/master/bip-0039/english.txt
[ietf]: https://ietf.org/
