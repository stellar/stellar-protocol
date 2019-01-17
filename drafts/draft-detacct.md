

## Preamble

```
CAP: <to be assigned>
Title: Deterministic accounts and creatorTxID
Author: David Mazières
Status: Draft
Created: 2019-01-17
Discussion: https://groups.google.com/forum/#!forum/stellar-dev
Protocol version: TBD
```

## Simple Summary

Allow an accounts to be created with deterministic sequence numbers
and proofs of the creating transaction.

## Abstract

Allow a new type of account to be created whose name is a
deterministic function of the source account and sequence number of
the creating transaction and whose sequence numbers are deterministic.
Such deterministic accounts also contain a creation time and the
transaction id of the creating account, allowing transactions to
verify that an account was created at least some time in the past and
that it was created by a specific account.

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
allowing the current transaction to add signers and otherwise
manipulate options on the account.

~~~ {.c}
enum OperationType
{
    /* ... */
    BUMP_SEQUENCE = 11,
    CREATE_DET_ACCOUNT = 12,
    CHECK_ACCOUNT = 13
};

struct Operation
{
    AccountID* sourceAccount;

    union switch (OperationType type) {
    case CREATE_ACCOUNT:
    case CREATE_DET_ACCOUNT:
        CreateAccountOp createAccountOp;

    case CHECK_ACCOUNT:
        CheckAccountOp checkAccount;

    /* ... */

    } body;
};
~~~

XXX - maybe use a different `CreateDetAccountOp` argument that also
allows additional signers to be specified, so people do not forget to
do this?

### Modifications to `AccountID`

There are now two account types, depending on how the account was
created.  To simplify the XDR, we also propose merging the public key,
account type, and signer type constants into a single `enum`, since it
will be convenient to keep the constants distinct.

~~~ {.c}
enum AccountOrSigner {
    // A Key can name a signer or an account (or both)
    KEY_ED25519 = 0,

    // These specifiers can only designate signers
    SIGNER_PRE_AUTH_TX = 1,
    SIGNER_HASH_X = 2,

    // These specifiers can only designate accounts
    ACCT_DETERMINISTIC = 3,    // The other kind of primary ID
};

union AccountID switch (AccountOrSigner type) {
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

### Changes to `AccountEntry`

Each account created with `CREATE_DET_ACCOUNT` contains two extra
pieces of information:

* The transaction ID of the transaction that created the account (a
  hash of `TransactionSignaturePayload` for that transaction), and

* The creation time of the account (`closeTime` from the ledger in
  which the creation transaction ran).

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
            Liabilities liabilities;
            Hash creationTxID;
            uint64 creationTime;

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

### `CHECK_ACCOUNT`

A new `CHECK_ACCOUNT` operation has no side effects, but is invalid if
the source account does not exist or does not meet certain criteria.
The `CHECK_ACCOUNT` operation does not require a signature from the
operation's source account.

~~~ {.c}
enum AccountConditionType {
    ACC_MIN_AGE = 1,
    ACC_CREATOR = 2,
    ACC_MIN_SEQNO = 3,
    ACC_MAX_SEQNO = 4
};
struct AccountCondition switch (AccountConditionType type) {
  case ACC_AGE_MIN:
    uint64 ageMin;
  case ACCT_CREATOR:
    // Invalid unless this matches the source account creationTxID
    Hash creationTxID;
  case ACC_SEQ_MIN:
    // Invalid if source account's sequence number is less than this
    SequenceNumber seqMin;
  case ACC_SEQ_MAX:
    // Invalid unless source account's sequence number is less than this
    SequenceNumber seqMax;
};

typedef AccountConditionType CheckAccountOp<2>;
~~~

Note that `CHECK_ACCOUNT` affects the validity of a transaction, but
does not make the transaction fail, as a currently invalid transaction
may be valid at a later point.  If transaction $C$ refers to
transaction $P$ using an `ACC_SEQ_MIN` condition, and $C$'s sequence
number is one less than `seqMin`, then any extra fees in $C$ can
contribute to executing $P$ if $P$ does not have a sufficient `fee`.
This solves the problem of insufficient fees on a transaction that
cannot be resigned.

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
