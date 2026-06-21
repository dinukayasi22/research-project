# Adaptive Robust Steganography Resilient to Aggressive JPEG Compression and Geometric Scaling


---

## 1. Overview

This project implements a **Content-Adaptive Hybrid DWT-SVD steganography framework** designed to hide secret text inside cover images while surviving the lossy image processing pipelines of social media platforms (JPEG re-compression and geometric resizing).

The system follows a **Defense-in-Depth** architecture across five sequential phases:

1. **Content-Adaptive Suitability Analyzer** — rejects low-texture (low-entropy) cover images before any data is hidden.
2. **Payload Cryptography & Error Correction** — AES-256 (CBC) encryption + Reed-Solomon parity encoding.
3. **Hybrid DWT-SVD Embedding Engine** — embeds the encoded payload into the singular values of 4×4 blocks within the LH sub-band of a 2D Haar wavelet transform.
4. **Attack Simulation Engine** — emulates a lossy transmission channel (JPEG re-compression + optional geometric scaling).
5. **Extraction & Decoding Engine** — reverses the pipeline: SVD-based bit retrieval → Reed-Solomon repair → AES-256 decryption.

---

## 2. Repository Structure

```
analyzer/
├── analyzer.py             # Phase 1 — Shannon entropy cover-image analysis & filtering
├── phase2_payload.py        # Phase 2 — AES-256 CBC encryption + Reed-Solomon encoding (PayloadEncoder)
├── phase3_embedding.py      # Phase 3 — DWT-SVD embedding/extraction (DWTSVDEmbedder, DWTSVDExtractor)
├── phase4_attack.py         # Phase 4 — JPEG + geometric scaling attack simulator (AttackSimulator)
├── extractor_decoder.py     # Phase 5 — Reed-Solomon repair + AES-256 decryption (PayloadDecoder)
├── main.py                  # Console orchestrator — runs the full pipeline end-to-end
├── gui_app.py                # Desktop GUI (CustomTkinter) — interactive pipeline runner
├── suitable_covers/          # Generated: cover images that passed the entropy filter
├── stego_images/              # Generated: cover images with payload embedded
├── attacked_images/           # Generated: stego images after the attack simulation
├── ALASKA_V2/                 # Source dataset (raw cover-image candidates)
```

---

## 3. Installation

**Requirements:** Python 3.10+

```bash
pip install opencv-python numpy PyWavelets pycryptodome reedsolo scikit-image customtkinter Pillow
```

| Package | Purpose |
|---|---|
| `opencv-python` (`cv2`) | Color-space conversion, JPEG compression simulation, geometric resizing |
| `numpy` | Array/bit manipulation, SVD numerics |
| `PyWavelets` (`pywt`) | 2D Haar Discrete Wavelet Transform |
| `pycryptodome` (`Crypto`) | AES-256 CBC encryption/decryption |
| `reedsolo` | Reed-Solomon error-correction encoding/decoding |
| `scikit-image` (`skimage`) | PSNR / SSIM imperceptibility metrics |
| `customtkinter` | Desktop GUI widgets |
| `Pillow` | Image conversion for GUI display |

---

## 4. Usage

### 4.1 Build the cover image pool (run once)

`analyzer.py` scans a source dataset (`ALASKA_V2/`) and copies only images whose Shannon entropy exceeds the threshold into `suitable_covers/`:

```bash
python analyzer.py
```

### 4.2 Run the pipeline — console mode

```bash
python main.py
```
You'll be prompted for a secret message and an encryption password. The script then selects a random suitable cover, embeds the payload, attacks the stego image, extracts and repairs it, and reports PSNR / SSIM / BER plus a PASS/FAIL verdict.

### 4.3 Run the pipeline — desktop GUI (recommended)

```bash
python gui_app.py
```

The GUI provides:
- Secret message / password inputs
- **Adaptive embedding strength** — alpha is automatically linked to the cover image's Shannon entropy (no manual override)
- **JPEG Quality Factor** slider, clamped to **50–100**
- **Geometric Scale** slider, clamped to **50%–100%**
- **Spread-spectrum redundancy** slider (bit repetition factor)
- Live previews of the Cover / Stego / Attacked images
- Real-time PSNR, SSIM, raw BER, and final PASS/FAIL metric cards
- A scrollable execution log mirroring the phase-by-phase pipeline output

Click **RUN FULL PIPELINE** to execute all five phases. Stego and attacked images are saved automatically to `stego_images/` and `attacked_images/`.

---

## 5. Methodology Summary

| Phase | Technique | Purpose |
|---|---|---|
| 1 | Shannon Entropy `H = -Σ p_i log₂(p_i)` | Reject smooth/low-texture images that would show visible embedding artifacts |
| 2 | AES-256 (CBC) + Reed-Solomon | Confidentiality + resilience against burst-error corruption |
| 3 | YCbCr → 2D Haar DWT → LH sub-band → 4×4 block SVD → QIM on σ₁ | Robust, imperceptible frequency-domain embedding |
| 4 | JPEG re-encode + bilinear downscale/upscale | Simulate a lossy social-media transmission channel |
| 5 | SVD bit retrieval → majority vote → RS repair → AES decrypt | Self-healing recovery of the original message |

---

## 6. Known Limitations

In summary:

- **Payload capacity bottleneck:** spread-spectrum redundancy (×8) + 100% Reed-Solomon parity limits a 512×512 cover (4,096 SVD slots) to roughly 35–40 safely recoverable characters.
- **Geometric desynchronization:** the system has no resistance to cropping, rotation, or translation — any spatial misalignment breaks the 4×4 block grid and collapses BER to ~50%.
- **Statistical detectability:** quantizing σ₁ creates unnatural histogram bins, potentially detectable by steganalysis tools (Chi-Square, RS-Analysis).
- **Computational cost:** per-block SVD is expensive; not suitable for real-time or high-resolution/video applications.
- **Semi-blind extraction:** the receiver must know the payload length and alpha in advance — a real deployment would need a secure side-channel for this metadata.

---

## 7. Tuning Reference

Quick summary:

| Parameter | Increasing it → | Decreasing it → |
|---|---|---|
| Entropy threshold (`analyzer.py`) | More secure covers, fewer images pass | More images pass, risk of visible artifacts |
| Embedding strength `alpha` | Higher robustness, lower visual quality | Higher visual quality, fragile payload |
| Spread redundancy / `SPREAD` | Higher reliability, lower capacity | Higher capacity, lower reliability |
| Reed-Solomon `redundancy_ratio` | Survives heavier corruption | Less overhead, less tolerance for errors |
| JPEG `qf` (GUI-clamped to 50–100) | Lighter compression, easier extraction | Heavier compression, requires higher alpha |
| Geometric `scale` (GUI-clamped to 50–100%) | Less distortion, easier recovery | More distortion, risk of total desync |

---

## 8. Tools & Technologies

- **Language:** Python 3.10+
- **Image processing:** OpenCV
- **Signal transform:** PyWavelets (Haar DWT)
- **Matrix operations:** NumPy (SVD)
- **Cryptography:** PyCryptodome (AES-256 CBC)
- **Error correction:** reedsolo (Reed-Solomon)
- **Metrics:** scikit-image (PSNR, SSIM)
- **GUI:** CustomTkinter + Pillow
- **Dataset:** ALASKA v2 (high-resolution, uncompressed images for steganalysis research)
