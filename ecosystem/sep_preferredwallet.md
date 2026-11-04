## Preamble

```
SEP: To Be Assigned
Title: Preferred Wallet Resolution
Author: Pamphile Roy <@tupui>
Track: Standard
Status: Draft
Created: 2026-10-13
Updated: 2026-10-13
Version: 0.0.1
Discussion: https://github.com/orgs/stellar/discussions/2017
```

## Simple Summary

An account records which wallet its owner uses. Given an address, an
application reads that record and opens the wallet directly, without a wallet
picker, as a card number routes a payment to the cardholder's bank. The record
is a domain, stored as a data entry on `G` accounts and behind a function on
`C` accounts. A wallet that serves `https://<domain>/connect` is reached from
the record alone. A registry covers wallets that do not serve it yet, and a
connector's own integrations remain the last resort, so that the record works
with wallets that exist today.

## Dependencies

- [SEP-18]: registers `config.wallet` and `config.wallet_label` in the `config`
  namespace. A companion change is required.
- [SEP-23]: `M` addresses reduce to their base `G` address.
- [SEP-43]: the methods served over the connect channel.
- [SEP-60]: wallets already announced in the page. Complementary, not changed.
- [SEP-47], [SEP-53], [SEP-7], [CAP-84]: optional or informative, see below.

## Motivation

[SEP-43] defines what an application asks a wallet, and [SEP-60] how it finds
wallets present in the page. Both leave the choice to the user through a
picker, which has costs SEP-60 does not remove:

- Announcement reaches only wallets with code in the page. Mobile wallets used
  from a desktop, web, passkey, hardware and bridge wallets are not reached, so
  applications ship one integration per wallet.
- A picker lists wallets, not the user's wallet. Every application makes the
  user search, and the order of the list is a commercial lever.
- The choice is not portable. It is remembered per application and browser.

Web wallets have in practice converged on one shape: the application opens a
page of the wallet in a popup, which answers with `postMessage`. xBull,
GHOSTSIG, Albedo and, outside Stellar, the Coinbase Smart Wallet do so, each
with its own page and messages, so every connection library carries code for
each. The account is the one durable, public, user-controlled place that can
say which wallet to open, and a standard page is what makes that answer usable
by everyone.

This proposal is discussed with [SEP-60] in the same [discussion], the two
being complementary.

## Abstract

1. A **wallet record**, the domain of the wallet an account owner uses: the
   data entry `config.wallet` on `G` accounts, `get_wallet` and `set_wallet` on
   `C` accounts.
2. **Resolution** of an address to its record with Stellar RPC alone.
3. The **connect page** `https://<domain>/connect`, and a `postMessage`
   **channel** carrying [SEP-43] methods.
4. A **registry** of wallets and the routes by which each is reached, including
   wallets that predate this proposal.
5. How a connector chooses a route, and the rules that keep the user in
   control.
6. An optional free form **wallet label**.

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119].

### Required and optional

| Role                     | Required                                                                                      | Optional                                                     |
| ------------------------ | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `G` account              | Nothing. It takes part by holding `config.wallet`.                                            | `config.wallet_label`                                        |
| `C` account              | `get_wallet` and `set_wallet`                                                                 | The `label` field. Event on change. [SEP-47] meta.           |
| Wallet                   | Nothing. To be reached with no registry entry: serve the connect page and channel             | Set the record (SHOULD). Registry entry. Label. [SEP-60].    |
| Application or connector | [Resolution](#resolution), the connect route, [User rules](#user-rules), account verification | Registry, own integrations, [SEP-60] matching, showing label |
| Registry                 | Nothing depends on it                                                                         | All of it. Any source, none designated. It is a fallback.    |

An **Application** has an account's address and wants its wallet. A
**Connector** is the code that connects an Application to a wallet: the
Application itself, or a library acting for it. Requirements on Applications
apply to Connectors.

### Wallet Record

The Wallet Record is the domain name of the host that serves the wallet's
connect page: lowercase ASCII, 1 to 64 bytes (the data entry value limit), a
valid RFC 1123 host name with at least two labels, no scheme, port, path,
query, user information or trailing dot, internationalized names in A-label
form. It is the host that serves `/connect`, not necessarily the marketing
site.

A Resolver MUST treat a value that fails these rules as no record, and MUST NOT
repair it.

### Storage

**`G` accounts** store the Wallet Record, as UTF-8 bytes, in the data entry
`config.wallet`, set and cleared with `ManageData`. The key follows [SEP-18].

**`C` accounts** implement, with the storage layout left to the contract:

```rust
#[contracttype]
pub struct WalletInfo {
    pub wallet: Option<String>, // the Wallet Record
    pub label: Option<String>,  // the optional Wallet Label
}

/// Both fields are None if nothing is set. MUST NOT require auth or write.
fn get_wallet(env: Env) -> WalletInfo;

/// Replaces both fields. MUST call
/// `env.current_contract_address().require_auth()`, MUST panic if `wallet`
/// breaks the Wallet Record rules or `label` exceeds 64 bytes.
fn set_wallet(env: Env, info: WalletInfo);
```

`set_wallet` authorizes against the account itself, so it is changed under the
account's own signers and policies, and MAY have a dedicated context rule. It
SHOULD emit an event with topic `wallet_updated`. The value SHOULD live in
persistent storage with its TTL extended on use. Contracts SHOULD advertise the
interface through [SEP-47]. Smart account frameworks are expected to offer it
as an optional extension.

### Wallet Label (optional)

A free form UTF-8 note of 0 to 64 bytes, for the owner to tell accounts apart.
It has no format and no meaning an Application may act on. For `G` accounts it
is the data entry `config.wallet_label`, for `C` accounts the `label` field. It
works without a record. A Resolver reads it with the record, and a missing,
unreadable or over long label is no label and never fails a resolution. A
displayed label MUST be rendered as plain text.

### Resolution

A Resolver needs only a Stellar RPC endpoint and contacts no wallet.

1. Reduce an `M` address to its base `G` address
   ([Muxed addresses](#muxed-addresses)).
2. Read the record:
   - `G`: `getLedgerEntries` for the data entries `config.wallet` and
     `config.wallet_label` of the account in one call. Horizon MAY be used.
   - `C`: `simulateTransaction` of `get_wallet`, from any well formed source,
     never submitted. A failure, a missing function, an archived entry (restore
     preamble) or a `None` wallet is no record.
3. Validate the record.

With no usable record the Application falls back to its usual selection, the
picker or the [SEP-60] flow, and never blocks the user from another wallet.

### The connect page

A wallet reached from its domain serves `https://<Wallet Domain>/connect`,
opened by the Application as a top-level popup or tab, with no query. The page:

- MUST NOT be framed, and MAY redirect within its domain.
- MUST be a web page with an opener. A native-only wallet cannot answer: an app
  opened from a link has no window to talk to. It is reached by another route,
  such as its in-app browser announcing with [SEP-60], or a registry route.
- MUST check that its wallet controls the requested account, otherwise answer
  with an error and not offer another account silently.
- MUST show the user the `origin` of the requesting Application, from the
  message and never from its content, and MUST route every request through its
  own approval flow.

### The channel

Messages are objects with `channel: "stellar:connect:v1"`, and others are
ignored.

1. **Ready.** The page sends `{ channel, type: "ready" }` to `window.opener`,
   with target origin `"*"` as it carries nothing.
2. **Request.** The Application sends, to the page's origin only,
   `{ channel, type: "request", id, address, method, params }`. `address` is
   the account as the Application was given it, muxed part included. `method`
   is a [SEP-43] method (`getAddress`, `signTransaction`, `signAuthEntry`,
   `signMessage`, `getNetwork`) and `params` its arguments.
3. **Response.** The page replies, to the request's origin only, with
   `{ channel, type: "response", id, result }` where `result` is the SEP-43
   return value, or `{ ..., id, error }` with the SEP-43 error shape.

Rules:

- The page serves only `window.opener`, only an origin that is `https` or local
  `http`, and pins the origin of the first request. The Application accepts
  only messages whose `source` is its popup and `origin` is the Wallet
  Domain's.
- `getAddress` returns the request's `address`, or an error. The page pins the
  first request's `address` and errors on a different one later.
- After `getAddress` the page SHOULD stay open for a couple of seconds, as a
  signature usually follows (for example to sign in) and a second window opened
  outside the click is blocked. The Application reopens the page after a click
  once it is closed.
- No ready message within ten seconds, or the window closing before it, means
  the route is unavailable. Closing after ready and before a response is a
  rejection by the user, as [SEP-43] defines it.
- The Application opens the page inside the click with nothing awaited before
  `window.open`, under a random window name so no frame can reuse it, never
  with `noopener`, and is not served with
  `Cross-Origin-Opener-Policy: same-origin` (`same-origin-allow-popups` works).

### Registries

A registry maps a Wallet Record to an **entry** describing how the wallet is
reached. It is meant to cover every wallet that Applications can reach, those
that serve the connect page and those that do not yet, so a record naming a
wallet is found. This is how existing wallets work with the proposal. This
proposal defines the entry and leaves the rest open:

- A registry MAY be a document served over `https`, a smart contract, or any
  other source. A Connector MAY use any registry it trusts, several, or none,
  and MAY keep a local list of its own.
- This proposal designates no registry. How a Connector picks one, who curates
  it, and how entries are added are the registry's own business.
- Nothing depends on a registry being available, see [Connecting](#connecting).

An entry has:

- `domain`: the Wallet Record it applies to. It MUST be the domain that the
  wallet's publisher uses and controls.
- `name` and `icon`: for display. `icon` is an `https` URL or a `data:` URI,
  rendered as an image only.
- `routes`: an ordered list of the ways to reach the wallet. Each has a `type`
  and type specific fields, and a Connector ignores types it does not know:
  - `connect`: the wallet serves the connect page. An optional `url`, on the
    domain or a subdomain, replaces the default address.
  - `walletconnect`: a pairing through a universal link, `link` being a
    template where `{uri}` is replaced with the URL encoded pairing URI.
  - `legacy`: a protocol or integration that predates this proposal, named by
    `protocol` so that Connectors with code for it can use it as if the user
    had picked the wallet.

A wallet that adopts `/connect` adds that route and keeps `legacy` as long as
Connectors need it.

A registry that is a smart contract SHOULD expose the read function below, so
that a generic Connector can query any such registry from its address, without
code per registry. Routes are maps of string fields. The storage and the way
entries are added or changed, for example by governance or by the wallet's own
authorization, are the contract's concern.

```rust
#[contracttype]
pub struct WalletEntry {
    pub name: String,
    pub icon: String,
    pub routes: Vec<Map<Symbol, String>>,
}

/// None if the domain is not listed. MUST NOT require auth or write.
fn get_wallet_entry(env: Env, domain: String) -> Option<WalletEntry>;
```

A document registry is a JSON object `{ "wallets": [ entry, ... ] }` with the
same fields. Such a document and a contract MAY be mirrors of each other.

### Connecting

After resolution a Connector takes the first route that works:

1. **A present provider.** A [SEP-60] provider whose `rdns` is the Wallet
   Record with its labels reversed (`wallet.example.com` announces
   `com.example.wallet`). Connectors with SEP-60 SHOULD do this first.
2. **The registry entry.** The first route of the entry that the Connector
   supports: `connect`, `walletconnect` (with a WalletConnect client) or
   `legacy`. The entry says which routes exist, so none is tried blindly.
3. **The connect page**, when there is no entry or no registry. A Connector
   that complies MUST support this route.
4. **The Connector's own integration** for the wallet, such as a module of
   Stellar Wallets Kit, as if the user had picked it. This is what `legacy`
   means.
5. **None.** The normal picker, optionally saying the account names a wallet
   that cannot be reached.

The route is chosen before the click as far as possible. A route that fails
after a window opened ends in the picker, not another window.

After any route the Application MUST verify that the returned address equals
the resolved one (the base `G` address for `M`). Wallets let users pick the
account, so a mismatch is expected: the user retries or picks another wallet.
Proof of ownership still needs a signature ([SEP-53]).

#### User rules

1. Connecting starts only from a user gesture, never on load. Resolution
   happens earlier, for example when the address is entered, so the click opens
   the window at once. A button that names the wallet is the confirmation, and
   no prompt stands between the click and the window.
2. The Application shows the Wallet Record before connecting, so a record the
   user did not set can be noticed. Registry name and icon MAY accompany it.
3. The record is a default, never a restriction. Offer a visible way to use
   another wallet at every step. Overriding shows the normal picker, does not
   reopen the recorded wallet that session unless asked, and never changes the
   record. Connectors are where this lives.
4. The record and label never decide what an Application may do or prove
   ownership.

#### Relation to SEP-60

SEP-60 forbids choosing a provider from `info`, as it is self-attested by code
in the page. The record is read from the ledger by the Application and states
the account holder's choice, which a script cannot forge. An announced provider
is matched on `rdns` and trusted no more than any other.

### Muxed addresses

An `M` address resolves through its base `G` address, where the record is
stored. The identifier is dropped for the lookup only: the request's `address`
is the original, so a custodian that is the wallet knows which customer is
meant. [CAP-84] muxed contract addresses SHOULD resolve the same way, by their
base `C` address, once their strkey is in [SEP-23]. This is provisional.

### Setting the record

Only the account's signers set it: `ManageData` for `G`, `set_wallet` for `C`
(which sets record and label together).

A wallet:

- SHOULD offer to set the record, to its own domain, at account creation, and a
  setting to change or remove it. It MAY sponsor the entry reserve ([CAP-33]).
- MUST NOT overwrite a record naming another wallet without explicit
  confirmation that shows it. It SHOULD show the current record to the owner.
- MAY offer a label field, independent of the record and never set on its own.

An Application MAY ask a user to set the record with a [SEP-7] `tx` URI. SDKs
SHOULD expose the same operations for both account types:

```typescript
interface WalletRecordClient {
  /** Resolution, steps 1 to 3. Null when there is no usable record. */
  resolve(address: string): Promise<{ record: string; label?: string } | null>;
  /** ManageData for G, invokeHostFunction for C. Null clears. */
  buildSetRecord(address: string, record: string | null): Operation;
  /** Same for the label, keeping the current record on C. */
  buildSetLabel(address: string, label: string | null): Operation;
}
```

### Open Questions

- **Registries:** whether one is designated by default, for example an on-chain
  one, and who curates it. For disputes over an entry and for containing a
  compromise, a DAO with a council that can act quickly is suggested, as other
  ecosystem registries do, so that no single party decides.
- **Existing popup wallets.** xBull, GHOSTSIG and Albedo already open a page
  and use `postMessage`, each with its own envelope, method names and page
  address. Serving this channel is additive for them. Until they do, their
  entries use `legacy`.
- **WalletConnect route:** it needs a relay and a project identifier, and
  wallet links that are not confirmed. It may not belong in the first registry
  version.
- **Sessions and events** (such as account change) are not defined.
- **Muxed addresses:** whether a custodian could route by identifier instead of
  by base account.
- **Names:** resolving the record from a name service name.

## Design Rationale

**On the account.** The owner chooses the record, so it lives where the owner
has authority and anyone can read it. `G` accounts already have data entries
and `config.*` is reserved for this by [SEP-18]. `C` accounts have no uniform
storage readers can find, so the interface is a function.

**A domain and a fixed page.** 64 bytes fit few URLs and a URL would let the
account pick any page to open. A domain is how wallets already identify
themselves in [SEP-60], reverses to its `rdns`, and the publisher may move the
page behind it. The path is fixed so no file or lookup is needed to find it. It
is a path and not a query flag so that it can be served, rewritten or
redirected as a resource of its own, with its own CSP, framing and COOP
headers, and without defining how a page ignores or reads a query. A single
page app can redirect it to its own connect mode. `/connect` follows xBull and
the Coinbase Smart Wallet. `home_domain` was rejected: it is an issuer's field,
limited to 32 bytes, and absent on `C` accounts.

**One channel.** Web wallets already use popup plus `postMessage`. Carrying
[SEP-43] methods and errors unchanged means a SEP-43 wallet has little to add
and a connector needs one piece of code for all of them. The ready handshake
and origin pinning are the pattern the existing popup wallets use. The registry
read function is the one public API that lets an on-chain registry be read
without a client per registry.

**Three routes.** The connect page needs nothing from anyone else and scales: a
new wallet works everywhere the day it serves the page. The registry is data,
so it cannot hold a wallet's own protocol, but it names it and lets any
connector find existing wallets, from a document or an on-chain contract alike.
Connector integrations remain the last resort. Only the connect page is
required, so the core depends on no list, library or organization.

**One record, a default.** A list does not fit 64 bytes and the user can always
override to the normal picker. The label is free form and optional because any
structure would guess how people name accounts, and it shares `set_wallet`
because an empty field in a simulation costs nothing.

**Alternatives.**

- _Only a library_ (Stellar Wallets Kit): not a standard, rebuilt by every
  connector, and wallets cannot add themselves. Kept as a last resort.
- _Only a registry:_ data cannot carry a wallet's protocol, and it becomes a
  dependency of every Application. Kept as a fallback.
- _A wallet info file_ like [SEP-1]: most wallets publish none, it needs a
  third party fetch first, and it only describes routes already standard.
- _A central registry that routes requests_, as card networks route a number to
  a bank, possibly by amount or with notifications: it adds a trusted,
  observing party, and these behaviors belong to the chosen wallet, which holds
  the keys, while hard limits belong in account policies enforced on chain. No
  account level wallet routing standard was found elsewhere: [EIP-6963] is per
  session and [ERC-5792] reports capabilities. OpenID Connect discovery is the
  closest.
- _[SEP-7] as transport:_ one transaction with a callback, not a SEP-43
  session.
- _WalletConnect alone:_ it needs a pairing the Application creates, cannot
  start from an address, and relies on a registry for wallet links. It is a
  registry route.
- _Name services:_ only for those who registered a name, and silent about the
  wallet. They can complement this as a source of addresses.

## Security Concerns

**Advice, not authority.** The record names a wallet and authorizes nothing.
Every request goes through the wallet's approval, and the Application verifies
the account.

**Hijacked record.** Changing it requires the account's authorization, so the
attacker already controls the account. The remaining case is a user tricked
into signing a change. Wallets MUST show the change and MUST NOT overwrite a
record silently, and Applications MUST show the domain so a foreign one is
noticed.

**Opening a page chosen by someone else.** Only after a gesture, domain shown,
in a separate window and never a frame. The page learns the Application's
origin from the message and the public address from the request. A connector
MAY refuse domains absent from the registries it trusts, trading reach for
safety.

**The channel.** Requests go only to the page's origin, responses only to the
request's. Both sides check `source` and `origin`, and the page pins the first
origin and address.

**Registry.** A wrong or compromised entry cannot change what the user is shown
or asked: the record is displayed as plain text, the account verified and every
request approved in the wallet. Use sources whose integrity is protected, such
as `https` or a contract, and render icons as images only. An entry says
someone listed the wallet, not that it is honest.

**Spoofed matches.** A script can announce a matching `rdns`, as it can
announce anything under SEP-60, and the same protections apply.

**Lapsed domains.** A wallet domain taken over sends accounts that name it to
the new owner. Wallets SHOULD keep their domain, and showing it gives users a
chance to notice.

**Privacy.** The record is public and permanent in ledger history, showing
which wallet an address uses. The wallet's domain sees the address and the
Application's origin. Wallets SHOULD say so when offering to set it.

**The label is untrusted text.** Anyone who can authorize for the account can
write it, and it is public. Render as plain text, truncated, never as markup or
a link, never for a decision. Users should not store private data in it.

**Contract accounts.** `set_wallet` MUST authorize against the account itself,
not a caller supplied address, and SHOULD bound input length.

## Changelog

- `v0.0.1`: Initial draft.

[SEP-1]: ./sep-0001.md
[SEP-7]: ./sep-0007.md
[SEP-18]: ./sep-0018.md
[SEP-23]: ./sep-0023.md
[SEP-43]: ./sep-0043.md
[SEP-47]: ./sep-0047.md
[SEP-53]: ./sep-0053.md
[SEP-60]: ./sep-0060.md
[CAP-33]: ../core/cap-0033.md
[CAP-84]: ../core/cap-0084.md
[discussion]: https://github.com/orgs/stellar/discussions/2017
[EIP-6963]: https://eips.ethereum.org/EIPS/eip-6963
[ERC-5792]: https://eips.ethereum.org/EIPS/eip-5792
[RFC 2119]: https://www.rfc-editor.org/rfc/rfc2119
