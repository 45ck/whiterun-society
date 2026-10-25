# Native UI compiler pipeline

The **Native UI baseline build** workflow prepares a reproducible source and dependency selection for an unchanged NirnLab UI build on a GitHub-hosted Windows worker. It does not install software on the local workstation, run on a self-hosted runner, dispatch itself, publish a release, or deploy to Skyrim. Its first successful hosted compilation is still unverified.

The baseline artifact is **not suitable for deployment**. Upstream lacks the lab's `kAllowSaving` compatibility change and contains no native-input correction. Compiling it establishes a baseline for subsequent reviewed patches; it does not repair RTS controls.

## Manual build and evidence

After review and publication, run `.github/workflows/native-ui-build.yml` manually from the intended reviewed revision. There are no arbitrary source, command, patch or URL inputs. The workflow uses `windows-2022`, existing Visual Studio 2022 C++ tools and CMake, and refuses an absent compiler instead of installing one. The script also refuses local and self-hosted execution. Its permissions are `contents: read`; checkout credentials are not persisted.

The workflow verifies the preparation tests, downloads and verifies exact inputs, builds only the `NirnLabUIPlatform` target in Release, and retains evidence for 14 days. The build has a 90-minute timeout. It does not run any newly built DLL. `BUILD_AS_SHARED=ON` and x64 static vcpkg dependencies match upstream. `/DEBUG` is an explicit linker option to obtain a matching PDB; `CMAKE_POLICY_VERSION_MINIMUM=3.5` permits older dependency CMake projects when the hosted CMake version requires it. Neither option changes application source. No input or save-compatibility patch is applied.

The artifact contains, when available:

- DLL and its adjacent linker PDB, with SHA-256 and byte counts.
- The pinned input manifest and all 109 verified upstream file hashes.
- Build outcome, source revision, runner image/version, Visual Studio details, MSVC version/compiler hash, CMake version/hash, PowerShell/Python versions and exact configure arguments.
- CMake cache/compiler records including the selected Windows SDK; vcpkg installed package status and generated dependency SBOMs.
- NirnLab, vcpkg and dependency copyright/license files, including CommonLib and CEF notices.
- Preparation/configuration/compilation logs and dependency logs. Dependency logs are capped at 100 files and 5 MiB per file; omitted paths are explicitly recorded.

Failures also upload available evidence. A `compiled-unqualified` result means only that the target DLL and linker PDB were produced with required license files present. The workflow does not package Skyrim assets or the full CEF runtime. It does not upload environment variables or checkout credentials.

## Pinned inputs

The machine-readable authority is [`tools/native-ui/manifest.json`](../tools/native-ui/manifest.json). The complete expected source listing is [`upstream-files.json`](../tools/native-ui/upstream-files.json).

| Input | Exact selection | Evidence |
| --- | --- | --- |
| NirnLab UI | `c9514ac16434e2edc2bbfb348be2fcdc47e1d6e2` | Source archive SHA-256 `8edbf90e6e42265e57242e986b880b17e8cc54fb1036fe94562f6168fc0e159d`; 109 Git blob hashes verified locally |
| vcpkg ports/scripts | `8eb57355a4ffb410a2e94c07b4dca2dffbee8e50` | Public tag `2023.10.19`; archive SHA-256 `029cca70c19063086f5ed735f78a1e2adeaf745519a01113b8c4b24476dcad4a` |
| vcpkg executable | Release `2023-10-18` | SHA-256 `ff4f02ba2ceede4b413ee6fa618441b39fe76b81369d334a602d5410c03988ee`, 8,108,992 bytes; matches pinned source release metadata |
| CommonLibSSE-NG overlay | `9b7c386d0355e756b4153416a76b0532f755f8de` | Upstream overlay SHA-512 retained and checked by vcpkg |
| CEF overlay | `141.0.11+g7e73ac4+chromium-141.0.7390.123`, Windows64 | Exact upstream URL and SHA-512 retained and checked by vcpkg |
| Checkout action | `11bd71901bbe5b1630ceea73d27597364c9af683` | Verified public `v4.2.2` tag |
| Upload artifact action | `ea165f8d65b6e75b540449e92b4886f43607fa02` | Verified public `v4.6.2` tag |

The vcpkg snapshot was selected because it retains `vcpkg_configure_cmake`, `vcpkg_install_cmake` and `vcpkg_extract_source_archive_ex`, used by NirnLab's unchanged overlay ports. It also predates fmt 11. Public source inspection supports this selection; **it does not establish compilation compatibility**. The unchanged upstream manifest has no `builtin-baseline`: this pipeline locks the entire ports/scripts archive instead, uses its current package versions and no version overrides. It does not resolve a floating vcpkg checkout. Binary caches are disabled, and source archives retain their port-defined checksums.

Selected registry manifests at that exact commit declare fmt 10.1.1, spdlog 1.12.0, directxtk 2023-09-01#1, directxmath 2022-12-12, palsigslot 1.2.2, nlohmann-json 3.11.2, rapidcsv 8.64 and xbyak 6.69. The hosted vcpkg installed-status/SBOM evidence determines the complete resolved graph. No claims about newly resolved packages are inferred from these top-level declarations.

The old vcpkg bootstrap script downloads its executable without a pinned checksum. This pipeline **does not run that script**: `prepare.py` downloads and checks the exact release executable before the hosted worker executes it. The local preparation of this change only read and hashed those public asset bytes; no executable or compiler ran locally.

The hosted image and compiler are serviced externally. Their actual identities are recorded, not immutable. This is a pinned-input, auditable build recipe; **byte-identical rebuilds are not proven**. The first hosted run must establish toolchain/dependency compatibility and availability. There are no invented or unresolved source/dependency archive hashes in the manifest.

## Input correction remains a separate patch

The inspected upstream source uses Skyrim's virtual `MenuCursor` coordinates in `DefaultBrowser.h:44–45`. `DefaultBrowser.cpp:430–447` refreshes the CEF position on native mouse movement; click and wheel handling reuse it. `WinProcHook.cpp` has no Windows pointer forwarding, and `MultiLayerMenu.cpp` depends on Skyrim's native input events. This creates a plausible stale-coordinate or coordinate-space mismatch, but cannot by itself explain trials with no events arriving.

A later patch must first collect bounded, focus-gated traces comparing client-space Win32 coordinates, Skyrim virtual cursor, render/CEF dimensions, native event delivery and DOM coordinates. Keyboard text must not be logged. The coordinate source and scaling correction should follow those measurements, preserving unfocused controls and avoiding duplicate event delivery. It must also add `kAllowSaving` in source; the existing binary-offset patch must never be applied blindly to a rebuilt DLL.

No patches are currently eligible: `reviewed_patches` is empty, the preparation helper rejects any nonempty patch list, and the workflow has no patch-selection input. A reviewed follow-up must add an explicit opt-in variant, exact patch hashes, baseline-first build and separate artifact labels.

Native acceptance still requires click/drag/wheel/selection/follow, keyboard controls, focus loss/recovery, actual window position and resolution changes, save/load and shutdown in the isolated lab. Physical input and automated input should be measured separately. A hosted compiler cannot supply this runtime proof. Parent-controlled deployment must preserve the currently installed save-enabled DLL and its hash for rollback.

## Local checks without native execution

```powershell
python -m unittest discover -s tools/native-ui -p test_prepare.py -v
```

These tests cover source identity, invalid/unpinned inputs, checksum mismatch, archive traversal/link/case-collision rejection and source mutation. They execute no downloads, package manager, compiler or DLL. PowerShell syntax can be checked with the PowerShell parser without invoking `build.ps1`.
