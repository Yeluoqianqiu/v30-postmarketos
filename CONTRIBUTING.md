# Contributing

- Start with [sources.lock.json](sources.lock.json) and the [validation boundaries](docs/validation.md). State the target version and concrete problem.
- Provide source and reproducible host checks. Report hardware observations separately, with device, version and scope. A running process, registration or successful write is not proof of two-way audio or delivery.
- Preserve upstream copyright, SPDX and author information. Explain borrowed and modified material in the provenance record.
- Do not commit credentials, firmware, raw SMS/audio, SIM data, personal UUIDs, raw device logs or partition images.
- Keep prose, comments and CLI messages in English. Retain Unicode protocol/test coverage; escaped literals are appropriate for non-English synthetic payloads.
- Run `python3 scripts/check.py`. Changes affecting hardware still require the owner to arrange fresh tests.
- Attribute AI assistance to the actual tool/model. AI cannot certify a human's contribution rights. Follow each upstream's DCO/GPG and commit conventions when submitting there.

Publication and host testing do not authorize calls, answering, SMS, reboots or partition writes.
