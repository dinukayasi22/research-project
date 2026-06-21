import cv2
import numpy as np
import pywt
import math

def scramble_array(arr, seed=42):
    rng = np.random.RandomState(seed)
    idx = np.arange(len(arr))
    rng.shuffle(idx)
    res = np.zeros_like(arr)
    res[idx] = arr
    return res

def unscramble_array(arr, seed=42):
    rng = np.random.RandomState(seed)
    idx = np.arange(len(arr))
    rng.shuffle(idx)
    res = np.zeros_like(arr)
    for i, pos in enumerate(idx):
        res[i] = arr[pos]
    return res

class DWTSVDEmbedder:

    def __init__(self, alpha: float = 30.0, redundancy: int = 5):
        self.alpha = alpha
        self.redundancy = redundancy

    def embed(self, cover: np.ndarray, payload_bits: np.ndarray) -> np.ndarray:
        # 1. Spread and Scramble (Interleave)
        spread_payload = np.repeat(payload_bits, self.redundancy)
        scrambled_payload = scramble_array(spread_payload)
        
        ycc = cv2.cvtColor(cover.astype(np.float32), cv2.COLOR_BGR2YCrCb)
        y, cb, cr = cv2.split(ycc)
        coeffs = pywt.dwt2(y, 'haar')
        LL, (LH, HL, HH) = coeffs
        
        h, w = LH.shape
        bit_idx = 0
        mod_LH = LH.copy()
        
        # Methodology: 4x4 blocks in LH band
        for i in range(0, h, 4):
            for j in range(0, w, 4):
                if i + 4 > h or j + 4 > w: continue
                if bit_idx >= len(scrambled_payload): break

                block = mod_LH[i:i+4, j:j+4]
                u, s, vt = np.linalg.svd(block)
                
                step = self.alpha
                k = math.floor(s[0] / step)
                if k % 2 != scrambled_payload[bit_idx]: 
                    # NEAREST NEIGHBOR QIM
                    if s[0] < (k + 0.5) * step:
                        k -= 1 
                    else:
                        k += 1 
                        
                if k < 0: k = 1 
                s[0] = (k + 0.5) * step
                
                mod_LH[i:i+4, j:j+4] = u @ np.diag(s) @ vt
                bit_idx += 1
        
        stego_y = pywt.idwt2((LL, (mod_LH, HL, HH)), 'haar')
        stego_y = stego_y[:y.shape[0], :y.shape[1]]
        return np.clip(cv2.cvtColor(cv2.merge([stego_y, cb, cr]), cv2.COLOR_YCrCb2BGR), 0, 255).astype(np.uint8)

class DWTSVDExtractor:
    def __init__(self, alpha: float = 30.0, redundancy: int = 5):
        self.alpha = alpha
        self.redundancy = redundancy

    def extract(self, stego: np.ndarray, length: int) -> np.ndarray:
        ycc = cv2.cvtColor(stego.astype(np.float32), cv2.COLOR_BGR2YCrCb)
        y = ycc[:, :, 0]
        coeffs = pywt.dwt2(y, 'haar')
        LH = coeffs[1][0] 
        
        raw_bits = []
        h, w = LH.shape
        total_target = length * self.redundancy
        
        for i in range(0, h, 4):
            for j in range(0, w, 4):
                if i + 4 > h or j + 4 > w: continue
                if len(raw_bits) >= total_target: break
                block = LH[i:i+4, j:j+4]
                _, s, _ = np.linalg.svd(block)
                # Use floor to perfectly match the (k + 0.5) embedder logic
                k = math.floor(s[0] / self.alpha)
                raw_bits.append(k % 2)
        
        if len(raw_bits) < total_target:
            raw_bits.extend([0] * (total_target - len(raw_bits)))
            
        # 1. Unscramble back to sequential spread chunks
        unscrambled_bits = unscramble_array(np.array(raw_bits))
            
        # 2. Majority Voting
        final_bits = []
        for i in range(0, len(unscrambled_bits), self.redundancy):
            chunk = unscrambled_bits[i:i+self.redundancy]
            if len(chunk) == self.redundancy:
                final_bits.append(1 if sum(chunk) > self.redundancy / 2 else 0)
        return np.array(final_bits[:length])
