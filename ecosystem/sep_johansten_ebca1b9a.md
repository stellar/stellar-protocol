SEP: 00xy<br>
Title: Self-verification of validator nodes<br>
Author: Johan Stén <johan@futuretense.io><br>
Track: Standard<br>
Status: Draft<br>
Created: 2018-05-06<br>
Discussion: https://github.com/stellar/stellar-protocol/issues/111<br>

# Simple Summary

Using Stellar accounts to link validator nodes to the entities operating them.

# Abstract

Contrary to Bitcoin, which was designed to remove the need to trust third parties, trust is fundamental to FBA/SCP -- node operators explicitly have to select sets of nodes which they trust. 

So who *do* you trust? And how do you know what nodes belong to them?

Just as Stellar uses federation for anchors, and federated address lookups, we suggest using the same mechanics for a baseline level of verification of validator nodes.

# Motivation

The current protocol for publishing node metadata is highly centralized, relying on SDF as a central gatekeeper as the maintainers of the different validator lists (https://github.com/stellar/docs/blob/master/validators.md, and https://www.stellar.org/developers/guides/nodes.html / https://github.com/stellar/dashboard/blob/master/common/nodes.js)

We need better scalability, better discoverability, more decentralization, better information quality.

# Specification

## Linking

* create an account for the validator node you operate
* set the account homedomain to your website
* create a stellar.toml file in `/.well-known` on the website server
* add your validator node to the stellar.toml file

This creates a two-way link between the node and the website of the operating entity, uniquely identifying it.

## Stellar.toml metadata

Please refer to SEP-0001<sup>[1](#note1)</sup> for specifics on how this works.

Whereas SEP-0001 is primarily targetted at asset issuers, the idea is to re-use as much from SEP-0001 as makes sense.

At an absolute minimum, `OUR_VALIDATORS` MUST be used since that is what creates a link from the website back to the validator node.

Recommended fields would be:

```
NODE_NAMES - to give display names to the nodes listed in OUR_VALIDATORS
HISTORY
[DOCUMENTATION]
[[PRINCIPALS]]
```



#### Example code for linking:

```javascript
const userKeys = StellarSdk.Keypair.fromSecret(...);
                                               
// validator node NODE_SEED                                               
const nodeKeys = StellarSdk.Keypair.fromSecret(...);
const nodeId = nodeKeys.publicKey();

// the 
const homeDomain = '...';

const account = await server.loadAccount(userKeys.publicKey());
const tx = new StellarSdk.TransactionBuilder(account,  {fee: 100})
    .addOperation(StellarSdk.Operation.createAccount({
        destination: nodeId,
        startingBalance: '1'
    }))
    .addOperation(StellarSdk.Operation.setOptions({
        source: nodeId,
        homeDomain: homeDomain
    }))
    .setTimeout(0)
    .build();

tx.sign(userKeys);
tx.sign(nodeKeys);

const result = await server.submitTransaction(tx);
```



#### Example look-up:

```
MacBook-Pro:~ Johan$ curl https://horizon.stellar.org/accounts/GBFZFQRGOPQC5OEAWO76NOY6LBRLUNH4I5QYPUYAK53QSQWVTQ2D4FT5
{
  ...
  "id": "GBFZFQRGOPQC5OEAWO76NOY6LBRLUNH4I5QYPUYAK53QSQWVTQ2D4FT5",
  ...
  "home_domain": "futuretense.io",
  ...
}

MacBook-Pro:~ Johan$ curl https://futuretense.io/.well-known/stellar.toml
...
OUR_VALIDATORS=[
    "GBFZFQRGOPQC5OEAWO76NOY6LBRLUNH4I5QYPUYAK53QSQWVTQ2D4FT5"
]
...
```



# Design Rationale

Federation is well-established as a building block for protocols built on Stellar.

Validator nodes have keypairs and are already using public keys as their identity, so it's not much of a stretch to add accounts into the mix, in order to start using reverse federation as a means of looking up metadata associated with a specific validator node.

# Security Concerns

With a validator node account linked to a homedomain stellar.toml file like suggested, we're really relying on the integrity of the stellar.toml file and the server it resides on, making sure it only has write access by authorized users.

Additional security measures that could be taken include signing the stellar.toml file with the validator key(s), and serving in a file next to the stellar.toml file. 

Another thing might be to add DKIF<sup>[2](#note2)</sup>-style protection, and sign the stellar.toml file with a private key unrelated to the validator node(s), and publish the public key in the DNS response.

These are most likely the topic of an SEP by themselves.



# Links

<a name="note1">1) https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0001.md</a><br>
<a name="note2">2) https://github.com/stellar/stellar-protocol/issues/80</a><br>
