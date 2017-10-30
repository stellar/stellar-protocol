## Preamble

```
SEP: Not assigned
Title: Anchor/Client interoperability
Author: stellar.org
Status: Draft
Created: 2017-10-30
```

## Simple Summary
It will be easier for users if wallets and other clients can interact with anchors directly without the user having to leave the wallet to go to the anchor's site. This SEP is intended to create a standard way that anchors allow this to be done.

## Abstract
Proposal for a standard protocol that allows wallets to deposit and withdraw funds info from anchors.


## Specification


### Deposit

This is the user getting a token from the anchor. Deposits will be a new endpoint on the federation server. It will just return the accountId where we should send the currency that we specified. We will get the equivalent Asset issued by the anchor in return.

`DEPOSIT_SERVER` should be specified in the stellar.toml of the anchor.

Endpoint: `DEPOSIT_SERVER/deposit`<br>
Purpose: Get intructions for depositing an asset with the anchor.<br>
Method: GET<br>
Request parameters

Name | Type | Description
-----|------|------------
`currency_code` | string | The currency code of the asset the user is wanting to deposit with the anchor. Ex BTC,ETH,USD,INR,etc
`account` | string | The stellar account ID of the user that wants to deposit. This is where the asset token will be sent.
`create_new` | boolean | If true, then the anchor will create the given account with some of the asset that is sent in. After the client must call `DEPOSIT_SERVER/trusted` to notify the anchor it is ready to recieve the asset tokens in Stellar.

On success the endpoint should return `200 OK` HTTP status code and a JSON object with the following fields:

Name | Type | Description
-----|------|------------
how | string | Intstructions for how to deposit the asset. In the case of cryptocurrency it is just an address.
eta | int | (optional) Estimate of how long the deposit will take to credit in seconds.
min_amount | float | (optional) Minimum amount of an asset that a user can deposit.
max_amount | float | (optional) Maximum amount of asset that a user can deposit.
fee_fixed | float | (optional) If there is a fee for deposit. In units of the deposited asset.
fee_percent | float | (optional) If there is a percent fee for deposit. 
extra_info | object | (optional) Any additional data needed as an input for this deposit, example: Bank Name

Example:
```json
{
    "how" : "1Nh7uHdvY6fNwtQtM1G5EZAFPLC33B59rB"
    "fee_fixed" : 0.0002
}
```

Every other HTTP status code will be considered an error. The body should contain error details. 
For example:
```json
{
   "error": "This anchor doesn't support the given currency code: ETH"
}
```
<hr>
Endpoint: `DEPOSIT_SERVER/trusted`<br>
Purpose: Notify the anchor the given account has created the needed trust line. Only needed if `create_new` is true in the intial call to `DEPOSIT_SERVER/deposit`<br>
Method: GET<br>
Request parameters

Name | Type | Description
-----|------|------------
`account` | string | The stellar account ID of the user that wants to deposit. This is where the asset token will be sent.

On success the endpoint should return `200 OK` HTTP status code and send the asset token to the given account.

Every other HTTP status code will be considered an error. The body should contain error details. 
For example:
```json
{
   "error": "Given account doesn't trust this anchor."
}
```


### Withdraw

Withdrawals use the existing (federation)[../ecosystem/sep-0002.md] `forward` type and will return the Stellar account and memo where the user should send the asset to be withdrawn. The implicit understanding here is that the anchor is the issuer and we are redeeming the underlying asset from them in exchange for the token they issued to us in Stellar.

Endpoint: `FEDERATION_SERVER/federation`<br>
Purpose: Get the Stellar account and memo to send withdraw the asset to.<br>
Method: GET<br>
Request parameters

Name | Type | Description
-----|------|------------
`type` | string | forward
`forward_type` | string | either {bank_account,crypto}
`currency_code` | string | (for crypto) Specify the asset you are withdrawing
`dest` | string | (for crypto) The account you want to withdraw to 


On success the endpoint should return `200 OK` HTTP status code and a JSON object with the following fields:

Name | Type | Description
-----|------|------------
account_id | string | The account the user should send its token back to.
memo_type | string | (optional) type of memo to attach to transaction, one of `text`, `id` or `hash`
memo | string | (optional) value of memo to attach to transaction, for `hash` this should be base64-encoded.
min_amount | float | (optional) Minimum amount of an asset that a user can withdraw.
max_amount | float | (optional) Maximum amount of asset that a user can withdraw.
fee_fixed | float | (optional) If there is a fee for withdraw. In units of the withdrawn asset.
fee_percent | float | (optional) If there is a percent fee for withdraw. 
extra_info | object | (optional) Any additional data needed as an input for this withdraw, example: Bank Name

Example:
```json
{
  "account_id": "GCIBUCGPOHWMMMFPFTDWBSVHQRT4DIBJ7AD6BZJYDITBK2LCVBYW7HUQ",
  "memo_type": "id",
  "memo": "123"
}
```

Every other HTTP status code will be considered an error. The body should contain error details. 
For example:
```json
{
   "error": "This anchor doesn't support the given currency code: ETH"
}
```
