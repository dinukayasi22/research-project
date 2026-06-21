import math
from dataclasses import dataclass
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad
from reedsolo import RSCodec

@dataclass
class PayloadEncoder:

    redundancy_ratio: float = 1.0 # 100% Redundancy for extreme survival

    def encode(self, plaintext: str, aes_key: bytes) -> bytes:
        # AES Encryption
        iv = get_random_bytes(16)
        cipher = AES.new(aes_key, AES.MODE_CBC, iv=iv)
        ciphertext = cipher.encrypt(pad(plaintext.encode('utf-8'), 16))
        
        # Combine IV + Ciphertext
        raw_payload = iv + ciphertext
        
        # Reed-Solomon Encoding
        parity_count = math.ceil(len(raw_payload) * self.redundancy_ratio)
        rs = RSCodec(parity_count)
        return bytes(rs.encode(raw_payload))
