## Preamble

```
CAP: To Be Assigned
Title: Contract Signers for Stellar Accounts in Soroban Authorization
Working Group:
    Owner: Leigh McCulloch <@leighmcculloch>
    Authors: Leigh McCulloch <@leighmcculloch>
    Consulted: TBD
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

G accounts are supported across the ecosystem, but their authorization is limited to a fixed set
of signer types. C accounts can implement any authorization logic in `__check_auth`, such as
passkeys or spending limits, but are not yet supported as broadly. A user who wants custom
authorization has to move to a C account.

An account's address is its public interface, where interoperability matters. Its signers mostly
matter only to the account holder and their wallet. Separating the two allows the ecosystem to
utilize custom authorization without needing interop buy-in: account holders can adopt contract
signers now, while keeping a G address that the rest of the ecosystem already supports.

For example:

- A G account adds a contract signer that verifies passkey (secp256r1/WebAuthn) signatures, so
  the user can authorize Soroban invocations, such as Stellar Asset Contract transfers, with a
  passkey.
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

This CAP adds a new signer key type, `SIGNER_KEY_TYPE_DELEGATE_CONTRACT`, which identifies a
contract by its contract ID. It can be added to an account with the existing `SetOptionsOp`, with a
weight, like any other signer.

Contract signers on an account are skipped when a transaction's signatures are checked against the
account's signers, and are invalid in the `extraSigners` field. They are accepted only in Soroban
authorization, when a G account authorizes with the delegated address credentials
(`SOROBAN_CREDENTIALS_ADDRESS_WITH_DELEGATES`) introduced by [CAP-71-01](./cap-0071-01.md). Each
contract signer's signature is provided in the credentials' `delegates` list, and the host
authenticates it the same way `delegate_account_auth` does: it calls the contract's `__check_auth`
with the G account's signature payload and authorization context, and the contract signer's own
signature. If the call succeeds, the signer's weight is added to the weight of the account's
ed25519 signatures, and the total must meet the account's medium threshold, as today.

No other changes are made to G accounts, classic operations, Soroban credentials, or the Soroban
authorization payload.

## Specification

### XDR changes

This patch of XDR changes is based on the XDR files in commit
`4f524bbac80c781c06e4fb5fc93a2d0d331d6705` of `stellar-xdr`.

```diff mddiffcheck.base=4f524bbac80c781c06e4fb5fc93a2d0d331d6705
diff --git a/Stellar-types.x b/Stellar-types.x
index 4a9d5bd..77fb305 100644
--- a/Stellar-types.x
+++ b/Stellar-types.x
@@ -34,6 +34,7 @@ enum CryptoKeyType
     KEY_TYPE_PRE_AUTH_TX = 1,
     KEY_TYPE_HASH_X = 2,
     KEY_TYPE_ED25519_SIGNED_PAYLOAD = 3,
+    KEY_TYPE_DELEGATE_CONTRACT = 4,
     // MUXED enum values for supported type are derived from the enum values
     // above by ORing them with 0x100
     KEY_TYPE_MUXED_ED25519 = 0x100
@@ -49,9 +50,12 @@ enum SignerKeyType
     SIGNER_KEY_TYPE_ED25519 = KEY_TYPE_ED25519,
     SIGNER_KEY_TYPE_PRE_AUTH_TX = KEY_TYPE_PRE_AUTH_TX,
     SIGNER_KEY_TYPE_HASH_X = KEY_TYPE_HASH_X,
-    SIGNER_KEY_TYPE_ED25519_SIGNED_PAYLOAD = KEY_TYPE_ED25519_SIGNED_PAYLOAD
+    SIGNER_KEY_TYPE_ED25519_SIGNED_PAYLOAD = KEY_TYPE_ED25519_SIGNED_PAYLOAD,
+    SIGNER_KEY_TYPE_DELEGATE_CONTRACT = KEY_TYPE_DELEGATE_CONTRACT
 };
 
+typedef Hash ContractID;
+
 union PublicKey switch (PublicKeyType type)
 {
 case PUBLIC_KEY_TYPE_ED25519:
@@ -76,6 +80,10 @@ case SIGNER_KEY_TYPE_ED25519_SIGNED_PAYLOAD:
         /* Payload to be raw signed by ed25519. */
         opaque payload<64>;
     } ed25519SignedPayload;
+case SIGNER_KEY_TYPE_DELEGATE_CONTRACT:
+    /* Contract whose __check_auth must authorize. Usable only in Soroban
+       authorization, never for transaction signatures. */
+    ContractID contractID;
 };
 
 // variable size as the size depends on the signature scheme used
@@ -86,8 +94,6 @@ typedef opaque SignatureHint[4];
 typedef PublicKey NodeID;
 typedef PublicKey AccountID;
 
-typedef Hash ContractID;
-
 struct Curve25519Secret
 {
     opaque key[32];
```

The existing `ContractID` typedef is moved above `SignerKey` so that it can be used there.

### Semantics

#### Adding and removing contract signers

`SetOptionsOp` accepts a `signer` whose key is of type `SIGNER_KEY_TYPE_DELEGATE_CONTRACT`. Adding,
updating the weight of, and removing a contract signer follow the same rules as for every other
signer type:

- A contract signer is an account subentry, counts toward the limit of 20 signers, and requires
  a base reserve.
- Setting its weight to 0 removes it.
- `SetOptionsOp` does not check that the contract exists. As with an ed25519 signer, the
  account owner is responsible for adding a signer that can sign.

Signers on an account are sorted by `SignerKey`, as today. Because the new type has the highest
discriminant, contract signers sort after all other signer types.

Before the protocol upgrade, a transaction containing a `SetOptionsOp` with a
`SIGNER_KEY_TYPE_DELEGATE_CONTRACT` signer is invalid and fails with `txMALFORMED`.

#### Transaction and operation signatures

When the signatures of a transaction are checked against the signers already on an account (the
transaction's source account or an operation's source account), signers of type
`SIGNER_KEY_TYPE_DELEGATE_CONTRACT` on that account are skipped. They contribute no weight toward
the low, medium, or high thresholds in those checks, and no `DecoratedSignature` is matched to
them. The account's other signers are checked as today.

This also means a contract signer cannot authorize a Soroban invocation that uses
`SOROBAN_CREDENTIALS_SOURCE_ACCOUNT`, because those credentials are checked through the
transaction's signatures.

A `SIGNER_KEY_TYPE_DELEGATE_CONTRACT` key cannot be used as an extra signer in a transaction's
`PreconditionsV2.extraSigners`. A transaction whose `extraSigners` contains one is invalid and
fails with `txMALFORMED`.

#### Soroban authorization of G accounts

Authorization of a G account with `SOROBAN_CREDENTIALS_ADDRESS` or
`SOROBAN_CREDENTIALS_ADDRESS_V2` credentials is unchanged. Only ed25519 signers can authorize
with those credentials.

Contract signers authorize a G account through `SOROBAN_CREDENTIALS_ADDRESS_WITH_DELEGATES`
credentials, as defined in [CAP-71-01](./cap-0071-01.md). As for any address using those
credentials, the signature payload `P` is the SHA-256 hash of the
`ENVELOPE_TYPE_SOROBAN_AUTHORIZATION_WITH_ADDRESS` `HashIDPreimage`, with `address` set to the G
account, and the authorization context `C` is derived from the authorization entry.

When the host authenticates a G account with these credentials, it checks the account as follows:

1. The `signature` in `addressCredentials` is checked as today: it is an `SCV_VEC` of
   `AccountEd25519Signature` elements in strictly increasing order of `public_key`, each verified
   against `P` and each belonging to a signer of the account. Unlike today, the vector may be
   empty, so that an account can authorize with contract signers alone.
2. Each entry in the top-level `delegates` list must have an `address` that is a contract address
   (`SC_ADDRESS_TYPE_CONTRACT`) matching the `contractID` of a `SIGNER_KEY_TYPE_DELEGATE_CONTRACT`
   signer of the account with weight greater than 0. Otherwise authentication fails, as it does
   today for an ed25519 key that is not a signer of the account. The `delegates` list is already
   required by CAP-71-01 to be sorted by `address` with no duplicates, so the same signer cannot
   be used twice.
3. For each entry in `delegates`, the host authenticates the contract exactly as if the G
   account's `__check_auth` had called `delegate_account_auth` for its `address`: it calls the
   contract's `__check_auth(P, signature, C)`, where `signature` is the entry's `signature`, and
   the entry's `nestedDelegates` become the delegated signers available to that call. If the
   contract is missing, has no `__check_auth`, or `__check_auth` fails, authentication fails.
4. The weights of all verified ed25519 signers and contract signers are added up. Authentication
   fails if no signer was provided. Otherwise, it succeeds if the total is at least the account's
   medium threshold, as today.

The G account's nonce is consumed and its signature expiration is enforced, as today. A contract
signer does not consume a nonce of its own.

Nested authorization inside a contract signer's `__check_auth` follows the rules that already
apply inside any `__check_auth`. For example, the contract can call `require_auth` on another
address, or call `delegate_account_auth` for one of its own `nestedDelegates`.

#### Footprint

When a contract signer is used, the contract instance entry and its executable (for example its
`CONTRACT_CODE` entry) must be in the transaction's footprint, as with any contract call.
Recording-mode simulation adds them as it does for contract accounts.

#### Strkey

Wherever a `SignerKey` is encoded as a strkey, a `SIGNER_KEY_TYPE_DELEGATE_CONTRACT` signer key is
encoded as the contract's strkey (`C...`), as defined in SEP-23. This includes the `key` field of
an account's signers in Horizon's API, the JSON form of `SignerKey` produced by `stellar-xdr`, and
the signer key types in the SDKs. No new strkey version byte is needed.

## Design Rationale

### Scope

The discussion proposed several changes to make G accounts more programmable. This CAP covers
only one of them: contracts as signers of G accounts for Soroban authorization. It does not make
the account's signers manageable from Soroban or add a way to manage trustlines from Soroban
beyond the Stellar Asset Contract's `trust` function ([CAP-0073](./cap-0073.md)).
Those can come later. Releasing only what this CAP proposes first does not limit or restrict
what can be added separately in future protocols.

### No transaction signing

Contract signers cannot sign transactions. Transaction signatures are checked before the fee is
charged, and during flooding and transaction set validation. Running contract code at those
points would let anyone make validators run code without paying for it, and would make a
transaction's validity depend on contract state that can change between validation and
application.

The consequence is that a contract signer can do anything a G account can do in Soroban, but
cannot authorize classic operations such as `SetOptionsOp` or a classic `PaymentOp`. Trustlines
can still be created from Soroban with the Stellar Asset Contract's `trust` function
([CAP-0073](./cap-0073.md)), which a contract signer can authorize. The G account must keep at
least one classic signer that meets its thresholds for classic operations and for paying
transaction fees, unless the account is intended to never use those classic operations.
Transaction fees for Soroban invocations that a contract signer authorizes can be paid by another
account, for example a relayer, a fee bump, or a wallet service. This is the same model that C
accounts use today.

### Reusing `__check_auth`

Contract signers reuse the existing `__check_auth` interface and arguments. Contracts that
already work as contract accounts, and the libraries that build them, can be used as G account
signers without changes. Wallet SDKs already know how to build the `signature` value for those
contracts. The authorization contexts let a contract signer apply policies (for example spending
limits) to the G account's invocations in the same way it applies them to its own.

The authorization context does not identify the address being authorized, and `__check_auth`
only receives the hash of the signature payload. A separate function that also receives the G
account address was considered, so that a contract could know which account it is signing for.
It would need new contract interfaces and would not work with existing contract accounts. It is
also not needed: `delegate_account_auth` passes delegates the same arguments, and the
`ENVELOPE_TYPE_SOROBAN_AUTHORIZATION_WITH_ADDRESS` payload binds every signature to the G
account. See [Security Concerns](#security-concerns).

### Weight and thresholds

Contract signers use the same weights and the same medium threshold as other signers. This keeps
the account's existing model: an account can require a contract signer and an ed25519 key
together, or give either one enough weight to act alone.

### Reusing CAP-71 delegation

[CAP-71-01](./cap-0071-01.md) already defines how an account delegates authentication to other
addresses: `SOROBAN_CREDENTIALS_ADDRESS_WITH_DELEGATES` carries each delegate's signature, and
`delegate_account_auth` calls each delegate's `__check_auth` with the account's signature payload
and context. A contract signer of a G account is a delegate whose authority comes from the
account's signers instead of from contract code, so this CAP reuses that mechanism instead of
defining a new signature format. The G account's `signature` format is unchanged, the
address-bound payload is used, and wallets and SDKs can build contract signer signatures with the
same tooling they use for CAP-71 delegates.

A G account has no contract code to call `delegate_account_auth`, so the host's built-in check for
G accounts performs the delegation itself, for every entry in `delegates`, and only for addresses
that are contract signers of the account.

### Signer key type

A new `SignerKey` type is the smallest change that lets an account record a contract and its
weight using existing operations, subentry accounting, and ledger entries. No new
ledger entry type or operation is needed.

## Protocol Upgrade Transition

### Backwards Incompatibilities

The protocol upgrade adds a new arm to `SignerKey`. Software that decodes XDR containing a
`SignerKey`, such as `AccountEntry`, `SetOptionsOp`, and `PreconditionsV2`, must be updated to
decode the new type. This affects
Horizon, RPC, SDKs, block explorers, wallets, and indexers.

Software that lists an account's signers and assumes every signer can sign transactions should
learn that contract signers cannot. For example, a wallet that computes whether it can meet a
threshold for a classic transaction must ignore contract signers.

No existing behavior changes for accounts that do not add contract signers. Existing Soroban
signatures for G accounts stay valid, and `SOROBAN_CREDENTIALS_ADDRESS` and
`SOROBAN_CREDENTIALS_ADDRESS_V2` credentials for G accounts are unchanged.

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
  cannot change the account's signers or thresholds, merge the account, or make classic
  payments. It can authorize any Soroban invocation that the G account can authorize, including
  transfers of the account's balances and creating trustlines through the Stellar Asset Contract.
- **Replay across accounts.** Contract signers only sign the
  `ENVELOPE_TYPE_SOROBAN_AUTHORIZATION_WITH_ADDRESS` payload, which includes the G account's
  address. If the same contract signer is a signer of more than one account, a signature it
  produces for one account cannot be used for another.
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

- Adding, updating, and removing a contract signer with `SetOptionsOp`, including subentry
  limits and reserves.
- `SetOptionsOp` with a contract signer before the protocol upgrade fails with `txMALFORMED`.
- Contract signers never contribute to transaction or operation signature thresholds.
- A transaction with a contract signer in `extraSigners` fails with `txMALFORMED`.
- Soroban authorization of a G account with only a contract signer, with ed25519 signers and a
  contract signer together, and with several contract signers.
- Soroban authorization of a G account with only contract signers and an empty `signature`
  vector.
- Failures: a delegate that is not a contract signer of the account, a delegate that is a G
  address, a missing contract, a failing `__check_auth`, no signers provided, and total weight
  below the medium threshold.
- Contract signers are not accepted with `SOROBAN_CREDENTIALS_ADDRESS` or
  `SOROBAN_CREDENTIALS_ADDRESS_V2` credentials.
- `__check_auth` receives the expected signature payload, signature, and authorization contexts,
  and can call `delegate_account_auth` for its `nestedDelegates`.
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
