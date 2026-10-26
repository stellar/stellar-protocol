## Preamble

```
CAP: To Be Assigned
Title: Contract Signers for Stellar Accounts in Soroban Authorization
Working Group:
    Owner: Leigh McCulloch <@leighmcculloch>
    Authors: Leigh McCulloch <@leighmcculloch>
    Consulted: Dmytro Kozhevin <@dmkozh>, Tyler van der Hoeven <@kalepail>, Nicolas Barry <@MonsieurNicolas>, Anup Pani <@anupsdf>, Jake Urban <@jakeurban>, Tomer Weller <@tomerweller>
Status: Draft
Created: 2026-10-26
Discussion: https://github.com/orgs/stellar/discussions/1763
Protocol version: TBD
```

## Simple Summary

Allow a contract to be added as a signer of a Stellar account (G account). A contract
signer can authorize Soroban operations on behalf of the account, using the contract's own
`__check_auth` logic, but cannot sign transactions or be extra signers.

## Working Group

As specified in the Preamble.

## Motivation

Stellar accounts (G accounts) and contract accounts (C accounts) offer different trade-offs.

G accounts have broad support across the ecosystem: wallets, exchanges, custodians, anchors,
Horizon, SDKs, and tooling all understand them. Their authorization is limited to a fixed set
of signer types (ed25519 keys, pre-authorized transactions, hash preimages, and ed25519 signed
payloads) combined with weights and thresholds.

C accounts can implement any authorization logic in their `__check_auth` function, for example
passkeys (secp256r1/WebAuthn), multisig policies, spending limits, session keys, and recovery
schemes. But they are not yet supported as broadly as G accounts.

Today a user who wants custom authorization, such as a passkey wallet, has to move their funds and
identity to a C account. There is no way to keep a G account and add custom authorization to it.

This CAP lets a contract be a signer of a G account. The contract signer can authorize anything
the G account can authorize in Soroban, such as token transfers through the Stellar Asset
Contract and calls to other contracts. Users keep the G account and its existing ecosystem
support, and gain the programmable authorization of a contract.

For example:

- A wallet keeps an ed25519 device key as the G account's master key for everyday transactions,
  and adds a passkey-verifying contract as a signer, so the user can authorize Soroban payments
  with a passkey from a new device.
- A G account adds a contract signer that enforces a spending limit or an allow-list of
  contracts, and gives it enough weight to meet the medium threshold alone.

### Goals Alignment

This CAP is aligned with the following Stellar Network Goals:

- The Stellar Network should make it easy for developers of Stellar projects to create highly
  usable products.
- The Stellar Network should enable cross-border payments, i.e. payments via exchange of assets,
  throughout the globe, enabling users to make payments between assets in a manner that is fast,
  cheap, and highly usable.

## Abstract

This CAP adds a new signer key type, `SIGNER_KEY_TYPE_DELEGATE_CONTRACT`, which identifies a contract by
its contract ID. It can be added to an account with the existing `SetOptionsOp`, with a weight,
like any other signer.

Contract signers are ignored when checking transaction and operation signatures. They have
effect only in Soroban authorization, when a G account authorizes with address credentials
(`SOROBAN_CREDENTIALS_ADDRESS`). The signature format that the host accepts for a G account
is extended so that it can contain contract signatures next to ed25519 signatures. For each
contract signature, the host calls the contract's `__check_auth` function with the same
arguments it would pass if the contract were authorizing for itself. If the call succeeds,
the signer's weight is added to the total, and the total must meet the account's medium
threshold, as today.

No other changes are made to G accounts, classic operations, or the Soroban authorization
payload.

## Specification

### XDR changes

```diff
diff --git a/Stellar-types.x b/Stellar-types.x
--- a/Stellar-types.x
+++ b/Stellar-types.x
@@ enum SignerKeyType
 enum SignerKeyType
 {
     SIGNER_KEY_TYPE_ED25519 = KEY_TYPE_ED25519,
     SIGNER_KEY_TYPE_PRE_AUTH_TX = KEY_TYPE_PRE_AUTH_TX,
     SIGNER_KEY_TYPE_HASH_X = KEY_TYPE_HASH_X,
-    SIGNER_KEY_TYPE_ED25519_SIGNED_PAYLOAD = KEY_TYPE_ED25519_SIGNED_PAYLOAD
+    SIGNER_KEY_TYPE_ED25519_SIGNED_PAYLOAD = KEY_TYPE_ED25519_SIGNED_PAYLOAD,
+    SIGNER_KEY_TYPE_DELEGATE_CONTRACT = 4
 };
 
+typedef Hash ContractID;
+
 union PublicKey switch (PublicKeyType type)
@@ union SignerKey switch (SignerKeyType type)
 case SIGNER_KEY_TYPE_ED25519_SIGNED_PAYLOAD:
     struct
     {
         /* Public key that must sign the payload. */
         uint256 ed25519;
         /* Payload to be raw signed by ed25519. */
         opaque payload<64>;
     } ed25519SignedPayload;
+case SIGNER_KEY_TYPE_DELEGATE_CONTRACT:
+    /* Contract whose __check_auth must authorize. Usable only in Soroban
+       authorization, never for transaction signatures. */
+    ContractID contractID;
 };
@@ typedef PublicKey AccountID;
 typedef PublicKey NodeID;
 typedef PublicKey AccountID;
 
-typedef Hash ContractID;
-
 struct Curve25519Secret
```

The existing `ContractID` typedef is moved above `SignerKey` so that it can be used there.

`SIGNER_KEY_TYPE_DELEGATE_CONTRACT` is not tied to a `CryptoKeyType` value, because it is not a
cryptographic key.

### Semantics

#### Adding and removing contract signers

`SetOptionsOp` accepts a `signer` whose key is of type `SIGNER_KEY_TYPE_DELEGATE_CONTRACT`. Adding,
updating the weight of, and removing a contract signer follow the same rules as for every other
signer type:

- A contract signer is an account subentry, counts toward the limit of 20 signers, and requires
  a base reserve.
- Setting its weight to 0 removes it.
- It can be sponsored, and its sponsorship can be revoked with `RevokeSponsorshipOp` using
  `REVOKE_SPONSORSHIP_SIGNER`, like any other signer.
- `SetOptionsOp` does not check that the contract exists. As with an ed25519 signer, the
  account owner is responsible for adding a signer that can sign.

Signers on an account are sorted by `SignerKey`, as today. Because the new type has the highest
discriminant, contract signers sort after all other signer types.

Before the protocol upgrade, `SetOptionsOp` with a `SIGNER_KEY_TYPE_DELEGATE_CONTRACT` signer is invalid,
and the `SignerKey` value is rejected wherever XDR containing it is validated.

#### Transaction and operation signatures

Contract signers are never considered when checking the signatures of a transaction or of an
operation's source account. A contract signer contributes no weight toward the low, medium, or
high thresholds in those checks, and no `DecoratedSignature` can match it.

This also means a contract signer cannot authorize a Soroban invocation that uses
`SOROBAN_CREDENTIALS_SOURCE_ACCOUNT`, because those credentials are checked through the
transaction's signatures.

A `SIGNER_KEY_TYPE_DELEGATE_CONTRACT` key cannot be used as an extra signer in a transaction's
`PreconditionsV2.extraSigners`. A transaction whose `extraSigners` contains one is invalid and
fails with `txMALFORMED`.

#### Soroban authorization of G accounts

When the host authenticates a G account that uses `SOROBAN_CREDENTIALS_ADDRESS`, it computes
the `signature_payload` (the SHA-256 hash of the `ENVELOPE_TYPE_SOROBAN_AUTHORIZATION`
`HashIDPreimage`) and checks the `signature` `SCVal` against the account. This is unchanged.

Today the `signature` must be an `SCV_VEC` where each element is an `AccountEd25519Signature`:

```rust
#[contracttype]
struct AccountEd25519Signature {
    public_key: BytesN<32>,
    signature: BytesN<64>,
}
```

This CAP lets each element instead be an `AccountContractSignature`:

```rust
#[contracttype]
struct AccountContractSignature {
    contract: Address,
    signature: Val,
}
```

Both types are encoded as `SCV_MAP` with `SCV_SYMBOL` keys, as for any `#[contracttype]`
struct. The host tells them apart by their keys: a map with exactly the keys `public_key` and
`signature` is an `AccountEd25519Signature`, and a map with exactly the keys `contract` and
`signature` is an `AccountContractSignature`. Any other element is an error.

The host checks the signature vector as follows:

1. The vector must have between 1 and 20 elements, as today.
2. All `AccountEd25519Signature` elements must come before all `AccountContractSignature`
   elements.
3. `AccountEd25519Signature` elements must be in strictly increasing order of `public_key`, as
   today.
4. `AccountContractSignature` elements must be in strictly increasing order of `contract`. Each
   `contract` must be a contract address (`SC_ADDRESS_TYPE_CONTRACT`).
5. Rules 2 to 4 mean the elements are in strictly increasing order of the `SignerKey` they
   refer to, so the same signer cannot be used twice.
6. Each `AccountEd25519Signature` is verified exactly as today.
7. For each `AccountContractSignature`:
   1. The account must have a signer of type `SIGNER_KEY_TYPE_DELEGATE_CONTRACT` whose `contractID`
      matches `contract`, with weight greater than 0. Otherwise authentication fails, as it does
      today for an ed25519 key that is not a signer of the account.
   2. The host calls `__check_auth` on `contract` with these arguments:
      - `signature_payload`: the same `signature_payload` that ed25519 signers sign.
      - `signature`: the `signature` value from the element.
      - `auth_contexts`: the same authorization contexts, built from the authorized invocation
        tree, that the host passes when it authenticates a contract account.

      This is the same call, with the same reentry rules, that the host makes when it
      authenticates a contract account. If the contract is missing, has no `__check_auth`, or
      `__check_auth` fails, authentication fails.
8. The weights of all verified signers are added up. Authentication succeeds if the total is at
   least the account's medium threshold, as today.

When the host authenticates the contract signer, the G account's nonce is consumed and its
signature expiration is enforced, as today. The contract signer does not consume a nonce of its
own.

Nested authorization inside `__check_auth` (for example, the contract calling `require_auth`
on another address) follows the rules that already apply inside a contract account's
`__check_auth`.

#### Footprint

When a contract signer is used, the contract instance entry and its executable (for example its
`CONTRACT_CODE` entry) must be in the transaction's footprint, as with any contract call.
Recording-mode simulation adds them as it does for contract accounts.

#### Strkey

A `SIGNER_KEY_TYPE_DELEGATE_CONTRACT` signer key is shown as the contract's strkey (`C...`), as defined
in SEP-23. No new strkey version byte is needed.

## Design Rationale

### Scope

The discussion proposed several changes to make G accounts more programmable. This CAP covers
only one of them: contracts as signers of G accounts for Soroban authorization. It does not make
the account's signers manageable from Soroban, add a way to manage trustlines from Soroban, or
change how sponsorship applies to subentries. Those can be proposed separately, and this CAP
does not prevent any of them.

### No transaction signing

Contract signers cannot sign transactions. Transaction signatures are checked before the fee is
charged, and during flooding and transaction set validation. Running contract code at those
points would let anyone make validators run code without paying for it, and would make a
transaction's validity depend on contract state that can change between validation and
application.

The consequence is that a contract signer can do anything a G account can do in Soroban, but
cannot authorize classic operations such as `SetOptionsOp`, `ChangeTrustOp`, or a classic
`PaymentOp`. The G account must keep at least one classic signer that meets its thresholds for
classic operations and for paying transaction fees. Transaction fees for Soroban invocations
that a contract signer authorizes can be paid by another account, for example a relayer, a fee
bump, or a wallet service. This is the same model that C accounts use today.

### Reusing `__check_auth`

Contract signers reuse the existing `__check_auth` interface and arguments. Contracts that
already work as contract accounts, and the libraries that build them, can be used as G account
signers without changes. Wallet SDKs already know how to build the `signature` value for those
contracts. The authorization contexts let a contract signer apply policies (for example spending
limits) to the G account's invocations in the same way it applies them to its own.

A separate function (for example one that also receives the G account address) was considered.
It would let a contract know which account it is signing for, but it would need new contract
interfaces and would not work with existing contract accounts. The `signature_payload` that
ed25519 signers sign today does not include the account address either, so this CAP does not
change that property. See [Security Concerns](#security-concerns).

### Weight and thresholds

Contract signers use the same weights and the same medium threshold as other signers. This keeps
the account's existing model: an account can require a contract signer and an ed25519 key
together, or give either one enough weight to act alone.

### Signature encoding

The existing signature format is kept and extended, so all existing signatures stay valid and
SDKs only need to add support for the new element type. Requiring ed25519 elements first and
ordering within each type keeps signers unique with a simple check, and matches the order of
signers on the account.

### Signer key type

A new `SignerKey` type is the smallest change that lets an account record a contract and its
weight using existing operations, subentry accounting, sponsorship, and ledger entries. No new
ledger entry type or operation is needed.

## Protocol Upgrade Transition

### Backwards Incompatibilities

The protocol upgrade adds a new arm to `SignerKey`. Software that decodes XDR containing a
`SignerKey`, such as `AccountEntry`, `SetOptionsOp`, `RevokeSponsorshipOp`, and
`LedgerKey`s for signer sponsorship, must be updated to decode the new type. This affects
Horizon, RPC, SDKs, block explorers, wallets, and indexers.

Software that lists an account's signers and assumes every signer can sign transactions should
learn that contract signers cannot. For example, a wallet that computes whether it can meet a
threshold for a classic transaction must ignore contract signers.

No existing behavior changes for accounts that do not add contract signers. Existing Soroban
signatures for G accounts stay valid.

### Resource Utilization

Using a contract signer runs the contract's `__check_auth`, which is metered and charged to the
transaction like any other contract call. Each contract signer adds read entries to the footprint.
Accounts that do not use contract signers have no extra cost. A contract signer uses the same
storage as any other signer on the account.

## Security Concerns

- **Contract trust.** Adding a contract signer gives that contract's `__check_auth` the
  authority of its weight over the account's Soroban authorizations. If the contract is
  upgradable, whoever can upgrade it can change that logic. Users and wallets should add only
  contracts they trust, and should know who can upgrade them.
- **Limited scope.** Contract signers cannot sign transactions, so a compromised contract signer
  cannot change the account's signers or thresholds, change trustlines, merge the account, or
  make classic payments. It can authorize any Soroban invocation that the G account can
  authorize, including transfers of the account's balances through the Stellar Asset Contract.
- **Replay across accounts.** The `signature_payload` does not include the address being
  authorized. If the same contract signer (with the same internal keys) is a signer of more
  than one account, a signature it produces for one account may be valid for another account
  with the same nonce, expiration, and invocation. This is the same property ed25519 signers
  have today when they are shared between accounts. Contracts that need to tell accounts apart
  can include account-specific data in their own `signature` format.
- **Shared contract accounts.** A contract that is also used as a C account receives the same
  `__check_auth` call whether it authorizes for itself or as a signer of a G account. Its
  policies apply to the authorization contexts it is given, which are the G account's
  invocations in the signer case.
- **Unavailable contracts.** If a contract signer's entries are archived, it cannot authorize
  until they are restored. If the contract is deleted or cannot authorize, the account's other
  signers still work. Accounts should not rely on a contract signer as their only way to meet
  thresholds that they cannot otherwise meet.
- **Denial of service.** `__check_auth` runs only during transaction application, within the
  transaction's resource limits, after fees have been charged. It never runs during transaction
  validation.

## Test Cases

TBD. Test cases should cover at least:

- Adding, updating, and removing a contract signer with `SetOptionsOp`, including sponsorship,
  subentry limits, and reserves.
- `SetOptionsOp` with a contract signer before the protocol upgrade is rejected.
- Contract signers never contribute to transaction or operation signature thresholds.
- Soroban authorization of a G account with only a contract signer, with ed25519 signers and a
  contract signer together, and with several contract signers.
- Failures: unordered or duplicate elements, ed25519 elements after contract elements, a
  contract that is not a signer of the account, a non-contract address, a missing contract, a
  failing `__check_auth`, and total weight below the medium threshold.
- `__check_auth` receives the expected `signature_payload`, `signature`, and `auth_contexts`.
- Existing G account Soroban signatures are still accepted unchanged.

## Implementation

TBD.

## Exit Criteria

- The feature has been exercised on [Futurenet] or via [Quickstart], with Horizon and RPC up and
  reflecting the change.
- A G account with a contract signer has authorized a Soroban invocation, such as a Stellar
  Asset Contract transfer, on Futurenet or Quickstart.
- Stellar Core `LedgerCloseMeta`s (captured via `--capture-lcm` from new tests relevant to this
  CAP) pass Horizon ingestion test cases.
- The [Test Cases](#test-cases) are passing.

[stellar-core repository]: https://github.com/stellar/stellar-core
[Futurenet]: https://developers.stellar.org/docs/networks
[Quickstart]: https://github.com/stellar/quickstart
