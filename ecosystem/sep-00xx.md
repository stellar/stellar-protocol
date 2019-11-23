## Preamble

```
SEP: 00xx
Title: Stellar Web Authorization
Author: Leigh McCulloch <@leighmccullcoh>
Status: Draft
Created: 2019-11-22
Version 1.0.0
```

## Simple Summary

This SEP defines the standard way for clients such as wallets or exchanges to expand authenticated web sessions created with SEP-10 with additional claims about control over Stellar accounts to facilitate authorization of a specific Stellar account. SEP-10 provides a JWT that proves possession of a Stellar key. This SEP provides additional claims that can be added to the JWT that prove a weight of control of a Stellar account, and a process that a client and server can follow to augment a SEP-10 JWT with those claims.

## Abstract

This protocol is the definition of additional claims an implementer of SEP-10 can include in the JWT that capture at a point in time the weight of control a Stellar key, or multiple keys, has for a given account.

The authorization flow is as follows:

1. The client obtains a [JWT](jwt.io) using SEP-10 proving possession of one or more Stellar keys.
1. The client calls the server with the SEP-10 JWT requesting authorization of a Stellar account.
1. The server verifies that the keys in the SEP-10 JWT are signers of the Stellar account.
1. The server responds with the JWT augmented with additional claims representing the account and weighted control of the keys.
1. Any future calls to the server can be authenticated by including the JWT as a parameter and a level of control of the account can be authorized by the additional claims.

The flow achieves several things:

* The server can verify that the client holds the secret key(s) that can sign for an account without checking the network on every request containing a SEP-10 JWT
* The server can chose a timeout for the user's proof that they are a signer of a Stellar account independent of the timeout that they possess their secret keys
* Since the signers of a Stellar account can change at anytime the server can choose a small timeout of JWTs of this SEP, while keeping a longer timeout of JWTs of SEP-10. A longer lasting SEP-10 JWT can be used to check and refresh proof of control of an account without the user needing to resign transactions.

## Authentication Endpoint

A web service indicates that it supports account authorization via this protocol by specifying `WEB_AUTHZ_ENDPOINT` in their [`stellar.toml`](sep-0001.md) file. This is how a wallet knows where to find the authorization server. A web server is required to implement the following behavior for the web authorization endpoint:

* [`POST <WEB_AUTH_ENDPOINT>`](#authorize): exchange a SEP-10 key JWT for an account JWT

## Cross-Origin Headers

Valid CORS headers are necessary to allow web clients from other sites to use the endpoints. The following HTTP header must be set for all authentication endpoints, including error responses.

```
Access-Control-Allow-Origin: *
```

In order for browsers-based wallets to validate the CORS headers, as [specified by W3C]( https://www.w3.org/TR/cors/#preflight-request), the preflight request (OPTIONS request) must be implemented in all the endpoints that support Cross-Origin.

### Authorize

This endpoint accepts a Stellar account address and a SEP-10 JWT, validates it and responds with a augmented JWT containing additional claims about the level of control the signers in the SEP-10 JWT have over the Stellar account.

Client submits as a HTTP POST request to `WEB_AUTHZ_ENDPOINT` using one of the following formats (both should be equally supported by the server):

* Content-Type: `application/x-www-form-urlencoded`, body: `account=<Stellar account address>`)
* Content-Type: `application/json`, body: `{"account": "<Stellar account address>"}`

With the SEP-10 JWT in the `Authorization` header in the format `BEARER <JWT>`.

To validate the request the server should complete the following steps. If any of the listed steps fail, then the authorization request must be rejected with HTTP Status Code 401. 
* Verify the SEP-10 JWT is issued from a trusted issuer, is signed by that issuer with an expected signing method, and has not expired. The server should follow all JWT best practices to ensure the JWT can be trusted and that any other application specific claims are present and valid.
* Verify the Stellar account is an active Stellar account.
* Verify all the Stellar keys in the SEP-10 JWT `sub` field are signers of the Stellar account.

Upon successful validation service responds with a session JWT, containing the following claims:

* `iss` (the principal that issued a token, [RFC7519, Section 4.1.1](https://tools.ietf.org/html/rfc7519#section-4.1.1)) — a [Uniform Resource Identifier (URI)] for the issuer (`https://example.com` or `https://example.com/G...`)
* `sub` (the principal that is the subject of the JWT, [RFC7519, Section 4.1.2](https://tools.ietf.org/html/rfc7519#section-4.1.2)) — the public keys of the authenticating client copied from the SEP-10 JWT
* `iat` (the time at which the JWT was issued [RFC7519, Section 4.1.6](https://tools.ietf.org/html/rfc7519#section-4.1.6)) — current timestamp (`1530644093`)
* `exp` (the expiration time on or after which the JWT must not be accepted for processing, [RFC7519, Section 4.1.4](https://tools.ietf.org/html/rfc7519#section-4.1.4)) — a server can pick its own expiration period for the token, however a few minutes is recommended (`1530730493`)
* `acc` — the Stellar account that authorization was verified (`G...`)
* `thr` — the low, medium, and high threshold of the Stellar account comma separated (`1,10,20`)
* `wei` — the total weight that all signers in `sub` have when their weights are summed

The JWT may contain other claims specific to your application, see [RFC7519].

[Uniform Resource Identifier (URI)]: https://en.wikipedia.org/wiki/Uniform_Resource_Identifier
[RFC7519]: https://tools.ietf.org/html/rfc7519

#### Request

```
POST <WEB_AUTHZ_ENDPOINT>
```

Request Parameters:

Name      | Type          | Description
----------|---------------|------------
`account` | `G...` string | The Stellar account the user wants to prove authorization.

Example:

```
POST https://auth.example.com/
Content-Type: application/json
Authorization: BEARER eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJHQTZVSVhYUEVXWUZJTE5VSVdBQzM3WTRRUEVaTVFWREpIREtWV0ZaSjJLQ1dVQklVNUlYWk5EQSIsImp0aSI6IjE0NGQzNjdiY2IwZTcyY2FiZmRiZGU2MGVhZTBhZDczM2NjNjVkMmE2NTg3MDgzZGFiM2Q2MTZmODg1MTkwMjQiLCJpc3MiOiJodHRwczovL2ZsYXBweS1iaXJkLWRhcHAuZmlyZWJhc2VhcHAuY29tLyIsImlhdCI6MTUzNDI1Nzk5NCwiZXhwIjoxNTM0MzQ0Mzk0fQ.8nbB83Z6vGBgC1X9r3N6oQCFTBzDiITAfCJasRft0z0

{"account": "GBAULR7QM6CA7ELGNUMUW3JFUJDMFDNFV4LCBYR5NAER4JJJ72CA7LPX"}
```

#### Response

If the web service successfully validates the submitted SEP-10 JWT and account, the endpoint should return `200 OK` HTTP status code and a JSON object with the following fields:

Name    | Type   | Description
--------|--------|------------
`token` | string | The JWT that a user can use as authorization in future endpoint calls

Example:

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJHQTZVSVhYUEVXWUZJTE5VSVdBQzM3WTRRUEVaTVFWREpIREtWV0ZaSjJLQ1dVQklVNUlYWk5EQSIsImFjYyI6IkdBNlVJWFhQRVdZRklMTlVJV0FDMzdZNFFQRVpNUVZESkhES1ZXRlpKMktDV1VCSVU1SVhaTkRBIiwidGhyIjoiMSw1LDEwIiwid2VpIjoiMTAiLCJpc3MiOiJodHRwczovL2ZsYXBweS1iaXJkLWRhcHAuZmlyZWJhc2VhcHAuY29tLyIsImlhdCI6MTUzNDI1Nzk5NCwiZXhwIjoxNTM0MzQ0Mzk0fQ==.8nbB83Z6vGBgC1X9r3N6oQCFTBzDiITAfCJasRft0z0"
}
```

Check the example session token on [JWT.IO](https://jwt.io/#debugger-io?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJHQTZVSVhYUEVXWUZJTE5VSVdBQzM3WTRRUEVaTVFWREpIREtWV0ZaSjJLQ1dVQklVNUlYWk5EQSIsImFjYyI6IkdBNlVJWFhQRVdZRklMTlVJV0FDMzdZNFFQRVpNUVZESkhES1ZXRlpKMktDV1VCSVU1SVhaTkRBIiwidGhyIjoiMSw1LDEwIiwid2VpIjoiMTAiLCJpc3MiOiJodHRwczovL2ZsYXBweS1iaXJkLWRhcHAuZmlyZWJhc2VhcHAuY29tLyIsImlhdCI6MTUzNDI1Nzk5NCwiZXhwIjoxNTM0MzQ0Mzk0fQ==.8nbB83Z6vGBgC1X9r3N6oQCFTBzDiITAfCJasRft0z0).

Every other HTTP status code will be considered an error.

## JWT best practices

When generating and validating JWTs it's important to follow best practices. The IETF in the process of producing a set of best current practices when using JWTs: [IETF JWT BCP].

[IETF JWT BCP]: https://tools.ietf.org/wg/oauth/draft-ietf-oauth-jwt-bcp/

## Implementations

* TODO
