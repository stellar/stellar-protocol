## Preamble

```
SEP: <to be assigned>
Title: Bootstrapping Multisig Coordination
Author: Paul Selden <paul.selden@stellarguard.me>, Nikhil Saraf <nikhil@interstellar.com>
Status: Draft
Created: 2018-10-18
```

## Simple Summary

Provides a standard way for multisig accounts to designate where transactions should be submitted for coordination of additional signatures.

## Abstract

An account may designate which multisig server to use in a data entry that points to a server with a `stellar.toml` file. This file contains a `MULTISIG_SERVER` field which is an API where multisig transactions should be submitted. Wallets should implement this SEP so they can support multisig accounts without requiring them to run a multisig service themselves.

## Motivation

Currently there are only a few public tools that allow for multisig accounts, and they all do it by implementing their own signature coordinator services to do so. Wallets or other services that do not implement their own backends have no real way to deal with multisig accounts, so most of them just don't at all. By allowing an account to specify where they want their multisig transactions submitted to, it enables those wallets to interop with existing multisig services without relying on vendor-specific SDKs and APIs.

Additionally, there may be use cases where users do not want their multisig transactions broadcasted to a public coordinator, but would still like to use existing wallets to submit them to a private coordinator.

## Specification

### Account Data

A multisig account adds a data entry with the key `multisig_server` and the value of a hostname used to resolve the `stellar.toml` file of the multisig service.

Example:
Key: `multisig_server`
Value: `stellarguard.me`

## Multisig Server stellar.toml

Multisig coordinators advertise the existence of their service through the `stellar.toml` file. The top-level parameter `MULTISIG_SERVER` should contain a fully-qualified URL of a multisig coordination service where transactions will should be submitted.

Example of `stellar.toml`:
```
MULTISIG_SERVER="https://stellarguard.me/api/transactions"
```

### Multisig Server API Endpoint

Multisig Services must expose one REST API endpoint that is defined in their `stellar.toml` under the `MULTISIG_SERVER` key.

**Request**

An `HTTP POST` to `<MULTISIG_SERVER>` using ContentType `application/x-www-form-urlencoded`.

Request Parameters:

- **tx** - A base64 encoded Transaction Envelope XDR
- **callback** -An optional fully qualified url where transactions will be `POST`ed to after the service collects enough signatures. 

Example:

```
POST https://stellarguard.me/api/transactions 

Body:

tx=AAAAAKOO6%2F8v1w601RU0cxTffeRTE1%2BYJg8%2FLehhY%2BuKT70LAAAAZAADh8QAAAABAAAAAAAAAAAAAAABAAAAAAAAAAEAAAAAo47r%2Fy%2FXDrTVFTRzFN995FMTX5gmDz8t6GFj64pPvQsAAAAAAAAAAACYloAAAAAAAAAAAYpPvQsAAABAHL1r%2BZlf4fFWmbFmnKO%2BN36ZoovVCbwQUP8hl1ChtT0bfa4InFJQEs8RhGe8Rt1mwTdhtV13v1DR71Kxik06Dw%3D%3D&callback=https%3A%2F%2Fmywallet.com%2Ftransactions
```

**Response**

On success, the endpoint should return 200 OK HTTP status code and a JSON-encoded object that has service-specific data in it.

Example:

```json
{
  "stellarGuard": true,
  "url": "https://stellarguard.me/transactions/c585ceee-b1b9-4009-aa37-b8544346a036"
}
```

####  CORS headers

In order to comply with browser cross-origin access policies, the service should provide wildcard CORS response HTTP header. The following HTTP header must be set for the API endpoint:

```
Access-Control-Allow-Origin: *
```

### Multisig Transaction Flow

1. Determine whether a transaction requires additional signatures in order to be valid.
1. If the transaction requires more signatures, look up the data entry with the key `multisig_server` on the transaction source account.
1. Resolve the `stellar.toml` associated with the account's `multisig_server` entry and return the `MULTISIG_SERVER` field.
1. `POST` the transaction to the `MULTISIG_SERVER` endpoint.
1. The service responds with 200 and the wallet that made the call can present additional details about the transaction. If a `callback` parameter was provided.

## Rationale

When implementing StellarGuard for the Stellar Account Viewer, it was rightly pointed out that it was trying to avoid vendor-specific implementations such as the one that was provided (https://github.com/stellar/account-viewer/pull/68#issuecomment-410746896). Instead, we discussed an alternative approach that could be used by other products and tools that want to support multisig without implementing it over and over again for each service.

One design choice I considered was whether or not to use a SEP-0007 style URI as a parameter to the API endpoint instead of using `tx` and `callback`, since SEP-0007 already encodes these things. However, this would just complicate creating and parsing the transaction for little discernable benefit.

Another design choice was whether to skip the `stellar.toml` step and add the fully qualified multisig server endpoint to the account's data field. I believe that the `stellar.toml` approach affords greater flexibilty for the server to change its implementations, since it is much easier to update the `stellar.toml` than to update the data entry of every account that uses it.

### Previous Discussion

I initially introduced the idea on GalacticTalk: https://galactictalk.org/d/1651-a-vendor-agnostic-way-to-bootstrapping-multisig-coordination, and the idea was met with mixed reviews. The primary argument was that it doesn't go far enough and provide the full story about how to actually handle the multisig coordination. However, I feel that fully specifying that part of it would actually limit its usage, as there may be use-case specific implementation details.

## Implementation

The server implementation is currently live on [https://test.stellarguard.me](https://test.stellarguard.me) and [https://stellarguard.me](https://stellarguard.me).

A library that implements this protocol has been published here: [https://github.com/stellarguard/multisig-utils](https://github.com/stellarguard/multisig-utils)

## Outstanding Questions

- Should we require the transaction to be signed at least once in order for it to be submitted? StellarGuard requires that it is signed by an account that is associated with a StellarGuard user and uses the signature to prove ownership to prevent transaction notification spam.
- Should `callback` be part of the server requirements? Do we need to force all multisig services to allow a callback, or should it be optional that it's supported?
- Is there anything that should be required to be returned in the response data?