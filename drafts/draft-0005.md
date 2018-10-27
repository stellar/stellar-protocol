## Preamble

```
SEP: <to be assigned>
Title: Data Entry Namespaces
Author: Mister.Ticot <mister.ticot@cosmic.plus>
Status: Draft
Created: 2018-10-26
```

## Simple Summary

Defines a standard syntax to represent namespaces in data entries.

## Abstract

This SEP provides a standard way to represent
[namespaces](https://en.wikipedia.org/wiki/Namespace) into Stellar accounts
data entries, and provides guideline about how to parse them and to handle
edge cases.

## Motivation

As a generic mechanism to store key/value pairs on the ledger, data entries 
accept a very wide range of use cases. If each actor use it following its own 
syntax, it will lead to a confusing experience and ultimatelly to naming 
conflicts.

Introducing namespaces allow to hierarchize and organize data, in such a way 
that sorting the key/value entries will result in a readable output even when 
using them for various purpose on the same account. It also helps to prevent
name clash.

The present SEP ensure that all other SEP that will use data entries will do so 
in a consistent way. It provides guidelines ontop of which generic tool to 
handle data entries can be created.

## Specification

Namespace hierarchy is encoded in the key using one or more terms separated by 
dots. Terms are made of lowcase letters, undescore and numbers and musn't start
with a number.

**Examples**

```
conf.two_factor
conf.multisig.server
conf.multisig.network
conf.multisig.key
profile.name
profile.language
wallet.btc
wallet.eth
```

* **Term REGEXP:** `[_a-z][_a-z0-9]*`
* **Key REGEXP:** `[_a-z][_a-z0-9]*(\.[_a-z][_a-z0-9]*)*`

When parsing the data tree in a given programming language, keys that doesn't 
respect this syntax must be ignored and valid entries must be hierarchized in 
an adequate data structure. If a term is used both as an identifier and a 
namespace, a warning must be thrown by the parser and the identifier value must 
be ignored.


**Example: same data tree in JSON**

```js
{
  conf: {
    two_factor: ...,
    multisig: {
      server: ...,
      network: ...,
      key: ...
    }
  },
  profile: {
    name: ...,
    language: ...
  },
  wallet: {
    btc: ...,
    eth: ...
  }
}
```


## Rationale

**Syntax**

The namespace syntax had to be familiar, and terms have to be written in a way
that is valid accross a broad range of programming languages.

This protocol uses JavaScript syntax because it is the language the most 
developers uses. It is also familiar to anybody using JSON, which is a format 
widely used to pass data, and the one already used by horizon API.

Parsing the data tree must lead to the same namespace/key/value structure 
regardless of the programming language being used. This is the reason why term 
syntax must be restricted, as any unusual character could lead to errors in 
this or that language. The lowcase restiction is meant to prevent a different 
data tree interpretation between case-sensitive and case-insensitive languages.

Forbidding the use of numbers and/or undescore is advisable if it appears that 
they prevent the data tree to be properly parsed in any well known programming 
language.

**Identifier/namespace conflict**

This conflict arise when a term is used both as an identifier and a namespace, 
such as: 

```
config.multisig = 1234
config.multisig.server = https://myserver.org
```

This kind of situation is hard/impossible to translate into a data structure in
most programming languages.

There are three ways to solve it:

* Ignore all related definitions
* Ignore the identifier definition
* Ignore the definitions under that namespace

While no solution is ideal, the last one seems better as at least it prevents
the shortcutting of a whole branch.

## Backwards Compatibility

This SEP doesn't introduce incompatibilities: the keys that are not formatted
following the defined syntax rules are simply not considered as part of the
data tree, and they are still accessible as account data entries.

This SEP leverage the fact that it permits the introduction of convenient 
standard utilities to manage the data entries tree, which will provide incentive
to comply with the proposed semantic.
