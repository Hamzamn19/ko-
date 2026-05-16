import cv2
import numpy as np
import os
from typing import List, Tuple, Dict, Any, Optional

class ReaderEngine:
    def __init__(self, model_path: str = "mnist_gtx_model.onnx"):
        self.model_path = model_path
        self.session = None
        self.qr_detector = cv2.QRCodeDetector()
        print(f"[ReaderEngine] Initialized with model path: {self.model_path}")
        
    def load_model(self):
        """Loads the MNIST ONNX model lazily."""
        if self.session is None:
            if os.path.exists(self.model_path):
                try:
                    import onnxruntime as ort
                    self.session = ort.InferenceSession(self.model_path)
                    print(f"[ReaderEngine] Successfully loaded ONNX model: {self.model_path}")
                except Exception as e:
                    print(f"[ReaderEngine] Failed to load ONNX model: {e}")
            else:
                print(f"[ReaderEngine] Model file NOT FOUND: {self.model_path}")
        return self.session

    def detect_qr_code(self, image: np.ndarray) -> Optional[str]:
        """Detects and decodes the QR code from the image."""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
            
        data, points, _ = self.qr_detector.detectAndDecode(gray)
        if data:
            print(f"[ReaderEngine] Detected QR Code: {data}")
            return data
        print("[ReaderEngine] No QR Code detected in image")
        return None

    # --- 1. Handwritten OCR System ---

    def preprocess_mnist_style(self, roi: np.ndarray) -> np.ndarray:
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kernel = np.ones((2, 2), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        coords = cv2.findNonZero(binary)
        if coords is None:
            return np.zeros((1, 28, 28, 1), dtype=np.float32)
            
        x, y, w, h = cv2.boundingRect(coords)
        digit_roi = binary[y:y+h, x:x+w]

        if w > h:
            new_w, new_h = 20, int(h * (20 / w))
        else:
            new_h, new_w = 20, int(w * (20 / h))
        
        new_w, new_h = max(1, new_w), max(1, new_h)
        resized_digit = cv2.resize(digit_roi, (new_w, new_h), interpolation=cv2.INTER_AREA)

        canvas = np.zeros((28, 28), dtype=np.uint8)
        start_x, start_y = (28 - new_w) // 2, (28 - new_h) // 2
        canvas[start_y:start_y+new_h, start_x:start_x+new_w] = resized_digit

        M = cv2.moments(canvas)
        if M["m00"] != 0:
            cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]
            shift_x, shift_y = 14 - cx, 14 - cy
            trans_mat = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
            canvas = cv2.warpAffine(canvas, trans_mat, (28, 28))

        return canvas.astype(np.float32).reshape(1, 28, 28, 1) / 255.0

    def predict_digit(self, roi: np.ndarray) -> int:
        session = self.load_model()
        if session is None:
            return -1
            
        input_data = self.preprocess_mnist_style(roi)
        input_name = session.get_inputs()[0].name
        prediction = session.run(None, {input_name: input_data})[0]
        return int(np.argmax(prediction))

    # --- 2. Student ID System (Hybrid OMR) ---

    def scan_omr_circle(self, gray_image: np.ndarray, x: int, y: int, radius: int, luma_refs: Dict[str, float]) -> bool:
        padding = int(radius * 0.1)
        roi_x = max(0, x - radius + padding)
        roi_y = max(0, y - radius + padding)
        roi_w, roi_h = (radius * 2) - (2 * padding), (radius * 2) - (2 * padding)
        
        roi = gray_image[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        if roi.size == 0: return False
        
        upscaled = cv2.resize(roi, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        _, binary = cv2.threshold(upscaled, luma_refs["grey"], 255, cv2.THRESH_BINARY_INV)
        pixel_ratio = np.sum(binary == 255) / binary.size
        
        avg_luma = np.mean(upscaled)
        luma_ratio = (luma_refs["white"] - avg_luma) / (luma_refs["white"] - luma_refs["black"] + 0.001)
        luma_ratio = np.clip(luma_ratio, 0, 1)
        
        return ((pixel_ratio * 0.4) + (luma_ratio * 0.6)) > 0.55

    def crop_roi_safely(self, image: np.ndarray, x: int, y: int, w: int, h: int, margin_pct: float = 0.1) -> np.ndarray:
        ox, oy = int(w * margin_pct), int(h * margin_pct)
        return image[y+oy:y+h-oy, x+ox:x+w-ox]
