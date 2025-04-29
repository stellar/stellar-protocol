## Preamble

```
SEP: TBD
Title: Contract Build Verification
Authors: OrbitLens <@orbitlens>, Nando Vieira <@fnando>
Track: Standard
Status: Draft
Created: 2024-09-28
Updated: 2025-03-12
Version: 0.4.0
Discussion: https://github.com/stellar/stellar-protocol/discussions/1573
```

## Simple Summary

A toolkit for the verification of the contract WASM build.

## Motivation

Stellar doesn't store the source code of contracts in the blockchain, so it may
be quite challenging for users to make sure that a contract they are going to
invoke is not malicious and behaves as advertised.

## Abstract

This SEP describes an approach to contract build verification using GitHub
Attestations. It provides the ability to display information about the contract
that's been deployed and the build pipeline that generated the WASM file.

This proposal makes no assumptions on how your WASM file is generated, but
requires developers to add a metadata entry to the WASM, as well as making an
artifact attestion using GitHub Actions.

Once the contract is deployed, anyone can verify and inspect the build pipeline
that generated the WASM file. It's important to be aware that this doesn't mean
that the contract is safe to use, but it does provide a way to verify how the
contract was built, by giving access to the workflow file that was used to
build the contract.

## Specification

The verification mechanism relies on the GitHub automation and
[Attestations](https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds)
build artifacts generated during the automated smart contract compilation. Each
attestation contains:

- Source code repository
- Environment variables
- Output binary hash (matches the hash of the contract WASM deployed on the
  ledger)
- Commit hash (required to point at a specific point-in-time codebase snapshot)
- Link to the workflow associated with the artifact (used to ensure the
  security of the compilation process)

In addition to the source code repository link, the workflow can also store a
home domain in the contract to provide a consistent off-chain organization
and/or token information resolution using a standard
[SEP-0001](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0001.md)
`stellar.toml` file.

During the compilation, the pipeline stores a repository address in every
compiled contract by adding WASM metadata to the `contractmetav0` custom
sections. Metadata is stored in the contract as `SCMetaEntry` XDR entry.
Downstream systems can retrieve this information directly from the WASM, read
repository contents and retrieve corresponding attestation from the GitHub API
endpoint:
`https://api.github.com/repos/<user_name>/<repo_name>/attestations/sha256:<wasm_hash>`,
where `wasm_hash` is the SHA256 hash of the contract WASM binary.

Metadata entries stored in the contract WASM:

- `source_repo=github:<user_name>/<repo_name>` - source repository link (e.g.
  `source_repo=github:reflector-network/reflector-dao-contract`)
- `home_domain=<domain_name>` - domain that hosts organization's `stellar.toml`
  (e.g. `home_domain=reflector.network`, no schema or path is allowed)

Based on this information anyone can verify the authenticity of the smart
contract source code, and perform a reverse lookup of the contract information
from the organization's domain.

## Design Rationale

Currently, the pipeline relies on GitHub platform tools and does not provide
the toolkit for other platforms, like GitLab or BitBucket. GitHub has the
largest market share, so the initial implementation utilized its standard APIs
and instruments. In the future, in response to the demand, similar automated
workflow can be created for other platforms as well. The `source_repo` metadata
record contains a platform prefix (`github:`) as an extension point for the
smooth integration of other repository hosting providers. In addition,
attestations can be also potentially stored on IPFS or other distributed
storage to increased the data availability.

Likewise, this SEP and workflow can be extended in the future to execute
automatic contract deployment to the network on build. However, this process
has a huge a list of potential security concerns which need to be evaluated,
addressed, and documented before including this functionality in the continuous
delivery pipeline.

## Attestation Verification Flow

Steps to assemble the trust chain between the deployed smart contract and the
source code repository:

1. Obtain a HEX-encoded WASM hash of the smart contract in question.
2. Download the corresponding WASM binary from the ledger.
3. Parse the binary to retrieve the metadata stored in `contractmetav0` custom
   sections.
4. Iterate through the entries to find the metadata with a `source_repo` key.
   Retrieve GitHub `user_name` and `repo_name` from the meta value stored in
   the format described above.
5. Load the attestation from
   `https://api.github.com/repos/<user_name>/<repo_name>/attestations/sha256:<wasm_hash>`.
   Parse the response as JSON.
6. Retrieve the encoded payload from the path
   `attestations[0].bundle.dsseEnvelope.payload`. The format follows
   [in-toto.io/Statement/v1](https://in-toto.io/Statement/v1) standard. Decode
   the payload as Base64 and parse resulting string as JSON.
7. Validate `subject[0].digest.sha256` to match the smart contract hash
   obtained at step 1.
8. Validate `predicate.buildDefinition.resolvedDependencies[0].uri` to match
   the GitHub repository obtained at step 4.
9. Field `predicate.buildDefinition.resolvedDependencies[0].digest.gitCommit`
   will contain the git commit hash at which the attestation has been produced.

If any of the above steps fail, the entire attestation verification process
fails.

### Workflow Setup and Configuration

#### Prerequisites

- Create a GitHub Actions workflow file `.github/workflows/release.yml` in your
  repository.
- Decide how the compilation workflow will be triggered. The recommended way is
  to configure workflow activation on git tag creation. This should simplify
  versioning and ensure unique release names.

#### Workflow Permissions

In order to create a release, the workflow needs `id-token: write`,
`contents: write` and `attestations: write permissions`. Default workflow
permissions for a repository can be found at "Settings" -> "Actions" ->
"Workflow permissions". It's important to specify permissions on the top level
in the workflow file itself:

```yml
permissions:
  id-token: write
  contents: write
  attestations: write
```

#### Example: Basic workflow using Stellar CLI

The following workflow uses
[Stellar CLI](https://developers.stellar.org/docs/tools/developer-tools/cli) to
build and optimize the contract.

```yml
---
name: Build and Release
on:
  push:
    # 1️⃣ Create a release whenever a new tag like `v0.0.0 is pushed.
    tags:
      - "v*"

  # 2️⃣ Create a release manually from GitHub's user interface.
  workflow_dispatch:
    inputs:
      release_name:
        description: "Release Version (e.g. v0.0.0)"
        required: true
        type: string

permissions:
  id-token: write
  contents: write
  attestations: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: rustup update
      - run: rustup target add wasm32-unknown-unknown
      - run: cargo version

      # 3️⃣ Set up env vars that will be used in the workflow.
      - name: Set up env vars
        run: |
          echo "WASM_FILE=target/wasm32-unknown-unknown/release/hello.wasm" >> $GITHUB_ENV

          if [ -n "${{ github.event.inputs.release_name }}" ]; then
            echo "TAG_NAME=${{ github.event.inputs.release_name }}" >> $GITHUB_ENV
          else
            echo "TAG_NAME=${{ github.ref_name }}" >> $GITHUB_ENV
          fi

      # 4️⃣ Set up the Stellar CLI.
      - uses: stellar/stellar-cli@v22.5.0
        with:
          version: 22.5.0

      # 5️⃣ Build the contract and mark the WASM with the current repository.
      - name: Build contract
        run: |
          stellar contract build \
            --meta home_domain=example.com \
            --meta source_repo=github:${{ github.repository }}

          stellar contract optimize --wasm ${{ env.WASM_FILE }}
          file=${{ env.WASM_FILE }}
          cp "${file%.*}.optimized.wasm" ${{ env.WASM_FILE }}

      # 6️⃣ Upload the WASM file to the artifacts.
      - name: Upload to Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: hello.wasm
          path: ${{ env.WASM_FILE }}

      # 7️⃣ Build the attestation for the wasm file.
      - name: Build Attestation for Release
        uses: actions/attest-build-provenance@v1
        with:
          subject-name: hello.wasm
          subject-path: ${{ env.WASM_FILE }}

      # 8️⃣ Make a new release.
      - name: Make a new Release
        id: release
        uses: actions/github-script@v7
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          script: |
            const response = await github.rest.repos.createRelease({
              owner: context.repo.owner,
              repo: context.repo.repo,
              tag_name: '${{ env.TAG_NAME }}',
              target_commitish: '${{ github.sha }}',
              make_latest: 'true'
            });

            const { data } = response;
            core.setOutput('release_id', data.id);

      # 9️⃣ Upload the wasm file to the release.
      - name: Upload to Release
        uses: actions/github-script@v7
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          script: |
            const fs = require('fs');
            const path = require('path');
            await github.rest.repos.uploadReleaseAsset({
              owner: context.repo.owner,
              repo: context.repo.repo,
              release_id: '${{ steps.release.outputs.release_id }}',
              name: path.basename('${{ env.WASM_FILE }}'),
              data: fs.readFileSync('${{ env.WASM_FILE }}'),
            });
```

## Security Concerns

This SEP does not create any direct security concerns for the Stellar protocol
or ecosystem applications.

Since the verification routine relies on the GitHub build automation and
attestation mechanism, this approach implies the trust in GitHub’s security. If
GitHub security is compromised, it means that verification data cannot be
trusted. The possibility of such an event looks very low considering the track
records of GitHub and its enterprise backers.

Unlike other building artifacts, attestations are stored in GitHub forever (or
at least until the code repository is removed). Therefore, if developers decide
to remove a smart contract repository, the verification chain may be broken.
However, downstream systems (like blockchain explorers) may retain the
verification information indefinitely, alleviating such risks.

While the build process itself is performed in the virtual GitHub environment
shielded from an external access, smart contract developers still can
potentially use some subtle techniques to inject malicious code into the
contract during the compilation phase. Protecting end users from malicious
developer actions is out of the scope of this SEP – the primary goal is to
provide unfalsifiable evidences that a contract has been compiled automatically
using a particular GitHub repository.

## Changelog

- `v0.4.0` - Simplify proposal by removing steps that don’t provide additional
  safety because they are easily circumvented.
- `v0.3.0` - Updated workflow to exclude the Docker image, clarified what
  attestation fields are used during the verification
- `v0.2.0` - Added `home_domain` meta, notes on meta XDR and format, design
  rationale for the GitHub platform lock-in
- `v0.1.1` - Defined metadata storage key format explicitly
- `v0.1.0` - Initial draft
