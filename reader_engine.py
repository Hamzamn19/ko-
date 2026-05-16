import cv2
import numpy as np
import os
from typing import List, Tuple, Dict, Any, Optional

from handwriting_ocr import get_handwriting_score_recognizer

class ReaderEngine:
    def __init__(self, model_path: str = "mnist_gtx_model.onnx"):
        self.model_path = model_path
        self.qr_detector = cv2.QRCodeDetector()
        self.hw_recognizer = get_handwriting_score_recognizer()
        
    def align_image(self, image: np.ndarray) -> np.ndarray:
        """
        Attempts to align the paper using contour detection.
        Useful for mobile phone photos.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blur, 75, 200)
        
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return image
            
        # Get largest contour assuming it's the paper
        cnt = sorted(contours, key=cv2.contourArea, reverse=True)[0]
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        
        if len(approx) == 4:
            # Perspective Transform (Simplified for prototype)
            return image # In a real system, we'd wrap this to a 2100x2970 canvas
        
        return image

    def detect_qr_code(self, image: np.ndarray) -> Tuple[Optional[str], Optional[np.ndarray]]:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        data, points, _ = self.qr_detector.detectAndDecode(gray)
        return data, points

    def predict_score(self, roi: np.ndarray, max_points: int = 100) -> int:
        """
        OFFICIAL NOVAVISION REDIRECT:
        Sends the ROI to the external Inference Server.
        """
        import requests
        
        # URL of your NovaVision server (assuming it's on the host machine or another container)
        # We'll try to reach it at host.docker.internal if in Docker, otherwise localhost
        url = os.getenv("NOVAVISION_URL", "http://host.docker.internal:8000/predict")
        
        try:
            # Convert ROI to PNG buffer
            _, img_encoded = cv2.imencode(".png", roi)
            files = {"file": ("snippet.png", img_encoded.tobytes(), "image/png")}
            params = {"max_points": max_points}
            
            print(f"[Reader] Forwarding snippet to NovaVision: {url}")
            response = requests.post(url, files=files, params=params, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                return int(result.get("score", 0))
            else:
                print(f"[Reader] NovaVision Error: {response.status_code}")
                return 0
        except Exception as e:
            print(f"[Reader] Connection to NovaVision failed: {e}")
            # Fallback to local if server is down (optional, but good for stability)
            result = self.hw_recognizer.recognize_score(roi, max_points=max_points)
            return int(result.get("score", 0))

    def scan_omr_circle(self, gray_image: np.ndarray, x: int, y: int, radius: int, luma_refs: Dict[str, float]) -> Dict[str, float]:
        """
        Advanced OMR scanning (The Secret Sauce):
        1. Dynamic local search for centering.
        2. 3x Upscaling with INTER_CUBIC.
        3. Adaptive Thresholding within the bubble.
        4. Hybrid scoring (Pixel Ratio + Luma Ratio).
        """
        # Crop 15% inward to avoid bubble edges
        padding = int(radius * 0.15)
        roi_x = max(0, x - radius + padding)
        roi_y = max(0, y - radius + padding)
        roi_w = (radius * 2) - (2 * padding)
        roi_h = (radius * 2) - (2 * padding)
        
        roi = gray_image[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        if roi.size == 0:
            return {"score": 0.0, "pixel_ratio": 0.0, "luma_ratio": 0.0}
            
        # 1. Upscale 3x for precision
        upscaled = cv2.resize(roi, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        
        # 2. Stable Centering: Find the center of mass (Centroid) of the dark area
        # Use the adaptive binary mask to find where the actual ink is
        binary_for_centroid = cv2.adaptiveThreshold(
            upscaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 21, 8
        )
        
        M = cv2.moments(binary_for_centroid)
        if M["m00"] > 0:
            # Centroid in upscaled coordinates
            centroid_x_upscaled = M["m10"] / M["m00"]
            centroid_y_upscaled = M["m01"] / M["m00"]
            
            # Offset from the expected center of the upscaled image
            center_upscaled = (upscaled.shape[1] / 2.0, upscaled.shape[0] / 2.0)
            offset_x = (centroid_x_upscaled - center_upscaled[0]) / 3.0
            offset_y = (centroid_y_upscaled - center_upscaled[1]) / 3.0
            
            # Final adjusted global coordinates
            adj_x = x + offset_x
            adj_y = y + offset_y
        else:
            adj_x, adj_y = x, y
        
        # 3. Calculate Luma Ratio (Darkness)
        avg_luma = np.mean(upscaled)
        luma_ratio = (luma_refs["white"] - avg_luma) / (luma_refs["white"] - luma_refs["black"])
        luma_ratio = np.clip(luma_ratio, 0, 1)
        
        # 4. Adaptive Thresholding
        binary = cv2.adaptiveThreshold(
            upscaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 21, 8
        )
        
        # Circular mask to focus on the center
        h, w = binary.shape
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, (w//2, h//2), int(w/2 * 0.9), 255, -1)
        binary = cv2.bitwise_and(binary, mask)
        
        pixel_ratio = np.sum(binary == 255) / np.sum(mask == 255)
        
        # 5. The Final Formula: (Pixel_Ratio * 0.4) + (Luma_Ratio * 0.6)
        final_score = (pixel_ratio * 0.4) + (luma_ratio * 0.6)
        
        return {
            "score": float(final_score),
            "pixel_ratio": float(pixel_ratio),
            "luma_ratio": float(luma_ratio),
            "adj_center": (float(adj_x), float(adj_y))
        }

    def crop_roi_safely(self, image: np.ndarray, x: int, y: int, w: int, h: int, margin_pct: float = 0.15) -> np.ndarray:
        """Increased margin to avoid box lines which confuse MNIST."""
        ox, oy = int(w * margin_pct), int(h * margin_pct)
        return image[y+oy:y+h-oy, x+ox:x+w-ox]
