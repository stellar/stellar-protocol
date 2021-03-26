## Preamble

```
CAP: To Be Assigned
Title: Automated Market Makers
Working Group:
    Owner: Nicolas Barry <nicolas@stellar.org>
    Authors: OrbitLens <orbit@stellar.expert>
    Consulted: Jon Jove <jon@stellar.org>, Nikhil Saraf<nikhil@stellar.org>, Phil Meng <phil@stellar.org>, Leigh McCulloch <leigh@stellar.org>, Tomer Weller <tomer@stellar.org> 
Status: Draft
Created: 2021-03-03
Discussion: https://groups.google.com/g/stellar-dev/c/Ofb2KXwzva0/m/LLcUKWFmBwAJ
Protocol version: TBD
```

## Simple Summary

This proposal introduces liquidity pools and automated market makers on the
protocol level. AMMs rely on a mathematical formula to quote asset prices. A
liquidity pool is a ledger entry that contains funds deposited by users
(liquidity providers). In return for providing liquidity to the protocol, users
earn fees from trades. The described approach of the interleaved order execution
combines the liquidity of existing orderbooks with liquidity pools.

## Motivation

Orderbooks market-making (especially on-chain) may be quite tricky. It requires
trading bots that constantly track external asset prices and adjust on-chain
orders accordingly. In turn, this process results in endless offer adjustments
which clog ledger history.

Market makers need to provision liquidity and maintain inventories. For a few
trading pairs it is more or less straightforward but the ecosystem expansion
brings new assets, new trading pairs. Consequently, inventory requirements
increase, as well as the number of operations required to maintain positions on
all orderbooks.

On the other hand, automated market makers provide natural incentives for
liquidity crowdsourcing, making it much easier for ordinary users to participate
in the process while gaining interest on their long-term holdings.

Asset issuers don't need to wait until the token attracts a critical mass of
users. They can start making several trading pairs with a newly issued asset by
merely depositing tokens to the pool or engaging community users to provision
liquidity. This will certainly simplify the process of starting a new project on
Stellar, as well as provide a powerful marketing flywheel for early-stage
tokens.

The AMM concept implies that no third-party company holds user funds at any
point, and the algorithm itself doesn't rely on external data. Therefore,
potential regulatory risks are limited compared to the classic exchange design.

Liquidity pools don't store any complex information, don't require regular
position price adjustments, and work completely deterministically. From the
perspective of the on-chain execution, those characteristics offer much better
scalability compared to the existing DEX.

Proposed interleaved order execution on both the orderbook and liquidity pool
provides a familiar exchange experience in combination with the ability to have
on-chain limit orders. On the other hand, it fully incorporates all benefits of
shared liquidity pools, at the same time hiding the underlying technical details
from end-users. Users always get the best possible exchange price based on the
combined liquidity.

## Abstract

This proposal brings the concept of shared liquidity pools with automated market
making to the protocol. Users deposit funds to a pool providing liquidity to the
automated market maker execution engine which can quote asset prices based on an
algorithm that derives the price directly from the amounts of tokens deposited
to the pool.

Pool fees charged on every executed trade are accumulated in the pool,
increasing its liquidity. A user can withdraw the pool stake plus proportional
accrued interest from the pool. Collected interest incentivizes users to deposit
their funds to the pool, participating in the collective liquidity allocation.

## Specification

- New ledger entries `LiquidityPoolEntry` and `LiquidityStakeEntry`
- New operations `DepositPoolLiquidityOp` and `WithdrawPoolLiquidityOp`
- `LedgerHeader` extended with new settings
- Semantic altered for existing operations `ManageSellOfferOp`,
  `ManageBuyOfferOp`, `CreatePassiveSellOfferOp`, `PathPaymentStrictReceiveOp`,
  `PathPaymentStrictSendOp`

### XDR changes

```diff
--- a/src/xdr/Stellar-ledger-entries.x
+++ b/src/xdr/Stellar-ledger-entries.x
@@ -403,6 +403,43 @@ struct ClaimableBalanceEntry
     ext;
 };
 
+/* Contains information about current balances of the liquidity pool*/
+struct LiquidityPoolEntry
+{
+    uint32 poolID;  // pool invariant identifier
+    Asset assetA;   // asset A of the liquidity pool
+    Asset assetB;   // asset B of the liquidity pool
+    int64 amountA;  // current amount of asset A in the pool
+    int64 amountB;  // current amount of asset B in the pool
+    int64 stakes;   // total number of pool shares owned by the account
+
+    // reserved for future use
+    union switch (int v)
+    {
+    case 0:
+        void;
+    }
+    ext;
+};
+
+/* Represents information about the account stake in the pool */
+struct LiquidityStakeEntry
+{
+    AccountID accountID; // account this liquidity stake belongs to
+    uint32 poolID;       // pool invariant identifier
+    Asset assetA;        // asset A of the liquidity pool
+    Asset assetB;        // asset B of the liquidity pool
+    int64 stake;         // share of the pool that belongs to the account
+
+    // reserved for future use
+    union switch (int v)
+    {
+    case 0:
+        void;
+    }
+    ext;
+};
+

@@ -431,6 +468,10 @@ struct LedgerEntry
         DataEntry data;
     case CLAIMABLE_BALANCE:
         ClaimableBalanceEntry claimableBalance;
+    case LIQUIDITY_POOL:
+        LiquidityPoolEntry LiquidityPool;
+    case LIQUIDITY_STAKE:
+        LiquidityStakeEntry LiquidityStake;
     }
     data;
 
@@ -479,6 +520,29 @@ case CLAIMABLE_BALANCE:
     {
         ClaimableBalanceID balanceID;
     } claimableBalance;
+
+case CLAIMABLE_BALANCE:
+    struct
+    {
+        ClaimableBalanceID balanceID;
+    } claimableBalance;
+	
+case LIQUIDITY_POOL:
+	struct
+    {
+		uint32 poolID;
+        Asset assetA;
+        Asset assetB;
+    } LiquidityPool;
+	
+case LIQUIDITY_STAKE:
+	struct
+    {
+		uint32 poolID;
+        AccountID accountID;
+        Asset assetA;
+        Asset assetB;
+    } LiquidityStake;
 };
```

```diff
--- a/src/xdr/Stellar-transaction.x
+++ b/src/xdr/Stellar-transaction.x
@@ -48,7 +48,9 @@ enum OperationType
     END_SPONSORING_FUTURE_RESERVES = 17,
     REVOKE_SPONSORSHIP = 18,
     CLAWBACK = 19,
-    CLAWBACK_CLAIMABLE_BALANCE = 20
+    CLAWBACK_CLAIMABLE_BALANCE = 20,
+    DEPOSIT_POOL_LIQUIDITY = 21,
+    WITHDRAW_POOL_LIQUIDITY = 22
 };
 
@@ -390,6 +392,38 @@ 
 
+/* Deposits funds to the liquidity pool
+
+    Threshold: med
+
+    Result: DepositPoolLiquidityResult
+*/
+struct DepositPoolLiquidityOp
+{
+    uint32 poolID;    // pool invariant identifier
+    Asset assetA;     // asset A of the liquidity pool
+    Asset assetB;     // asset B of the liquidity pool
+    int64 maxAmountA; // maximum amount of asset A a user willing to deposit
+    int64 maxAmountB; // maximum amount of asset B a user willing to deposit
+};
+
+/* Withdraws all funds that belong to the account from the liquidity pool
+
+    Threshold: med
+
+    Result: WithdrawPoolLiquidityResult
+*/
+struct WithdrawPoolLiquidityOp
+{
+    uint32 poolID; // pool invariant identifier
+    Asset assetA;  // asset A of the liquidity pool
+    Asset assetB;  // asset B of the liquidity pool
+};
+

@@ -1186,6 +1220,67 @@ 
 
+/******* DepositPoolLiquidity Result ********/
+
+enum DepositPoolLiquidityResultCode
+{
+    // codes considered as "success" for the operation
+    DEPOSIT_SUCCESS = 0,
+    // codes considered as "failure" for the operation
+    DEPOSIT_MALFORMED = -1,     // bad input
+    DEPOSIT_NO_ISSUER = -2,     // could not find the issuer of one of the assets
+    DEPOSIT_POOL_NOT_ALLOWED = -3, // invalid pool assets combination
+    DEPOSIT_INSUFFICIENT_AMOUNT = -4, // not enough funds for a deposit
+    DEPOSIT_ALREADY_EXISTS = -5, // account has a stake in the pool already
+    DEPOSIT_LOW_RESERVE =  -6 // not enough funds
+};
+
+struct DepositPoolLiquiditySuccessResult
+{
+    // liquidity pool stake that has been created
+    LiquidityStakeEntry stake;
+};
+
+union DepositPoolLiquidityResult switch (
+    DepositPoolLiquidityResultCode code)
+{
+case DEPOSIT_SUCCESS:
+    DepositPoolLiquiditySuccessResult success;
+default:
+    void;
+};
+
+/******* WithdrawPoolLiquidity Result ********/
+
+enum WithdrawPoolLiquidityResultCode
+{
+    // codes considered as "success" for the operation
+    WITHDRAW_STAKE_SUCCESS = 0,
+    // codes considered as "failure" for the operation
+    WITHDRAW_STAKE_MALFORMED = -1,    // bad input
+    WITHDRAW_STAKE_NOT_FOUND = -2,    // account doesn't have a stake in the pool    
+    WITHDRAW_STAKE_NO_TRUSTLINE = -3, // account does not have an established and authorized trustline for one of the assets    
+    WITHDRAW_STAKE_TOO_EARLY = -4     // an attempt to withdraw funds beforethe lockup period ends
+};
+
+struct WithdrawPoolLiquiditySuccessResult
+{
+    int32 poolID;   // pool invariant identifier
+    Asset assetA;   // asset A of the liquidity pool
+    Asset assetB;   // asset B of the liquidity pool
+    int64 amountA;  // amount of asset A withdrawn from the pool
+    int64 amountB;  // amount of asset B withdrawn from the pool
+    int64 stake;    // pool share that has been redeemed
+};
+
+union WithdrawPoolLiquidityResult switch (
+    WithdrawPoolLiquidityResultCode code)
+{
+case WITHDRAW_STAKE_SUCCESS:
+    WithdrawPoolLiquiditySuccessResult success;
+default:
+    void;
+};
+
```

```diff
--- a/src/xdr/Stellar-ledger.x
+++ b/src/xdr/Stellar-ledger.x
@@ -84,6 +84,8 @@ struct LedgerHeader
     {
     case 0:
         void;
+    case 1:
+        uint32 liquidtyPoolYield; // fee charged by liquidity pools on each trade in permile (‰)    
     }
     ext;
 };
```

## Semantics

Modified semantics of trading-related operations presented in this CAP allows to
drastically reduce the number of new interaction flows. Liquidity from the pools
will be immediately available for existing Stellar applications through the
convenient offers and path payment interface operations.

In this section, a constant product invariant (`x*y=k`) is used for all
calculations. Other invariants can be implemented as separate pools with
different price quotation formulas and execution conditions.

#### DepositPoolLiquidityOp

`DepositPoolLiquidityOp` operation transfers user funds to the selected
liquidity pool defined as `LiquidityPoolEntry`.

- Before processing a deposit, a lookup of issuer accounts for `assetA` and
  `assetB` is performed. If an asset is not a native asset and the issuer
  account does not exist, `DEPOSIT_NO_ISSUER` error is returned.
- Basic validation is needed to ensure that a given combination of assets is
  allowed. For example, the situation when `assetA`=`assetB` should result in
  `DEPOSIT_POOL_NOT_ALLOWED` error. This version of the proposal doesn't imply
  any other restrictions, but this may change in the future.
- The node performs a lookup of a `LiquidityStakeEntry` by operation source
  account, `poolID`, `assetA`, and `assetB`. If corresponding
  `LiquidityStakeEntry` was found, `DEPOSIT_ALREADY_EXISTS` error is returned.
- The node loads source account balances for `assetA`, `assetB`. If any of the
  balances do not exist, `DEPOSIT_INSUFFICIENT_AMOUNT` error returned.
- The actual deposit amount is calculated based on the current liquidity pool
  price from `maxAmountA` and `maxAmountB`. The current price can be determined
  as `P=Ap/Bp` where `Ap` and `Bp` - correspondingly amount of token A and token
  B currently deposited to the pool. Maximum effective amount that can be
  deposited to the pool `Bdm=Ad/P` and `Adm=Bd*P` where
  `Ad=min(maxAmountA,accountBalanceA)`, `Bd=min(maxAmountB,accountBalanceB)`,
  `Bdm` and `Adm` – maximum effective amounts of tokens A and B that can be
  deposited to the pool. If the actual deposited amount of any token equals
  zero, `DEPOSIT_INSUFFICIENT_AMOUNT` error returned. In case if `maxAmountA` or
  `maxAmountB` provided in the operation equals zero, the node takes the value
  from the matching source account balance entry.
- Stake weights are calculated as `S=A*B*Sp/(Ap*Bp)` where `S` - share of the
  pool an account obtains after the deposit, `A` and `B` - actual amount of
  tokens to deposit, `Sp` - total stakes currently in the pool (the value from
  the `LiquidityPoolEntry`), `Ap` and `Bp` - correspondingly amount of token A
  and B currently deposited to the pool. If `S`=0 (this can be the case with a
  very small stake or as a result of rounding approximation), the node returns
  `DEPOSIT_INSUFFICIENT_AMOUNT`. If the native asset balance does not satisfy
  the basic reserve requirement, `DEPOSIT_LOW_RESERVE` error returned.
- If `LiquidityPoolEntry` does not exist on-chain (this is the first deposit) it
  is automatically created. The stake weight for the deposit, in this case, is
  calculated as `S=min(A,B)`.
- The node creates `LiquidityStakeEntry` with `stake`=`S`.
- `numsubEntries` for the source account incremented.
- The node modifies `LiquidityPoolEntry` setting `amountA`+=`A`, `amountB`+=`B`,
  `stakes`+=`S`.
- `DEPOSIT_SUCCESS` code returned.

#### WithdrawPoolLiquidityOp

`WithdrawPoolLiquidityOp` operation withdraws funds from a liquidity pool
proportionally to the account stake size.

- The node performs a lookup of a `LiquidityStakeEntry` by operation source
  account, `poolID`, `assetA`, and `assetB`. If
  corresponding `LiquidityStakeEntry` was not found,
  `WITHDRAW_STAKE_NOT_FOUND` error is returned.
- The node loads the liquidity pool information.
- The amount of tokens to withdraw is computed as `Kw=S*Ap*Bp/Sp` where `Kw` -
  the constant product of the assets to withdraw, `S` - share of the account in
  the pool from the `LiquidityStakeEntry`, `Sp` - total number of pool shares
  from `LiquidityPoolEntry`, `Ap` and `Bp` - current token amount of **asset A**
  and **asset B** in the pool respectively. Current pool price is `P=Ap/Bp`.
- The amounts of assets to withdraw calculated as
  `A=√(Kw*P)=Ap√(S/Sp)`
  `B=√(Kw/P)=Bp√(S/Sp)`
- If the `LiquidityStakeEntry` has been created after `now() - 24hours`,
  `WITHDRAW_STAKE_TOO_EARLY` error returned.
- Trustlines info loaded for `assetA` and `assetB`. If the source account does
  not have a trustline for one of the assets, the trustline is not authorized,
  or a trustline limit prevents the transfer,
  `WITHDRAW_STAKE_NO_TRUSTLINE` error returned.
- `numSubEntries` for the source account decremented.
- `LiquidityPoolEntry` updated: `amountA`-=`A`, `amountB`-=`B`, `stakes`-=`S`.
- Withdrawn funds get transferred to the source account balances.
- `LiquidityStakeEntry` removed.
- `WITHDRAW_STAKE_SUCCESS` code returned.

To deal with disambiguation and simplify the aggregation process, `assetA` and
`assetB` in `LiquidityPoolEntry` and `LiquidityStakeEntry` should always be
sorted in alphabetical order upon insertion. The comparator function takes into
account the asset type, asset code, and asset issuer address respectively.

#### LedgerHeader changes

Ledger header contains new fields that can be adjusted by validators during the
voting process.

`liquidtyPoolYield` represents the fee charged by a liquidity pool on each trade
in permile (‰), so the `poolFeeCharged=tradeAmount*liquidtyPoolYield/1000`

#### Semantic changes for existing operations

Behavior updated for `ManageSellOfferOp`, `ManageBuyOfferOp`,
`CreatePassiveSellOfferOp`, `PathPaymentStrictReceiveOp`,
`PathPaymentStrictSendOp` operations.

When a new (taker) order arrives, the DEX engine loads the current state of all
liquidity pools for the traded asset pair, fetches available cross orders
(maker orders) from the orderbook, and iterates through the fetched orders.

On every step, it checks whether the next maker order crosses the price of the
taker order. Before maker order execution the engine estimates the number of
tokens that can be traded on each liquidity pool for the same trading pair up to
the price of the current maker order.

The maximum amount of tokens A to be bought from the pool can be expressed as
`Aq=Ap-Bp*(1+F)/P` where `F` - trading pool fee, `P` - maximum price (equals
currently processed maker order price in this case), `Ap` and `Bp` - current
amounts of **asset A* and **asset B** in the pool respectively.

If `Aq>0`, the corresponding amount of tokens is deducted from the pool and
added to the variable accumulating the total amount traded on the pool.

After that, the current order itself is matched to the remaining taker order
amount, and so on, up to the point when a taker order is executed in full. If
the outstanding amount can't be executed on the orderbook nor the pool, a new
order with the remaining amount is created on the orderbook.

In the end pool settlement occurs – traded **asset A** tokens are deducted from
the pool and added to the account balance, a matching amount of **asset B**
transferred from the account balance to the pool.

A trade against a pool generates a `ClaimOfferAtom` result with `sellerID` and
`offerID` equal to zero.

## Design Rationale

#### Orderbook+AMM Execution

Basic liquidity pools implementation separately from the existing DEX has
several shortcomings:

- The new AMM interface requires new trading operations. In addition to the
  existing `ManageSellOfferOp` and `ManageBuyOfferOp`, it also requires
  something like `SwapSellOp` and `SwapBuyOp` for the interaction with AMM.
  Another two operations required for path payments:
  `SwapPathPaymentStrictReceiveOp` and `SwapPathPaymentStrictSendOp`.
- While having separate DEX and orderbook looks like a simpler solution, in
  reality, it results in significantly larger codebase changes (more operations
  and more use-cases to handle), a lot of work on the Horizon side, and much
  more effort from the ecosystem developers.
- The trading process becomes confusing for regular users. What's the difference
  between an order and a swap? How to get the best rate?  
  Of course, sooner or later wallets and exchange interfaces should come to the
  rescue, providing hints in the interface and maybe even aggregating
  information across the liquidity pool and orderbook for a given assets pair to
  ensure the best possible exchange price. That's feasible, but not very
  user-friendly and may lead to confusion.
- Fragmented liquidity means that for any trade or path payment larger than
  several dollars a wallet needs to perform several trades (against the
  orderbook and liquidity pools) in order to deliver an adequate price to a
  user, increasing the number of transactions necessary for a swap. In the case
  of path payments, users will have to choose whether they want operation
  atomicity with inferior price (due to the path payment tapping either into a
  liquidity pool or an orderbook) or get a better price while sacrificing the
  atomicity.
- The long-existing problem of bots spamming the ledger while competing for
  arbitrage opportunities substantially widens because independent AMMs rely on
  arbitrage actors that rebalance pools if the price on the AMM floats too far
  from global market prices. This presents much more profitable opportunities
  than doing circular path payments for several ordebook trading pairs. Given
  the limited capacity of the ledger, this will lead to the whole network
  paralysis once the competition between several arbitrage bots and market
  makers inflate transaction fees to the sky. Most of the time, it will be
  impossible to execute a simple payment because the whole ledger capacity will
  be flooded with arbitrage transactions sent in response to any DEX offer
  update from market makers.

Advantages of the proposed approach:

- Users always receive the best possible price as the trade is executed against
  the entire liquidity available for the certain trading pair.
- The orderbook and liquidity pool always remain in the balanced state which
  means there are no arbitrage opportunities between the pool and orderbook. The
  trading engine automatically conducts arbitrage rebalancing on each trade
  under the hood, eliminating the need for external arbitrage actors.
- There are no reasonable use-cases that require trading exclusively on the
  pool. Price manipulations is probably the only applicable example of pool-only
  swaps.
- Smaller attack surface since there is no way to trade on pool directly. This
  also automatically prevents attacks based on the imbalanced oracle state and
  significantly increases the cost of intentional price manipulations as the
  attacker has to trade against the entire aggregated liquidity on the given
  asset pair.
- Better developer experience and interoperability between assets and products.
  Keeping things simple allows to avoid developer mistakes, and streamline the
  experience.
- Immediate availability of liquidity pools for existing applications without
  the need to upgrade the codebase.
- It's fairly easy to add new pool-specific swap operations in the future if
  such a necessity emerges. At the same time, deprecating swap operations in
  favor of the interleaved orderbook+AMM execution looks fairly more complex.

#### Deposit/Withdraw Semantics

`DepositPoolLiquidityOp` and `WithdrawPoolLiquidityOp` operations have
intentionally simplified interfaces. `WithdrawPoolLiquidityOp` removes all
liquidity from the given pool supplied by the account. This makes partial funds
withdrawal somewhat difficult because a client will need to remove all the
liquidity and then call the `DepositPoolLiquidityOp` to return the desired
portion back to the pool. But this makes the overall process much more reliable,
especially under the price fluctuation conditions. Both operations can be
executed in the same transaction, so overall it looks like the best option.

Proposed enforcement of the minimal pool deposit retention time results in a
more predictable liquidity allocation and helps to avoid frequent switching
between pools from users willing to maximize profits by providing liquidity only
to the most active markets.

#### Other Pool Invariants Support

The `poolID` identifier present in new operations and ledger entries provides
the way to use more than one pool per trading pair, with different price
quotation functions and execution parameters.

## Protocol Upgrade Transition

### Backwards Incompatibilities

Proposed changes do not affect existing ledger entries. Updated trading
operations semantics are consistent with the current implementation and do not
require any updates on the client side.

This CAP should not cause a breaking change in existing implementations.

### Resource Utilization

The price quotation on the liquidity pool adds additional CPU workload in the
trading process. However, this may be compensated by the fewer orderbook orders
matched.

Utilized constant product formula may require 128-bit number computations which
may be significantly slower than 64-bit arithmetics. This potentially can be
addressed by modifying ledger entries to store values derived from asset
balances in the pool (`L=√(A*B)` and `√P=√(B/A)`).

Every `LiquidityPoolEntry` requires storage space on the ledger but unlike
`LiquidityStakeEntry` it is not backed by the account base reserve.

## Security Concerns

TBD