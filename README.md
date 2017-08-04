Stellar Protocol
================

This repository contains **Core Advancement Proposals** (CAPs) and **Stellar Ecosystem Proposals** (SEPs). 
Similarly to [BIPs](https://github.com/bitcoin/bips) and [EIPs](https://github.com/ethereum/EIPs), CAPs and SEPs are the proposals of standards to improve Stellar protocol and related client APIs.

CAPs deal changes to the core protocol of the Stellar network. 

SEPs deal with changes to the standards, protocols, and methods used in the ecosystem built on top of the Stellar network. 

## Repository structure

The root directory of this repository contains:

* Accepted CAPs (`cpp-xxxx.md` where `xxxx` is a CAP number with leading zeros, ex. `cpp-0051.md`),
* `contents` directory with `cap-xxxx` subdirectories that contain all media/script files for a given CAP document.

Example repository structure in a future:
```
├── README.md
├── contents
│   ├── cap-0001
│   │   └── image.png
│   └── sep-0002
│       └── script.go
├── core
│   ├── cap-0001.md
|   ├── cap-0002.md
|   └── cap-0003.md
├── ecosystem
│   ├── sep-0001.md
|   ├── sep-0002.md
|   ├── sep-0003.md
|   └── sep-0004.md
├── cap-template.md
└── sep-template.md
```

## Process

1. Write your CAP or SEP using `cap-template.md` or `sep-template.md` (`DRAFT`).
2. Create a PR in this repository.
3. CAP or SEP number assigned (`ACCEPTED`) or CAP or SEP rejected (`REJECTED`).
4. Discussion and changes.
5. CAP or SEP merged (`FINAL`) or CAP or SEP rejected (`REJECTED`).
