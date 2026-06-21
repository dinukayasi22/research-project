import os
import random
import cv2
import numpy as np
import hashlib
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage.metrics import structural_similarity as ssim

# Local Module Imports
from phase2_payload import PayloadEncoder
from phase3_embedding import DWTSVDEmbedder, DWTSVDExtractor
from phase4_attack import AttackSimulator
from extractor_decoder import PayloadDecoder
from analyzer import calculate_shannon_entropy

def bytes_to_bits(data_bytes):
    bits = []
    for byte in data_bytes:
        bits.extend([int(b) for b in bin(byte)[2:].zfill(8)])
    return np.array(bits)

def bits_to_bytes(bits):
    byte_list = []
    for i in range(0, len(bits), 8):
        if i + 8 > len(bits): break
        byte_val = int("".join(map(str, bits[i:i+8])), 2)
        byte_list.append(byte_val)
    return bytes(byte_list)

def run_adaptive_validation():

    # 1. USER INPUTS
    user_msg = input("\nEnter the text (Max 15 chars): ")
    if not user_msg:
        user_msg = "somethingishere"
        print(f"Using default message: {user_msg}")
        
    user_key = input("Enter an encryption password: ")
    if not user_key:
        user_key = "batman123"
        print("Using default password.")

    SECRET_MESSAGE = user_msg
    AES_KEY = hashlib.sha256(user_key.encode('utf-8')).digest()
    
    SPREAD = 8 
    RS_RATIO = 1.0  

    # Directories
    COVERS_DIR = "suitable_covers"
    STEGO_DIR = "stego_images"
    ATTACK_DIR = "attacked_images"
    os.makedirs(STEGO_DIR, exist_ok=True)
    os.makedirs(ATTACK_DIR, exist_ok=True)
    

    # 2. PHASE 1: CONTENT-ADAPTIVE SELECTION
    valid_images = [f for f in os.listdir(COVERS_DIR) if f.lower().endswith(('.jpg', '.png'))]
    if not valid_images:
        print("Error: No images in suitable_covers folder.")
        return
        
    target_image_name = random.choice(valid_images)
    cover_img = cv2.imread(os.path.join(COVERS_DIR, target_image_name))
    
    # STANDARDIZE: Resize to 512x512
    # 
    cover_img = cv2.resize(cover_img, (512, 512), interpolation=cv2.INTER_AREA)
    
    # Calculate actual entropy of the chosen image
    entropy_result = calculate_shannon_entropy(cover_img)
    entropy_val = entropy_result['entropy_value']
    
    print(f"1. Cover Selected: {target_image_name}", flush=True)
    print(f"          Shannon Entropy: {entropy_val:.4f}", flush=True)

    # ADAPTIVE LOGIC: Link Entropy to Embedding Strength (Alpha)
    if entropy_val >= 7.6:
        ALPHA = 65.0
        print(f"          Texture Analysis: Highly Complex -> Adaptive Alpha: {ALPHA}")
    elif entropy_val >= 7.3:
        ALPHA = 55.0
        print(f"          Texture Analysis: Moderately Complex -> Adaptive Alpha: {ALPHA}")
    else:
        ALPHA = 45.0
        print(f"          Texture Analysis: Standard -> Adaptive Alpha: {ALPHA}")

    # 3. PHASE 2: CRYPTO & RS
    print(f"\n2. Encoding Message: '{SECRET_MESSAGE}'", flush=True)
    encoder = PayloadEncoder(redundancy_ratio=RS_RATIO)
    robust_bytes = encoder.encode(SECRET_MESSAGE, AES_KEY)
    payload_bits = bytes_to_bits(robust_bytes)

    # 4. PHASE 3: ADAPTIVE EMBEDDING (LH Band, 4x4 Blocks)
    print(f"3. Embedding in LH sub-band using Adaptive Alpha ({ALPHA})...", flush=True)
    print(f"          (Processing {len(payload_bits) * SPREAD} SVD blocks — please wait...)", flush=True)
    embedder = DWTSVDEmbedder(alpha=ALPHA, redundancy=SPREAD)
    stego_img = embedder.embed(cover_img, payload_bits)
    stego_path = os.path.join(STEGO_DIR, "stego_" + target_image_name)
    cv2.imwrite(stego_path, stego_img)
    print(f"          Embedding complete. Saved -> {stego_path}", flush=True)

    psnr_val = psnr(cover_img, stego_img)
    ssim_val = ssim(cover_img, stego_img, channel_axis=2)
    
    print(f"PSNR: {psnr_val:.2f} dB")
    print(f"SSIM: {ssim_val:.4f}")

    # 5. PHASE 4: ATTACK SIMULATION

    print(f"\n4. Applying Attack: JPEG QF=50", flush=True)
    attack_sim = AttackSimulator()
    attacked_img = attack_sim.simulate_transmission(stego_img, qf=50, scale=1.0)
    attacked_path = os.path.join(ATTACK_DIR, "attacked_" + target_image_name)
    cv2.imwrite(attacked_path, attacked_img)
    print(f"          Attack complete.    Saved -> {attacked_path}", flush=True)

    # 6. PHASE 5: EXTRACTION & DECODING
    print(f"5. Extracting & Repairing Bits... (please wait...)", flush=True)
    extractor = DWTSVDExtractor(alpha=ALPHA, redundancy=SPREAD)
    extracted_bits = extractor.extract(attacked_img, len(payload_bits))
    
    raw_ber = (np.sum(payload_bits != extracted_bits) / len(payload_bits)) * 100
    print(f"          Raw Signal BER (Post-Spread Recovery): {raw_ber:.2f}%")

    # Final Self-Healing
    decoder = PayloadDecoder(redundancy_ratio=RS_RATIO)
    try:
        recovered_text = decoder.decode(bits_to_bytes(extracted_bits), AES_KEY)
        print(f"\n--- METRIC CHECK: ROBUSTNESS ---")
        print(f"Original:  {SECRET_MESSAGE}")
        print(f"Recovered: {recovered_text}")
        assert recovered_text == SECRET_MESSAGE
        print(f"STATUS: PASSED (Final BER = 0%)")
    except Exception as e:
        print(f"\n--- METRIC CHECK: ROBUSTNESS ---")
        print(f"STATUS: FAILED ({e})")

    print("="*65 + "\n")

if __name__ == "__main__":
    if not os.path.exists("suitable_covers"):
        print("Please run analyzer.py to generate suitable_covers first.")
    else:
        run_adaptive_validation()
