# Contributing CAPs

 1. Review [CAP-0001](cap-0001.md).
 2. Fork the repository by clicking "Fork" in the top right.
 3. Add your CAP to your fork of the repository. There is a [template CAP here](../cap-template.md).
 4. Add a link to your CAP proposal in this document, linking to the appropriate `/core/cap-XXXX.md`
 4. Submit a Pull Request to Stellar's [protocol repository](https://github.com/stellar/protocol).

Your first PR should be a first draft of the CAP. It must follow the template.

An editor will review the PR for a new CAP and ensure that its number is valid before before merging it.
A simple way to avoid conflicts with CAP numbers is to simply use the PR number as CAP number (requiring to add a new commit with the number when known).

Make sure you include a `Discussion` header with the URL to an open GitHub issue where people can discuss the CAP as a whole - typically an [issue](https://github.com/stellar/stellar-protocol/issues) in the protocol repository.

If your CAP requires images or other supporting files, they should be included in a subdirectory of the `contents` folder for that CAP as follows: `contents/cap-X` (for CAP **X**). Links should be relative, for example a link to an image from CAP-X would be `../contents/cap-X/image.png`.

For subsequent changes to your CAP, editors will only merge your PR after one of the CAP owners gives approval to do so (allowing for code review when needed).

When you believe your CAP is mature and ready to progress past the draft phase, you should open a PR changing the state of your CAP to 'Accepted'. An editor will review your draft and ask if anyone objects to accepting it. If the editor decides there is no rough consensus - for instance, because contributors point out significant issues with the CAP - they may close the PR and request that you fix the issues in the draft before trying again.

Once a CAP is implemented, a PR should be submitted to update its status to 'Final'.

# CAP status terms
* **Draft** - a CAP that is open for consideration.
* **Accepted** - a CAP that is planned for immediate adoption, i.e. expected to be included in a next version of the protocol.
* **Final** - a CAP that has been implemented (ie, changes fully merged into `stellar-core/master`).

# Summary list of all CAP proposals

Number             | Title                                    | Owner                 |   Status
------------------ | ---------------------------------------- | --------------------- | -------------
[0001](cap-0001.md)| Bump Sequence                            | Nicolas Barry         |   Final
[0002](cap-0002.md)| Transaction level signature verification | Nicolas Barry         |   Draft
[0003](cap-0003.md)| Asset-backed offers                      | Jonathan Jove         |   Draft
