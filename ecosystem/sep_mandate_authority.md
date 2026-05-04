---
Title: Hierarchical Mandate Tokens for Autonomous Agent Authority
SEP: To Be Assigned
Author: Felipe Nunes Oliveira <@felipezolvency>
Track: Standard
Status: Draft
Created: 2026-05-01
Updated: 2026-05-01
Version: 0.0.1
Discussion: https://github.com/orgs/stellar/discussions/1925
---

## Simple Summary

A standard interface for issuing non-transferable, revocable **Mandate tokens** that allow a sovereign identity (**Anchor**) to delegate programmable, scoped authority to AI agents or automated systems — without sharing private keys.

---

## Abstract

This proposal defines a contract interface for hierarchical, non-transferable authority tokens on the Stellar network (Soroban). The standard separates **Sovereign Identity** (who owns the authority) from **Operational Authority** (what can be done with it).

A **Mandate** is a Soulbound Token (SBT) issued by an **Anchor** to an agent's address. It contains a cryptographically enforced **Scope** that defines the temporal and operational boundaries of the delegated authority. Third parties (dApps, protocols, other agents) can verify the validity and scope of a Mandate by querying the **Nexus** — the on-chain registry contract that maps and validates the parent-child relationships between Anchors and Mandates.

An Anchor may optionally permit a Mandate holder to issue sub-Mandates to other agents, always with an equal or narrower Scope than the parent Mandate.

---

## Motivation

The emerging agentic economy requires AI agents to execute financial transactions, sign contracts, and interact with decentralized protocols autonomously. Current approaches present two critical failure modes:

**1. Custody Risk:** Giving an AI agent full private key access exposes the entire principal account. A compromised or misbehaving agent can drain funds, sign unauthorized transactions, or interact with malicious contracts without limit.

**2. Identity Vacuum:** AI agents currently have no on-chain identity of their own, nor a verifiable link to the human or institution that authorized them. There is no standard way for a dApp to answer: *"Is this agent authorized to perform this action, and by whom?"*

The Mandate standard solves both problems by creating a **programmable power of attorney**: the agent can only act within a pre-defined Scope, and the Anchor retains full, instant revocation rights. Any counterparty can verify the authorization chain on-chain before executing a transaction.

This standard is especially relevant as the Stellar ecosystem grows to include agentic use cases, micropayment protocols (such as x402), and cross-chain identity infrastructure.

---

## Terminology

- **Anchor:** The sovereign root identity that holds the authority to issue Mandates. An Anchor is any valid Soroban `Address` (account or contract). Implementations MAY require the Anchor to hold a specific credential (e.g., a Soulbound identity token) as a prerequisite for issuing Mandates.
- **Mandate:** A non-transferable, revocable token issued by an Anchor to an agent's address. It encodes the Scope of delegated authority and a reference to its parent Anchor.
- **Scope:** The set of rules and constraints embedded in a Mandate. At minimum, a Scope MUST include a temporal expiration (`ttl`). Additional constraints are defined as optional extensions in this standard.
- **Nexus:** The registry smart contract that stores and validates the parent-child relationships between Anchors and Mandates. Third parties query the Nexus to verify authority.
- **Agent:** Any address (account or contract) that receives a Mandate and operates within its Scope.
- **Sub-Mandate:** A Mandate issued by a Mandate holder to a downstream agent. Only possible if the parent Mandate has `can_delegate: true`. A Sub-Mandate's Scope must be equal to or narrower than the parent Mandate's Scope.

---

## Specification

### I. The Mandate Data Structure

Every Mandate MUST contain the following fields:

```rust
pub struct Mandate {
    // Unique identifier for this Mandate
    pub id: u64,

    // The Soroban Address of the issuing Anchor
    pub anchor: Address,

    // The Soroban Address of the authorized agent
    pub agent: Address,

    // The Scope defining the boundaries of this authority
    pub scope: Scope,

    // The ledger timestamp at which this Mandate was issued
    pub issued_at: u64,

    // Whether the agent may issue Sub-Mandates to other agents
    // Sub-Mandates must have a Scope equal to or narrower than this Mandate
    pub can_delegate: bool,

    // Optional: ID of the parent Mandate, if this is a Sub-Mandate
    // None if issued directly by an Anchor account
    pub parent_mandate_id: Option<u64>,
}
```

### II. The Scope Data Structure

A Scope defines the authority boundaries of a Mandate. The `ttl` field is **mandatory**. All other fields are optional extensions.

```rust
pub struct Scope {
    // REQUIRED: Unix timestamp after which this Mandate is no longer valid
    pub ttl: u64,

    // OPTIONAL EXTENSION: List of contract addresses this agent is permitted to invoke
    // If None, the agent may invoke any contract (subject to Anchor policy)
    pub contract_allowlist: Option<Vec<Address>>,

    // OPTIONAL EXTENSION: List of function names this agent is permitted to call
    // If None, no function-level restriction applies
    pub function_allowlist: Option<Vec<String>>,

    // Implementations MAY define additional Scope fields as needed.
    // Future extensions (e.g., financial limits, reputation thresholds) 
    // should be proposed as amendments to this SEP.
}
```

### III. Core Interface

Implementations of this standard MUST expose the following three functions. The Nexus contract MUST implement all three.

---

#### `issue_mandate`

Issued by an Anchor to authorize an agent.

```rust
/// Issues a new Mandate from the caller (Anchor) to a target agent.
///
/// # Arguments
/// * `env`          - The Soroban environment.
/// * `agent`        - The address of the agent receiving authority.
/// * `scope`        - The Scope defining the boundaries of the authority.
/// * `can_delegate` - Whether this agent may issue Sub-Mandates.
///
/// # Returns
/// * The unique `mandate_id` of the newly issued Mandate.
///
/// # Authorization
/// * Requires authorization from the calling Anchor address.
/// * If the caller is a Mandate holder (not a root Anchor), 
///   `can_delegate` must be `true` on the caller's Mandate,
///   and the new Scope must be equal to or narrower than the caller's Scope.
///
/// # Errors
/// * Panics if the Anchor is not authorized.
/// * Panics if a Sub-Mandate Scope exceeds the parent Mandate Scope.
/// * Panics if `ttl` is in the past.
fn issue_mandate(
    env: Env,
    agent: Address,
    scope: Scope,
    can_delegate: bool,
) -> u64;
```

---

#### `revoke_mandate`

Called by the Anchor to immediately cancel a Mandate. Revocation MUST be atomic — the Mandate must be invalidated within the same ledger as the revocation transaction.

```rust
/// Revokes an existing Mandate, immediately cancelling the agent's authority.
///
/// # Arguments
/// * `env`        - The Soroban environment.
/// * `mandate_id` - The unique ID of the Mandate to revoke.
///
/// # Authorization
/// * Only the original Anchor that issued this Mandate may revoke it.
/// * An Anchor MAY also revoke any Sub-Mandate in its chain.
///
/// # Behavior
/// * Revocation is atomic: after this call, `is_valid(mandate_id)` MUST return false.
/// * Revoking a parent Mandate MUST cascade and invalidate all child Sub-Mandates.
///
/// # Errors
/// * Panics if the caller is not the Anchor of this Mandate.
/// * Panics if `mandate_id` does not exist.
fn revoke_mandate(env: Env, mandate_id: u64);
```

---

#### `verify_authority`

Called by any third party (dApp, protocol, agent) to check whether a given Mandate is valid and whether the intended action falls within the Mandate's Scope.

```rust
/// Verifies whether a Mandate is currently valid and authorizes a specific action.
///
/// # Arguments
/// * `env`             - The Soroban environment.
/// * `mandate_id`      - The unique ID of the Mandate to verify.
/// * `action_context`  - The context of the action being authorized 
///                       (e.g., target contract address, function name).
///
/// # Returns
/// * `true`  if the Mandate is valid, not expired, not revoked, 
///           and the action is within Scope.
/// * `false` in any other case. Implementations MUST NOT panic — 
///           they MUST return false for invalid or expired Mandates.
///
/// # Behavior
/// * MUST check that the Anchor is still active (not itself revoked, if applicable).
/// * MUST check that the current ledger timestamp is before `scope.ttl`.
/// * MUST check that the action_context is permitted by `scope.contract_allowlist`
///   and `scope.function_allowlist`, if those fields are set.
/// * For Sub-Mandates, MUST also verify the parent Mandate is valid.
fn verify_authority(
    env: Env,
    mandate_id: u64,
    action_context: ActionContext,
) -> bool;
```

#### `ActionContext` Structure

`ActionContext` is the argument passed to `verify_authority` to describe the action the agent intends to perform. The Nexus contract evaluates this against the Mandate's Scope before returning a result.

```rust
pub struct ActionContext {
    // The contract address the agent intends to invoke
    pub target_contract: Address,

    // The function name the agent intends to call
    pub function_name: String,
}
```

---

### IV. The `is_valid` Helper

Implementations SHOULD also expose a simple validity check:

```rust
/// Returns true if the Mandate exists, is not revoked, and has not expired.
/// This is a lightweight check that does not evaluate Scope constraints.
fn is_valid(env: Env, mandate_id: u64) -> bool;
```

---

### V. Required Events

Implementations MUST emit the following Soroban events to allow off-chain indexers and monitoring tools to track the authority lifecycle. For interoperability, the `topics` layout, topic order, and `data` fields are normative and MUST match this specification exactly.

```rust
// Emitted when a Mandate is issued
// topics: (Symbol("mandate"), Symbol("issued"), u64 mandate_id)
// data:   { anchor: Address, agent: Address, ttl: u64 }
//
// Topic 0 MUST be the Symbol "mandate".
// Topic 1 MUST be the Symbol "issued".
// Topic 2 MUST be the Mandate identifier as u64.
// The data payload MUST contain exactly:
// - anchor: Address
// - agent: Address
// - ttl: u64

// Emitted when a Mandate is revoked
// topics: (Symbol("mandate"), Symbol("revoked"), u64 mandate_id)
// data:   { anchor: Address, revoked_at: u64 }
//
// Topic 0 MUST be the Symbol "mandate".
// Topic 1 MUST be the Symbol "revoked".
// Topic 2 MUST be the Mandate identifier as u64.
// The data payload MUST contain exactly:
// - anchor: Address
// - revoked_at: u64
```

---

### VI. Scope Narrowing Rule (for Sub-Mandates)

When `can_delegate: true`, a Mandate holder may call `issue_mandate` to create a Sub-Mandate. The following rules MUST be enforced by the Nexus contract:

- The Sub-Mandate's `ttl` MUST be less than or equal to the parent Mandate's `ttl`.
- If the parent Mandate defines a `contract_allowlist`, the Sub-Mandate's allowlist MUST be a subset of the parent's.
- If the parent Mandate defines a `function_allowlist`, the Sub-Mandate's allowlist MUST be a subset of the parent's.
- A Sub-Mandate MUST NOT grant permissions that the parent Mandate does not have.

---

## Rationale

### Why a new token standard, not multisig?

Multisig accounts allow multiple signers to approve transactions, but they do not encode *what* those signers are permitted to do, nor do they create a portable, verifiable, revocable authority record. A 2-of-3 multisig cannot tell a dApp: *"This agent is authorized to interact with contracts A and B until timestamp T, on behalf of identity X."*

Mandates are also **portable reputation carriers**: an agent operating under a Mandate can access the trust and credit history of its Anchor (e.g., a Zenith-level reputation score), enabling AI agents to access services that would otherwise require high collateral for new, unestablished accounts. Multisig accounts cannot carry this identity context.

### Why is TTL the only mandatory Scope field?

Maximizing adoption requires minimizing the implementation burden. A Mandate with only a TTL is already significantly safer than sharing a private key — it expires automatically and can be revoked at any time. More complex Scope constraints (financial limits, allowlists) are opt-in extensions. This follows the same design philosophy as ERC-20, which defined the minimum viable interface and allowed the ecosystem to build on top of it.

### Why is `verify_authority` a required function?

Third-party verifiability is the core value proposition of this standard. Without a standard verification interface, every dApp would need to implement its own logic for reading Mandate state from the Nexus. By standardizing `verify_authority`, any protocol on Stellar can verify agent authority with a single contract call, without understanding the internal structure of the Nexus.

### Why is cascading revocation required?

An Anchor that revokes a Mandate must be able to trust that all downstream authority derived from that Mandate is also cancelled. Without cascading revocation, a bad actor could create a chain of Sub-Mandates and retain authority even after the parent is revoked. Atomic, cascading revocation is a security requirement, not a convenience feature.

---

## Backwards Compatibility

This standard is additive and does not modify any existing Soroban or Stellar protocol primitives. It is designed to be compatible with and composable alongside:

- **SEP-41** (Soroban Token Interface): Mandate tokens are non-transferable and do not implement the SEP-41 transfer interface. However, the Nexus contract MAY be deployed alongside SEP-41 token contracts.
- **SEP-10 / SEP-45** (Web Authentication): Anchors may use SEP-10 or SEP-45 authentication to prove identity before issuing Mandates to agents.
- Future payment delegation standards (e.g., based on the x402 protocol) are explicitly intended as Scope extensions to this standard and may be proposed as a follow-up SEP.

---

## Security Considerations

### Atomic Revocation

Revocation MUST be processed atomically. The Nexus contract MUST invalidate the Mandate within the same ledger in which the revocation transaction is submitted. Implementations MUST NOT use asynchronous or delayed revocation mechanisms.

### Cascading Revocation

As specified in Section III, revoking a parent Mandate MUST cascade to all child Sub-Mandates in the delegation chain. Nexus implementations MUST maintain a mapping from each Mandate to its children to enforce this.

### Scope Narrowing Enforcement

The Nexus contract MUST enforce Scope narrowing at the time of Sub-Mandate issuance. It MUST NOT rely on agents self-reporting their Scope constraints.

### Anchor Liveness

If an Anchor account is itself revoked, deactivated, or otherwise invalidated (depending on the identity system used), all Mandates issued by that Anchor MUST also be considered invalid. The `verify_authority` function MUST check Anchor liveness as part of its verification logic.

### Privacy Considerations

The full delegation structure of an Anchor — which agents it authorizes and with what Scope — is visible on-chain by default. Implementations that require confidential delegation SHOULD consider using Zero-Knowledge Proofs (ZKPs) to allow `verify_authority` to confirm that an action is within Scope without revealing the full Scope to the verifier. This is a recommended enhancement and is not required by this standard.

### Sybil Resistance

This standard does not define Sybil resistance for Anchors. Implementations that require Anchor uniqueness (e.g., one Anchor per human) SHOULD combine this standard with a Proof-of-Personhood or hardware-bound identity mechanism.

---

## Reference Implementation

The first reference implementation of this standard is provided by the **Zolvency protocol** on the Stellar Soroban network. In the Zolvency ecosystem, Mandates are branded as **Wills** — authority tokens issued by a sovereign **Soul** identity to AI agents operating within the Zolvency Nexus registry.

---

## Copyright

This SEP is licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).
