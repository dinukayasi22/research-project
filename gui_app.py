import os
import random
import hashlib
import threading
import traceback

import cv2
import numpy as np
from PIL import Image
import customtkinter as ctk
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage.metrics import structural_similarity as ssim

from phase2_payload import PayloadEncoder
from phase3_embedding import DWTSVDEmbedder, DWTSVDExtractor
from phase4_attack import AttackSimulator
from extractor_decoder import PayloadDecoder
from analyzer import calculate_shannon_entropy

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COVERS_DIR = "suitable_covers"
STEGO_DIR = "stego_images"
ATTACK_DIR = "attacked_images"

THUMB_SIZE = (340, 340)

ACCENT = "#3B82F6"
SUCCESS = "#22C55E"
DANGER = "#EF4444"
MUTED = "#94A3B8"


def bytes_to_bits(data_bytes):
    bits = []
    for byte in data_bytes:
        bits.extend([int(b) for b in bin(byte)[2:].zfill(8)])
    return np.array(bits)


def bits_to_bytes(bits):
    byte_list = []
    for i in range(0, len(bits), 8):
        if i + 8 > len(bits):
            break
        byte_val = int("".join(map(str, bits[i:i + 8])), 2)
        byte_list.append(byte_val)
    return bytes(byte_list)


def cv2_to_ctk_image(cv_img, size=THUMB_SIZE):
    rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    pil_img.thumbnail(size, Image.LANCZOS)
    return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)


class ImagePanel(ctk.CTkFrame):


    def __init__(self, master, title):
        super().__init__(master, corner_radius=12, fg_color="#1E2433")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self, text=title, font=ctk.CTkFont(family="Roboto", size=14, weight="bold"), text_color="#E2E8F0"
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))

        self.image_label = ctk.CTkLabel(
            self, text="—", image=None, width=THUMB_SIZE[0], height=THUMB_SIZE[1],
            fg_color="#0F1420", corner_radius=10, text_color=MUTED
        )
        self.image_label.grid(row=1, column=0, padx=14, pady=4, sticky="nsew")

        self.caption_label = ctk.CTkLabel(
            self, text="Awaiting run...", font=ctk.CTkFont(family="Roboto", size=12), text_color=MUTED
        )
        self.caption_label.grid(row=2, column=0, sticky="w", padx=14, pady=(4, 12))

        self._ctk_img = None

    def set_image(self, cv_img):

        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        pil_img.thumbnail(THUMB_SIZE, Image.LANCZOS)

        if self._ctk_img is None:
            self._ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
            self.image_label.configure(image=self._ctk_img, text="")
        else:
            self._ctk_img.configure(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
            self.image_label.configure(text="")

    def set_caption(self, text, color=MUTED):
        self.caption_label.configure(text=text, text_color=color)


class MetricCard(ctk.CTkFrame):
    def __init__(self, master, label):
        super().__init__(master, corner_radius=10, fg_color="#1E2433")
        self.grid_columnconfigure(0, weight=1)
        self.label_widget = ctk.CTkLabel(
            self, text=label, font=ctk.CTkFont(family="Roboto", size=12), text_color=MUTED
        )
        self.label_widget.grid(row=0, column=0, padx=16, pady=(12, 0), sticky="w")
        self.value_widget = ctk.CTkLabel(
            self, text="—", font=ctk.CTkFont(family="Roboto", size=22, weight="bold"), text_color="#E2E8F0"
        )
        self.value_widget.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

    def set_value(self, text, color="#E2E8F0"):
        self.value_widget.configure(text=text, text_color=color)


class StegoApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Adaptive Hybrid DWT-SVD Steganography — Team Steno")
        self.geometry("1920x1080")
        self.minsize(1180, 760)

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()

        self._cover_img = None
        self._stego_img = None
        self._attacked_img = None
        self._payload_bits_len = None
        self._is_running = False


    # Sidebar (controls)


    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color="#161B26")
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_rowconfigure(20, weight=1)

        header = ctk.CTkLabel(
            sidebar, text="Content-Adaptive Hybrid DWT-SVD", font=ctk.CTkFont(family="Roboto", size=20, weight="bold"),
            text_color="#FFFFFF"
        )
        header.grid(row=0, column=0, padx=22, pady=(26, 22), sticky="w")

        # --- Payload section ---
        self._section_label(sidebar, "SECRET PAYLOAD", row=2)
        self.msg_entry = ctk.CTkEntry(sidebar, placeholder_text="Secret message (max 15 chars)")
        self.msg_entry.grid(row=3, column=0, padx=22, pady=(6, 10), sticky="ew")

        self.pwd_entry = ctk.CTkEntry(sidebar, placeholder_text="Encryption password", show="•")
        self.pwd_entry.grid(row=4, column=0, padx=22, pady=(0, 16), sticky="ew")

        # --- Embedding section ---
        self._section_label(sidebar, "EMBEDDING STRENGTH", row=5)
        self.alpha_value_label = ctk.CTkLabel(sidebar, text="Alpha: Adaptive (entropy-linked)",
                                               font=ctk.CTkFont(family="Roboto", size=11), text_color=MUTED)
        self.alpha_value_label.grid(row=6, column=0, padx=22, pady=(6, 16), sticky="w")

        # --- Attack section ---
        self._section_label(sidebar, "LOSSY CHANNEL ATTACK", row=9)
        self.qf_slider = ctk.CTkSlider(sidebar, from_=50, to=100, number_of_steps=50,
                                        command=self._on_qf_slider)
        self.qf_slider.set(50)
        self.qf_slider.grid(row=10, column=0, padx=22, pady=(6, 2), sticky="ew")
        self.qf_label = ctk.CTkLabel(sidebar, text="JPEG Quality Factor: 50",
                                      font=ctk.CTkFont(family="Roboto", size=11), text_color=MUTED)
        self.qf_label.grid(row=11, column=0, padx=22, pady=(0, 10), sticky="w")

        self.scale_slider = ctk.CTkSlider(sidebar, from_=0.5, to=1.0, number_of_steps=50,
                                           command=self._on_scale_slider)
        self.scale_slider.set(1.0)
        self.scale_slider.grid(row=12, column=0, padx=22, pady=(2, 2), sticky="ew")
        self.scale_label = ctk.CTkLabel(sidebar, text="Geometric Scale: 100% (disabled)",
                                         font=ctk.CTkFont(family="Roboto", size=11), text_color=MUTED)
        self.scale_label.grid(row=13, column=0, padx=22, pady=(0, 18), sticky="w")

        # --- Spread / RS section ---
        self._section_label(sidebar, "ROBUSTNESS LAYER", row=14)
        self.spread_label = ctk.CTkLabel(sidebar, text="Spread-Spectrum Redundancy: 8x (fixed)",
                                          font=ctk.CTkFont(family="Roboto", size=11), text_color=MUTED)
        self.spread_label.grid(row=15, column=0, padx=22, pady=(6, 18), sticky="w")

        # --- Run button ---
        self.run_btn = ctk.CTkButton(
            sidebar, text="RUN", height=44,
            font=ctk.CTkFont(family="Roboto", size=14, weight="bold"), fg_color=ACCENT, hover_color="#2563EB",
            command=self._on_run_clicked
        )
        self.run_btn.grid(row=17, column=0, padx=22, pady=(8, 6), sticky="ew")

        self.status_label = ctk.CTkLabel(sidebar, text="Idle", font=ctk.CTkFont(family="Roboto", size=11),
                                          text_color=MUTED)
        self.status_label.grid(row=18, column=0, padx=22, pady=(0, 10), sticky="w")

    def _section_label(self, parent, text, row):
        lbl = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(family="Roboto", size=11, weight="bold"),
                            text_color=ACCENT)
        lbl.grid(row=row, column=0, padx=22, pady=(4, 0), sticky="w")

    # Main area (images, metrics, log)
    def _build_main_area(self):
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="#0F1420")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure((0, 1, 2), weight=1)
        main.grid_rowconfigure(1, weight=0)
        main.grid_rowconfigure(2, weight=0)
        main.grid_rowconfigure(3, weight=1)

        title = ctk.CTkLabel(main, text="Pipeline Visualization",
                              font=ctk.CTkFont(family="Roboto", size=18, weight="bold"), text_color="#E2E8F0")
        title.grid(row=0, column=0, columnspan=3, padx=26, pady=(22, 12), sticky="w")

        # Image panels
        self.cover_panel = ImagePanel(main, "1 · Cover Image")
        self.cover_panel.grid(row=1, column=0, padx=(26, 10), pady=4, sticky="nsew")

        self.stego_panel = ImagePanel(main, "2 · Stego Image")
        self.stego_panel.grid(row=1, column=1, padx=10, pady=4, sticky="nsew")

        self.attacked_panel = ImagePanel(main, "3 · Attacked Image")
        self.attacked_panel.grid(row=1, column=2, padx=(10, 26), pady=4, sticky="nsew")

        # Metric cards
        metrics_frame = ctk.CTkFrame(main, fg_color="transparent")
        metrics_frame.grid(row=2, column=0, columnspan=3, padx=26, pady=(18, 10), sticky="ew")
        metrics_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.psnr_card = MetricCard(metrics_frame, "PSNR (target ≥ 35 dB)")
        self.psnr_card.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.ssim_card = MetricCard(metrics_frame, "SSIM (target > 0.90)")
        self.ssim_card.grid(row=0, column=1, padx=8, sticky="ew")

        self.ber_card = MetricCard(metrics_frame, "Raw BER (pre-RS)")
        self.ber_card.grid(row=0, column=2, padx=8, sticky="ew")

        self.status_card = MetricCard(metrics_frame, "Final Result")
        self.status_card.grid(row=0, column=3, padx=(8, 0), sticky="ew")

        # Log console
        log_frame = ctk.CTkFrame(main, corner_radius=12, fg_color="#1E2433")
        log_frame.grid(row=3, column=0, columnspan=3, padx=26, pady=(6, 22), sticky="nsew")
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        log_title = ctk.CTkLabel(log_frame, text="Execution Log",
                                  font=ctk.CTkFont(family="Roboto", size=13, weight="bold"), text_color="#E2E8F0")
        log_title.grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")

        self.log_box = ctk.CTkTextbox(log_frame, font=ctk.CTkFont(family="Consolas", size=12),
                                       fg_color="#0F1420", text_color="#A7F3D0")
        self.log_box.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="nsew")
        self.log_box.configure(state="disabled")


    # Slider callbacks


    def _on_qf_slider(self, value):
        self.qf_label.configure(text=f"JPEG Quality Factor: {int(float(value))}")

    def _on_scale_slider(self, value):
        pct = float(value) * 100
        suffix = "(disabled)" if pct >= 99.5 else ""
        self.scale_label.configure(text=f"Geometric Scale: {pct:.0f}% {suffix}")

    # Logging helpers (thread-safe via .after)

    def log(self, text):
        def _append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", text + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _append)

    def set_status(self, text, color=MUTED):
        self.after(0, lambda: self.status_label.configure(text=text, text_color=color))


    # Run pipeline


    def _on_run_clicked(self):
        if self._is_running:
            return
        if not os.path.exists(COVERS_DIR):
            self.log(f"[ERROR] '{COVERS_DIR}' not found. Run analyzer.py first to build the cover set.")
            return

        self._is_running = True
        self.run_btn.configure(state="disabled", text="RUNNING...")
        self.set_status("Running pipeline...", ACCENT)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        for panel in (self.cover_panel, self.stego_panel, self.attacked_panel):
            panel.set_caption("Processing...", ACCENT)
        for card in (self.psnr_card, self.ssim_card, self.ber_card, self.status_card):
            card.set_value("—")

        thread = threading.Thread(target=self._run_pipeline_worker, daemon=True)
        thread.start()

    def _finish_run(self, success_color):
        self._is_running = False
        self.run_btn.configure(state="normal", text="RUN")
        self.set_status("Idle", MUTED)

    def _run_pipeline_worker(self):
        try:
            os.makedirs(STEGO_DIR, exist_ok=True)
            os.makedirs(ATTACK_DIR, exist_ok=True)

            user_msg = self.msg_entry.get().strip() or "somethingishere"
            user_key = self.pwd_entry.get().strip() or "batman123"
            secret_message = user_msg
            aes_key = hashlib.sha256(user_key.encode("utf-8")).digest()

            spread = 8  
            rs_ratio = 0.3
            qf = int(self.qf_slider.get())
            scale = round(float(self.scale_slider.get()), 2)

            # Phase 1
            valid_images = [f for f in os.listdir(COVERS_DIR) if f.lower().endswith((".jpg", ".png"))]
            if not valid_images:
                self.log("[ERROR] No images found in suitable_covers/.")
                self.after(0, lambda: self._finish_run(DANGER))
                return

            target_image_name = random.choice(valid_images)
            cover_img = cv2.imread(os.path.join(COVERS_DIR, target_image_name))
            cover_img = cv2.resize(cover_img, (512, 512), interpolation=cv2.INTER_AREA)
            self.after(0, lambda: self.cover_panel.set_image(cover_img))
            self.after(0, lambda: self.cover_panel.set_caption(f"{target_image_name} · 512×512"))

            entropy_result = calculate_shannon_entropy(cover_img)
            entropy_val = entropy_result["entropy_value"]
            self.log(f"1. Cover Image: {target_image_name}  |  Shannon Entropy: {entropy_val:.4f}")

            if entropy_val >= 7.6:
                alpha = 65.0
                tier = "Highly Complex"
            elif entropy_val >= 7.3:
                alpha = 55.0
                tier = "Moderately Complex"
            else:
                alpha = 45.0
                tier = "Standard"
            self.log(f"          Texture: {tier}  ->  Alpha = {alpha}")

            # Phase 2
            self.log(f"2. Encrypting (AES-256 CBC) + Reed-Solomon encoding (ratio={rs_ratio})...")
            encoder = PayloadEncoder(redundancy_ratio=rs_ratio)
            robust_bytes = encoder.encode(secret_message, aes_key)
            payload_bits = bytes_to_bits(robust_bytes)
            self.log(f"          Payload: {len(robust_bytes)} bytes -> {len(payload_bits)} bits")

            # Phase 3
            total_blocks = len(payload_bits) * spread
            self.log(f"3. Embedding in LH sub-band ({total_blocks} SVD blocks, spread={spread}x)...")
            embedder = DWTSVDEmbedder(alpha=alpha, redundancy=spread)
            stego_img = embedder.embed(cover_img, payload_bits)

            stego_path = os.path.join(STEGO_DIR, "stego_" + target_image_name)
            cv2.imwrite(stego_path, stego_img)
            self.after(0, lambda: self.stego_panel.set_image(stego_img))

            psnr_val = psnr(cover_img, stego_img)
            ssim_val = ssim(cover_img, stego_img, channel_axis=2)
            self.after(0, lambda: self.stego_panel.set_caption(
                f"PSNR {psnr_val:.2f} dB · SSIM {ssim_val:.4f}"))
            self.log(f"          Saved -> {stego_path}")
            self.log(f"          PSNR: {psnr_val:.2f} dB   SSIM: {ssim_val:.4f}")

            psnr_ok = psnr_val >= 35
            ssim_ok = ssim_val > 0.90
            self.after(0, lambda: self.psnr_card.set_value(
                f"{psnr_val:.2f} dB", SUCCESS if psnr_ok else DANGER))
            self.after(0, lambda: self.ssim_card.set_value(
                f"{ssim_val:.4f}", SUCCESS if ssim_ok else DANGER))

            # Phase 4
            self.log(f"4. Attack simulation: JPEG QF={qf}, geometric scale={scale*100:.0f}%...")
            attack_sim = AttackSimulator()
            attacked_img = attack_sim.simulate_transmission(stego_img, qf=qf, scale=scale)
            attacked_path = os.path.join(ATTACK_DIR, "attacked_" + target_image_name)
            cv2.imwrite(attacked_path, attacked_img)
            self.after(0, lambda: self.attacked_panel.set_image(attacked_img))
            self.after(0, lambda: self.attacked_panel.set_caption(f"QF={qf} · Scale={scale*100:.0f}%"))
            self.log(f"          Saved -> {attacked_path}")

            # Phase 5
            self.log("5. Extracting and self-healing...")
            extractor = DWTSVDExtractor(alpha=alpha, redundancy=spread)
            extracted_bits = extractor.extract(attacked_img, len(payload_bits))

            raw_ber = (np.sum(payload_bits != extracted_bits) / len(payload_bits)) * 100
            self.log(f"          Raw Signal BER (post spread-recovery): {raw_ber:.2f}%")
            ber_ok = raw_ber < 25  # rough viability threshold before RS repair
            self.after(0, lambda: self.ber_card.set_value(
                f"{raw_ber:.2f}%", SUCCESS if raw_ber == 0 else (DANGER if raw_ber > 25 else "#F59E0B")))

            decoder = PayloadDecoder(redundancy_ratio=rs_ratio)
            try:
                recovered_text = decoder.decode(bits_to_bytes(extracted_bits), aes_key)
                match = recovered_text == secret_message
                self.log(f"Original : '{secret_message}'")
                self.log(f"Recovered: '{recovered_text}'")
                if match:
                    self.log("STATUS: PASSED — Final BER = 0%")
                    self.after(0, lambda: self.status_card.set_value("PASSED", SUCCESS))
                    self.after(0, lambda: self._finish_run(SUCCESS))
                else:
                    self.log("STATUS: FAILED — decoded text does not match original")
                    self.after(0, lambda: self.status_card.set_value("FAILED", DANGER))
                    self.after(0, lambda: self._finish_run(DANGER))
            except Exception as e:
                self.log(f"STATUS: FAILED — {e}")
                self.after(0, lambda: self.status_card.set_value("FAILED", DANGER))
                self.after(0, lambda: self._finish_run(DANGER))

            self.log("=" * 60)

        except Exception:
            self.log("[FATAL ERROR]")
            self.log(traceback.format_exc())
            self.after(0, lambda: self._finish_run(DANGER))


if __name__ == "__main__":
    app = StegoApp()
    app.mainloop()
