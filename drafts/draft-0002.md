## Preamble

```
SEP: Not assigned
Title: AUTHORIZED_STELLAR_ADDRESS proposal
Author: @nekrataal
Status: Draft
Created: 2018-01-23
```

## Simple Summary
This feature allows user to verify if the stellar public address received from a federation server has been binded from the owner of public address himself. 

## Motivation
Currently lot of federations servers allow any user to register arbitrary federation address.
This could create a lot of confusion and could facilitate phishing attack

To avoid this problem, some federation server ask the owner to perform a transaction to verify the account ownership. Even if this can solve the problem during the registration phase, there is no equivalent for the query phase

## Abstract
This proposal has the goal to create a standard for federation addresses bind operation, and it introduce the "Authorized Stellar Address" concept

## Specification

### Binding (optional)

Endpoint: `FEDERATION_SERVER/bind`<br>
Purpose: Bind a stellar address.<br>
Method: POST<br>
Request parameters

Name | Type | Optional | Description
-----|------|------|------
`stellar_address ` | string | false | The whole stellar address with domain included.
`account` | string | false | The stellar account ID that should be bind with the stellar address specified.
`memo_type` | string | true | Type of memo to bind, one of `text`, `id` or `hash`.
`memo` | string | true | Value of memo to bind, for `hash` this should be base64-encoded.
`sig`| string: base64 encoded | true | The signature performed with the corresponding secret key over the concatenation of "`stellar_address`\|`account`\|`memo_type `\|`memo `". 
`data` | string | true | Any additional data required by federation server for binding operation.


`FEDERATION_SERVER` should be specified in the stellar.toml of the requested domain.

### Querying
There are not substantial differences with the actual implemented operation, except to add the `sig` field into the response

```
{
  "stellar_address": <username*domain.tld>,
  "account_id": <account_id>,
  "memo_type": <"text", "id" , or "hash"> *optional*
  "memo": <memo to attach to any payment. if "hash" type then will be base64 encoded> *optional*
  "sig": <signature(<stellar_address>|<account_id>|<memo_type>|<memo>)> *optional*
}
```