# Upstream relationships and review status

This is an unofficial experimental US998 integration and reconstruction project. Linux drivers, postmarketOS, the IMS stack and the media engine remain the work of their respective upstreams.

Status checked on 2026-10-31:

| Work | Location and status |
|---|---|
| TTY SMS tooling and voice source reference | [lg-v30-port #11](https://github.com/ShapeShifter499/lg-v30-port/pull/11): **Ready for review**, open and not merged |
| Fuel gauge, charge inhibition, IPA QMI and two GCC fixes | [linux-lg-v30-joan #12](https://github.com/ShapeShifter499/linux-lg-v30-joan/pull/12): **Ready for review**, open and not merged; base `dc9c669…`; four target objects compiled, with no complete image or device boot |
| LG six-tuple security offer, Via preservation and offerless re-INVITE/ACK SDP | Local imsd patch; no Forgejo PR. Submission still requires a Forgejo account and the project's configured GPG signing. |
| IPA system header table, GLINK deadlock, ADC MUX8 and MCLK routes | Already present at the newer kernel base and not duplicated in #12. The historical reconstruction inputs still include the corresponding patches/routes. |

The two GCC commits retain Dmitry Baryshkov's authorship. Their adaptation is not a newly invented clock fix. Diagnostic/compatibility patches are retained only in the historical baseline to explain and reconstruct that older stack; they are not presented as clean Linux-mainline submissions.

## What Ready for review means

Both PRs were initially drafts and have now been marked Ready for review. That allows normal review and eventual merge under upstream policy. It does not mean they have been approved, merged or device-qualified. Their existing validation limits continue to apply. See [GitHub's PR documentation](https://docs.github.com/en/pull-requests/reference/pull-requests#draft-pull-requests).

## Developer Certificate of Origin

The DCO records a contributor's certification of the right to submit code under its applicable open-source license, and acknowledgement that the sign-off record is public. `Signed-off-by` records that certification. GPG commit signing is a separate cryptographic mechanism. See [DCO 1.1](https://developercertificate.org/).

A human contributor must make their own certification; AI cannot certify it on their behalf.
