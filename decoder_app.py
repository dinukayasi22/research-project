
import os
import hashlib
import threading
import traceback
from tkinter import filedialog

import cv2
import numpy as np
import customtkinter as ctk

from app import (ImagePanel, bytes_to_bits, bits_to_bytes, standardize_cover, COVER_SIZE,
                 ACCENT, SUCCESS, DANGER, MUTED)
from phase2_payload import PayloadEncoder
from phase3_embedding import DWTSVDExtractor
from extractor_decoder import PayloadDecoder
from analyzer import calculate_shannon_entropy

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

SPREAD = 8        # fixed, must match the embedder
RS_RATIO = 0.3    # fixed, must match the embedder


def alpha_for_entropy(entropy_val):
    if entropy_val >= 7.6:
        return 65.0
    elif entropy_val >= 7.3:
        return 55.0
    return 45.0


def total_slots_for(img):
    h, w = img.shape[:2]
    return (h // 2 // 4) * (w // 2 // 4)


def probe_payload_bit_length(message_char_length, rs_ratio=RS_RATIO):

    dummy_msg = "A" * message_char_length
    dummy_key = hashlib.sha256(b"probe").digest()
    encoder = PayloadEncoder(redundancy_ratio=rs_ratio)
    probe_bytes = encoder.encode(dummy_msg, dummy_key)
    return len(probe_bytes) * 8


def candidate_payload_bit_lengths(total_slots, rs_ratio=RS_RATIO, spread=SPREAD):
    lengths = []
    char_len = 1
    while True:
        bits = probe_payload_bit_length(char_len, rs_ratio)
        if bits * spread > total_slots:
            break
        if bits not in lengths:
            lengths.append(bits)
        char_len += 1
    return lengths


class DecoderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Stego Decoder — Receiver Tool")
        self.geometry("1100x760")
        self.minsize(900, 640)

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.loaded_image = None
        self.loaded_image_path = None
        self._is_running = False

        self._build_sidebar()
        self._build_main_area()

    # ------------------------------------------------------------------
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color="#161B26")
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_rowconfigure(20, weight=1)

        header = ctk.CTkLabel(
            sidebar, text="Stego Decoder", font=ctk.CTkFont(family="Roboto", size=20, weight="bold"),
            text_color="#FFFFFF"
        )
        header.grid(row=0, column=0, padx=22, pady=(26, 4), sticky="w")
        sub = ctk.CTkLabel(
            sidebar, text="Receiver Tool — Extract Hidden Message",
            font=ctk.CTkFont(family="Roboto", size=11), text_color=MUTED
        )
        sub.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="w")

        self._section_label(sidebar, "STEGO IMAGE", row=2)
        self.browse_btn = ctk.CTkButton(
            sidebar, text="Browse Image...", height=38,
            font=ctk.CTkFont(family="Roboto", size=13), command=self._on_browse_clicked
        )
        self.browse_btn.grid(row=3, column=0, padx=22, pady=(6, 6), sticky="ew")
        self.file_label = ctk.CTkLabel(sidebar, text="No image selected",
                                        font=ctk.CTkFont(family="Roboto", size=11), text_color=MUTED,
                                        wraplength=270, justify="left")
        self.file_label.grid(row=4, column=0, padx=22, pady=(0, 16), sticky="w")

        self._section_label(sidebar, "DECRYPTION KEY", row=5)
        self.pwd_entry = ctk.CTkEntry(sidebar, placeholder_text="Encryption password", show="•")
        self.pwd_entry.grid(row=6, column=0, padx=22, pady=(6, 18), sticky="ew")

        self.decode_btn = ctk.CTkButton(
            sidebar, text="DECODE", height=44,
            font=ctk.CTkFont(family="Roboto", size=14, weight="bold"), fg_color=ACCENT, hover_color="#2563EB",
            command=self._on_decode_clicked
        )
        self.decode_btn.grid(row=7, column=0, padx=22, pady=(8, 6), sticky="ew")

        self.status_label = ctk.CTkLabel(sidebar, text="Idle", font=ctk.CTkFont(family="Roboto", size=11),
                                          text_color=MUTED)
        self.status_label.grid(row=8, column=0, padx=22, pady=(0, 10), sticky="w")

    def _section_label(self, parent, text, row):
        lbl = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(family="Roboto", size=11, weight="bold"),
                            text_color=ACCENT)
        lbl.grid(row=row, column=0, padx=22, pady=(4, 0), sticky="w")

    # ------------------------------------------------------------------
    def _build_main_area(self):
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="#0F1420")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(1, weight=1)

        title = ctk.CTkLabel(main, text="Decoded Result",
                              font=ctk.CTkFont(family="Roboto", size=18, weight="bold"), text_color="#E2E8F0")
        title.grid(row=0, column=0, columnspan=2, padx=26, pady=(22, 12), sticky="w")

        self.image_panel = ImagePanel(main, "Loaded Stego Image")
        self.image_panel.grid(row=1, column=0, padx=(26, 10), pady=4, sticky="nsew")

        result_frame = ctk.CTkFrame(main, corner_radius=12, fg_color="#1E2433")
        result_frame.grid(row=1, column=1, padx=(10, 26), pady=4, sticky="nsew")
        result_frame.grid_columnconfigure(0, weight=1)
        result_frame.grid_rowconfigure(2, weight=1)

        result_title = ctk.CTkLabel(result_frame, text="Recovered Message",
                                     font=ctk.CTkFont(family="Roboto", size=14, weight="bold"),
                                     text_color="#E2E8F0")
        result_title.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")

        self.result_label = ctk.CTkLabel(
            result_frame, text="—", font=ctk.CTkFont(family="Roboto", size=20, weight="bold"),
            text_color=MUTED, wraplength=360, justify="left"
        )
        self.result_label.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        log_frame = ctk.CTkFrame(main, corner_radius=12, fg_color="#1E2433")
        log_frame.grid(row=2, column=0, columnspan=2, padx=26, pady=(6, 22), sticky="nsew")
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        log_title = ctk.CTkLabel(log_frame, text="Execution Log",
                                  font=ctk.CTkFont(family="Roboto", size=13, weight="bold"), text_color="#E2E8F0")
        log_title.grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")

        self.log_box = ctk.CTkTextbox(log_frame, font=ctk.CTkFont(family="Consolas", size=12),
                                       fg_color="#0F1420", text_color="#A7F3D0", height=160)
        self.log_box.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="nsew")
        self.log_box.configure(state="disabled")

    # ------------------------------------------------------------------
    def log(self, text):
        def _append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", text + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _append)

    def set_status(self, text, color=MUTED):
        self.after(0, lambda: self.status_label.configure(text=text, text_color=color))

    # ------------------------------------------------------------------
    def _on_browse_clicked(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Select stego image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        )
        if not path:
            return

        img = cv2.imread(path)
        if img is None:
            self.file_label.configure(text="Could not read that file as an image.", text_color=DANGER)
            return

        # Normalize to the same working resolution the sender used (shared helper).
        img = standardize_cover(img)

        self.loaded_image = img
        self.loaded_image_path = path
        self.file_label.configure(text=os.path.basename(path), text_color=MUTED)
        self.image_panel.set_image(img)
        self.image_panel.set_caption(os.path.basename(path))
        self.log(f"Loaded image: {path}")

    # ------------------------------------------------------------------
    def _on_decode_clicked(self):
        if self._is_running:
            return
        if self.loaded_image is None:
            self.log("[ERROR] No image loaded. Click 'Browse Image...' first.")
            return

        password = self.pwd_entry.get().strip()
        if not password:
            self.log("[ERROR] Enter the decryption password.")
            return

        self._is_running = True
        self.decode_btn.configure(state="disabled", text="DECODING...")
        self.set_status("Decoding...", ACCENT)
        self.result_label.configure(text="—", text_color=MUTED)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        thread = threading.Thread(
            target=self._decode_worker, args=(password,), daemon=True
        )
        thread.start()

    def _finish(self):
        self._is_running = False
        self.decode_btn.configure(state="normal", text="DECODE")
        self.set_status("Idle", MUTED)

    def _decode_worker(self, password):
        try:
            img = self.loaded_image
            aes_key = hashlib.sha256(password.encode("utf-8")).digest()

            entropy_val = calculate_shannon_entropy(img)["entropy_value"]
            alpha = alpha_for_entropy(entropy_val)
            self.log(f"Image entropy: {entropy_val:.4f}  ->  Alpha = {alpha}")

            # Try every payload length that could physically fit and keep whichever
            # one decodes cleanly. A wrong length fails RS/AES, so it self-validates.
            candidates = candidate_payload_bit_lengths(total_slots_for(img))
            self.log(f"Auto-detecting across {len(candidates)} "
                      f"possible payload size(s): {candidates} bits")

            extractor = DWTSVDExtractor(alpha=alpha, redundancy=SPREAD)
            decoder = PayloadDecoder(redundancy_ratio=RS_RATIO)

            for payload_bit_length in candidates:
                self.log(f"  Trying {payload_bit_length} bits...")
                extracted_bits = extractor.extract(img, payload_bit_length)
                try:
                    recovered_text = decoder.decode(bits_to_bytes(extracted_bits), aes_key)
                except Exception:
                    continue  # wrong length/key for this candidate — try the next

                self.log("STATUS: SUCCESS")
                self.after(0, lambda t=recovered_text: self.result_label.configure(
                    text=t, text_color=SUCCESS))
                self.after(0, lambda: self._finish())
                return

            # No candidate decoded successfully
            self.log("STATUS: FAILED — no payload length produced a valid message.")
            self.log("Possible causes: wrong password, or the image was too "
                      "corrupted by transmission/compression to recover.")
            self.after(0, lambda: self.result_label.configure(
                text="Decoding failed — see log", text_color=DANGER))
            self.after(0, lambda: self._finish())

        except Exception as e:
            self.log(f"STATUS: FAILED — {e}")
            self.after(0, lambda: self.result_label.configure(
                text="Decoding failed — see log", text_color=DANGER))
            self.after(0, lambda: self._finish())


if __name__ == "__main__":
    app = DecoderApp()
    app.mainloop()
