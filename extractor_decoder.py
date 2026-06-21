from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from reedsolo import RSCodec, ReedSolomonError
from dataclasses import dataclass

@dataclass
class PayloadDecoder:
    """
    Self-Healing Pipeline: RS Repair and AES Decryption.
    """
    redundancy_ratio: float = 1.0

    def decode(self, robust_payload: bytes, aes_key: bytes) -> str:
        # 1. Determine parity
        total_len = len(robust_payload)
        data_len = round(total_len / (1 + self.redundancy_ratio))
        parity_count = total_len - data_len
        
        # 2. RS Repair
        rs = RSCodec(parity_count)
        try:
            repaired_data = rs.decode(robust_payload)[0]
        except ReedSolomonError:
            raise ReedSolomonError("Corruption exceeds healing capacity.")

        # 3. Decrypt
        iv = repaired_data[:16]
        ciphertext = repaired_data[16:]
        cipher = AES.new(aes_key, AES.MODE_CBC, iv=iv)
        return unpad(cipher.decrypt(ciphertext), 16).decode('utf-8')
