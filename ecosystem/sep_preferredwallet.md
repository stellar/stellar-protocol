## Preamble

```
SEP: To Be Assigned
Title: Preferred Wallet Resolution
Author: Pamphile Roy <@tupui>
Status: Draft
Created: 2026-10-13
Updated: 2026-11-21
Version: 0.0.1
Discussion: https://github.com/orgs/stellar/discussions/2017
```

## Simple Summary

A standard for an account to indicate which wallet its owner uses, and for an
application to open this wallet from the address of the account without
presenting a wallet picker.

## Dependencies

- [SEP-18]
- [SEP-43]
- [SEP-60] (optional)
- [SEP-47] (optional)

## Motivation

[SEP-43] defines the methods an application can call on a wallet. [SEP-60]
defines how an application discovers the wallets which are present in the page.
In both cases, the user still has to select a wallet in a list, and this for
every application.

This is different from what users know with card payments. When paying with a
card, the user is redirected to the application of their bank without having to
select it. This works because the card number can be linked to the bank.

The discovery defined in [SEP-60] also only works for wallets which have code
running in the page, i.e. browser extensions and in-app browsers. Web wallets
and wallets running on another device are not covered. For these, applications
rely on libraries which maintain one integration per wallet.

An account can hold the information about which wallet is used. An application
which is given an address can then open the corresponding wallet directly.

## Abstract

This SEP defines how an account stores the domain of its wallet, how an
application reads it, and how the application connects to the wallet from this
domain. `G` accounts use a data entry and `C` accounts expose a contract
function. The wallet is reached with a web page served at a fixed path of its
domain. This page exchanges [SEP-43] calls with the application using
`postMessage`. For wallets which do not serve this page, a registry format
describes how they can be reached.

## Specification

An application which supports this SEP must implement the
[Resolution](#resolution), the [Connect Page](#connect-page) with its
[Messages](#messages), and the rules of [Connection](#connection). A `C`
account which supports this SEP must implement the
[Contract Interface](#contract-interface).

The other parts are optional. This includes the wallet label, the registries
and the use of [SEP-60]. A wallet has nothing to implement to be referenced by
an account. It serves the connect page if it wants to be reached without a
registry.

### Wallet Record

The wallet record is the domain name of the wallet, e.g. `wallet.example.com`.
It must be a valid host name in lowercase ASCII, without scheme, port or path.
Internationalized domain names must use their A-label form. The record is at
most 64 bytes long, which is the maximum size of a data entry value.

A value which does not respect this format must be treated as if no record was
set.

### Wallet Label

The wallet label is an optional free text of at most 64 bytes. It allows users
to annotate their accounts as they see fit. It has no meaning for applications.
Applications which display it must display it as plain text.

### Data Entries

A `G` account stores the wallet record in a data entry named `config.wallet`,
following [SEP-18]. The wallet label is stored in a second data entry named
`config.wallet_label`. Both values are encoded in UTF-8.

### Contract Interface

A `C` account implements the following interface. The storage layout is left to
the contract.

```rust
#[contracttype]
pub struct WalletInfo {
    pub wallet: Option<String>,
    pub label: Option<String>,
}

fn get_wallet(env: Env) -> WalletInfo;

fn set_wallet(env: Env, info: WalletInfo);
```

`get_wallet` must not require authorization and must not modify the state, so
that it can be called with a simulation. Both fields are `None` when nothing is
set.

`set_wallet` replaces both fields. It must require the authorization of the
account itself using `env.current_contract_address().require_auth()`. It must
fail if the record is not valid or if the label is longer than 64 bytes.

The contract should emit an event when the record changes. It should also list
this SEP in its contract meta as defined in [SEP-47].

### Resolution

An application resolves an address to its wallet record using Stellar RPC only:

- for a `G` address, the two data entries are read with `getLedgerEntries`,
- for a `C` address, a call to `get_wallet` is simulated,
- for an `M` address, the underlying `G` address is resolved.

If there is no valid record, the application uses its usual wallet selection.

The muxed id is only removed to read the record. The address which is later
sent to the wallet is the `M` address.

### Connect Page

A wallet which can be reached from its domain serves a web page at:

```
https://<domain>/connect
```

The application opens this page in a new window, following a user action. The
page must not be embedded in a frame. A wallet which only exists as a native
application cannot serve this page. It is reached with one of the other routes
described in [Connection](#connection).

### Messages

The application and the page communicate using `postMessage`. There are three
messages:

```
page to application:  { channel, type: "ready" }
application to page:  { channel, type: "request", id, address, method, params }
page to application:  { channel, type: "response", id, result }
                      { channel, type: "response", id, error }
```

- `channel` is always `"stellar:connect:v1"`. Other messages are ignored.
- `ready` is sent by the page to its opener once it can receive requests.
- `id` is chosen by the application and is copied in the response.
- `address` is the account the application wants to use.
- `method` is one of the methods of [SEP-43], and `params` is the list of its
  arguments.
- `result` and `error` are the return value and the error of this method, as
  defined in [SEP-43].

The following rules apply:

1. The application must only send requests to the origin of the wallet domain.
   It must only accept messages which come from the window it opened and from
   this origin.
2. The page must only answer its opener. It keeps the origin and the address of
   the first request, and refuses requests which use another origin or another
   address.
3. The page must display the origin of the application to the user before any
   approval.
4. `getAddress` returns the address of the request. If the wallet does not
   control this account, an error is returned.
5. If the page does not send `ready` within 10 seconds, the application
   considers that the wallet cannot be reached this way.
6. If the window is closed before a response is received, the request is
   considered as rejected by the user.

Browsers only allow a window to be opened as the direct result of a user
action. The application should therefore resolve the record before the user
clicks. For the same reason, the page should stay open for a few seconds after
`getAddress`, as applications commonly ask for a signature right after. The
page cannot reach its opener if the window is opened with `noopener`, or if the
application is served with `Cross-Origin-Opener-Policy: same-origin`.

### Registries

A registry describes how to reach wallets, in particular the ones which do not
serve the connect page. This SEP only defines the format of an entry. A
registry may be a file served over `https`, a smart contract or a list
maintained by a library. An application may use any registry, or none.

An entry has the following fields:

```json
{
  "domain": "wallet.example.com",
  "name": "Example Wallet",
  "icon": "https://wallet.example.com/icon.png",
  "routes": [
    { "type": "connect" },
    {
      "type": "walletconnect",
      "link": "https://wallet.example.com/wc?uri={uri}"
    },
    { "type": "legacy", "protocol": "example" }
  ]
}
```

- `domain` is the wallet record the entry applies to.
- `name` and `icon` are used for display.
- `routes` lists the ways to reach the wallet, by order of preference.
  Applications ignore the types they do not support.

Three types of routes are defined:

- `connect`: the wallet serves the connect page.
- `walletconnect`: the wallet accepts a WalletConnect pairing using a link, in
  which `{uri}` is replaced by the pairing URI.
- `legacy`: the wallet uses its own protocol, which is named in `protocol`. An
  application which already has an integration for this protocol uses it.

A registry which is a smart contract should expose the following function, so
that applications can read any such registry the same way:

```rust
#[contracttype]
pub struct WalletEntry {
    pub name: String,
    pub icon: String,
    pub routes: Vec<Map<Symbol, String>>,
}

fn get_wallet_entry(env: Env, domain: String) -> Option<WalletEntry>;
```

### Connection

Once the record is resolved, the application uses the first of the following
which is available:

1. a [SEP-60] provider announced in the page, whose `rdns` is the wallet domain
   in reverse order, e.g. `com.example.wallet`,
2. the routes of the registry entry of the domain, if a registry is used,
3. the connect page,
4. its own integration of the wallet, if any,
5. its usual wallet picker.

The record is a default choice. The application must display the wallet domain
before connecting. It must also allow the user to select another wallet, in
which case the usual wallet picker is displayed.

After connecting, the application must verify that the address returned by the
wallet corresponds to the address it resolved. Wallets commonly let the user
select the account, so the two can differ.

### Setting the Record

The record is set by the account itself, with a `ManageData` operation for a
`G` account and by calling `set_wallet` for a `C` account.

Wallets should propose to set the record when an account is created, and should
allow users to change or remove it. A wallet must not replace an existing
record without the user confirming it.

## Limitations

### No Designated Registry

This proposal does not designate a registry and does not define how one is
maintained. For a registry which is shared by the ecosystem, it is suggested to
rely on a DAO with a council to add entries and to resolve disputes.

### Muxed Addresses

The record of an `M` address is the record of its underlying `G` address. This
proposal does not provide a way to set a different wallet per muxed id. Muxed
contract addresses, as defined in [CAP-84], are expected to be resolved the
same way using the underlying `C` address.

### No Sessions

The messages only cover requests and responses. This proposal does not define
sessions, or events such as a change of account.

### WalletConnect Route

The `walletconnect` route has not been tested with existing wallets and may
change.

## Design Rationale

### Storage on the Account

The wallet is chosen by the owner of the account. Storing the record on the
account means that only the owner can change it, and that anyone can read it
without relying on a third party. `G` accounts already have data entries and
the `config` namespace of [SEP-18] is made for this. `C` accounts have no
equivalent, which is why a contract function is used.

The `home_domain` of the account was not used. It is the domain of an issuer,
it is limited to 32 bytes and it does not exist for `C` accounts.

### Domain Instead of a URL

The record could also be the URL of the page to open. A domain was preferred
because it identifies the wallet. The same value is used to find a registry
entry, to match a [SEP-60] provider with its `rdns`, and to show the user which
wallet is about to be opened. With a fixed path, wallets also do not have to
agree on anything else to be reached.

### Messages

Existing web wallets, e.g. xBull, Albedo or GHOSTSIG, are already opened in a
new window and use `postMessage`. Each wallet has its own messages, and
applications need one integration per wallet. The messages of this proposal
only carry the methods and errors of [SEP-43]. A wallet which implements
[SEP-43] has little to add, and an application needs a single integration.

### Registries and Existing Wallets

Without a registry, the record would only work for the wallets which serve the
connect page, and no existing wallet does. A registry entry allows to reference
existing wallets with the protocol they use today. The application then relies
on the integration it already has, e.g. through a library such as Stellar
Wallets Kit. Wallets can add the `connect` route to their entry later on.

A central service routing the requests to wallets was also considered, in a
similar way to card networks. It could apply rules depending on the amount, or
send notifications. Such a service would have to be trusted by all applications
and would see all the requests. These rules can be applied by the wallet
itself, or by the policies of a smart account.

### Single Record

An account has a single record. The user can always select another wallet in
the application, so a list of wallets ordered by preference was not found to be
necessary.

### Relation with SEP-60

[SEP-60] states that an application must not select a provider based on the
information it announces, as any script in the page can announce anything. In
this proposal, the wallet is selected by the owner of the account and the
record is read from the ledger. The announced `rdns` is only used to find the
corresponding provider.

## Security Concerns

The record does not give any authority to an application or to a wallet. All
requests are still approved by the user in the wallet. The application also
verifies that the address returned by the wallet is the one it resolved.

Setting the record requires the authorization of the account. An attacker who
is able to change it already controls the account. A user could still be
tricked into signing a transaction which sets the record to a malicious domain.
For this reason, wallets should clearly display such a change, and applications
display the domain before connecting.

The application opens a page whose domain is read from the ledger. This page is
only opened following a user action and in its own window. An application may
also decide to only open the domains which are listed in a registry it trusts.

Messages are only exchanged between the application and the window it opened,
and both sides verify the origin of each message. The application should open
the window with a random name, so that another frame cannot reuse it.

If the domain of a wallet is taken over by another party, the accounts which
reference it are directed to this party. Displaying the domain to the user
before connecting helps to detect such cases.

The wallet label and the content of a registry entry are not trusted. They are
only used for display, as plain text for the name and the label, and as an
image for the icon.

The record is public. Anyone can know which wallet is used by an account.
Wallets should inform users about this before setting the record.

## Changelog

- `v0.0.1`: Initial draft.

[SEP-18]: ./sep-0018.md
[SEP-43]: ./sep-0043.md
[SEP-47]: ./sep-0047.md
[SEP-60]: ./sep-0060.md
[CAP-84]: ../core/cap-0084.md
