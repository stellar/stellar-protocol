## Preamble

```
CAP: To Be Assigned
Title: <CAP title>
Working Group:
    Owner: <Person accountable for the CAP - name/email address/github alias>
    Authors: <List of comma separated name/email address/github alias>
    Consulted: <List of comma separated name/email address/github alias>
Status: Draft
Created: <date created on, in ISO 8601 (yyyy-mm-dd) format>
Discussion: <link to where discussion for this CAP is taking place, typically the mailing list>
Protocol version: TBD
```

## Simple Summary
"If you can't explain it simply, you don't understand it well enough." Please provide a simplified
and layman-accessible explanation of the CAP.

## Working Group

This section describes the composition of the working group.

### Recommended structure

The recommended structure of the working group is based on the [RACI](https://en.wikipedia.org/wiki/Responsibility_assignment_matrix#Role_distinction) model.

The model contains the following roles:
  * Authors - ("Recommender" in RACI) group of people that author the CAP with the owner
  * Owner - ("Accountable" in RACI) the person that owns the CAP. This includes
    * signing off on any changes to the CAP and
    * moving the CAP through the [CAP process](core/README.md)
  * Consulted - list of people that need to be consulted and provide feedback
  * Informed - not explicitely listed, the developer mailing list allows for that.

### Example working group composition

#### Semantic protocol changes

Example:
  * adding or modifying operations
  * modifying the behavior of operations

The working group must include a representative set of
  * downstream systems developers (Horizon, block explorers, etc)
  * SDK developers (Go, Javascript, etc)

In some cases, application developers (or somebody representing their interest) can also be involved.

The motivation section should clearly show how the changes will be used end to end.

#### Ledger and historical subsystem changes

The working group must include a representative set of
  * downstream systems developers (Horizon, block explorers, etc)
  * node operators

The motivation section should articulate the positive impact on stakeholders (the "Protocol Upgrade Transition" section can focus on other aspects).

## Motivation
You should clearly explain why the existing protocol specification is inadequate to address the
problem that the CAP solves. In particular, CAP submissions without sufficient motivation may be
rejected outright.

### Goals Alignment
You should reference the Stellar Network goal(s) that this proposal advances, such as:
* The Stellar Network should run at scale and at low cost to all participants of the network.
* The Stellar Network should enable cross-border payments.

## Abstract
A short (~200 word) description of the technical issue being addressed.

## Specification
The technical specification should describe the syntax and semantics of any new feature.

### XDR changes
This section includes all changes to the XDR (`.x` files), presented as a "diff"
against the latest version of the protocol (or in some rare exception,
on top of a different CAP). Diffs should be generated against on the XDR in the
[stellar-core repository].

To generate diffs, use the `git diff` command.

To apply diffs, use the `git apply --reject --whitespace=fix` command.

For large changes, it may be beneficial to link to actual XDR files copied
in the relevant "contents" folder.

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
