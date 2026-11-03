# Provenance, licensing and publication boundaries

| Path | Origin and license |
|---|---|
| `baseline/kernel/` | ShapeShifter499's Linux branch and local r30 packaging changes. Kernel patches retain original file licenses, including GPL-2.0. Historical maintainer metadata in APKBUILD records the source and does not imply upstream maintains this repository. |
| `patches/current-kernel/` | Five submitted kernel commits. The two GCC changes derive from Dmitry Baryshkov and retain original authorship/sign-offs and the backporter's sign-off. |
| `patches/imsd/` | V30 interoperability changes against Catcrafts imsd `2b5de7a…`, GPL-3.0-only. Their publication here does not imply upstream acceptance. |
| `runtime/voice/ims-pdn-up.sh` and D-Bus/polkit files | Derived from Catcrafts imsd; original GPL-3.0-only and Catcrafts copyright headers are preserved. |
| Other `runtime/`, `scripts/`, `tests/` and repository documentation | Local integration tools and publication adaptations, GPL-3.0-only; references are listed in the acknowledgements. Initial publication adaptations had host checks; selected r37 device changes and their limits are documented in [incoming alerts](docs/incoming-alerts.md). |
| `runtime/reference-r81/` and `patches/r81-reference/` | Selected local integration sources and the incremental Linux TCPM change. Third-party firmware and libraries are separate dependencies. See the r81 reference README for the packaging boundary. |
| Console font | The operator captures the device's original console glyphs before scaling them; that original bitmap is not bundled and retains its license. `runtime/support/console-glyphs.json` adds original battery/signal drawings and a derived bitmap subset of Noto Sans CJK SC. Chinese glyphs retain OFL-1.1, their Adobe copyright and source-font digest; see `LICENSES/OFL-1.1.txt`. Private-use cells implement fixed console labels, not a general CJK font. |

The root LICENSE and LICENSES/GPL-3.0-only.txt contain GPLv3. LICENSES/GPL-2.0-only.txt is the GPLv2 text supplied by Linux. The root license does not relicense third-party code.

[FILE_ORIGINS.json](provenance/FILE_ORIGINS.json) records source labels and current file hashes; [SHA256SUMS](SHA256SUMS) records public-file integrity. Translation changes are identified in the origin entries. These hashes do not turn private device captures into publicly verifiable or immutable acceptance evidence.

Excluded from publication: vendor/device-extracted firmware, codec binaries, personal boot/initramfs images, SIM/NV state, contacts/SMS archives, credentials, private keys, raw device logs, partition backups and personal filesystem UUIDs. Generated binaries and operator configuration belong in ignored output directories.

AI assistance is declared as `Assisted-by: Codex:OpenAI/GPT-6`; a more specific model route was not exposed to the session. Existing contributor identities are not replaced.
