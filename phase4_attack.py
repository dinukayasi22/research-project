import cv2
import numpy as np

class AttackSimulator:
    @staticmethod
    def simulate_transmission(image: np.ndarray, qf: int = 50, scale: float = 0.5) -> np.ndarray:
        # 1. JPEG Attack
        _, enc = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, qf])
        img = cv2.imdecode(enc, cv2.IMREAD_COLOR)
        
        # 2. Geometric Attack
        h, w = img.shape[:2]
        low = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_LINEAR)
        return cv2.resize(low, (w, h), interpolation=cv2.INTER_LINEAR)
