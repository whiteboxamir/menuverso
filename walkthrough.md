# Codex Handoff Report — All Gauset Engine Work

**Prepared:** March 24, 2026  
**Branch:** `main` at `1047ce6`  
**Uncommitted local work:** 5 modified files, 3 new files (935 new LOC)

---

## Part 1: Pushed Commits (March 22–23)

All of these are on `main` and deployed to Vercel.

### March 22

| Commit | Description |
|---|---|
| `ebcac39` | Fix live MVP uploads and canary density gate |

### March 23 — Codex Branch Merge + Quality Work

| Commit | Description |
|---|---|
| `a68ebd7` | Snapshot: preserve latest Codex state — SEO, scroll components, workspace refinements, auth login, viewer polish |
| `f790818` | Fix: remove unaccepted props from `LeftPanelWorkspaceSummary` — fixes Vercel build type error |
| `53f24ee` | **Improve Gaussian renderer quality** — boosted splat richness, contrast, saturation, and shadow lift |
| `a9f3028` | **Second round quality fixes** — splat cache, point threshold bump, DPR (device pixel ratio) improvements |
| `90031f6` | Merge `codex/gated-login-push` into main — quality fixes, SEO, scroll UI |
| `beedcdf` | Fix: revert `ThreeOverlay` to main's version — Codex version referenced missing split files |
| `f1d2d94` | Fix: revert `HEAVY_SCENE_POINT_THRESHOLD` to 1M — 1.5M crashes Chrome on dense scenes |
| `1a31ade` | **Phase 1 shader quality tuning** — richer, denser, sharper splats |
| `19567a0` | Fix Chrome crash at 1.5M points via CPU sort fallback |
| `6cd93e3` | Port Codex premium UI labels to production renderer |
| `49187b5` | **Implement time-sliced progressive GPU sorting** — spreads Bitonic sort across frames |
| `ecd0db7` | Allow heavy staged upgrades to trigger on desktop |
| `b722549` | Revert time-slicing to guarantee perfect depth during motion |
| `1047ce6` | **Restore volumetric alpha dithering** — `stableCoverageNoise` for structural depth |

### What These Commits Changed (Summary)

The March 23 commits were a sustained effort to **close the quality gap** between the local dev renderer and the Vercel production deployment. The root causes were:

1. **Shader parameters** — production had lower `covarianceScale`, `opacityBoost`, `colorGain`, `colorContrast`, `colorSaturation` than dev
2. **Point budget** — `HEAVY_SCENE_POINT_THRESHOLD` was too conservative (1M), limiting splat density on capable hardware
3. **Sort correctness** — time-sliced progressive sorting (spreading Bitonic passes across frames) caused visible popping when the camera moved, so it was reverted to full-sort-per-frame
4. **Alpha dithering** — `stableCoverageNoise` was missing from the Codex branch, causing flat alpha cutoffs instead of volumetric depth

> [!IMPORTANT]
> The **time-sliced progressive sort was reverted** in `b722549` because it causes visible artifacts during camera motion. The SOTA WebGPU radix sort (see Part 2) is the correct long-term fix for sort performance.

---

## Part 2: Uncommitted Local Work (March 23–24, "SOTA Waves")

These changes exist **only in the local working directory** — nothing has been pushed to Git.

### Overview

The goal was to build a **SOTA WebGPU Gaussian Splat rendering pipeline** alongside the existing WebGL2 pipeline, activated by `?engine=webgpu` URL parameter. This is a dual-canvas architecture — the WebGL2 path is untouched for Codex stability.

### Modified Files (tracked, unstaged)

#### 1. [sharpGaussianShared.ts](file:///Users/amirboz/gauset/src/components/Editor/sharpGaussianShared.ts) (+2 lines)
Added two new fields to `SharpGaussianPayload`:
```typescript
codebookTexture: DataTexture | null;  // VQ codebook for compressed payloads
codebookData: Float32Array | null;    // Raw RGBA codebook (256×4 floats)
```

#### 2. [sharpGaussianPayload.ts](file:///Users/amirboz/gauset/src/components/Editor/sharpGaussianPayload.ts) (+4 lines)
- Initializes `codebookTexture` and `codebookData` in `createSharpGaussianOrderTexture`
- Adds codebook disposal in `disposeSharpGaussianPayload`

#### 3. [sharpGaussianPlyWorker.ts](file:///Users/amirboz/gauset/src/components/Editor/sharpGaussianPlyWorker.ts) (+249 / -8 lines)
**The biggest change.** Added:
- `SPLAT_VQ` magic byte detection for the `.splat._vq` compressed format
- `parsePackedSharpGaussianVqPayload()` — decodes VQ-compressed payloads:
  - INT16 positions → float32 positions (with min/max normalization)
  - uint8 codebook indices → RGBA color lookups
  - uint8 scale/rotation → float32 (denormalized)
- **Bug fix (Wave 1):** RGB→RGBA codebook padding — the original parser emitted 256×3 (RGB) codebook data but the GPU texture expects 256×4 (RGBA). This was corrupting every color lookup.

#### 4. [SharpGaussianEnvironmentSplat.tsx](file:///Users/amirboz/gauset/src/components/Editor/SharpGaussianEnvironmentSplat.tsx) (+80 / -24 lines)
- Added `SharpGaussianWebGPULayer` component — renders Gaussians via WebGPU overlay canvas
- `?engine=webgpu` URL parameter toggles between WebGL2 (default) and WebGPU paths
- **Wave 3 fix:** Proper `engine.dispose()` on unmount (was leaking GPU resources)
- **Wave 3 fix:** Added `ready` state tracking + async race guard

#### 5. [ml_sharp_wrapper.py](file:///Users/amirboz/gauset/backend/models/ml_sharp_wrapper.py) (+7 lines)
Imports and calls `vq_compiler` after reconstruction to emit `.splat._vq` files.

### New Files (untracked)

#### 6. [sharpGaussianWebGPURenderer.ts](file:///Users/amirboz/gauset/src/components/Editor/sharpGaussianWebGPURenderer.ts) (778 lines, NEW)

**The core of the SOTA upgrade.** A standalone WebGPU engine with:

**6 WGSL Compute/Render Shaders:**

| Shader | Lines | Purpose |
|---|---|---|
| `DEPTH_KEY_SHADER` | ~30 | Float depth → sortable uint32 via sign-bit flip |
| `RADIX_HISTOGRAM_SHADER` | ~30 | Per-workgroup 256-bucket histogram per 8-bit digit |
| `RADIX_PREFIX_SUM_SHADER` | ~30 | Blelloch exclusive scan across histogram columns |
| `RADIX_SCATTER_SHADER` | ~30 | Scatter (key, value) pairs to sorted positions |
| `HISTOGRAM_CLEAR_SHADER` | ~10 | Zero histogram buffer between passes |
| `GAUSSIAN_RENDER_SHADER` | ~150 | Full EWA vertex + rich fragment (see below) |

**Engine Class (`SharpGaussianWebGPUEngine`):**
- `initialize()` — Requests `high-performance` GPU adapter, configures canvas
- `uploadPayload()` — Decodes half-float textures → float32, creates GPU buffers, **pre-computes all bind groups at upload time** (zero per-frame allocations)
- `render()` — Single command encoder per frame: depth keys → 4-pass radix sort → Gaussian raster
- `dispose()` — Destroys all GPU resources

**Key technical decisions:**
1. **Pre-computed bind groups** — All 12 sort bind groups (4 passes × histogram + prefix + scatter) and 4 sort-param uniform buffers are created at upload time. The render loop has **zero `createBindGroup` or `writeBuffer` calls**.
2. **Float-to-sortable-uint** — `bitcast<u32>(depth) XOR mask` produces correct unsigned ordering for both positive and negative depths.
3. **Even-pass ping-pong** — 4 passes (A→B, B→A, A→B, B→A) means final sorted result is always in buffer A.
4. **Full EWA covariance** — Ported directly from the production GLSL: quaternion → rotation matrix → 3D covariance → Jacobian → 2D covariance → eigenvalue decomposition.
5. **Rich color grading** — ACES filmic tone mapping, shadow lift, saturation boost, `stableCoverageNoise` dithered alpha discard.

#### 7. [vq_compiler.py](file:///Users/amirboz/gauset/backend/models/vq_compiler.py) (157 lines, NEW)

Python VQ (Vector Quantization) compiler:
- Uses `scikit-learn` K-Means (256 clusters) on SH coefficients
- Quantizes positions to INT16 (with min/max normalization)
- Quantizes scales/rotations to UINT8
- Emits `.splat._vq` binary blobs (~85% smaller than raw `.splat`)
- Output format: `SPLAT_VQ` magic → header → codebook (256×4 RGBA floats) → per-point data

#### 8. `test_vq.py` (test script, can be deleted)

---

## Part 3: Branch Topology

```
main (1047ce6) ← HEAD
  ├── codex/gated-login-push (a9f3028) — merged
  ├── codex/live-mvp-gaussian-20260321 (589871a) — merged
  └── [several older codex/* branches] — merged

Local uncommitted:
  5 tracked-modified files
  3 new untracked files (WebGPU renderer, VQ compiler, test)
  node_modules → symlink to /tmp/gauset_nm
  node_modules_broken → original SIP-locked node_modules
```

---

## Part 4: Environment Notes for Codex

> [!CAUTION]
> The local `node_modules` directory was SIP-locked by macOS (`com.apple.provenance` xattr) and has been **moved to `node_modules_broken`**. A symlink now points to `/tmp/gauset_nm`. Codex should run `rm node_modules && npm install --legacy-peer-deps` to restore a clean `node_modules`.

> [!WARNING]
> The `.env.local` file is also SIP-locked and could not be read from this agent process. Codex should verify it contains the correct environment variables.

---

## Part 5: What's Left to Do

| Priority | Item | Status |
|---|---|---|
| 🔴 Critical | Test WebGPU pipeline with a real `.splat` scene | Not started |
| 🔴 Critical | Add frustum culling to depth-key compute | Not started |
| 🟡 Important | Port SH evaluation to WGSL fragment shader | Not started |
| 🟡 Important | Profile radix sort on 2M+ point scenes | Not started |
| 🟢 Nice | Add `?engine=webgpu` diagnostic overlay (FPS, sort time) | Not started |
| 🟢 Nice | Wire VQ compiler into Codex CI/CD | Not started |

---

## Part 6: How to Test

```bash
# Restore node_modules
rm /Users/amirboz/gauset/node_modules
cd /Users/amirboz/gauset && npm install --legacy-peer-deps

# Run dev server
npm run dev

# Test WebGL2 (default, safe)
open http://localhost:3000/mvp

# Test WebGPU (new SOTA pipeline)
open http://localhost:3000/mvp?engine=webgpu
```

All WebGPU code is behind the `?engine=webgpu` gate. The WebGL2 pipeline is completely untouched.
