## Preamble

```
SEP: To Be Assigned
Title: Trustline Onboarder
Author: The Aha Company <@theahaco>, Willem Wyndham <@willemneal>, Enzo Soyer <@Dgetsylver>, Pamphile Roy <@tupui>, Hugo Heer <@hugo-heer>
Status: Draft
Created: 2026-06-04
Updated: 2026-09-30
Version: 0.0.1
Discussion: https://github.com/orgs/stellar/discussions/2008
```

## Simple Summary

A standard that lets a **third party** — an exchange, broker, or wallet —
onboard a user into a classic Stellar asset on the user's behalf, so that
receiving or withdrawing the asset no longer requires the user to face a
context-free "create a trustline" prompt. The standard defines an on-chain
authorization-delegation interface, a `stellar.toml` discovery block, and an
integrator interface that together reduce the user to **at most one in-flow
signature, and often zero**. It is asset-agnostic: it serves the majority of
**open** classic assets (USDC, EURC — not `AUTH_REQUIRED`) and **regulated**
`AUTH_REQUIRED` assets (EURCV) under one interface. It builds on the
[Contract Admin SEP](https://github.com/theahaco/admin-sep) (`admin-sep`) and
references
[CAP-73](https://github.com/stellar/stellar-protocol/blob/master/core/cap-0073.md)
(Protocol 26).

## Dependencies

- [SEP-1](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0001.md)
  — `stellar.toml`; this SEP adds the `[TRUSTLINE_ONBOARDER]` table (§6).
- [SEP-7](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0007.md)
  — `web+stellar:` URIs, used for integrator-to-wallet handoffs (§7).
- [SEP-10](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0010.md)
  — authentication to an allowlist `AUTH_ENDPOINT` (§7).
- [CAP-33](https://github.com/stellar/stellar-protocol/blob/master/core/cap-0033.md)
  — sponsored reserves, used on the classic path for underfunded holders (§5).
- [CAP-46-06](https://github.com/stellar/stellar-protocol/blob/master/core/cap-0046-06.md)
  — the Stellar Asset Contract (SAC) and its admin functions (`admin`,
  `set_admin`, `set_authorized`, `authorized`, `mint`, `clawback`).
- [CAP-68](https://github.com/stellar/stellar-protocol/blob/master/core/cap-0068.md)
  — `get_address_executable`, used by the Onboard router to discover the SAC
  admin on-chain (§4).
- [CAP-73](https://github.com/stellar/stellar-protocol/blob/master/core/cap-0073.md)
  (Protocol 26) — `SAC.trust()`, required only by the one-signature `onboard()`
  fallback (§4, §5).
- [Contract Admin SEP](https://github.com/theahaco/admin-sep) (`admin-sep`) — a
  draft proposal, not yet numbered; the Trustline Authorizer implements its
  `Administratable` (`admin`, `set_admin`) and `Upgradable` (`upgrade`) traits
  (§3). The three functions this SEP relies on are restated in §3, so it can be
  implemented without `admin-sep`.

## Motivation

### The third-party reframe

The friction the standard removes is not, fundamentally, an end-user-page
problem. It is a **third-party integration** problem: an exchange, broker, or
wallet wants to deliver an asset to a user and is blocked because the user does
not yet hold an authorized trustline. Today the third party can only hand the
user a raw `CHANGE_TRUST` prompt and hope they complete it. This SEP defines
the standard, on-chain delegation and the discovery metadata that let the third
party do everything except the one signature that the protocol reserves for the
trustline owner — and, in the common case of a pre-existing unauthorized
trustline, removes even that.

### Withdrawal-flow friction

A regulated classic asset with `AUTH_REQUIRED` (e.g., a MiCA stablecoin) cannot
be received by a self-custody account until that account holds an _authorized_
trustline. In a CEX withdrawal this produces a poor UX: the user signs
`ChangeTrust` (and funds a 0.5 XLM reserve they may not have), the issuer
authorizes out of band, and only then can the withdrawal land. Each hop is a
place to lose the user. The objective is to collapse the "create + authorize"
sequence into a **single, predictable, self-service interaction** a third party
can drive, while keeping authorization under the issuer's on-chain policy
control.

### Two asset classes — do not assume the regulated model for all assets

The standard explicitly serves two classes. On the `onboard()` fallback the
discovery router (§4) detects which applies **on-chain** — it runs the SAC
admin's `authorize_trustline` for a regulated asset and skips it for an open
one — so an integrator driving `onboard()` never branches on the class. On the
default classic path (§5, Case B) the integrator reads the issuer's
`auth_required` flag, or the new trustline's `authorized` flag, to decide
whether a separate authorize step applies (§1):

- **Open classic assets (the majority — USDC, EURC):** not `AUTH_REQUIRED`.
  Onboarding is simply a reserve-free, sponsored `ChangeTrust` — the third
  party sponsors the reserve, the user signs once (a sponsored `CreateAccount`
  covers a brand-new zero-XLM account). There is **no** authorize step and
  **no** Authorizer contract needed.
- **Regulated `AUTH_REQUIRED` assets (EURCV):** `ChangeTrust` (user, once)
  **plus** authorize-on-behalf (third party, permissionless, no user or issuer
  signature) via the Trustline Authorizer.

The Authorizer / authorize-on-behalf is the _regulated-asset value_. For most
assets the value is reserve-free, one-tap (or zero-touch) trustline
establishment plus the handoff.

### Classic-asset compliance (MiCA)

Issuers of regulated classic assets need `AUTH_REQUIRED` (gate who may hold),
`AUTH_REVOCABLE` (freeze), and `AUTH_CLAWBACK_ENABLED` (clawback), plus an
auditable record of who was authorized, when, and under what policy. Performing
authorization off-chain with the issuer's keys provides no standard, reviewable
trail and cannot be composed atomically with trustline creation. Delegating
authorization to a **policy contract** set as the SAC admin makes the policy
on-chain, deterministic, and auditable, and lets the issuer retain
`SetTrustLineFlags`-equivalent freeze/clawback controls. (This is a compliance
_design and controls_ mapping, not legal advice.)

### Why now: CAP-73

Before Protocol 26, a Soroban contract could not create a classic trustline:
classic and Soroban operations cannot be mixed in a single transaction, so
"create trustline" (classic `CHANGE_TRUST`) and "authorize via SAC" (Soroban
`set_authorized`) could not be composed atomically.
[CAP-73](https://github.com/stellar/stellar-protocol/blob/master/core/cap-0073.md)
— _"Allow SAC to create G-account balances,"_ live on mainnet since the
Protocol 26 _"Yardstick"_ upgrade (vote 2026-05-06) — adds a SAC host function:

```rust
// CAP-73 (Protocol 26)
fn trust(env: Env, address: Address);
// Creates an UNLIMITED trustline for `address` if none exists.
// Requires require_auth(address). No-op for C-addresses and existing trustlines.
// DOES NOT support sponsorship: the trustline owner pays the 0.5 XLM reserve.
// DOES NOT authorize an AUTH_REQUIRED trustline — authorization remains a
// separate set_authorized call.
```

Because `trust()` is a Soroban host function, a contract can call it _and_ call
the SAC admin's `set_authorized` in **one Soroban transaction under one holder
auth**. This SEP defines the contract interface and discovery metadata that
turn that primitive into an interoperable onboarding standard.

### Why delegate authorization once, on-chain

Today an `AUTH_REQUIRED` issuer either approves trustlines by hand or runs a
SEP-8 approval server that co-signs **every** transaction. This SEP delegates
authorization **once** to a permissionless on-chain contract: after the issuer
transfers SAC admin to the Authorizer, authorization is a contract call subject
to an on-chain policy, with no issuer signature at authorize time and no
per-transaction co-signing server.

### Why build on admin-sep

The [Contract Admin SEP](https://github.com/theahaco/admin-sep) (a draft
proposal, not yet numbered) standardizes the SAC/contract admin surface via an
`Administratable` trait (`admin` / `set_admin`) plus `Upgradable`. The
Trustline Authorizer is an `Administratable` contract: the issuer transfers SAC
admin to it, and the Authorizer's own admin governs policy changes (ban/unban,
freeze, clawback, upgrade). Reusing `admin-sep` keeps the admin surface uniform
across the Stellar contract ecosystem rather than inventing a new one.

## Abstract

Holding a classic issued asset on Stellar requires a `CHANGE_TRUST` operation
that creates a trustline and locks a 0.5 XLM reserve. For an `AUTH_REQUIRED`
asset the trustline is then unusable until the issuer authorizes it, through
`SetTrustLineFlags` or, when authorization is delegated to the Stellar Asset
Contract (SAC), its admin function `set_authorized`. Today this is a
multi-step, multi-signature, off-band process, most visible when a user
withdrawing from an exchange to a self-custody wallet is stopped at a "create a
trustline" prompt with no context.

Creating a trustline always requires the owner's own signature, and this SEP
does not change that. It lets a third party do everything else: pay the reserve
through CAP-33 sponsorship, authorize the trustline on the issuer's behalf
through a permissionless policy contract installed as the SAC admin, and
orchestrate the transactions. The holder signs **at most once** — by default a
plain classic `ChangeTrust` — and **not at all** when an unauthorized trustline
already exists. The SEP defines the authorization-delegation interface and its
policy model, a one-signature fallback built on CAP-73, a `stellar.toml`
discovery block, the integrator flow and handoffs, and audit events. It
requires no protocol change.

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.txt).

This specification defines:

1. The **roles** in a third-party onboarding flow, and the two **asset
   classes** (open vs. regulated `AUTH_REQUIRED`) the standard serves under one
   interface (§1).
2. The **three onboarding cases** (A: zero-signature authorize-on-behalf; B:
   classic one-tap, sponsored when needed; C: CAP-73 one-transaction fallback)
   that arise across both asset classes and account states (§2).
3. A **Trustline Authorizer** contract, installed as the asset's SAC admin (via
   `admin-sep`'s `Administratable` trait), exposing an asset-agnostic,
   **permissionless** `authorize_trustline` interface gated by a configurable
   **denylist** (open-by-default) or **allowlist** (gated) policy. Required
   only for regulated `AUTH_REQUIRED` assets (§3).
4. A **Trustline Onboard** wrapper that composes CAP-73's `SAC.trust()` with
   the Authorizer's `authorize_trustline` so that creating and authorizing a
   trustline happen **atomically under one holder signature** — specified as
   the fallback for holders with nobody to pay a separate authorization
   transaction, and for wallets that render Soroban authorization well (§4).
5. **Two backends** an integrator selects between — the classic path
   (holder-signed `ChangeTrust`, CAP-33 sponsored when the holder is
   underfunded, then authorize-on-behalf) as the default, and the CAP-73
   one-signature path as the fallback — and the rules for choosing (§5).
6. A **`stellar.toml` `[TRUSTLINE_ONBOARDER]` discovery block** so any
   integrator can auto-discover an issuer's onboarder from one config —
   universal interop, no bilateral deals (§6).
7. The **integrator interface** (handoffs: SEP-7 URI, wallet deep-link, hosted
   redirect; §7) and a structured **audit-event** trail suitable for MiCA-style
   compliance reporting (§8).

### 1. Roles and asset classes

| Role                          | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Issuer**                    | The classic asset issuer (`G…`). For a regulated asset, sets `AUTH_REQUIRED` (and optionally `AUTH_REVOCABLE`, `AUTH_CLAWBACK_ENABLED`), wraps the asset as a SAC, and transfers SAC admin to the Trustline Authorizer. Publishes `[TRUSTLINE_ONBOARDER]` in its `stellar.toml`.                                                                                                                                                                                           |
| **Trustline Authorizer**      | A Soroban contract installed as the asset's **SAC admin**. Implements the authorization-delegation interface (§3). Is `Administratable` + `Upgradable` per `admin-sep`. Holds policy state (denylist or allowlist) and emits audit events (§8). **Required only for `AUTH_REQUIRED` assets.**                                                                                                                                                                              |
| **Trustline Onboard wrapper** | A stateless, immutable, asset-agnostic Soroban ROUTER whose `onboard(sac, holder)` (§4) composes CAP-73 `SAC.trust()` with the authorizer **discovered on-chain** from `SAC.admin()` (CAP-68). The **fallback** path (§5) for holders with nobody to submit a separate authorization transaction, and for wallets that render Soroban authorization well. Deployed once per network; integrators SHOULD use a pinned/curated router id (§6) rather than an advertised one. |
| **Integrator (third party)**  | A wallet, exchange, or broker that reads the issuer's `stellar.toml`, detects the asset class, checks eligibility, builds the trustline transaction the holder signs, submits and pays for the authorization transaction the holder does not sign, and reports completion from `is_authorized`.                                                                                                                                                                            |
| **Sponsor**                   | (Backend 2 only.) An account (issuer or platform) that pays the holder's reserve(s) via CAP-33 future-reserves sponsorship and co-signs the classic activation transaction.                                                                                                                                                                                                                                                                                                |
| **Holder (user)**             | The end user (`G…`). Signs **at most once** — and **zero** times when only authorization is needed (Case A).                                                                                                                                                                                                                                                                                                                                                               |

```
   Issuer  ──set_admin(Authorizer)──►  SAC (classic asset)
     │                                    ▲
     │ publishes stellar.toml             │ set_authorized(holder,true)
     │ [TRUSTLINE_ONBOARDER]              │  (regulated assets only)
     ▼                                    │
 Integrator ──reads toml──► Authorizer.is_eligible(holder)? ──► picks the case (§2)
   (3rd party)
 Holder     ──1 classic signature──► ChangeTrust          (sponsored by the integrator
                                                           only if the holder is underfunded)
 Integrator ──pays the fee, no holder signature──► Authorizer.authorize_trustline(holder)
                                                    (policy check → SAC.set_authorized)
 Integrator ──polls──► Authorizer.is_authorized(holder) ──► shows "done"

 Fallback (Case C, §4): Holder ──1 Soroban signature──► Onboard.onboard(sac, holder)
                        = SAC.trust(holder) + Authorizer.authorize_trustline(holder),
                          atomically, with the admin discovered via CAP-68
```

#### Asset-class detection (normative)

On the default path (§5, Case B) an integrator MUST determine whether an
authorize step follows the trustline, either by reading the issuer account's
`auth_required` flag before building the transaction, or by reading the
holder's trustline `authorized` flag once the trustline exists (a trustline to
an open asset is authorized on creation):

| Asset class                                 | `auth_required` | Trustline                                                                         | Authorize step                                              | Authorizer contract        |
| ------------------------------------------- | :-------------: | --------------------------------------------------------------------------------- | ----------------------------------------------------------- | -------------------------- |
| **Open** (USDC, EURC — majority)            |      false      | sponsored `ChangeTrust` (user signs once; sponsored `CreateAccount` if brand-new) | none                                                        | not used                   |
| **Regulated** (`AUTH_REQUIRED`, e.g. EURCV) |      true       | `ChangeTrust` (user, once)                                                        | authorize-on-behalf (third party, no user/issuer signature) | required, set as SAC admin |

For an open asset, the entire `[TRUSTLINE_ONBOARDER]`
Authorizer/onboard-wrapper machinery is unnecessary: the flow reduces to a
sponsored, reserve-free `ChangeTrust`. The standard MUST NOT require an
Authorizer for assets that are not `AUTH_REQUIRED`. On the `onboard()` fallback
(§5, Case C) no pre-classification is needed: the router detects the class
on-chain and reports the outcome in `OnboardStatus` (§4).

### 2. The three onboarding cases

Across both asset classes and the holder's account state, three cases arise.
Integrators MUST select among them by reading the holder's account and
trustline state, the asset class and — for a regulated asset — the Authorizer's
`is_eligible` (§3):

| Case                              | Precondition                                                                                                                                       | What the third party does                                                                                                                                                                                                                                                                                                              | Holder signatures |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------: |
| **A — zero-signature authorize**  | Holder already has an **unauthorized** trustline (common with `AUTH_REQUIRED`).                                                                    | Authorizer `authorize_trustline(holder)` on-behalf. No trustline creation needed.                                                                                                                                                                                                                                                      |       **0**       |
| **B — classic one-tap** (default) | Holder has **no** trustline, at any funding level.                                                                                                 | Holder signs one plain classic `ChangeTrust` — wrapped in a CAP-33 sponsorship sandwich (with a sponsored `CreateAccount` if brand-new) only when the holder cannot pay the reserve. Then, if `AUTH_REQUIRED`, the third party authorizes on-behalf (Case A) in a separate Soroban transaction it pays for, and polls `is_authorized`. |       **1**       |
| **C — CAP-73 one-tx** (fallback)  | Holder has a **funded** account, and either nobody will pay a separate authorization transaction or the wallet renders Soroban authorization well. | One CAP-73 Soroban tx (`onboard()` wrapper) creates **and** authorizes in a single holder signature.                                                                                                                                                                                                                                   |       **1**       |

Case A is the zero-signature path the protocol allows because the trustline
already exists — only authorization remains, and authorization is
permissionless and on-behalf. Cases B and C both reduce the holder to one
signature; they differ in **what the holder reviews** (B: a classic
`ChangeTrust`, the trustline prompt every wallet already renders; C: a Soroban
invocation with a nested authorization tree), in who pays the reserve (B: the
holder when funded, otherwise a sponsor; C: the holder) and in transaction
shape (B: a classic tx, then a Soroban authorize the holder never signs; C: a
single Soroban tx). **Case B is the default** because of how wallets render the
two today (see Design Rationale); Case C is the fallback (§5). The mapping to
backends (§5) is: Cases A and C use **Backend 1** (Soroban); Case B uses
**Backend 2** (classic, CAP-33-sponsored when needed) followed by a Case A
authorize.

### 3. Authorization-delegation interface and policy model (regulated assets)

The Trustline Authorizer MUST be set as the SAC admin of the asset
(`SAC.set_admin(authorizer)`), so that it — and only it — may call
`set_authorized` on the SAC. The Authorizer MUST implement `admin-sep`'s
`Administratable` (`admin`, `set_admin`) and SHOULD implement `Upgradable`.

The Authorizer MUST expose:

```rust
/// Authorize the trustline of `account` on the managed asset, on the account's behalf,
/// subject to the configured policy. Calls SAC.set_authorized(account, true) on success.
/// Permissionless: requires no issuer signature at call time.
fn authorize_trustline(env: Env, account: Address) -> Result<(), Error>;
```

Semantics of `authorize_trustline`:

- It performs **on-behalf** authorization: it does **not** require the _issuer_
  (or the _holder_) to sign at call time. Authorization authority comes from
  the Authorizer being the SAC admin. This is what enables **Case A's zero
  holder signatures**.
- It MUST evaluate the configured **policy** (below) on **every** call. The
  policy decision MUST NOT be cached or short-circuited by a prior
  authorization or a prior trustline: a banned, disallowed, or frozen account
  MUST NOT obtain authorization, even on a repeated or retried call (see §4
  idempotency and the freeze lifecycle below).
- On success it MUST call the SAC admin function
  `set_authorized(account, true)` and SHOULD record `account` as authorized in
  contract storage.
- It MUST return `NoTrustline` if `account` has no trustline for the asset
  (callers compose `SAC.trust()` first; see §4).
- It MUST NOT authorize the Authorizer contract itself
  (`CannotAuthorizeAdminContract`).
- It MUST return `ContractPaused` when the contract is paused.
- It MUST signal every rejection with a **typed contract error** (the error
  table below). Callers — including the Onboard router — MUST interpret an
  untyped abort (missing export, panic, host error) as "no one-step authorizer
  interface" (`TrustlineOnly`), never as a rejection. An authorizer that panics
  instead of returning a typed error will therefore be treated as absent, and
  holders will be left with unauthorized trustlines.

#### Read interface (normative)

The default flow (§5) is driven from the integrator's side — the integrator
decides which path to take before the holder signs, and decides when to show
"done" after the holder has signed — so the Authorizer MUST also expose the two
reads that flow relies on:

```rust
/// Would `authorize_trustline(account)` be permitted by policy right now?
/// True iff the contract is not paused, `account` is not the Authorizer itself,
/// and the policy admits `account` (not banned under denylist; allowed under
/// allowlist). Does NOT check whether a trustline exists.
fn is_eligible(env: Env, account: Address) -> bool;

/// Is `account`'s trustline for the managed asset authorized right now?
/// Answered from the SAC (`SAC.authorized(account)`); false when there is no
/// trustline.
fn is_authorized(env: Env, account: Address) -> bool;
```

- `is_eligible` MUST evaluate the same policy state `authorize_trustline`
  evaluates, so that a `true` read followed by an authorize is refused only if
  the policy changed in between (or the trustline is missing — `NoTrustline`).
  Integrators consult it before asking the holder to sign anything and before
  paying the fee for an authorize transaction; under an allowlist policy a
  `false` read is the moment to route the holder to `AUTH_ENDPOINT` (§7),
  rather than after a refused, fee-costing call.
- `is_authorized` MUST be answered from the SAC — the trustline's own
  `authorized` flag — and not from Authorizer storage, so it stays truthful
  across changes the Authorizer did not make (an issuer-signed
  `SetTrustLineFlags`, a deleted and recreated trustline). Integrators poll it,
  or read the trustline flags from the ledger directly, to confirm completion;
  they MUST NOT report completion on transaction success alone.
- Both are reads: simulate them, no signature, no fee.

The Authorizer SHOULD also expose `policy() -> Policy`, `is_paused() -> bool`
and `sac() -> Address`, so a wallet can check the `stellar.toml` values against
chain state before trusting them.

#### Policy model

The Authorizer MUST support one of two policies, fixed at deployment or set by
the admin:

| Policy        | Default         | `authorize_trustline(account)` succeeds when…                          | Use case                                              |
| ------------- | --------------- | ---------------------------------------------------------------------- | ----------------------------------------------------- |
| **Denylist**  | open-by-default | `account` is **not** in the banned set (permissionless / self-service) | Frictionless stablecoins (e.g., the live EURCV model) |
| **Allowlist** | gated           | `account` **is** in the allowed set (per-user KYC gate set by issuer)  | Securities / RWA, per-holder KYC                      |

The denylist policy makes `authorize_trustline` **permissionless and
self-service**: any account not banned authorizes itself (or is authorized
on-behalf by a third party). The allowlist policy makes it **gated**: the
issuer (Authorizer admin) MUST `allow(account)` first, typically after off-band
KYC (which MAY be fronted by a SEP-10–authenticated endpoint; §7).

#### Freeze / deauthorize lifecycle (normative)

To prevent a previously-frozen account from re-authorizing itself by replaying
`onboard()` or calling `authorize_trustline` again, the freeze and deauthorize
lifecycle MUST interact with policy as follows:

- **`freeze_accounts` MUST set the banned/disallowed bit AND deauthorize.**
  Under the **denylist** policy, `freeze_accounts(a)` MUST add `a` to the
  banned set **and** call `set_authorized(a, false)`. Under the **allowlist**
  policy, it MUST remove `a` from the allowed set **and** call
  `set_authorized(a, false)`. Freeze is precisely _ban/disallow + deauthorize_
  so the subsequent policy check blocks re-authorization.
- A **frozen-but-not-banned** state MUST NOT be representable: because denylist
  `authorize_trustline` only checks the banned set, an account that was
  deauthorized but not banned would be re-authorizable by a retried
  `onboard()`. Implementations MUST NOT expose any path that deauthorizes
  without also updating policy when the intent is to freeze.
  `deauthorize_trustline` is provided for transient, policy-consistent
  deauthorization and MUST NOT be used as a standalone freeze; callers needing
  a durable freeze MUST use `freeze_accounts`.
- `unfreeze_accounts` MUST reverse both effects: remove from the banned set
  (denylist) or re-add to the allowed set (allowlist), **and** re-authorize via
  `set_authorized(a, true)`.

This closes the lifecycle hole where a retried `onboard()` could re-authorize a
frozen holder: the policy check in `authorize_trustline` runs on every call,
and freeze guarantees the policy now rejects the account.

Required admin / lifecycle entry points (generalizing the live `eurcv_auth`
interface):

```rust
// Denylist policy
fn add_banned_accounts(env: Env, accounts: Vec<Address>);      // max 50 per call
fn remove_banned_accounts(env: Env, accounts: Vec<Address>);   // max 50 per call

// Allowlist policy
fn allow(env: Env, accounts: Vec<Address>);
fn disallow(env: Env, accounts: Vec<Address>);

// Lifecycle controls (require SetTrustLineFlags-equivalent asset flags)
fn freeze_accounts(env: Env, accounts: Vec<Address>);   // ban/disallow + de-authorize
fn unfreeze_accounts(env: Env, accounts: Vec<Address>); // un-ban/re-allow + re-authorize
fn deauthorize_trustline(env: Env, account: Address, reason: Reason); // set_authorized(account, false), policy-consistent
fn clawback(env: Env, from: Address, amount: i128);     // requires AUTH_CLAWBACK_ENABLED
fn mint_to_account(env: Env, to: Address, amount: i128);
fn pause(env: Env);
fn unpause(env: Env);

// From admin-sep
fn admin(env: Env) -> Address;
fn set_admin(env: Env, new_admin: Address);
fn upgrade(env: Env, wasm_hash: BytesN<32>);
```

`freeze_accounts`/`unfreeze_accounts` require `AUTH_REVOCABLE`; `clawback`
requires `AUTH_CLAWBACK_ENABLED`. Implementations MUST gate all admin entry
points on `admin().require_auth()`. `Reason` is the enumerated deauthorization
code carried into the audit event (§8); implementations SHOULD offer at least
`Sanctions`, `KycExpired`, `IssuerRequest` and `Unspecified`.

`pause` MUST stop `authorize_trustline`; implementations SHOULD also stop every
other state-changing entry point, leaving only `unpause`, `set_admin` and
`upgrade` callable so a paused contract stays recoverable.

#### Error codes (normative minimum)

Contract errors are encoded on the wire as `u32` values, so the names alone do
not make implementations interoperable. Wallets and integrators branch on the
value to show the right message (banned vs. not-yet-allowed vs. paused), and
they MUST be able to do so against any conforming Authorizer. Implementations
MUST therefore use exactly these values:

| Code | Error                          | Condition                                |
| ---- | ------------------------------ | ---------------------------------------- |
| `1`  | `AccountBanned`                | denylist policy, `account` is banned     |
| `2`  | `AccountNotAllowed`            | allowlist policy, `account` not allowed  |
| `3`  | `NoTrustline`                  | `account` has no trustline for the asset |
| `4`  | `ContractPaused`               | contract is paused                       |
| `5`  | `CannotAuthorizeAdminContract` | `account == authorizer contract address` |

Codes `1`–`5` are reserved by this SEP. An implementation MAY define further
errors for its own admin entry points (for example an invalid batch, or an
issuer flag the asset does not carry) and MUST assign them values of `6` or
above so they never collide with the normative set. Callers MUST treat any
unknown code from `authorize_trustline` as a rejection of unspecified cause.

In soroban-sdk terms:

```rust
#[contracterror]
#[repr(u32)]
pub enum Error {
    AccountBanned = 1,
    AccountNotAllowed = 2,
    NoTrustline = 3,
    ContractPaused = 4,
    CannotAuthorizeAdminContract = 5,
    // 6+ are implementation-defined
}
```

### 4. One-signature onboard composition (over CAP-73)

The Trustline Onboard router composes trustline creation and authorization
atomically, **discovering** the authorizer from `SAC.admin()` (CAP-68
`get_address_executable`) instead of taking it as a parameter.

```rust
/// Outcome of `onboard`, reported truthfully from on-chain state.
#[contracttype]
#[derive(Copy, Clone, Debug, Eq, PartialEq)]
pub enum OnboardStatus {
    /// Trustline exists and is authorized — the holder can receive the asset.
    Authorized,
    /// Trustline exists but is not authorized: the asset is AUTH_REQUIRED and
    /// its SAC admin offers no one-step `authorize_trustline` interface — the
    /// issuer authorizes off-platform (manual path).
    TrustlineOnly,
}

/// One-signature onboarding with ON-CHAIN capability discovery.
/// `sac`    — Stellar Asset Contract address of the asset (any class).
/// `holder` — the G-account being onboarded.
/// Create the holder's trustline and, when the asset's SAC admin is a
/// contract exposing `authorize_trustline`, authorize it — all under one
/// holder signature. The asset's capability is DISCOVERED on-chain
/// (CAP-68 `get_address_executable` + `SAC.admin()`), not configured.
///
/// Returns `Authorized` when the trustline is usable, `TrustlineOnly`
/// when the asset is AUTH_REQUIRED with no one-step authorizer (the
/// trustline is kept; the issuer authorizes off-platform).
///
/// **Atomic on rejection:** if the discovered authorizer rejects the
/// holder with a typed contract error, the WHOLE transaction (including
/// the trustline creation) is rolled back.
///
/// **Immutable by design:** no admin or upgrade entrypoint; fixing a bug
/// means deploying a new instance and updating the pinned router id.
///
/// # Security
///
/// The discovered admin is a contract CHOSEN BY THE ASSET, executed under
/// the holder's signed authorization tree: in recording-mode simulation,
/// any nested `holder.require_auth()` the admin triggers is folded into
/// the single root auth entry the holder signs. The router cannot prevent
/// a malicious admin from abusing this — only onboard SACs from a
/// trusted/pinned source, and wallets SHOULD render the full auth tree.
pub fn onboard(env: Env, sac: Address, holder: Address) -> Result<OnboardStatus, Error> {
    holder.require_auth();

    // Anti-copycat, on-chain: only a built-in SAC has classic trustlines.
    if !matches!(sac.executable(), Some(Executable::StellarAsset)) {
        return Err(Error::NotSac);
    }
    let sac_client = StellarAssetClient::new(&env, &sac);

    // CAP-73: create the trustline if needed (silent no-op when it
    // already exists; created UNauthorized for an AUTH_REQUIRED issuer).
    sac_client
        .try_trust(&holder)
        .map_err(|_| Error::TrustFailed)?
        .map_err(|_| Error::TrustFailed)?;

    // Open asset, or already authorized: done.
    if sac_client.authorized(&holder) {
        return Ok(OnboardStatus::Authorized);
    }

    // Discover the one-step capability from the only address the
    // protocol allows to authorize: the SAC admin. A non-wasm admin
    // (G-account, SAC, nonexistent) cannot expose the interface.
    let admin = sac_client.admin();
    if !matches!(admin.executable(), Some(Executable::Wasm(_))) {
        return Ok(OnboardStatus::TrustlineOnly);
    }
    match AuthorizerClient::new(&env, &admin).try_authorize_trustline(&holder) {
        // Post-condition: the authorizer must have authorized the holder
        // on THIS sac — guards a no-op or divergent authorizer. Also
        // covers a wrong-return-shape success (Ok(Err(ConversionError))):
        // the post-condition resolves it either way.
        Ok(_) => {
            if sac_client.authorized(&holder) {
                Ok(OnboardStatus::Authorized)
            } else {
                Err(Error::NotAuthorized)
            }
        }
        // A typed contract error is a REJECTION (SEP rule) — revert
        // everything, including the trustline.
        Err(Ok(e)) if e.is_type(ScErrorType::Contract) => Err(Error::AuthorizationRefused),
        // Statically unreachable for E = soroban_sdk::Error (its error
        // conversion is infallible, so typed rejections always surface
        // as Err(Ok(_)) above); kept as defense-in-depth.
        Err(Err(soroban_sdk::InvokeError::Contract(_))) => Err(Error::AuthorizationRefused),
        // Anything else (squashed Context/InvalidAction abort: missing
        // export or an untyped panic) means "no authorize_trustline
        // interface": keep the trustline and report it truthfully.
        Err(_) => Ok(OnboardStatus::TrustlineOnly),
    }
}
```

Properties:

- The **only** required authorization is `holder.require_auth()` — one
  signature on a single Soroban transaction (Case C).
- `onboard` returns `OnboardStatus::Authorized` or
  `OnboardStatus::TrustlineOnly` — the caller learns whether the trustline is
  usable from the return value (or a simulation of it) rather than
  pre-classifying the asset.
- A typed contract error from the discovered authorizer is a REJECTION and
  reverts the whole transaction, including the trustline. An untyped abort
  (missing export, panic) is read as _no one-step interface_ and yields
  `TrustlineOnly`.
- `try_trust` is a no-op if the trustline already exists, so `onboard()` is
  **idempotent with respect to trustline creation** and MAY be retried safely.
  Idempotency is scoped to trustline creation only: it does **not** bypass
  policy. Because `authorize_trustline` re-evaluates policy on every call (§3),
  a retried `onboard()` against a banned, disallowed, or frozen holder MUST
  fail at the authorization step rather than re-authorize the account.
- Because `trust()` and `set_authorized` are both Soroban operations, they
  execute in one transaction; partial states (trustline created but not
  authorized) do not persist on success. On failure the whole Soroban
  invocation reverts.
- `onboard()` is the **fallback** single-signature path (§5): it exists for
  holders who have nobody to submit and pay a separate authorization
  transaction, and for wallets that render a Soroban authorization tree as
  clearly as a classic operation. On either path, integrators MUST NOT require
  the holder to sign `authorize_trustline` separately.

The router's own errors are fixed `u32` values for the same reason as the
Authorizer's (§3): a wallet needs to tell a refused holder apart from a failed
trustline creation without knowing which router implementation it hit.

| Code | Error                  | Condition                                                                             |
| ---- | ---------------------- | ------------------------------------------------------------------------------------- |
| `1`  | `NotSac`               | `sac` is not a built-in Stellar Asset Contract (CAP-68 check)                         |
| `2`  | `TrustFailed`          | CAP-73 `trust()` failed (reserve, missing account, native asset, issuer as holder, …) |
| `3`  | `AuthorizationRefused` | the discovered authorizer rejected `holder` with a typed error; whole tx reverted     |
| `4`  | `NotAuthorized`        | the authorizer reported success but `holder` is still not authorized                  |

This is mechanism (a) of the Design Rationale — _authorize trustlines on behalf
of users via a standard interface_ — which also explains why it is preferred
over (b) an intermediate account and (c) claimable balances.

### 5. The two reserve backends and integrator selection

CAP-73's `trust()` **does not support sponsorship**: the holder pays their own
0.5 XLM trustline reserve. This is correct for a CEX-withdrawal recipient who
already has a funded `G`-account, but it cannot onboard a **brand-new,
zero-XLM** account, which has no reserve to pay. The standard therefore defines
**two backends** and an integrator-side selection rule. **Backend 2 — the
classic path — is the default** for every holder, funded or not: the holder
signs a classic `ChangeTrust` (sponsored only when needed) and the integrator
completes authorization in a separate Soroban transaction the holder never
signs. Backend 1 — CAP-73 `onboard()` — is the fallback.

|                                | **Backend 1 — CAP-73 one-signature** (Cases A, C; fallback)                                           | **Backend 2 — classic `ChangeTrust`, CAP-33 sponsored when needed** (Case B; default)                                                                                                                 |
| ------------------------------ | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Primitive                      | Soroban `SAC.trust()` (CAP-73)                                                                        | Classic `ChangeTrust` signed by the holder; wrapped in `BEGIN/END_SPONSORING_FUTURE_RESERVES` (CAP-33), plus `CREATE_ACCOUNT` for a non-existent account, only when the holder cannot pay the reserve |
| Who pays the reserve(s)        | **Holder** (0.5 XLM trustline reserve)                                                                | **Holder** when funded; otherwise the **sponsor** (1 XLM base reserve if the account must be created + 0.5 XLM trustline reserve)                                                                     |
| Authorization (regulated only) | `Authorizer.authorize_trustline` inside `onboard()` (same Soroban tx)                                 | `Authorizer.authorize_trustline` (Case A) in a **separate** Soroban tx submitted and paid by the integrator — no holder or issuer signature; completion read from `is_authorized`                     |
| Holder signatures              | 1 (Case C); 0 if the trustline already exists (Case A)                                                | 1 holder signature on a classic tx (multi-signer only when sponsored: the sponsor co-signs)                                                                                                           |
| Transaction shape              | Single Soroban tx (`onboard`)                                                                         | Classic tx (plain, or a sponsorship sandwich), then one Soroban tx the holder does not sign                                                                                                           |
| What the holder reviews        | A Soroban invocation with an authorization tree                                                       | A plain `ChangeTrust` — the trustline prompt every wallet already renders                                                                                                                             |
| Account precondition           | Holder account already exists and is funded                                                           | Holder must control an on-ledger account to sign; a non-existent account requires sponsored `CREATE_ACCOUNT`                                                                                          |
| Best for                       | Self-custody holders with nobody to pay the second tx; wallets that render Soroban authorization well | **Default** — every holder; brand-new / underfunded holders additionally need a sponsor                                                                                                               |

Why there are two backends, and why the classic one is the default, is covered
in the Design Rationale.

#### Account existence on Backend 2 (normative)

Backend 2 onboards an account with **zero spendable XLM**, but it MUST
distinguish two cases, because an account that does not yet exist on the ledger
cannot sign anything and cannot hold a trustline:

- **(a) Existing account, insufficient XLM.** The holder account already exists
  (it holds at least the base reserve) but lacks the 0.5 XLM trustline reserve.
  The sponsor sponsors only the **trustline reserve**. The holder co-signs
  `ChangeTrust` / `END_SPONSORING_FUTURE_RESERVES` with the key that controls
  the existing account.
- **(b) Brand-new (non-existent) account.** The target `G`-address has no
  account entry. The transaction MUST additionally **create the account** via a
  `CREATE_ACCOUNT(holder, starting_balance)` sourced from the sponsor, so the
  sponsor pays **both** the 1 XLM base reserve **and** the 0.5 XLM trustline
  reserve. The holder keypair MUST control the resulting on-ledger account to
  provide its single signature on `ChangeTrust` /
  `END_SPONSORING_FUTURE_RESERVES`.

In both cases the holder MUST control an on-ledger account to sign
`END_SPONSORING_FUTURE_RESERVES` and `ChangeTrust`; the sponsor co-signs and
pays the sponsored reserves. The integrator MUST NOT treat "zero spendable XLM"
as equivalent to "account does not exist": the latter requires the additional
sponsored account creation in (b).

#### Selection rule (normative)

An integrator MUST select the path as follows, in order:

1. If the asset is `AUTH_REQUIRED` **and** the holder already has an
   **unauthorized** trustline → **Case A**: read `is_eligible(holder)`, call
   `authorize_trustline(holder)` on-behalf — **zero holder signatures** — and
   confirm via `is_authorized`.
2. Else → **Case B / Backend 2 (default)**. For a regulated asset, read
   `is_eligible(holder)` first; under an allowlist policy a `false` read routes
   the holder to `AUTH_ENDPOINT` (§7) before anything is signed. Then the
   holder signs one classic `ChangeTrust`, shaped by the account state:

   - account **exists** and its available balance ≥ the next reserve increment
     (0.5 XLM) → a plain `ChangeTrust` sourced by the holder, no sponsor;
   - account **exists** but is underfunded → **Backend 2 (a)**: the issuer's
     advertised `SPONSOR` (when `cap33-sponsored` is in `BACKENDS`) or the
     integrator itself sponsors the trustline reserve;
   - account **does not exist** → **Backend 2 (b)**: sponsor the base and
     trustline reserves, including `CREATE_ACCOUNT`.

   Then, for a regulated asset, the integrator submits
   `authorize_trustline(holder)` (Case A), paying the fee, and polls
   `is_authorized` before reporting completion. For an open asset the flow ends
   at the trustline.

3. **Case C / Backend 1 (fallback)** — CAP-73 `onboard()`, one holder signature
   on a Soroban transaction. An integrator MUST take this path instead of step
   2 when no party will submit and pay the separate authorization transaction
   (a self-custody holder onboarding with no relayer or sponsor behind them),
   and MAY take it when the wallet renders the Soroban authorization tree as
   clearly as a classic operation. It requires a funded holder account and
   `cap73-onesig` in `BACKENDS`.

Both backends MUST result in the same end state: the holder holds an
**authorized** trustline for a regulated asset, or a usable trustline for an
open asset.

### 6. `stellar.toml` discovery — `[TRUSTLINE_ONBOARDER]`

Per
[SEP-1](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0001.md),
an issuer advertises onboarder support with a `[TRUSTLINE_ONBOARDER]` table in
its `stellar.toml`. Any integrator reads exactly this block to drive the flow —
one issuer config yields universal interop, with no bilateral integration
deals.

| Field               | Type   | Req.  | Description                                                                                                                                                                                                                                                                                                                             |
| ------------------- | ------ | :---: | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `VERSION`           | string |  yes  | Version of this SEP the issuer implements (e.g., `"0.0.1"`).                                                                                                                                                                                                                                                                            |
| `ASSET_CODE`        | string |  yes  | Classic asset code being onboarded.                                                                                                                                                                                                                                                                                                     |
| `ASSET_ISSUER`      | `G…`   |  yes  | Classic issuer account.                                                                                                                                                                                                                                                                                                                 |
| `SAC`               | `C…`   |  yes  | Stellar Asset Contract address of the asset.                                                                                                                                                                                                                                                                                            |
| `AUTHORIZER`        | `C…`   |  no   | Trustline Authorizer contract (the SAC admin). INFORMATIONAL for the one-signature path (the router discovers the admin on-chain); used by integrators for the zero-signature Case-A authorize-on-behalf.                                                                                                                               |
| `ONBOARD_WRAPPER`   | `C…`   | cond. | The Trustline Onboard **router** exposing `onboard(sac, holder)`. REQUIRED if `cap73-onesig` is in `BACKENDS`. Integrators SHOULD prefer a pinned/curated router id over an advertised one.                                                                                                                                             |
| `POLICY`            | string | cond. | `"denylist"` or `"allowlist"`. REQUIRED when `AUTHORIZER` is set.                                                                                                                                                                                                                                                                       |
| `BACKENDS`          | list   |  yes  | Ordered preference, subset of `["cap73-onesig", "cap33-sponsored"]`. The default path (§5) needs neither token — a holder-signed plain `ChangeTrust` followed by authorize-on-behalf works with `AUTHORIZER` alone; `cap33-sponsored` advertises a sponsor for underfunded holders, `cap73-onesig` advertises the `onboard()` fallback. |
| `SPONSOR`           | `G…`   | cond. | Reserve sponsor account. REQUIRED if `cap33-sponsored` is in `BACKENDS`.                                                                                                                                                                                                                                                                |
| `AUTH_ENDPOINT`     | url    |  no   | Off-chain authorization/KYC endpoint (allowlist policy). SHOULD be SEP-10 gated.                                                                                                                                                                                                                                                        |
| `WEB_AUTH_ENDPOINT` | url    | cond. | SEP-10 endpoint used to authenticate to `AUTH_ENDPOINT`. REQUIRED if `AUTH_ENDPOINT` is set.                                                                                                                                                                                                                                            |

Example (regulated asset, denylist / open-by-default):

```toml
[TRUSTLINE_ONBOARDER]
VERSION = "0.0.1"
ASSET_CODE = "EURCV"
ASSET_ISSUER = "GCEYGIVOLAVBF2TG2RUSGTUJCIN75KEX3NGLMY4VPL4GFE5L355AXW3G"
SAC = "CANKBYNNAYKEZXLB655F2UPNTAZFK5HILZUXL7ZTFR3NF6LKDSVY7KFH"   # SAC for EURCV
AUTHORIZER = "CB2DHZMQHQE3TGUMD6BRM7UCJZNIPKDRVEQOWBIRRS3G2FZOGDTRKSB3"
ONBOARD_WRAPPER = "C…"              # Trustline Onboard wrapper
POLICY = "denylist"
BACKENDS = ["cap33-sponsored", "cap73-onesig"]
SPONSOR = "G…"                      # reserve sponsor for new / underfunded users
# AUTH_ENDPOINT / WEB_AUTH_ENDPOINT omitted: denylist policy is self-service
```

Example (open asset — no Authorizer, no authorize step):

```toml
[TRUSTLINE_ONBOARDER]
VERSION = "0.0.1"
ASSET_CODE = "USDC"
ASSET_ISSUER = "G…"
SAC = "C…"
ONBOARD_WRAPPER = "C…"              # required: cap73-onesig is in BACKENDS
# AUTHORIZER / POLICY omitted: asset is not AUTH_REQUIRED
BACKENDS = ["cap33-sponsored", "cap73-onesig"]
SPONSOR = "G…"
```

> The `AUTHORIZER` and `SAC` values above are the live mainnet EURCV contracts
> (`eurcv_auth` admin `CB2DHZ…KSB3`; SAC `CANKBYNN…7KFH`). No router is
> deployed on mainnet at the time of writing, so `ONBOARD_WRAPPER` is shown as
> a placeholder; the testnet router and authorizer ids are recorded with the
> reference implementation's testnet evidence (Reference Implementation).

### 7. Integrator interface and handoffs

A conformant integrator implements the following surface (the reference
implementation is the `@theahaco/authline` TypeScript SDK):

- `discover(toml)` — parse the issuer's `stellar.toml` `[TRUSTLINE_ONBOARDER]`
  block into a config. One config, any integrator.
- `decodeOnboardStatus(returnValue)` — decode the router's `OnboardStatus`
  (`Authorized` | `TrustlineOnly`) from a transaction's return value, so the
  integrator reports the truthful outcome instead of treating tx success as
  full activation. On this path the router detects the asset class on-chain, so
  no `auth_required` pre-check is needed (§1).
- `status(address)` — report whether the holder holds a trustline and whether
  it is authorized (`is_authorized`, or the trustline flags read from the
  ledger), to select the case (§2) and, polled after the authorize transaction,
  to confirm completion and show the holder "done".
- `eligible(address)` — read the Authorizer's `is_eligible` (§3) before
  building anything the holder signs or the integrator pays for.
- `buildSponsoredOnboardTx(...)` — build a reserve-free classic `ChangeTrust`
  (Backend 2 / Case B), with an optional sponsored `CreateAccount` for a
  brand-new account.
- `buildAuthorizeTx(...)` — build the permissionless authorize-on-behalf call
  (Case A; no holder/issuer signature) — the second transaction of the default
  path, which the integrator submits and pays for.
- `buildOnboardTx(...)` — build the CAP-73 one-transaction `onboard()` (Backend
  1 / Case C, the fallback).
- `onboardingRequest(...)` — produce the **handoffs**: a **SEP-7**
  `web+stellar:` URI, a wallet **deep link**, and a **hosted-redirect URL**. An
  exchange withdrawal screen hands the user off via any of these; a Stellar
  Wallets Kit wallet opens and signs the SEP-7 URI.

The handoffs decouple the third party that _initiates_ onboarding from the
wallet that holds the user's key: the third party builds the transaction and
emits a SEP-7 URI / deep link / hosted URL; the user's wallet completes the
at-most-one signature. The hosted-redirect target MAY be a reference
"activation page" (one reference consumer of this interface), but the standard
does not require any hosted page — a wallet that embeds the SDK can drive the
flow in-app.

**Co-signatures in a handoff.** A SEP-7 wallet adds the _holder's_ signature
and submits. That completes a **Backend 1 / Case C** transaction, whose only
required signer is the holder. It does **not** complete a **Backend 2 / Case
B** transaction: the sponsor sources the envelope and must sign it as well. An
integrator handing off a sponsored transaction MUST therefore either sign as
the sponsor **before** emitting the URI — a SEP-7 `xdr` is a full
`TransactionEnvelope`, so that signature travels with it and the holder's
completes it — or set the SEP-7 `callback` parameter so the wallet returns the
signed XDR for the integrator to countersign and submit. Emitting an unsigned
sponsored envelope with no `callback` produces a signature request that cannot
succeed, and implementations SHOULD reject it rather than hand the user a link
that fails on submit.

**Error handling.** A refused `authorize_trustline` or `onboard` surfaces as a
Soroban contract error carrying only a `u32` code (`Error(Contract, #n)`); the
name is not on the wire. Integrators MUST map that code through the §3 and §4
tables to choose what the user sees — a banned holder, a holder awaiting
allowlisting, a paused authorizer and a failed trustline creation each call for
a different message and a different next step — and SHOULD do so by simulating
the transaction before asking the holder to sign, so a refusal is shown up
front rather than after a signature.

For an **allowlist** policy, the integrator MUST ensure the holder is allowed
before submitting: it SHOULD authenticate to `WEB_AUTH_ENDPOINT` (SEP-10) and
call `AUTH_ENDPOINT` to trigger off-band KYC and a subsequent `allow(holder)`
by the Authorizer admin.

#### Backend 2 — classic `ChangeTrust`, then authorize-on-behalf (default, Case B)

The holder signs **once**, on a classic transaction that is a plain
`ChangeTrust` when the holder can pay the reserve, and a multi-signer
sponsorship sandwich co-signed by the sponsor when it cannot (with
`CREATE_ACCOUNT` for a brand-new account, so the sponsor pays the base reserve
as well). Authorization is a **second** transaction — Soroban, submitted and
paid by the integrator, carrying no holder signature — and completion is read
back from `is_authorized`.

```
Integrator (3rd party)              Holder                      Chain
    │ GET <issuer>/.well-known/stellar.toml; discover()          │
    │◄── [TRUSTLINE_ONBOARDER] ────────┤                           │
    │ simulate AUTHORIZER.is_eligible(holder) ────────────────────►│
    │◄── true  (false → AUTH_ENDPOINT / KYC first) ────────────────┤
    │ build classic tx:               │                           │
    │   [BEGIN_SPONSORING_FUTURE_RESERVES(holder)  source: SPONSOR]   (underfunded only)
    │   [CREATE_ACCOUNT(holder, base)             source: SPONSOR]   (new acct only)
    │   ChangeTrust(asset)                         source: holder  │
    │   [END_SPONSORING_FUTURE_RESERVES            source: holder]   (underfunded only)
    │── SEP-7 URI / deep link ────────►│                           │
    │◄── holder signs (1 signature) ───┤  a plain trustline prompt │
    │── co-sign as SPONSOR if sponsored; submit ──────────────────►│
    │◄── trustline exists (unauthorized when AUTH_REQUIRED) ───────┤
    │── AUTHORIZER.authorize_trustline(holder)  [integrator pays; no holder sig] ─►│
    │                                  │  policy check → set_authorized(true)     │
    │── poll AUTHORIZER.is_authorized(holder) ────────────────────►│
    │◄── true → show "done" ───────────────────────────────────────┤
```

> The holder MUST control an on-ledger account to sign `ChangeTrust` (and
> `END_SPONSORING_FUTURE_RESERVES` when sponsored). A brand-new (non-existent)
> account is created in the same transaction via the sponsored
> `CREATE_ACCOUNT`, and the holder keypair must control that account to provide
> its single signature (§5 "Account existence").

#### Backend 1 — CAP-73 one-signature (fallback, Case C)

```
Integrator (3rd party)              Holder                      Chain
    │ GET <issuer>/.well-known/stellar.toml; discover()          │
    │◄── [TRUSTLINE_ONBOARDER] ────────┤                           │
    │ build tx: invoke ONBOARD_WRAPPER.onboard(SAC, holder)
    │── SEP-7 URI / deep link ────────►│                           │
    │                                  │ sign (1 holder signature) │
    │◄─────────────────────────────────┤                           │
    │── submit ───────────────────────────────────────────────────►│
    │                                  │      trust(holder) [CAP-73]│
    │                                  │      authorize_trustline   │
    │                                  │      → set_authorized(true)│
    │◄── success: authorized trustline ───────────────────────────┤
```

A status check MUST be available by reading the holder's trustline flags
(classic) or the Authorizer's `is_authorized` (§3). After success the holder's
trustline has the `authorized` flag set (regulated) or simply exists (open).

On the default path the `ChangeTrust` transaction succeeding is **not**
completion for a regulated asset. Integrators MUST NOT report the holder as
onboarded until `is_authorized` (or the trustline's `authorized` flag) reads
true; they SHOULD show the intermediate "trustline created, authorization
pending" state with an explanation, SHOULD keep polling (or subscribe to the §8
`authorized` event) and notify the holder when it flips, and MUST surface a
refused authorize (§3 error codes) rather than leave the holder waiting.

### 8. Audit events

The Authorizer MUST emit a structured event for every authorization-state
transition so issuers can build a MiCA-style audit trail without an indexer of
their own.

| Topic                                              | Data                                   | Emitted on                                    |
| -------------------------------------------------- | -------------------------------------- | --------------------------------------------- |
| `("authorized", account)`                          | `{ policy, authorizer_admin, ledger }` | successful `authorize_trustline`              |
| `("deauthorized", account)`                        | `{ reason, authorizer_admin, ledger }` | `deauthorize_trustline`                       |
| `("banned", account)` / `("unbanned", account)`    | `{ authorizer_admin, ledger }`         | denylist updates                              |
| `("allowed", account)` / `("disallowed", account)` | `{ authorizer_admin, ledger }`         | allowlist updates                             |
| `("frozen", account)` / `("unfrozen", account)`    | `{ authorizer_admin, ledger }`         | freeze lifecycle (ban/disallow + deauthorize) |
| `("clawback", from)`                               | `{ amount, authorizer_admin, ledger }` | clawback                                      |
| `("paused")` / `("unpaused")`                      | `{ authorizer_admin, ledger }`         | pause lifecycle                               |

Events MUST identify the policy in force and the admin that authorized the
state change. `reason` SHOULD be an enumerated code (e.g., `sanctions`,
`kyc_expired`, `issuer_request`) to support compliance reporting.

## Design Rationale

### Why authorize-on-behalf via a standard interface

Three mechanisms can deliver frictionless activation: **(a)** authorize
trustlines on behalf of users via a standard interface, **(b)** an intermediate
account that holds and forwards, **(c)** claimable balances. This SEP specifies
**(a)** as the primary, general path and documents (b)/(c) as situational
alternatives.

- **(a) Authorize on behalf** keeps the holder as the **direct, sole owner** of
  the trustline and the asset. It works for both asset classes: for open assets
  it is a sponsored `ChangeTrust`; for regulated assets it adds permissionless
  authorize-on-behalf. With CAP-73 it is a single signature and a single atomic
  transaction (Case C), and for a pre-existing unauthorized trustline it is
  **zero** signatures (Case A). Authorization policy is on-chain (Authorizer =
  SAC admin), so it is deterministic and auditable. This matches the live EURCV
  model and the reference implementation.
- **(b) Intermediate account** has the third party control a temporary account,
  trust + receive there, then forward. It unblocks the _exchange side_, but the
  **user still needs their own trustline** to finally hold the asset — so it
  suits **custodial** flows or new-account provisioning, not self-custody. It
  adds a custodial hop, a second transfer, reconciliation, and — for a
  regulated asset — a custody/liability question.
- **(c) Claimable balances** let the third party send a claimable balance to a
  trustline-less user, so the withdrawal completes with **zero user action at
  that moment**; the user creates a trustline and **claims later**. It defers
  rather than removes the trustline step, and claimable-balance entries consume
  reserves.

  The deferred cost is **one signature for an open asset and two for a
  regulated one**, and the difference is a protocol constraint, not an
  implementation choice. For an open asset the claim transaction can carry the
  `ChangeTrust` that onboards the user —
  `BeginSponsoringFutureReserves · ChangeTrust · EndSponsoringFutureReserves · ClaimClaimableBalance`
  — so a single user signature both establishes the trustline and collects the
  funds, and with the sender as fee source and sponsor the user spends no XLM
  at all. For an `AUTH_REQUIRED` asset the claimant must be authorized **at
  claim time**, and authorization here is a Soroban call to the Authorizer; a
  Soroban invocation must be the **only** operation in its transaction (the
  network rejects a mixed envelope with
  `Transaction contains more than one operation`), so it cannot be placed
  between the `ChangeTrust` and the claim. A regulated claim is therefore
  necessarily three transactions — create trustline (user), authorize
  (**integrator, no user signature**, i.e. Case A), claim (user).

  The reference SDK implements this as an extension, exercised against testnet
  including the on-chain rejection of the fused regulated claim. It remains
  **outside the normative interface** (§1–§8): an integrator can interoperate
  fully without it.

This SEP specifies **(a)** as primary: the general, non-custodial,
interoperable path that works for both asset classes; **(b)/(c)** are
documented situational alternatives. (b) and (c) are not part of the normative
interface.

### Why the classic path is the default

CAP-73 makes a single-transaction, single-signature onboarding possible, yet
this SEP specifies it as the fallback rather than the default. Most wallets
render a classic `ChangeTrust` as a clear, familiar trustline prompt, and
render a Soroban invocation with a nested authorization tree far less legibly.
Moving the holder's one signature from a `ChangeTrust` to `onboard()` therefore
makes the signing step **less** clear for most holders, not more — and the
signature over `onboard()` covers the sub-invocations of an admin contract
chosen by the asset (Security Concerns), which is exactly the part a wallet
struggles to show.

Splitting the two steps adds nothing the holder has to sign or see. The only
step that needs the holder's key is creating the trustline, and that is what
the holder still signs. Authorization was never the holder's to sign:
`authorize_trustline` is permissionless, so the integrator submits it and pays
its fee in a second transaction the holder never sees, and `is_authorized`
tells the wallet when to say "done". `onboard()` stays specified for the two
situations where a second, integrator-paid transaction is unavailable or
unnecessary: a self-custody holder onboarding with no relayer or sponsor behind
them, and a wallet that already renders Soroban authorization as well as it
renders classic operations.

### What applications cannot fix on their own

Two of the frictions this SEP addresses are application problems. Reserve
friction is solved by sponsorship (CAP-33), which wallets and exchanges can
adopt today and many do not. Visibility — showing the holder that a trustline
exists but is not yet authorized, explaining what that means, and notifying
them when it flips — is achieved by polling the trustline's `authorized` flag,
which any application can do now and SHOULD (§7). Neither needs a standard, and
this SEP asks applications to do both.

What an application cannot do is **end the wait**. Authorizing an
`AUTH_REQUIRED` trustline requires the issuer: a `SetTrustLineFlags` signed by
the issuer key, or a call to whatever contract the issuer has made SAC admin —
and where an issuer has delegated to a contract, that contract's interface is
bespoke to the issuer, so a wallet that can authorize one regulated asset knows
nothing about the next. This SEP standardizes the delegation
(`authorize_trustline`, its policy model, its reads) and its discovery
(`[TRUSTLINE_ONBOARDER]`), so any third party can complete authorization for
any conforming asset without an issuer signature and without a bilateral
integration. Applications can make the wait visible; a standard authorization
interface is what lets them end it.

### Why two backends instead of one

Classic and Soroban operations cannot be mixed in one transaction. The
one-signature, atomic `onboard()` is only achievable on the Soroban side via
CAP-73 — but CAP-73 has no sponsorship, so it cannot onboard a brand-new or
underfunded holder. Letting someone else pay the base and trustline reserves
requires the _classic_ CAP-33 sponsorship construction, which is several
classic operations and therefore cannot be a single Soroban transaction. A
single backend cannot serve every holder, so the standard exposes both with a
deterministic selection rule (§5) rather than forcing integrators to pick
wrong.

The "one signature" property differs by backend: on Backend 1 the holder signs
a single Soroban transaction; on Backend 2 the holder signs one classic
transaction, which the sponsor co-signs only when it pays the reserves. The
standard is explicit about this so the one-signature claim is never read as
"single-signer."

### Why a contract as SAC admin (vs issuer-key authorization)

Setting a policy contract as SAC admin moves the authorization decision
on-chain. The policy (denylist/allowlist) is then transparent, deterministic,
retryable, and self-service for the common (denylist) case, and every state
change emits an audit event. Off-chain issuer-key authorization provides none
of these, requires the issuer to co-sign (as a SEP-8 approval server does, per
transaction), and cannot be composed atomically with CAP-73 `trust()`.
Delegating once to a permissionless contract replaces per-transaction
co-signing with a one-time admin transfer.

## Security Concerns

- **Admin compromise.** The Authorizer's `admin` can ban/freeze/clawback/mint
  and can `upgrade` the contract. Issuers SHOULD use a multisig or threshold
  account as the Authorizer admin (`admin-sep` `set_admin`), and SHOULD treat
  `upgrade` and `clawback` as the highest-privilege operations.
- **The holder's signature covers the discovered admin's sub-invocations.**
  `onboard()` invokes the asset's SAC admin — a contract chosen by the _asset_,
  not by the integrator. In recording-mode simulation, any nested
  `holder.require_auth()` the admin triggers is folded into the single root
  authorization the holder signs, and the router cannot prevent a malicious
  admin from abusing this. Integrators MUST therefore only onboard SACs from a
  trusted/pinned source, and wallets SHOULD render the full authorization tree
  before signing.
- **Permissionless self-authorization (denylist).** Under the denylist policy,
  `authorize_trustline` is intentionally permissionless — any non-banned
  account may authorize itself or be authorized on-behalf. Issuers requiring
  per-user gating MUST use the allowlist policy. Sanctions screening for the
  denylist MUST be enforced by keeping the banned set current; the standard
  cannot screen accounts the issuer has not banned.
- **Replayed authorization and the freeze lifecycle.** Because
  `authorize_trustline` is permissionless under denylist and a retried
  `onboard()` re-runs the authorization step, `authorize_trustline` MUST
  consult the policy on **every** call (§3), and `freeze_accounts` MUST set the
  banned/disallowed bit in addition to deauthorizing (§3 "Freeze / deauthorize
  lifecycle"). A frozen-but-not-banned state MUST NOT exist; otherwise a
  replayed `onboard()` would re-authorize a previously frozen account. Where
  stronger reversibility is needed, the issuer retains `clawback` (under
  `AUTH_CLAWBACK_ENABLED`).
- **`CannotAuthorizeAdminContract`.** The Authorizer MUST refuse to authorize
  its own address to avoid self-referential trust states.
- **Reserve griefing on the sponsored backend.** When Backend 2 is sponsored,
  the sponsor pays the base and/or trustline reserve. The sponsor SHOULD
  rate-limit and/or KYC-gate sponsorship to prevent reserve drain, and SHOULD
  reclaim reserves on trustline/account removal where applicable.
- **Reentrancy / partial state.** `onboard()` runs `trust()` then
  `authorize_trustline()` in one Soroban invocation; a failure reverts both.
  Implementations MUST NOT leave a trustline created-but-unauthorized as a
  _persisted success_ state of `onboard()`. On the default classic path a
  created-but-unauthorized trustline is the legitimate intermediate state
  between the two transactions; integrators MUST NOT present it as completion
  (§7), and MUST retry or surface a refused authorize rather than leave the
  holder there silently.
- **`stellar.toml` integrity.** Integrators MUST fetch `stellar.toml` over TLS
  from the issuer's `home_domain` and SHOULD verify the `AUTHORIZER`/`SAC`
  addresses against an out-of-band source before authorizing high-value flows.
  A compromised `stellar.toml` could redirect users to a malicious wrapper; the
  on-chain `onboard()` still requires the holder's signature, but the holder
  could be induced to sign against a wrong asset. SEP-7 URIs and deep links
  carry the same obligation: the wallet SHOULD display the asset and contract
  being signed.
- **CAP-73 no-op semantics.** `trust()` is a no-op for existing trustlines and
  C-addresses. Integrators MUST NOT assume `onboard()` created a _new_
  trustline; idempotency is a property to rely on, not a signal that nothing
  existed before.
- **SEP-10 gating.** Any off-chain `AUTH_ENDPOINT` (allowlist KYC) MUST be
  authenticated with SEP-10 to bind the request to the holder's account.

## Backwards Compatibility

This SEP introduces no protocol change and is **purely additive**.

- Issuers that do not publish `[TRUSTLINE_ONBOARDER]` are unaffected; wallets
  simply do not offer the onboarding flow.
- Open (non-`AUTH_REQUIRED`) assets need no Authorizer; the standard degrades
  to a sponsored `ChangeTrust` for them.
- The default path (holder signs `ChangeTrust`, then `authorize_trustline` is
  called on-behalf; §5) asks the holder for exactly the signature they give
  today. Adopting the SEP adds discovery, a standard authorize call and
  standard reads on top of that — not a new signing shape for the holder.
- The `onboard()` wrapper depends on CAP-73's `SAC.trust()`, live since
  Protocol 26; integrators on pre-26 history MUST use the default classic path.
  The standard therefore degrades gracefully if CAP-73 is unavailable.
- `admin-sep` compatibility: the Authorizer is an `Administratable` contract,
  so any tooling that understands `admin-sep`'s `admin`/`set_admin`/`upgrade`
  surface works unchanged.

## Reference Implementation

The reference implementation is at
[github.com/theahaco/authline](https://github.com/theahaco/authline)
(Apache-2.0).

| Component                                                                                                                                                       | Status          | Reference                                                                                                                 |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **Trustline Authorizer** — the full §3 interface: both policies, every admin and lifecycle entry point, the read interface, and a §8 event for every transition | Live on testnet | `contracts/trustline-authorizer`                                                                                          |
| **Trustline Onboard** router — `onboard(sac, holder)` with on-chain authorizer discovery (§4)                                                                   | Live on testnet | `contracts/trustline-onboard`                                                                                             |
| `eurcv_auth` — the denylist Authorizer this SEP generalizes, SAC admin of EURCV                                                                                 | Live on mainnet | [`CB2DHZ…KSB3`](https://stellar.expert/explorer/public/contract/CB2DHZMQHQE3TGUMD6BRM7UCJZNIPKDRVEQOWBIRRS3G2FZOGDTRKSB3) |
| `@theahaco/authline` integrator SDK — the §7 surface: discovery, status, transaction builders, SEP-7 handoffs                                                   | Available       | `packages/authline-sdk`                                                                                                   |
| Authorization **relayer** — the §7 interface as HTTP (`GET /v1/accounts/{a}/ready`, `POST /v1/accounts/{a}/authorize`), self-hostable                           | Available       | `packages/relayer`                                                                                                        |
| Issuer admin CLI over every Authorizer entry point                                                                                                              | Available       | `scripts/authorizer.mjs`                                                                                                  |

### Implementation notes (non-normative)

Implementing the §7 interface as a hosted service surfaced three points that
any implementation of this SEP should carry over:

- **"Not ready" is three different states, not one.** The integrator's remedial
  action differs per state, so a readiness answer must distinguish `no_account`
  (fund it, or deliver via claimable balance), `no_trustline` (onboard through
  the default path) and `trustline_unauthorized` (the §3 authorize fixes it). A
  missing account and a missing trustline read identically from the trustline
  ledger entry; disambiguating them costs one extra account lookup.
- **Expose the policy pre-check.** `is_eligible` (§3) should be consulted
  before submitting an authorize the integrator pays fees for: a readiness
  response that carries `authorizable: false` turns a fee-costing on-chain
  refusal into a free read. When the policy cannot be read, say "unknown"
  rather than guessing.
- **Authorize-on-behalf must be idempotent at the service layer.** Exchange
  flows naturally race (retry queues, duplicate webhooks); answering an
  already-authorized account with success-without-submission makes the
  permissionless entry point safe to call from at-least-once pipelines.

Because `authorize_trustline` is permissionless and the policy is enforced by
the Authorizer contract, a relayer holds **no authority**: its key only pays
fees, and denying service at the relayer denies nothing — the contract remains
the single enforcement point. Every compliance-relevant fact lives on-chain as
an address plus enumerated codes, and no personal data exists anywhere in the
flow.

### Testnet evidence

Every flow in this SEP has been exercised on testnet: the default path (Case B,
then A), authorize-on-behalf (Case A), the `onboard()` fallback for both asset
classes (Case C), claimable-balance delivery, and the full authorization
lifecycle, including the freeze-replay invariant. Because testnet is reset
periodically, the deployment ids and transaction links are kept outside this
document, in
[`docs/sep-testnet-evidence.md`](https://github.com/theahaco/authline/blob/main/docs/sep-testnet-evidence.md).

## Changelog

- `v0.0.1`: Initial draft. Pre-submission history and review:
  [discussion #2008](https://github.com/orgs/stellar/discussions/2008).
