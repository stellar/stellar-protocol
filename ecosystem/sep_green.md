## Preamble

```
SEP: To Be Assigned
Title: Green: A Language for Building Stellar Ledger Scenarios
Author: Bartek Nowotarski
Track: Standard
Status: Draft
Created: 2020-04-25
```

## Simple Summary

> [Green](https://www.nasa.gov/exploration/systems/sls/multimedia/what-is-green-run-infographic.html): New, untested rocket hardware.

Green is a language that allows running a set of commands to build and submit transactions and print information about the network state. Can be used to write tests, examples and playgrounds.

## Motivation

It's often useful to rebuild a given ledger state to share an example, test stellar-core or simply understand what's the result of running a set of transactions in Stellar network.

The existing solutions, `scc` and `txrep`, doesn't provide a specific format for sharing recipe files but also are not well suited for this use case (see Design Rationale section). Instead, users are forced to use SDK snippets. The problem with that is that they are using a specific programming language. A Python developer may not only have problems with understanding Go code but it will also be a problem for them to run it (runtime/compiler required). 

The larger problem is that a knowledge of a programming language is required to test Stellar network in an effective way. Laboratory provides a GUI for building transactions but it's hard to build more complicated scenarios and impossible to share them.

For developers, writing recipes will allow testing downstream systems (like Horizon) and smart contracts.

Finally, having a scenario language will allow building tools like playgrounds that will run a set of transactions on a fresh Stellar network. This will lead to better understanding of how Stellar network works.

## Abstract

This document specifies a YAML-based language for describing ledger scenarios for Stellar network. It's a very expresive language so it should allow fast development of test scenarios and examples in a specific format that can be shared with other users. It can be also be used in playgrounds.

Using YAML's anchors and merging maps prevents repetition and flow mappings allow one-liner commands. See Design Rationale for more examples.

## Specification

Scenario file consists of top-level `version` value and `commands` map. The list of commands can be found below.

### `account` command

Creates a new account using a network master account. Most often used to init accounts participating in a scenario and as an anchor to use in transactions and signing.

Param Name | Description
-|-
`random` | Creates a random account
`secret_key` | Secret key of the account
`public_key` | Public key of the account
`id` | ID if an account is a multiplexed account
`create` | Set to `false` to not create an account (ex. to use as a signer only).

Only one of `random`, `secret_key`, `public_key` are allowed.

### `transaction` command

Transaction command builds and submits a new transaction. The only required param is `operations`.

Param Name | Description
-|-
`source` | Anchor to an `account`, if not present defaults to network master account.
`operations` | List of operations

### `create_account` command

Create account is a helper that creates a transaction with a single `create_account` operation. Can be extended with `transaction` params like `memo` or `fee`.

Param Name | Description
-|-
`account` | Anchor to an account to create
`starting_balance` | Starting balance

#### Difference between `create_account` and `account` commands

`account` is used to initialize accounts participating in tests, accounts are created by master account but creation stage can be omited (`create: false`). `create_account` creates a transaction with `create_account` operation using one of the existing accounts as a `source`.

### `add_signer` command

Adds a new signer (sends a transaction with a single `set_options` operation). It's an example of a helper command that allow faster creation of transactions.

### `template` command

This command is ignored, it's only used for creating map templates that can be used for building other commands. See examples below.

### `print_account` command

Prints current account state. Useful in playgrounds to follow changes to a ledger entry or history data. Can be ignored in headless environments.

### Example

See this example in https://yaml-online-parser.appspot.com/ to understand how it will be parsed.

```yaml
version: 1
commands:
  # `account` creates an account but can be also used as a template for source, destination
  # fields or signing. Accounts are automatically created by network master unless create is
  # set to `false` (see below).
  - account: &alice {random: true}
  - account: &bob {secret_key: "SAC5JMWU6H47UEPJ3IRDJBWOMPSFUOHYJUO7RF33ZTVCEJD63DLJYCQA"}
  # below could also be a one-liner using flow mapping {public_key: "G...", create: false}
  - account: &joe
      public_key: "GBKXJQU7MOUWOFKRFCJJJ2QOVJEHD3KYTUOP7XO63QEZUUCFAWJBCUKP"
      create: false # accounts are automatically created, set to false to not create
  - account: &joe_multiplexed
      <<: *joe # entends joe to be a muliplexed account
      id: 100 # multiplexed account when `id` present
  - transaction:
      source: *alice # if not present network master account is used as source
      fee: 200 # if not present defaults to min_fee * #ops
      seqnum: 1000 # if not present will auto fill
      memo:
          type: hash
          value: !!binary | # yaml parser should autodecode it
              NDIxZTA4ZDkxOTlkNTZlMGIwYjc2NDQzZDUyZmVmMTI=
      operations:
          - create_account:
              account: *joe
              starting_balance: "1000"
              signatures:
                  - *alice
  # you can create single op transactions faster using helpers:
  - create_account:
      account: *joe
      starting_balance: "1000"
      # you can extend it with `transaction` params
      memo:
          type: text
          value: hello
      signatures: [*alice]
  # you can use yaml's flow mappings for faster creation, this is equivalent to above.
  # no `signatures` means that it will autosign using source account key
  - create_account: {source: *alice, account: *joe, starting_balance: "1000"}
  # adding other helpers, like in `scc`, is also possible, this will create `set_options` op:
  - set_master_signer_weight: {source: *alice, weight: 100}
  - add_signer: {source: *alice, signer: *joe, weight: 20}
  # yaml anchors make a lot of sense if you want to create many similar txs, example
  # below sends multiple offers to a single market
  - template: &usd_eur_market
      # template command is ignored, used to build other commands only
      sell: {code: "USD", issuer: *alice}
      buy: {code: "EUR", issuer: *alice}
  - template: &passive_source
      passive: true # passive offer
      source: *joe_multiplexed
  - buy_offer:
      <<: *usd_eur_market # extends the offer template
      price: {n: 100, d: 200}
      amount: "1000"
  - buy_offer:
      <<: *usd_eur_market # extends the offer template
      price: {n: 100, d: 300}
      amount: "2000"
  - buy_offer:
      <<: [*usd_eur_market, *passive_source] # you can extend multiple templates
      price: {n: 100, d: 400}
      amount: "3000"
  # commands below are not building transactions but print information
  # about the current state of the ledger or history, useful in playgrounds,
  # can be ignored in headless.
  - print_market: *usd_eur_market
  - print_account: *alice
  - print_transactions: *alice
```

## Design Rationale

### Why YAML?

YAML was selected due to multiple reasons:
* YAML has a minimal syntax so it's very expresive and easy to read. Because of this it should be possible for non-programmmers to use in playgrounds.
* YAML parsers exist for all major programming languages so it's easy to build interpreters as opossed to a new DSL that would require writing a custom parser.
* YAML anchors and merges allow easy extension of common values to create multiple similar transactions, operations and accounts, ex. create multiple offers for a single market. See examples above.
* YAML flow mappings allow one-liner commands. See examples above.
* YAML type tags allow easy transformation from base64 encoding to binary. See examples above.
* YAML syntax allows adding inline comments that will help understand recipe files.

### Why not scc?

* Ruby (and minimal knowledge of it) is required to run `scc`.
* It's possible to include arbitrary Ruby code inside a recipe file what can cause security implications when used in playgrounds.

### Why not txrep ([SEP-0011](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0011.md))?

* txrep is designed to represent a single transaction not a set of transactions.
* txrep is very explicit, thus hard to use.
* Requires understanding XDR definitions of transactions and operations.

## Security Concerns

N/A.
