Stellar Protocol
================

This repository contains Stellar Improvement Proposals (SIPs). Similarly to [BIPs](https://github.com/bitcoin/bips) and [EIPs](https://github.com/ethereum/EIPs), SIPs are the proposals of standards to improve Stellar protocol and related client APIs.

## Repository structure

The root directory of this repository contains:

* Accepted SIPs (`sip-xxxx.md` where `xxxx` is a SIP number with leading zeros, ex. `sip-0051.md`),
* `contents` directory with `sip-xxxx` subdirectories that contain all media/script files for a given SIP document.

Example repository structure in a future:
```
├── README.md
├── contents
│   ├── sip-0001
│   │   └── image.png
│   └── sip-0002
│       └── script.go
├── sip-0001.md
├── sip-0002.md
├── sip-0003.md
├── sip-0004.md
└── sip-template.md
```

## Process

1. Write your SIP using `sip-template.md` (`DRAFT`).
2. Create a PR in this repository.
3. SIP number assigned (`ACCEPTED`) or SIP rejected (`REJECTED`).
4. Discussion and changes.
5. SIP merged (`FINAL`) or SIP rejected (`REJECTED`).
