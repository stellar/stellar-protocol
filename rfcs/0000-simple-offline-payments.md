- Feature Name: Stored Value and Offline Payments In Stellar
- Start Date: 2016-01-30
- RFC PR:

# Summary

 A protocol in which two participants on the stellar network can make payments to one another when network connectivity is down at the moment of the transaction.

## Motivation

Infrastructure outages in developing nations can be intermittent.  While visiting Lagos, Nigeria, we have routinely experienced brief power and internet outages.  This situation is particularly damaging to low-value, quick financial transactions, such as making small purchases or paying for transit;  People simple say "Screw it" and reach for their paper cash to pay for a service when the electronic payment fails.

By designing a system such that payments can continue to happen in the face of untimely outages, we will serve areas with these types of infrastructure deficits better, and  trust in electronic payments can begin to be built.

This scheme is intended to be a service provided by an anchor in a given market, and is a potential source of revenue for the anchor by giving a touch point in which to charge fees.

Purchasers load currency into their wallet by returning credits to an anchor in the same fashion as if they were cashing out.  In return, the anchor signs a statement that includes the total balance available for offline expenditure.  This statement may be presented to a merchant (who also has an account with the anchor) as verification of available offline funds.  At the point of sale, both purchaser and merchant sign a "bill" authorizing the transfer of offline funds from one party to another.  When connectivity is restored, either party may transmit the bill to the anchor, whose software will verify the bill and trigger a transaction on the stellar network that pays the merchant.

## Detailed Design

This protocol is composed of several operations:
- Load funds
- Refresh balances
- Verify balance
- Craft and sign bill
- Countersign bill
- Redeem bill
- Settle offline payments

### Load Funds

The load operation allows a user to lock funds for offline use.  Funds that are available for offline use are not actually kept in the account of the user, but are instead held by the anchor in trust, such that a payment can be made without both participating parties present at the time when internet connectivity is restored.

To load funds, to sub-operations must be completed:

1.  A payment is sent from the user to the anchor, using a memo to specify that this payment should be credited to the user's offline balance.
2.  The user's client application retrieves the anchor's balance sheet from the anchor server. (perhaps as specified by another endpoint in stellar.toml?) See the "Refresh balances" operation for details.

After these operations are complete, the client should have all the necessary information to convince a merchant's client that the customer is good for the funds.

### Refresh balances

The "balance sheet", a signed statement that specifies how much of any given currency an account has for offline spending at a given anchor, contains an expiration date.  This expiration date can be consulted by the merchants client as a signal for deciding trust-worthiness of the customer.

While connectivity is a available, a client should periodically refresh their balance sheet to extend the expiration time.  To perform this refresh, several sub-operations are involved.

1.  The customer client requests a refresh challenge for an account from the anchor's service.
2.  The anchor produces a challenge with embedded nonce and transmits it to the customer client.
3.  The customer client signs the challenge and transmits it to the anchor.
4.  The anchor verifies the challenge is signed correctly by the customer client and then then crafts and signs a new balance sheet.
5.  The anchor returns the balance sheet to the customer client.
6.  The customer client verifies the balance sheet is correctly signed and the expiration date is in the future.

### Verify Balance

A merchant client will want to verify that the customer is in possession of the funds needed to pay for the services being provided:

1.  The customer client and merchant client form a connection over bluetooth LE (or other non-internet data connection)
2.  The merchant client transmits a list of anchor addresses in which it accepts payment.
3.  The customer client inspects anchor addresses and returns any balance sheets it possesses that share the same anchor address.
4.  The merchant client verifies the signature and expiration date on the balance sheet.

Note:  This verified balance does not account for any un-settled offline payments that may have been made since the client was last offline.

### Craft and sign bill

After the balance of a customer is confirmed by the merchant, it should choose what balance sheet can fulfill the proposed cost.  The merchant client will then craft a bill containing the following info:

- The anchor account ID
- An expiration date
- the customer's account ID
- the merchant's account ID
- The asset involved
- The cost
- An optional payment memo
- A random nonce

After crafting the bill, the merchant client signs it with the appropriate secret key.  The bill is now ready to transmit to the customer client.

#### Random Ideas regarding the bill

The bill could potentially just be an actual `Transaction` XDR struct... the only wrinkle involves the sequence number involved.  Since we are offline, neither party can know what the correct value should be.  Perhaps we set the sequence to zero, and then the transaction is simply wrapped in a new kind of envelope (`OfflineTransactionEnvelope`, `BillEnvelope`?)

### Countersign Bill

After receiving the signed bill from a merchant and confirming the payment with the customer, the customer client may now countersign the bill.  When fully signed (by both customer and merchant), this bill may be redeemed at the anchor.  A copy of the fully signed bill should be transmitted back to the merchant client, allowing either client to redeem the bill when connectivity to the Stellar network is restored.

### Redeem Bill

After having completed the signing of a bill, it may be redeemed with the anchor.  This will cause a well-functioning anchor to craft, sign, and submit a stellar transaction that settles the payment described by the bill:

1. Either client submits a fully signed bill to the anchor.
2. The anchor checks its database for prior settlement of this bill, returning success if found
2. If not prior settlement is found, the anchor verifies the expiration date and the signatures on the bill.
3. The anchor submits a transaction to the stellar that settles the payment and records the resultant hash to its database.
4. The settlement transaction's hash is returned to the client.

When processing a bill, the anchor MUST verify that the bill has not been processed in the past, ensuring that double payment does not occur.

### Settle Offline Payments

Both clients in this protocol should periodically trigger the settlement process with the anchor, providing connectivity is available.  Any unsettled offline payments should be redeemed with the anchor, and each successful redemption should trigger the removal from the clients "unsettled offline payments" list.  

## Drawbacks

This protocol is not intended to provide cross-currency offline payments.  Both the customer and the merchant must be members of the same anchor.

This protocol is only available to clients that have the capability to sign statements offline (i.e. they store the secret key on the local device).  Hosted wallets will not be available during an internet outage.

This protocol is only applicable when both parties have smart phones or devices that can communicate directly.

## User Experience

Presented here is one formulation of a user experience, from both the customer and merchant perspectives.

TODO

### Overdraft

TODO: talk about when a user goes into negative offline balance.

### Unresolved Questions

- How do we integrate this offline model with the notion that an account may have signing keys and thresholds different than the account id.

### Nuances

While it could be possible for the Stellar network to support this functionality in some way natively, I believe it is important that the anchor be involved in providing offline payment.  Since we cannot know whether an account has enough available funds at the point of sale, there is some exposure for fraud to the merchant.  The anchor is a logically entity to shoulder this exposure, hopefully providing protection for the merchant and fostering trust in the system.
