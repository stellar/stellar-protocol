## Preamble

```
CAP: To Be Assigned
Title: Host Functions for BLS12-381 curve operations
Working Group: 
    Owner: <Person accountable for the CAP - name/email address/github alias>
    Authors: <List of comma separated name/email address/github alias>
    Consulted: <List of comma separated name/email address/github alias>
Status: Draft
Created: 2024-01-05
Discussion: https://github.com/stellar/rs-soroban-env/issues/779
Protocol version: TBD
```

## Simple Summary
Add support for the BLS12-381 elliptical curve to enable zero knowledge proof systems.

## Working Group

This section describes the composition of the working group.

## Motivation
BLS12-381 host functions allow for cryptographic operations in the Soroban execution environment that are otherwise prohibitively expensive. It enables a variety of applications including confidentiality preserving systems, BLS signature schemes, and multiple types of scaling solutions. Pairing-friendly elliptic curves are needed for such systems and BLS12-381 is the state of the art in secure elliptical curves. 

### Goals Alignment
You should reference the Stellar Network goal(s) that this proposal advances, such as:
* The Stellar Network should run at scale and at low cost to all participants of the network.
* The Stellar Network should enable cross-border payments.

## Abstract
Add host functions that enable arithmetic, pairing, and mapping operations for points on the BLS12-381 curve. 

## Specification


### XDR changes

TBD

### Semantics
This section includes subsections, one for each logical change included in the XDR changes,
that describes how each new or changed type functions and is used, and for new operations
a step-by-step description of what happens when the operation is executed.

## Design Rationale
The rationale fleshes out the specification by describing what motivated the design and why
particular design decisions were made. It should describe alternate designs that were considered
and related work, e.g. how the feature is supported in other protocols. The rationale may also
provide evidence of consensus within the community, and should discuss important objections or
concerns raised during discussion.

## Protocol Upgrade Transition
Typically CAPs have a direct impact on core that should be well understood,
and indirect impact on other systems in the ecosystem (Horizon, SDKs,
application, etc).

The following sections look at common challenges associated with those
protocol transitions.

### Backwards Incompatibilities
All CAPs that introduce backwards incompatibilities must include a section describing these
incompatibilities and their severity.

The CAP must propose how to deal with these incompatibilities, potentially pointing to other standard documents that complements the CAP (for example SEPs).

CAP submissions with an insufficient discussion of backwards compatibility
may be rejected outright.

### Resource Utilization
Reasonable effort should be made to understand the impact of the CAP on
resource utilization like CPU, memory, network bandwidth and disk/database.

## Security Concerns
All CAPs should carefully consider areas where security may be a concern, and document them
accordingly. If a change does not have security implications, briefly explain why.

## Test Cases
Test cases for an implementation are mandatory for CAPs that are affecting consensus changes. Other
CAPs can choose to include links to test cases if applicable.

## Implementation
The implementation(s) must be completed before any CAP is given "Final" status, but it need not be
completed before the CAP is accepted. While there is merit to the approach of reaching consensus on
the specification and rationale before writing code, the principle of "rough consensus and running
code" is still useful when it comes to resolving many discussions of API details.

[stellar-core repository]: https://github.com/stellar/stellar-core
