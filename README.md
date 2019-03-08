Stellar Protocol
================

This repository contains **Core Advancement Proposals** (CAPs) and **Stellar Ecosystem Proposals**
(SEPs).

Similar to [BIPs](https://github.com/bitcoin/bips) and [EIPs](https://github.com/ethereum/EIPs),
CAPs and SEPs are the proposals of standards to improve Stellar protocol and related client APIs.

CAPs deal with changes to the core protocol of the Stellar network. Please see [the process for CAPs](core/README.md).

SEPs deal with changes to the standards, protocols, and methods used in the ecosystem built on top
of the Stellar network. Please see [the process for SEPs](ecosystem/README.md).

## Repository structure

The root directory of this repository contains:

* Templates for creating your own CAP or SEP
* `contents` directory with `[cap | sep]-xxxx` subdirectories that contain all media/script files for a given CAP or SEP document.
* core directory which contains accepted CAPs (`cap-xxxx.md` where `xxxx` is a CAP number with leading zeros, ex. `cap-0051.md`)
* ecosystem directory which contains accepted SEPs (`sep-xxxx.md` where `xxxx` is a SEP number with leading zeros, ex. `sep-0051.md`)

Example repository structure:
```
├── CONTRIBUTING.md
├── README.md
├── cap-template.md
├── contents
│   └── cap-0003
│       └── get_offer_stats.sql
├── core
│   ├── cap-0001.md
│   ├── cap-0002.md
│   ├── cap-0003.md
│   └── README.md
├── ecosystem
│   ├── README.md
│   ├── sep-0001.md
│   ├── sep-0002.md
│   ├── sep-0003.md
└── sep-template.md
```

See [CONTRIBUTING](CONTRIBUTING.md) to learn how to contribute.
