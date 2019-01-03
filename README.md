Stellar Protocol
================

This repository contains **Core Advancement Proposals** (CAPs) and **Stellar Ecosystem Proposals** (SEPs). 
Similarly to [BIPs](https://github.com/bitcoin/bips) and [EIPs](https://github.com/ethereum/EIPs), CAPs and SEPs are the proposals of standards to improve Stellar protocol and related client APIs.

CAPs deal with changes to the core protocol of the Stellar network. Please see [the process for CAPs](core/readme.md)

SEPs deal with changes to the standards, protocols, and methods used in the ecosystem built on top of the Stellar network. 

## Repository structure

The root directory of this repository contains:

* Templates for creating your own CAP or SEP
* `contents` directory with `cap-xxxx` subdirectories that contain all media/script files for a given CAP or SEP document.
* core directory which contains accepted CAPs (`cap-xxxx.md` where `xxxx` is a CAP number with leading zeros, ex. `cap-0051.md`)
* ecosystem directory which contains accepted SEPs (`sep-xxxx.md` where `xxxx` is a SEP number with leading zeros, ex. `sep-0051.md`)
* drafts directory for proposed SEPs or CAPs. These documents will be removed from here once approved.
  
Example repository structure:
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
├── drafts
|   ├── draft-0001.md
|   └── draft-0002.md
├── cap-template.md
└── sep-template.md
```

## Process

### CAP proposals

See [the core section](core/readme.md)

### SEP proposals

1. Write your SEP using `sep-template.md` (`DRAFT`).
2. Place it in the /drafts directory.
2. Create a PR in this repository.
3. SEP number assigned (`ACCEPTED`) or SEP rejected (`REJECTED`).
4. Discussion and changes.
5. SEP merged (`FINAL`) or SEP rejected (`REJECTED`).
