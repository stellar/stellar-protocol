## Preamble

```
CAP: TBD
Title: Separate TTL host functions for contract instance and contract code
Working Group:
    Owner: Anup Pani <@anupsdf>
    Authors: Tommaso De Ponti @heytdep
    Consulted: Leigh McCulloch <@leighmcculloch>, Dmytro Kozhevin <@dmkozh>
Status: Draft
Created: 2023-03-06
Discussion: TBD
Protocol version: TBD
```

## Simple Summary

Allow extending the Time To Live (TTL) for contract instance and contract code with separate Soroban smart contract host functions.

## Working Group

This change was authored by Tommaso De Ponti, with input from the consulted individuals mentioned at the top of this document.

#### Semantic protocol changes

Adding two Soroban smart contract host functions.

## Motivation

Currently, Soroban smart contract system has a host function, extend_contract_instance_and_code_ttl_from_contract_id, that extends the [TTL](cap-0046-12.md) of both contract instance and contract code ledger entries by the same amount. In decentralized contracts, the contract can extend its own lifetime from within the code with certain thresholds with the idea that the cost is distributed among users. 

Extending the TTL for contract code entries are very expensive due to the large binary sizes that occupy the ledger. There are numerous situations where a contract code entry is referenced by multiple contract instances. Thus allowing to extend them separately would enable implementing a more efficient lifetime extension logic. 

For example, a liquidity pool contract can be used by thousands of actively bumped contract instances. The contract instance of a single pool contract can be bumped by the users of that contract, but the contract code entry can be bumped by the users of all the pool contracts. So, when extending the lifetime of a contract instance, extending the lifetime of contract code separately and slightly less would make up for a better distribution of the fees across the network.

### Goals Alignment

This CAP is aligned with the following Stellar Network Goals:

  - The Stellar Network should make it easy for developers of Stellar projects to create highly
  usable products.

## Abstract

This CAP introduces these two new Soroban smart contract host functions to bump the TTL of contract code and instance:
1. extend_contract_instance_ttl to extend the contract instance's TTL
2. extend_contract_code_ttl to extend the contract code's TTL

## Specification

Two new functions `extend_contract_instance_ttl` and `extend_contract_code_ttl` with export name `c` and `d` are added to 
the Soroban environment's exported interface.

They both accept a contract, threshold, and extend_to as input arguments. The 
functions extend the TTL and don't return anything.

The `contract` parameter is an `AddressObject` that is the contract's address.

The `threshold` and `extend_to` parameters are `U32Val` type.

The `env.json` in `rs-soroban-env` will be modified as so:
```
{
    "export": "c",
    "name": "extend_contract_instance_ttl",
    "args": [
        {
            "name": "contract",
            "type": "AddressObject"
        },
        {
            "name": "threshold",
            "type": "U32Val"
        },
        {
            "name": "extend_to",
            "type": "U32Val"
        }
    ],
    "return": "Void",
    "docs": "If the TTL for the provided contract instance (if applicable) is below `threshold` ledgers, extend `live_until_ledger_seq` such that TTL == `extend_to`, where TTL is defined as live_until_ledger_seq - current ledger.",
    "min_supported_protocol": 21
},
{
    "export": "d",
    "name": "extend_contract_code_ttl",
    "args": [
        {
            "name": "contract",
            "type": "AddressObject"
        },
        {
            "name": "threshold",
            "type": "U32Val"
        },
        {
            "name": "extend_to",
            "type": "U32Val"
        }
    ],
    "return": "Void",
    "docs": "If the TTL for the provided contract code (if applicable) is below `threshold` ledgers, extend `live_until_ledger_seq` such that TTL == `extend_to`, where TTL is defined as live_until_ledger_seq - current ledger.",
    "min_supported_protocol": 21
}
```

### Semantics

## Design Rationale

## Protocol Upgrade Transition

### Backwards Incompatibilities

### Resource Utilization

## Security Concerns

## Test Cases

Unit tests will have to be written to test the extension of TTL for contract code and instance.

## Implementation

The host functions and other changes need to be implemented in [rs-soroban-env](https://github.com/stellar/rs-soroban-env). There will be a corresponding change to [soroban-sdk](https://github.com/stellar/rs-soroban-sdk) repo as well.

Here is how the host functions will look like,
```rust
fn extend_contract_instance_ttl(
    &self,
    _vmcaller: &mut VmCaller<Self::VmUserState>,
    contract: AddressObject,
    threshold: U32Val,
    extend_to: U32Val,
) -> Result<Void, Self::Error> {
    let contract_id = self.contract_id_from_address(contract)?;
    let key = self.contract_instance_ledger_key(&contract_id)?;
    self.try_borrow_storage_mut()?
        .extend_ttl(
            self,
            key,
            threshold.into(),
            extend_to.into(),
        )
        .map_err(|e| self.decorate_contract_instance_storage_error(e, &contract_id))?;

    Ok(Val::VOID)
}

fn extend_contract_code_ttl(
    &self,
    _vmcaller: &mut VmCaller<Self::VmUserState>,
    contract: AddressObject,
    threshold: U32Val,
    extend_to: U32Val,
) -> Result<Void, Self::Error> {
    let contract_id = self.contract_id_from_address(contract)?;
    let key = self.contract_instance_ledger_key(&contract_id)?;

    match self
        .retrieve_contract_instance_from_storage(&key)?
        .executable
    {
        ContractExecutable::Wasm(wasm_hash) => {
            let key = self.contract_code_ledger_key(&wasm_hash)?;
            self.try_borrow_storage_mut()?
                .extend_ttl(self, key, threshold.into(), extend_to.into())
                .map_err(|e| self.decorate_contract_code_storage_error(e, &wasm_hash))?;
        }
        ContractExecutable::StellarAsset => {}
    }

    Ok(Val::VOID)
}
```