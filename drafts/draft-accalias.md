

## Preamble

```
CAP: <to be assigned>
Title: Deterministic accounts and account aliases
Author: David Mazières
Status: Draft
Created: 2018-12-06
Discussion: https://groups.google.com/forum/#!forum/stellar-dev
Protocol version: TBD
```

## Simple Summary

Allow an account to be referenced by multiple names.

## Abstract

Allow every account to be referenced by an alias consisting of the
hash of the transaction and operation ID that created the account.
Hence, the ability to use such an account alias prove something
happened.  Moreover, new deterministic accounts all start at a fixed
sequence number, so it is possible to sign transactions on them before
they are created.  Finally, conditional references to an account make
it possible to do something only a minimum time after an account was
created (providing relative timelocks).

## Motivation

The goal is to enable several usage patterns:

- Do something only if a specific transaction has executed.

- Sign transactions on an account that doesn't exist yet.

- Allow arbitrarily nested pre-auth transactions that create accounts
  that have pre-auth transactions that create accounts and so forth.

- If two operations in the same transaction both have such nested
  accounts with pre-auth transactions, the most deeply nested accounts
  resulting from the two operations should be able to reference each
  other's issued assets.

- Require that one disclose the intent to execute a transaction some
  minimum time before actually executing the transaction.

- Pay the fee for another transaction if the original transaction's
  fee is too low.

## Specification

### Deterministic accounts

There are now two ways to create an account:  the original
`CREATE_ACCOUNT` operation and a new `CREATE_DET_ACCOUNT` that creates
an account whose sequence number is deterministically initialized to
0x100000000 (2^{32}).  A deterministically-created account has the
current transaction automatically added as a pre-auth transaction,
allowing the current transaction to add signers.

~~~ {.c}
enum OperationType
{
    /* ... */
    BUMP_SEQUENCE = 11,
    CREATE_DET_ACCOUNT = 12
};

struct Operation
{
    AccountID* sourceAccount;

    union switch (OperationType type) {
    case CREATE_ACCOUNT:
    case CREATE_DET_ACCOUNT:
        CreateAccountOp createAccountOp;

    /* ... */

    } body;
};
~~~

XXX - maybe use a different `CreateDetAccountOp` argument that also
allows additional signers to be specified, so people do not forget to
do this?

### Differentiating `AccountPrimaryID` and `AccountID`

Every account is named by one primary ID, and can be named by multiple
alias account IDs.  The two types of primary ID correspond to the
original style of account, named by a public key, and the new type of
deterministic account, which is named by a hash of the creating
account, the sequence number of the creating transaction, and the
index of the `CREATE_DET_ACCOUNT` operation within that transaction's
`operations` array.

The primary ID is defined as follows:

~~~ {.c}
enum AccountOrSigner {
    // A Key can name a signer or an account (or both)
    KEY_ED25519 = 0,

    // These specifiers can only designate signers
    SIGNER_PRE_AUTH_TX = 1,
    SIGNER_HASH_X = 2,

    // These specifiers can only designate accounts
    ACCT_DETERMINISTIC = 3,    // The other kind of primary ID
    ACCT_TESTAMENT = 4,        // alias: opid of tx that created account
    ACCT_COND = 5              // alias: an account and validity criteria
};

union AccountPrimaryID switch (AccountOrSigner type) {
  case KEY_ED25519:
    uint256 ed25519;
  case ACCT_DETERMINISTIC:
    Hash det;                  // Hash of CreatorSeqPayload
};

struct CreatorSeqPayload {
    AccountPrimaryID account;  // Account that created an account
    SequenceNumber seqNum;     // Sequence number of tx creating account
    unsigned opIndex;          // Index of operation that created account
};
~~~

Each account created after this change also has a "testament" alias
that attests to the execution of the specific transaction that created
the account.  We use the notion of an operation ID or opid, which is a
hash of the txid of a transaction and an index into the transactions
`operations` array.  An account can now be specified either by it's
primary ID or the opid of the operation that created the account,
which is a testament to the creating transaction's proper execution:

~~~ {.c}
struct OperationIdPayload {
    Hash txid;         // Hash of TransactionSignaturePayload
    unsigned opIndex;  // Index of operation
};

union AccountSpec switch (AccountOrSigner type) {
  case KEY_ED25519:
    uint256 ed25519;
  case ACCOUNT_CREATOR_SEQ:
    Hash det;
  case ACCOUNT_TESTAMENT:
    Hash opid;
};
~~~

Any place we can use an `AccountId` (as opposed to an
`AccountPrimaryID`), we can also specify conditions on the account.
Hence, and `AccountId` is a superset of an `AccountSpec` that also
allows for conditions.  We initially define two types of conditions:
that the account's sequence number must be at least some value, or
that the account's age must be at least some number of seconds.

~~~ {.c}
enum AccountConditionType {
    ACC_MIN_SEQNO = 1,
    ACC_MIN_AGE = 2
};
struct AccountCondition switch (AccountConditionType type) {
  case ACC_SEQ_MIN:
    SequenceNumber seqMin;
  case ACC_AGE_MIN:
    uint64 ageMin;
};
struct ConditionalAccount {
    AccountSpec id;
    AccountCondition conditions<2>;
};

union AccountId switch (AccountOrSigner type) {
  case KEY_ED25519:
    uint256 ed25519;
  case ACCOUNT_CREATOR_SEQ:
    Hash det;
  case ACCOUNT_TESTAMENT:
    Hash opid;
  case COND_ACCOUNT:
    ConditionalAccount cond;
};
~~~

If transaction $C$ refers to transaction $P$ using an `ACC_SEQ_MIN`
condition, and $C$'s sequence number is one less than `seqMin`, then
any extra fees in $C$ can contribute to executing $P$ if $P$ does not
have a sufficient `fee`.

XXX - the fee stuff might be too expensive to implement, so should be
carefully considered.

### Changes to `AccountEntry`

We extent the `AccountEntry` structure to record the testament alias
and creation the creation time, by adding a new case to the extension
union:

~~~ {.c}
struct AccountEntry {
    /* ... */
    // reserved for future use
    union switch (int v)
    {
    /* ... */
    case 2:
        struct
        {
            Hash creationOpid;
            uint64 creationTime;
            Liabilities liabilities;

            union switch (int v)
            {
            case 0:
                void;
            }
            ext;
        } v2;
    }
    ext;
};

~~~

## Rationale

These mechanisms solve a bunch of issues that come up in the context
of payment channels.  Because there are competing proposals already
(CAP-0007 and CAP-0008), this document adopts the rationale of those
documents by reference unless and until the protocol working group
decides to move forward with account aliases.

## Backwards Compatibility

The data structures are all backwards compatible.  However, the author
suggests moving keys, account IDs and account aliases into a single
namespace, namely the `AccountOrSigner` enum.  There's nothing wrong
with having unions that don't allow every value in an enum.  By
contrast, it will get confusing if we use multiple enums and try to
keep all of their values in sync.

## Test Cases

None yet.

## Implementation

None yet.
