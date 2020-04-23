
## Preamble

```
SEP: 00XX
Title: Fiat-To-Fiat payments
Author: SDF
Status: Draft
Created: 2020-04-07
Updated: 2020-04-07
Version 1.0.0
```

## Simple Summary

This SEP defines a protocol for enabling fiat to fiat payments between two real world accounts, facilitated by two different anchors.

## Abstract

This proposal facilitates the ability for anchors to build a rail between two regions, allowing end users to send fiat from one bank account directly into another end users bank account.  In this flow, neither user needs to deal with the stellar network, the two anchors take care of everything for them.

## Example

Alice, in Nigeria, wants to send money to Bob in Europe. Alice signs up with NigeriaPay to make this payment to send money directly into Bob’s bank account. Bob doesn’t need to do anything, or know anything about this payment, besides letting Alice know what his bank account information is. Alice only needs to deal with her anchor (NigeriaPay).

NigeriaPay will utilize its European rail, enabled with EuroPay Anchor service, to move the money to EuroPay in order to deposit it into Bob’s bank account.

## Prerequisites

* An anchor must define the location of their `DIRECT_PAYMENT_SERVER` in their [`stellar.toml`](sep-0001.md). Anchors will find each others servers by pulling this TOML file from their home domains.
* Anchors will create bi-lateral agreements to interoperate with each other.  This differs from other protocols in that there is no concept of 'discoverability'.  Anchors should keep a mapping of their partnerships in different regions to their home domains.
* Each anchor registers a stellar key with each counterparty anchor they interact with in order to identify themselves via [SEP-10 Web Authentication](sep-0010.md).


## Authentication

Anchors should support [SEP-10](sep-0010.md) web authentication to ensure the counterparty they're interoperating with is actually who they say they are.  Clients must submit the JWT obtained via the SEP-10 authentication flow to all API endpoints.

The JWT should be included in all requests as request header:
```
Authorization: Bearer <JWT>
```

Any API request the fails to meet proper authentication should return a 403 forbidden response with the error payload:

```
{
  "type": "authentication_required"
}
```

## HTTPS Only

This protocol involves the transfer of value, and so HTTPS is required for all endpoints for security.  Anchors should refuse to interact with any insecure HTTP endpoints.

## Implementation Notes

### Entities Involved

- Sending Client: The end user who is initiating a payment via the sending anchor
- Sending Anchor: The business offering outbound payment services.  Takes fiat in from the sending client, and has a business relationship with the receiving anchor.
- Receiving Anchor: The business offering inbound payment processing. Deposits fiat in the receiving clients bank account, and has a business relationship with the sending anchor.
- Receiving Client: The owner of the destination bank account.

### Setting up rails

1. To create a rail find a counterparty who implmements this SEP in the region you wish to provide access to, and agrees to do business with you.
1. Trade public keys with each other in order to identify and securely interoperate with each other
1. Keep a mapping of region to home_domain, using home_domain as your intial entry point to interoperating.

### User Onboarding

1. User onboarding happens with the sending anchor, and is out of the scope of this spec.
1. Sending anchor should use this to collect any KYC about the receiver it will need so it doesn't have to do it at every transaction.

### Payment Flow

1. Payment initiation happens in the sending anchors interface, and is also out of the scope of this spec.
1. The sending client chooses a destination region.
1. The sending anchor fetches the TOML file to find the SEND_SERVER API and [`/info`](#info) endpoint fields for the receiving anchor for this region.
1. Using the fields fetched from /info, the sending anchor collects all needed information from the sending client.
1. The sending anchor POSTs all that information to the [`/send](#send) endpoint of the receiving anchor.
1. If information is missing, or the receiving anchor needs extra information to complete this transaction, `POST /send` will return `403 Customer Information Needed` along with the missing fields. The sending anchor should collect these and retry the entire `POST /send` call, until it succeeds.
1. Once all needed information is provided and the receiving anchor is ready to complete this transaction, the `POST /send` call will return a `200` status along with information needed to complete the transaction over the stellar network.
1. The sending anchor should collect the fiat from the sending client, and perform the specified stellar transaction to send the money to the receiving anchor.  This is usually a path payment, but can be done with a regular payment as well, so long as the receiving anchor gets the token they expect.
1. Once the stellar transaction is completed, the receiving anchor should deposit the money in the receivers bank account.
1. If the receiver finds out during a bank deposit that some of the receivers information is incorrect, the transaction should be placed in the `pending_info_update` status so the sender can correct it.
1. The sending anchor can query the status of this transaction via the [`/transaction`](#transaction) endpoint, and should communicate updates to the sending client as that progresses.  If the status is `pending_info_update` it should request that info from the sending client and provide it to the receiving anchor via the [`/update`](#update) endpoint.
1. Once the [`/transaction`](#transaction) endpoint returns a `completed` status the transaction has been completed.



## API Endpoints

* [`GET /info`](#info)
* [`POST /send`](#send)
* [`GET /transaction`](#single-historical-transaction)
* [`PUT /update`](#update-transaction)

### Info
#### Request

```
GET DIRECT_PAYMENT_SERVER/info
```

Allows an anchor to communicate basic info about what currencies their `DIRECT_PAYMENT_SERVER` supports receiving from partner anchors.

Request parameters:

Name | Type | Description
-----|------|------------
`lang` | string | (optional) Defaults to `en`. Language code specified using [ISO 639-1](https://en.wikipedia.org/wiki/ISO_639-1). `description` fields in the response should be in this language.

#### Response

The response should be a JSON object like:

```json
{
   "receive":{
      "USD":{
         "enabled":true,
         "fee_fixed":5,
         "fee_percent":1,
         "min_amount":0.1,
         "max_amount":1000,
         "fields":{
            "sender":{
               "first_name":"The sender's first name",
               "last_name":"The sender's last name"
            },
            "receiver":{
               "first_name":"The receiver's first name",
               "last_name":"The receiver's last name",
               "email_address":"The receiver's email address"
            },
            "transaction":{
               "routing_number":{
                  "description":"routing number of the destination bank account"
               },
               "account_number":{
                  "description":"bank account number of the destination"
               },
               "type":{
                  "description":"type of deposit to make",
                  "choices":[
                     "SEPA",
                     "SWIFT"
                  ]
               }
            }
         }
      }
   }
}
```

The JSON object contains an entry for each asset that the anchor supports for receiving and completing a direct payment.

#### For each asset available for receiving, response contains:

* `min_amount`: Optional minimum amount. No limit if not specified.
* `max_amount`: Optional maximum amount. No limit if not specified.
* `fee_fixed`: Optional fixed (flat) fee for deposit. In units of the received asset. Leave blank if there is no fee or the fee schedule is complex.
* `fee_percent`: Optional percentage fee for deposit. In percentage points. Leave blank if there is no fee or the fee schedule is complex.
* `fields` object as explained below.

The `fields` object allows an anchor to describe fields that must be passed into `POST /send`. It should include any KYC fields required for the sender or receiver, account information, and anything else required by the receiving anchor in order to complete a transaction.  Fields are broken out by `sender`, `receiver`, and `transaction`.  `sender` and `receiver` contain KYC requests of values from SEP-9 while `transacton` contains transaction specific information requested.

Each `fields` sub-object contains a key for each field name and an object with the following fields as the value:

* `description`: description of field to show to user.
* `choices`: list of possible values for the field.

### Send

#### Request

```
POST DIRECT_PAYMENT_SERVER/send
Content-Type: application/json

{
  "amount": 100,
  "require_receiver_info": ["address", "tax_id"],
  "fields": {
    "sender": {
      "first_name": "Alice",
      "last_name": "Jones"
    },
    "receiver": {
      "first_name": "Bob",
      "last_name": "Dillon",
      "email_address": "bdillon@something.com"
    },
    "transaction": {
      "routing_number": "442928834",
      "account_number": "0029483242",
      "type": "SEPA"
    }
  }
}
```

This post requests attempts to initiate a payment through this anchor.  It should provide the amount and all the required fields (specified in the [`/info`](#info) endpoint).  The sending anchor can also provide a `require_receiver_info` object if it needs information on the receiver client that the receiving anchor can provide.

If the request describes a valid transaction that this anchor can fulfill, we return a success response with details on what to send. If the request is not valid, or we need more info, we can return with an error response and expect the sending anchor to try again with updated values.

##### Request Parameters

Name | Type | Description
-----|-----|------
`require_receiver_info` | array | A list of [SEP-9](sep-0009.md) values requested for the receiving client
`amount` | number | Amount of payment in destination currency
`fields` | object | A key-pair object containing the values requested by the receiving anchor in their `/info` endpoint, broken out by sender, receiver, and transacton.
`lang` | string | (optional) Defaults to `en`. Language code specified using [ISO 639-1](https://en.wikipedia.org/wiki/ISO_639-1).  Any human readable error codes or field descriptions will be returned in this language.

#### Responses

##### Success (200 ok)
This is the successful case where a receiving anchor confirms that they can fulfill this payment as described. The response body should be a JSON object with the following values

Name | Type | Description
-----|------|------------
`id` | string | Persistent identifier to check the status of this payment
`stellar_account_id` | string | Stellar account to send payment to
`stellar_memo_type` | string | Type of memo to attach to the stellar payment `(text | hash | id)`
`stellar_memo` | string | The memo to attach to the stellar payment
`receiver_info` | object | Key-value pairs of the information the sender requested via `require_receiver_info`

##### Customer Info Needed (403 forbidden)

In the case where the sending anchor didn't provide all the information requested in `/info`, or if the transacton requires extra information, the request should fail with a 403 status code and the following body in JSON format.  The sender should then retry the entire request including all the previously sent fields plus the fields described in the response.

Name | Type | Description
-----|------|------------
`error`| string | `customer_info_needed`
`fields` | object | A key-value pair of missing fields in the same format as fields described in [`/info`](#info), broken out by sender, receiver, and transacton.

##### Error (403 Forbidden)

In the case where the transacton just cannot be completed, return an error response with a JSON object containing an `error` key describing the error in human readable format in the language indicated in the request.

```
{
  'error': "The amount was above the maximum limit"
}

{
  'error': "That bank account is restricted via AML laws"
}
```

### Transaction

The transaction endpoint enables senders to query/validate a specific transaction at a receiving anchor.

```
GET DIRECT_PAYMENT_SERVER/transaction
```

Request parameters:

Name | Type | Description
-----|------|------------
`id` | string | The id of the transaction.

On success the endpoint should return `200 OK` HTTP status code and a JSON object with the following fields:

Name | Type | Description
-----|------|------------
`transaction` | object | The transaction that was requested by the client.

The `transaction` object should be of the following schema.

Name | Type | Description
-----|------|------------
`id` | string | Unique, anchor-generated id for the deposit/withdrawal.
`status` | string | Processing status of deposit/withdrawal.
`status_eta` | number | (optional) Estimated number of seconds until a status change is expected
`amount_in` | string | (optional) Amount received by anchor at start of transaction as a string with up to 7 decimals. Excludes any fees charged before the anchor received the funds.
`amount_out` | string | (optional) Amount sent by anchor to user at end of transaction as a string with up to 7 decimals.
`amount_fee` | string | (optional) Amount of fee charged by anchor.
`stellar_account_id` | string | Stellar account to send payment to
`stellar_memo_type` | string | Type of memo to attach to the stellar payment `(text | hash | id)`
`stellar_memo` | string | The memo to attach to the stellar payment
`started_at` | UTC ISO 8601 string | (optional) Start date and time of transaction.
`completed_at` | UTC ISO 8601 string | (optional) Completion date and time of transaction.
`stellar_transaction_id` | string | (optional) transaction_id on Stellar network of the transfer that either initiated the payment.
`external_transaction_id` | string | (optional) ID of transaction on external network that either completes the payment into the receivers account.
`refunded` | boolean | (optional) Should be true if the transaction was refunded. Not including this field means the transaction was not refunded.
`required_info_message` | string | (optional) A human readable message indicating any errors that require updated information from the sender
`required_info_updates` | object | (optional) A set of fields that require upate from the sender, in the same format as described in [/info](#info).  Fields should be broken out by sender, receiver, and transacton as in /info.

`status` should be one of:

* `pending_sender` -- awaiting payment to be initiated by sending anchor
* `pending_stellar` -- transaction has been submitted to Stellar network, but is not yet confirmed.
* `pending_info_update` -- certain pieces of information need to be updated by the sending anchor.  See [pending info update](#pending-info-update) section
* `pending_receiver` -- payment is being processed by the receiving anchor
* `pending_external` -- payment has been submitted to external network, but is not yet confirmed.
* `completed` -- deposit/withdrawal fully completed.
* `error` -- catch-all for any error not enumerated above.

Example response:

```json
{
  "transaction": {
      "id": "82fhs729f63dh0v4",
      "status": "pending_external",
      "status_eta": 3600,
      "external_transaction_id": "ABCDEFG1234567890",
      "amount_in": "18.34",
      "amount_out": "18.24",
      "amount_fee": "0.1",
      "started_at": "2017-03-20T17:05:32Z"
    }
}
```


```json
{
  "transaction": {
      "id": "82fhs729f63dh0v4",
      "status": "pending_info_update",
      "status_eta": 3600,
      "external_transaction_id": "ABCDEFG1234567890",
      "amount_in": "18.34",
      "amount_out": "18.24",
      "amount_fee": "0.1",
      "started_at": "2017-03-20T17:05:32Z",
      "required_info_message": "The bank reported an incorrect name for the receiver, please ensure the name matches legal documents",
      "required_info_fields": {
         "receiver": {
            "first_name":"The receiver's first name",
            "last_name":"The receiver's last name"
         }
      }
    }
}
```

If the transaction cannot be found, the endpoint should return a `404 NOT FOUND` result.

#### Pending info update

In certain cases the receiver might need to request updated information, for example if the bank tells them that the provided receiver name is incorrect, or missing a middle initial.  In this case, the transaction should go into the `pending_info_update` state until the sender provides updates.

### Update

The `/update` endpoint allows for updating certain pieces of information that need to be corrected.  For example a bank may reject a deposit because a name is mis-spelled, or a middle initial is missing.  This allows transactions to be updated instead of errored and refunded.

```
PUT DIRECT_PAYMENT_SERVER/update
```

Request parameters:

Name | Type | Description
-----|------|------------
`id` | string | The id of the transaction.
`fields` | object | A key-pair object containing the values requested to be updated by the receiving anchor.

#### Example

```
PUT DIRECT_PAYMENT_SERVER/update

{
   id: "82fhs729f63dh0v4",
   fields: {
      receiver: {
         first_name: "Bob",
         last_name: "Jones"
      }
   }
}
```

#### Success 200 OK

If the information was successfully updated, respond with a 200 status code, and return the transaction json in the body. The transaction should return to `pending_receiver`, though it is possible that the information could still need to be updated again.

#### Error 400

If the information was malformed, or if the sender tried to update data that isn't updateable, return a 400 with an object containing an error message.

```
{
   "error": "Supplied fields do not allow updates, please only try to updates the fields requested"
}