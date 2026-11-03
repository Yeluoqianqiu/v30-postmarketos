# Acknowledgements

We thank the upstream maintainers and contributors for the porting, driver, protocol and distribution work that makes this integration possible. The table records how their work is used or referenced; those contributions are not claimed as original work of this repository.

| Project or contributor | Links | Role in this integration |
|---|---|---|
| postmarketOS community | [postmarketOS](https://postmarketos.org/), [pmbootstrap](https://gitlab.postmarketos.org/postmarketOS/pmbootstrap), [pmaports](https://gitlab.postmarketos.org/postmarketOS/pmaports) | Distribution, device packaging, build tooling and package management |
| Linux and Qualcomm mainline contributors | [Linux](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/) | MSM8998 networking, audio, power, console and other kernel foundations |
| ShapeShifter499 / Lance and collaborators | [lg-v30-port](https://github.com/ShapeShifter499/lg-v30-port), [linux-lg-v30-joan](https://github.com/ShapeShifter499/linux-lg-v30-joan), [pmaports-lge-joan](https://github.com/ShapeShifter499/pmaports-lge-joan) | V30 mainline drivers, device tree, hardware support, packaging and bring-up evidence |
| Catcrafts and imsd contributors | [imsd](https://forgejo.catcrafts.net/Catcrafts/imsd) | IMS SIP/AKA/IPsec, RTP/codecs, D-Bus control and the PDN script; our changes add V30 interoperability and OpenRC/audio lifecycle integration |
| ShapeShifter499 / joan-volte-lineage | [joan-volte-lineage](https://github.com/ShapeShifter499/joan-volte-lineage) | Reference for LG IMS parameters, capability masks and Security-Client serialization; not a carrier configuration copied unchanged |
| Dmitry Baryshkov | [GPU clock patch](https://lore.kernel.org/all/20261019-msm8998-fix-clocks-v1-1-370949e4d8a0@oss.qualcomm.com/), [MMSS clock patch](https://lore.kernel.org/all/20261019-msm8998-fix-clocks-v1-2-370949e4d8a0@oss.qualcomm.com/) | Original GCC GPU/MMSS always-on fixes; the submitted adaptations retain authorship and sign-offs |
| GLINK upstream contributors, including Vishnu Santhosh | [Endpoint-destroy deadlock patch](https://lkml.rescloud.iu.edu/2606.0/08069.html) | Source of the driver-detach deadlock fix |
| V30 WCD934x and device-tree contributors | [ADC MUX8 fix](https://github.com/ShapeShifter499/linux-lg-v30-joan/commit/2059bbae94ddfb748278a30a229a94d0882155bf) | ADC3 capture-path fix and reference for microphone-bias/MCLK dependencies |
| LG, Qualcomm and the LineageOS community | [android_kernel_lge_msm8998](https://github.com/LineageOS/android_kernel_lge_msm8998) | Vendor hardware descriptions and reference implementations; owners obtain their own firmware, which is not distributed here |
| ModemManager, NetworkManager and libqmi | [ModemManager](https://modemmanager.org/), [NetworkManager](https://networkmanager.dev/), [libqmi](https://gitlab.freedesktop.org/mobile-broadband/libqmi) | Data connectivity, QMI and SMS D-Bus interfaces |
| PipeWire, ALSA, OpenRC, tmux and Alpine | [PipeWire](https://pipewire.org/), [ALSA](https://www.alsa-project.org/), [OpenRC](https://github.com/OpenRC/openrc), [tmux](https://github.com/tmux/tmux), [Alpine](https://alpinelinux.org/) | Media graph, mixer control, service lifecycle, text interface and userspace environment |
| Phosh/Phoc/Stevia, UIM, Foot, GTK and Mesa contributors | [Phosh](https://phosh.mobi/), [UIM](https://github.com/uim/uim), [Foot](https://codeberg.org/dnkl/foot), [GTK](https://www.gtk.org/), [Mesa](https://www.mesa3d.org/) | Compositor, virtual keyboard/Pinyin engine, terminal and graphical rendering for the optional manual session |
| X.Org, Openbox and Onboard contributors | [X.Org](https://www.x.org/), [Openbox](http://openbox.org/), [Onboard](https://github.com/onboard-osk/onboard) | X11/Xwayland display server, window management and touch keyboard for the experimental manual profiles |
| Adobe / Noto CJK contributors | [Noto CJK](https://github.com/notofonts/noto-cjk) | OFL-1.1 source for the limited Chinese console-label glyph subset and the installed graphical CJK font |
| greetd contributors | [greetd](https://git.sr.ht/~kennylevinsen/greetd) | Explicitly started PAM/seat session on tty8; no default display-manager boot change |
| Weston and seatd/libseat contributors | [Weston](https://wayland.pages.freedesktop.org/weston/), [seatd](https://git.sr.ht/~kennylevinsen/seatd) | DRM Pixman compositor with memory shadow and a temporary manual seat broker for the current experimental profile |
| Giuseppe Maggio and Lance | [Read-pointer pageflip patch](https://github.com/ShapeShifter499/linux-lg-v30-joan/commit/30d498482b40a09e6652fe40f301c7a6b747efd2) | Source of the offline display-latency kernel candidate; original authorship/sign-offs retained, not a device-qualified fix here |

Our main additions combine these components into a US998 TTY profile: boot dependencies, audio ownership and cleanup per call, a persistent SMS archive with explicit idempotent sending, selected IMS interoperability paths, and scoped operator-confirmed observations.

Assisted-by: Codex:OpenAI/GPT-6
Date: 2026-10-31
