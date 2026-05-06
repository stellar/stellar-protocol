## Preamble

```
SEP: XXXX
Title: Hierarchical Mandate Tokens for Autonomous Agent Authority
Authors: Felipe Nunes Oliveira <@devfelipenunes>
Track: Standard
Status: Draft
Created: 2026-05-01
Updated: 2026-05-05
Version: 0.3.0
Discussion: https://github.com/orgs/stellar/discussions/1925
```

## Simple Summary

A standardized Soroban contract interface for issuing non-transferable, revocable
**Mandate tokens** that allow a sovereign identity (**Root Anchor**) to delegate
programmable, scoped, and auditable authority to AI agents or automated systems —
without sharing private keys.

## Motivation

The emergence of agentic AI systems on Stellar creates a fundamental trust problem:
how can a human grant an autonomous agent the ability to act on their behalf without
handing over their private key?

Current approaches are inadequate:

- **Key sharing** is dangerous — a compromised agent gains unlimited authority forever.
- **Multisig schemes** require coordination overhead and do not encode spending limits
  or contract restrictions at the protocol level.
- **Off-chain permission systems** are invisible to smart contracts and cannot be
  verified by third-party dApps in a trustless manner.

This SEP defines a primitive that fills this gap: a cryptographically-enforced,
on-chain delegation standard that any Soroban contract can integrate to verify
whether an agent is authorized to act — and within what bounds.

## Abstract

This proposal defines a Soroban contract interface for hierarchical, non-transferable
authority tokens on the Stellar network. The standard separates **Sovereign Identity**
(who holds the authority) from **Operational Authority** (what actions are permitted).

A **Mandate** is a Soulbound Token (SBT) that encodes a cryptographically enforced
**Scope**. Mandates are registered in the **Nexus**, an on-chain registry that
third-party contracts can query to verify an agent's authority in a single call.

The standard introduces four interlocking mechanisms:

1. **Authority Epochs** — a single-transaction revocation mechanism for entire mandate
   trees, eliminating the gas cost of individual revocations.
2. **DelegationPolicy** — granular sub-delegation rules that prevent budget exhaustion
   through cascading sub-agents.
3. **Bounded Verification** — a depth cap and epoch-keyed cache that gives
   `verify_authority` a predictable, auditable gas cost.
4. **SEP-45 Remote Issuance** — allowing off-chain signers (hardware wallets, mobile
   signers) to issue Mandates without ever exposing their key to the contract
   environment.

## Dependencies

- **[SEP-41](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0041.md)**
  (Soroban Token Interface): Token structure baseline.
- **[SEP-10](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0010.md)**
  (Stellar Web Authentication): Authentication for Root Anchor operations performed
  via web clients.
- **[SEP-45](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0045.md)**
  (Stellar Remote Authentication): Foundation for the `MandateRequest` remote
  issuance flow defined in Section VI of this SEP.

## Terminology

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHOULD", "SHOULD NOT",
"RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as
described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

| Term | Definition |
|---|---|
| **Root Anchor** | The original sovereign identity (e.g., a SoulID) that holds primary authority over a mandate tree. |
| **Issuer** | The address that signs and submits a `issue_mandate` transaction. May be the Root Anchor or an authorized Agent. |
| **Agent** | The address that receives a Mandate and may act within its Scope. |
| **Mandate** | A non-transferable, revocable token encoding delegated authority. Called **Wills** in the Zolvency ecosystem. |
| **Scope** | The immutable set of rules (TTL, budget, allowlists) attached to a Mandate at issuance. |
| **MandateState** | The mutable runtime state of a Mandate (spent budget, revocation flag), maintained separately by the Nexus. |
| **Nexus** | The central Soroban smart contract that registers, validates, and caches Mandates. |
| **Authority Epoch** | A monotonic counter on the Root Anchor. Incrementing it globally invalidates all Mandates issued under prior epochs. |
| **Verification Cache** | An epoch-keyed, on-chain cache that reduces `verify_authority` cost from O(depth) to O(1) on cache hit. |
| **Delegation Depth** | The level of a Mandate in the delegation tree. Root Anchor is depth 0; each sub-delegation increments by 1. |

## Specification

### I. Data Structures

#### 1.1 Mandate

```rust
pub struct Mandate {
    /// Unique identifier assigned by the Nexus at issuance.
    pub id: u64,
    /// The sovereign identity at the root of this delegation chain.
    pub root_anchor: Address,
    /// The address that issued this specific Mandate (Root Anchor or Agent).
    pub issuer: Address,
    /// The address authorized to act under this Mandate.
    pub agent: Address,
    /// Immutable rules governing the Agent's authority. See Section I.2.
    pub scope: Scope,
    /// The Authority Epoch of the Root Anchor at the time of issuance.
    /// If root_anchor.current_epoch > issued_at_epoch, this Mandate is invalid.
    pub issued_at_epoch: u64,
    /// Controls whether and how this Agent may sub-delegate. See Section I.3.
    pub delegation_policy: DelegationPolicy,
    /// The id of the parent Mandate, if this is a sub-delegation.
    pub parent_mandate_id: Option<u64>,
    /// Depth of this Mandate in the delegation tree (Root Anchor = 0).
    pub depth: u8,
}
```

#### 1.2 Scope

The `Scope` struct is **immutable** after issuance. It represents the
"promise" made at delegation time. Runtime state (spent budget, revocation)
is tracked separately in `MandateState`.

```rust
pub struct Scope {
    /// REQUIRED. Unix timestamp after which this Mandate expires.
    pub ttl: u64,

    /// OPTIONAL. Maximum cumulative value (in stroops) this Agent may transfer.
    /// The Nexus tracks spending against this limit in MandateState.
    pub transfer_limit: Option<i128>,

    /// OPTIONAL. Hash commitment over this Scope for ZKP-based private
    /// verification. The scheme for generating and verifying this commitment
    /// is out of scope for this SEP and SHOULD be defined in a companion SEP.
    pub scope_commitment: Option<BytesN<32>>,

    /// OPTIONAL. If set, the Agent may only invoke contracts in this list.
    pub contract_allowlist: Option<Vec<Address>>,

    /// OPTIONAL. If set, the Agent may only call functions in this list.
    /// Function names are matched as exact strings.
    pub function_allowlist: Option<Vec<Symbol>>,
}
```

#### 1.3 DelegationPolicy

Replaces the previous `can_delegate: bool` field. Encodes granular constraints
on how an Agent may sub-delegate its authority.

```rust
pub enum DelegationPolicy {
    /// This Agent MUST NOT delegate authority to any other address.
    None,

    /// This Agent MAY delegate its full Scope without additional restrictions.
    Full,

    /// This Agent MAY delegate, subject to the rules in DelegationRules.
    Restricted(DelegationRules),
}

pub struct DelegationRules {
    /// Maximum number of additional delegation levels below this Mandate.
    /// 0 means the Agent may issue Mandates to direct sub-agents, but those
    /// sub-agents cannot delegate further.
    pub max_subdepth: u8,

    /// Restricts which Scope fields may be included in a sub-Mandate.
    /// If None, all fields from the parent Scope may be re-delegated
    /// (subject to the invariant that sub-Scope ≤ parent Scope).
    pub allowed_scope_tags: Option<Vec<ScopeTag>>,

    /// Maximum fraction of transfer_limit that may be allocated to a single
    /// child Mandate, expressed as a percentage (0–100).
    /// The Nexus additionally enforces that the SUM of all active child
    /// transfer_limit values does not exceed parent.transfer_limit.
    pub budget_fraction: Option<u8>,
}

pub enum ScopeTag {
    TransferLimit,
    ContractAllowlist,
    FunctionAllowlist,
    ScopeCommitment,
}
```

#### 1.4 MandateState

Mutable runtime state maintained by the Nexus. Separated from `Scope` to
preserve the immutability of the issuance record.

```rust
pub struct MandateState {
    pub mandate_id: u64,
    /// Cumulative value spent under this Mandate (in stroops).
    /// Updated by the Nexus each time verify_authority approves a transfer.
    pub spent_budget: i128,
    /// Set to true by revoke_mandate or when the Root Anchor increments its epoch.
    pub allocated_to_children: i128,
    pub is_revoked: bool,
}
```

#### 1.5 VerificationCache

Reduces the gas cost of repeated `verify_authority` calls within the same
Authority Epoch.

```rust
pub struct VerificationCache {
    pub mandate_id: u64,
    /// Epoch value at the time this entry was written.
    /// Stale if root_anchor.current_epoch != epoch_at_cache.
    pub epoch_at_cache: u64,
    pub is_valid: bool,
    pub cached_at_ledger: u32,
}
```

---

### II. Network Constants

| Constant | Default | Description |
|---|---|---|
| `MAX_DELEGATION_DEPTH` | `8` | Maximum depth of any Mandate in a delegation tree. Enforced at issuance. |
| `CACHE_TTL_LEDGERS` | `100` | Number of ledgers a VerificationCache entry remains valid. After expiry, `verify_authority` re-traverses the chain. |

---

### III. Core Interface

#### `issue_mandate`

```rust
fn issue_mandate(
    env: Env,
    issuer: Address,
    agent: Address,
    scope: Scope,
    delegation_policy: DelegationPolicy,
    parent_mandate_id: Option<u64>,
) -> Result<u64, MandateError>;
```

Issues a new Mandate. The Nexus MUST enforce all of the following before
persisting the Mandate:

1. **Issuer authorization**: `issuer` MUST have invoked this function (auth check
   via `issuer.require_auth()`).
2. **Parent validation**: If `parent_mandate_id` is `Some(id)`:
   - The parent Mandate MUST be valid (not revoked, not expired, epoch current).
   - The parent's `delegation_policy` MUST NOT be `None`.
   - If `Restricted(rules)`, the `budget_fraction` and `allowed_scope_tags`
     invariants MUST be satisfied.
   - The new Mandate's `scope` MUST be equal to or more restrictive than the
     parent's `scope` in every dimension.
3. **Depth cap**: `parent.depth + 1` MUST NOT exceed `MAX_DELEGATION_DEPTH`.
4. **Budget cap**: If `transfer_limit` is set, the parent's `MandateState.allocated_to_children`
     plus the new Mandate's `transfer_limit` MUST NOT exceed the parent's
     `scope.transfer_limit` after this issuance.

Returns the new Mandate's `id` on success.

---

#### `revoke_mandate`

```rust
fn revoke_mandate(
    env: Env,
    caller: Address,
    mandate_id: u64,
) -> Result<(), MandateError>;
```

Invalidates the specified Mandate and all of its descendants atomically.

- `caller` MUST be either the `root_anchor` of the mandate tree or the
  direct `issuer` of the target Mandate.
- The Nexus MUST set `MandateState.is_revoked = true` for the target and all
  descendant Mandates in a single atomic operation.
- All `VerificationCache` entries for affected Mandates MUST be invalidated.

---

#### `verify_authority`

```rust
fn verify_authority(
    env: Env,
    mandate_id: u64,
    contract: Address,
    function: Symbol,
    transfer_amount: Option<i128>,
) -> Result<bool, MandateError>;
```

The primary integration point for third-party Soroban contracts. Verifies that
a Mandate is currently authorized to perform the requested action.

**Verification algorithm:**

```
1. Load root_anchor.current_epoch (E).

2. Check VerificationCache for (mandate_id, E):
   - HIT (and not expired): return cached result.        → O(1)
   - MISS: proceed to step 3.

3. Traverse the chain from mandate_id up to root_anchor,
   bounded by MAX_DELEGATION_DEPTH:
   a. For each node, verify:
      - issued_at_epoch == E               (epoch current)
      - MandateState.is_revoked == false   (not revoked)
      - scope.ttl >= env.ledger().timestamp() (not expired)
   b. At the leaf node, additionally verify:
      - contract is in scope.contract_allowlist (if set)
      - function is in scope.function_allowlist (if set)
      - MandateState.spent_budget + transfer_amount
        <= scope.transfer_limit            (if set)

4. Write result to VerificationCache keyed by (mandate_id, E).

5. If valid and transfer_amount is Some(v):
   - Atomically increment MandateState.spent_budget by v.

6. Return result.
```

> **Gas bound**: Steps 1–4 traverse at most `MAX_DELEGATION_DEPTH` nodes
> (default 8). The worst-case gas cost is therefore a fixed, auditable constant
> regardless of ecosystem-wide tree size.

---

#### `increment_epoch`

```rust
fn increment_epoch(env: Env, root_anchor: Address) -> Result<u64, MandateError>;
```

- `root_anchor` MUST invoke this function (`root_anchor.require_auth()`).
- Atomically increments `root_anchor.current_epoch` by 1.
- All previously issued Mandates referencing the old epoch are immediately
  invalid from the perspective of `verify_authority` (step 3a above).
- The Nexus MAY clear the consumed-nonce set for this Root Anchor, as all
  prior `MandateRequest` nonces are rendered unreplayable by the epoch change.
- Returns the new epoch value.

---

### IV. SEP-45 Remote Mandate Issuance

SEP-45 is used when the Root Anchor resides off-chain (e.g., a hardware wallet,
mobile signer, or cross-chain address) and cannot submit Soroban transactions
directly. A relayer submits the signed request on the Root Anchor's behalf.

#### Flow

```
┌─────────────┐        ┌──────────────┐        ┌─────────────┐
│  Root Anchor│        │   Relayer    │        │    Nexus    │
│ (off-chain) │        │  (any party) │        │  (Soroban)  │
└──────┬──────┘        └──────┬───────┘        └──────┬──────┘
       │                      │                       │
       │  1. Build & sign      │                       │
       │  MandateRequest via   │                       │
       │  SEP-45 challenge     │                       │
       │─────────────────────>│                       │
       │                      │  2. Submit signed     │
       │                      │  MandateRequest       │
       │                      │──────────────────────>│
       │                      │                       │ 3. Validate SEP-45
       │                      │                       │    signature
       │                      │                       │ 4. Check epoch & nonce
       │                      │                       │ 5. issue_mandate(...)
       │                      │  6. Return mandate_id │
       │                      │<─────────────────────-│
```

#### MandateRequest Structure

```rust
pub struct MandateRequest {
    /// The sovereign identity authorizing this issuance.
    pub root_anchor: Address,
    /// The agent that will receive the Mandate.
    pub agent: Address,
    /// The scope to be granted.
    pub scope: Scope,
    /// The delegation policy to be granted.
    pub delegation_policy: DelegationPolicy,
    /// MUST match root_anchor.current_epoch at the time of Nexus processing.
    /// Prevents replay of this request after the Root Anchor increments its epoch.
    pub epoch: u64,
    /// A random nonce. The Nexus MUST reject any MandateRequest whose nonce
    /// has already been consumed for this Root Anchor in the current epoch.
    pub nonce: BytesN<32>,
    /// SEP-45 signature over the canonical encoding of all fields above.
    pub sep45_signature: BytesN<64>,
}
```

The Nexus MUST maintain a consumed-nonce set per Root Anchor per epoch and
MUST reject duplicate nonces. This set MAY be cleared when `increment_epoch`
is called, as the epoch change renders prior nonces irreplayable.

---

### V. Error Types

```rust
pub enum MandateError {
    Unauthorized,              // caller lacks permission
    MandateNotFound,           // mandate_id does not exist
    MandateRevoked,            // mandate or ancestor has been revoked
    MandateExpired,            // scope.ttl has passed
    EpochMismatch,             // issued_at_epoch < root_anchor.current_epoch
    BudgetExceeded,            // transfer would exceed scope.transfer_limit
    ContractNotAllowed,        // contract not in scope.contract_allowlist
    FunctionNotAllowed,        // function not in scope.function_allowlist
    DepthExceeded,             // sub-delegation would exceed MAX_DELEGATION_DEPTH
    DelegationNotAllowed,      // parent delegation_policy is None
    ScopeViolation,            // child scope is broader than parent scope
    BudgetFractionViolated,    // child transfer_limit exceeds budget_fraction
    NonceAlreadyConsumed,      // MandateRequest nonce has been used
    InvalidSep45Signature,     // SEP-45 signature verification failed
}
```
---

### VI. Normative Events

The Nexus MUST emit the following events to ensure off-chain observability:

    mandate_issued: [Symbol("mandate"), Symbol("issued"), mandate_id, agent]

    mandate_revoked: [Symbol("mandate"), Symbol("revoked"), mandate_id]

    budget_spent: [Symbol("mandate"), Symbol("spend"), mandate_id, amount]

    epoch_incremented: [Symbol("anchor"), Symbol("epoch_inc"), root_anchor, new_epoch]

---

### VII. Usage Example — Third-Party Integration

The following example shows how a lending protocol on Soroban would call the
Nexus to verify that an AI agent (`agent_address`) is authorized to borrow
on behalf of a user (`user_address`).

```rust
// lending_protocol/src/lib.rs

use soroban_sdk::{contract, contractimpl, Address, Env, Symbol};

// Import the Nexus client (generated from its contract interface)
use nexus_client::NexusClient;

#[contract]
pub struct LendingProtocol;

#[contractimpl]
impl LendingProtocol {
    /// Called by an AI agent to borrow on behalf of a user.
    ///
    /// # Arguments
    /// * `mandate_id` - The Mandate the agent is acting under.
    /// * `agent`      - The agent's address (must match Mandate.agent).
    /// * `amount`     - Amount to borrow in stroops.
    pub fn borrow(
        env: Env,
        mandate_id: u64,
        agent: Address,
        amount: i128,
    ) -> Result<(), LendingError> {
        // 1. Require the agent to have signed this transaction.
        agent.require_auth();

        // 2. Instantiate the Nexus client using its deployed contract address.
        let nexus_address = Address::from_str(&env, "Cnexus...ADDRESSHERE")
          .expect("Invalid Nexus address");
        let nexus = NexusClient::new(&env, &nexus_address);

        // 3. Verify authority. The Nexus checks epoch, TTL, budget, and allowlists.
        //    It also atomically increments spent_budget if the call is approved.
        let authorized = nexus.verify_authority(
            &mandate_id,
            &env.current_contract_address(), // this contract
            &Symbol::new(&env, "borrow"),    // this function
            &Some(amount),                   // transfer amount for budget tracking
        );

        match authorized {
            Ok(true) => { /* proceed */ }
            Ok(false) => return Err(LendingError::AgentNotAuthorized),
            Err(_) => return Err(LendingError::NexusError),
        }

        // 4. Execute the borrow logic.
        Self::execute_borrow(&env, mandate_id, amount)?;

        Ok(())
    }

    fn execute_borrow(env: &Env, mandate_id: u64, amount: i128) -> Result<(), LendingError> {
        // ... borrow implementation ...
        Ok(())
    }
}
```

**What this demonstrates:**

- The lending protocol has **zero knowledge** of the user's private key.
- The Nexus enforces all budget limits, TTL, contract allowlists, and epoch
  validity transparently.
- The protocol only needs to know the Nexus contract address — it does not need
  to implement any delegation logic itself.
- Any protocol can integrate the same Nexus, creating a composable trust layer
  across the Stellar ecosystem.

---

## Design Rationale

### Immutable Scope, Mutable State

Separating `Scope` (immutable) from `MandateState` (mutable) is a deliberate
design choice. The `Scope` is the cryptographic commitment made at issuance — it
forms the basis of any ZK-proof and MUST NOT change. The `MandateState` tracks
runtime facts (spending, revocation) that evolve over time. Conflating them (as
in v0.3.0's `spent_budget` inside `Scope`) would invalidate cached proofs and
make the issuance record untrustworthy as an audit artifact.

### DelegationPolicy over `can_delegate: bool`

A boolean flag cannot express the constraints needed in real agentic systems.
An orchestrator agent needs to spawn specialized sub-agents, but only with a
fraction of its budget and a narrower contract allowlist. `DelegationPolicy::Restricted`
encodes these constraints at the protocol level, removing the need for off-chain
coordination and making them auditable on-chain.

### Authority Epoch for Mass Revocation

Individually revoking thousands of Mandates (e.g., when rotating a key after a
suspected compromise) would require one transaction per Mandate — prohibitive in
gas and latency. A single `increment_epoch` transaction renders every prior
Mandate invalid instantly. This is analogous to rotating a certificate authority
root: all previously issued certificates become untrusted without needing to touch
each one individually.

### Bounded Gas via Depth Cap and Cache

Without a depth cap, a malicious actor could create a chain of `MAX_U8` levels
to make `verify_authority` run out of gas, creating a denial-of-service vector
against any protocol that integrates the Nexus. `MAX_DELEGATION_DEPTH = 8`
bounds worst-case gas. The `VerificationCache` further reduces the amortized
cost to O(1) for repeated checks of the same Mandate within an epoch.

### SEP-45 for Remote Issuance

Requiring the Root Anchor to be a live Soroban account would exclude sovereign
identities managed by hardware wallets, mobile signers, or cross-chain bridges.
The `MandateRequest` flow delegates on-chain submission to a stateless relayer,
while the Nexus enforces all security properties. This is consistent with the
trust model of SEP-45: the relayer cannot forge a signature and cannot replay
a request across epochs.

### Relation to Existing Standards

| Standard | Relationship |
|---|---|
| **SEP-41** | Mandates follow the token interface for discoverability, but are non-transferable (no `transfer` function). |
| **SEP-10** | Used for Root Anchor authentication in web-client issuance flows. |
| **SEP-45** | Used for off-chain issuance via `MandateRequest`. |
| **EIP-4973 (Ethereum)** | Conceptual ancestor (Account-Bound Tokens / SBTs). This SEP extends the concept with hierarchical delegation and financial limits for the agentic economy. |

---

## Security Concerns

### Cascading Revocation Atomicity

The Nexus MUST ensure that revoking a parent Mandate invalidates all descendants
atomically at the verification level. Implementations MUST NOT rely solely on the
`VerificationCache` for revocation propagation. On a cache miss, the full chain
MUST be re-traversed to detect revocation of any ancestor node.

### Budget Exhaustion via Sub-delegation

Without `budget_fraction`, a compromised intermediate agent could issue
sub-Mandates whose aggregate `transfer_limit` exceeds the original budget,
enabling fund drainage across multiple agents acting in parallel. The Nexus MUST
enforce at issuance time that the sum of all active child `transfer_limit` values
does not exceed the parent's `transfer_limit`.

### Replay Attacks on MandateRequest

The `epoch` field prevents replay of a captured `MandateRequest` after the Root
Anchor increments its epoch. The `nonce` field prevents replay within the same
epoch. The Nexus MUST maintain a consumed-nonce set per Root Anchor per epoch
and MUST reject duplicate nonces before performing any other validation.

### Depth Limit Enforcement Timing

`MAX_DELEGATION_DEPTH` MUST be enforced at **issuance time**, not at verification
time. Enforcing only at verification creates a window where an over-depth chain
exists on-chain but cannot be verified without running out of gas — a latent DoS
vector. Rejecting at issuance prevents the chain from being created.

### Scope Monotonicity Enforcement

The Nexus MUST verify at issuance that the child Scope is strictly less than or
equal to the parent Scope in every dimension: TTL, transfer_limit, contract_allowlist,
and function_allowlist. A child MUST NOT be able to grant itself permissions the
parent does not have. This invariant is the foundation of the trust model.

### ZK-Commitment Integrity

The `scope_commitment` field is informational within this SEP — the Nexus does
not verify ZK proofs natively. Implementations that use `scope_commitment` for
private verification SHOULD define a companion SEP specifying the proving system,
verification key management, and on-chain verifier contract interface.

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| `0.1.0` | 2026-05-01 | Initial draft. Core Mandate structure, Scope, Nexus concept, Authority Epoch. |
| `0.2.0` | 2026-05-05 | Added `DelegationRules`, `VerificationCache`, depth bounding, SEP-45 `MandateRequest` with epoch+nonce anti-replay. |
| `0.3.0` | 2026-05-05 | Extracted `spent_budget` and `is_revoked` into separate `MandateState` struct to preserve `Scope` immutability. (2) Restored full `DelegationRules` struct lost in 0.3.0. (3) Returned document language to English per Stellar SEP repository standard. (4) Added `MandateError` enum. (5) Added Usage Example (Section VI) demonstrating third-party Nexus integration in Rust. (6) Added Motivation section per SEP template requirements. (7) Added Design Rationale subsection comparing to EIP-4973. |

---

## Copyright

This SEP is licensed under the
[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).
