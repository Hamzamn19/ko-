import cv2
import numpy as np
import os
from typing import List, Tuple, Dict, Any, Optional

class ReaderEngine:
    def __init__(self, model_path: str = "mnist_gtx_model.onnx"):
        self.model_path = model_path
        self.session = None
        self.qr_detector = cv2.QRCodeDetector()
        
    def load_model(self):
        if self.session is None and os.path.exists(self.model_path):
            import onnxruntime as ort
            self.session = ort.InferenceSession(self.model_path)
        return self.session

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

    def preprocess_mnist_style(self, roi: np.ndarray) -> np.ndarray:
        """
        DRAMATICALLY IMPROVED MNIST PREPROCESSING:
        Uses Adaptive Thresholding and Precise Mass Centering.
        """
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi

        # 1. Use Adaptive Thresholding to handle shadows
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
        )

        # 2. Cleanup noise
        kernel = np.ones((2, 2), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        # 3. Find bounding box of the digit
        coords = cv2.findNonZero(binary)
        if coords is None:
            return np.zeros((1, 28, 28, 1), dtype=np.float32)
            
        x, y, w, h = cv2.boundingRect(coords)
        digit_roi = binary[y:y+h, x:x+w]

        # 4. Resize maintaining aspect ratio
        if w > h:
            new_w = 20
            new_h = int(h * (20 / w))
        else:
            new_h = 20
            new_w = int(w * (20 / h))
        
        new_w, new_h = max(1, new_w), max(1, new_h)
        resized_digit = cv2.resize(digit_roi, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # 5. Place in 28x28 canvas
        canvas = np.zeros((28, 28), dtype=np.uint8)
        start_x = (28 - new_w) // 2
        start_y = (28 - new_h) // 2
        canvas[start_y:start_y+new_h, start_x:start_x+new_w] = resized_digit

        # 6. Mass Centering (Centering by weight)
        M = cv2.moments(canvas)
        if M["m00"] != 0:
            cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]
            shift_x, shift_y = 14 - cx, 14 - cy
            trans_mat = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
            canvas = cv2.warpAffine(canvas, trans_mat, (28, 28))

        return canvas.astype(np.float32).reshape(1, 28, 28, 1) / 255.0

    def predict_digit(self, roi: np.ndarray) -> int:
        session = self.load_model()
        if session is None: return -1
            
        input_data = self.preprocess_mnist_style(roi)
        input_name = session.get_inputs()[0].name
        prediction = session.run(None, {input_name: input_data})[0]
        
        # If the highest probability is very low, return 0 (no digit)
        if np.max(prediction) < 0.3:
            return 0
            
        return int(np.argmax(prediction))

    def predict_score(self, roi: np.ndarray) -> int:
        """Segments ROI into individual digits and predicts the final combined score."""
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi
            
        # 1. Binarize for contour detection
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
        )
        kernel = np.ones((2, 2), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # 2. Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter and sort contours left-to-right
        h, w = binary.shape
        min_area = 15
        min_h = max(6, int(h * 0.20))
        
        boxes = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if cw * ch >= min_area and ch >= min_h and cw >= 2:
                boxes.append((x, y, cw, ch))
                
        boxes.sort(key=lambda b: b[0]) # sort by x-coordinate (left to right)
        
        if not boxes:
            return 0
            
        # Merge overlapping/very close boxes
        merged = []
        for box in boxes:
            if not merged:
                merged.append(box)
                continue
            px, py, pw, ph = merged[-1]
            x, y, cw, ch = box
            # If horizontal distance is very small (e.g. 3 pixels), merge them (handles disconnected parts)
            if x <= (px + pw + 3):
                nx1 = min(px, x)
                ny1 = min(py, y)
                nx2 = max(px + pw, x + cw)
                ny2 = max(py + ph, y + ch)
                merged[-1] = (nx1, ny1, nx2 - nx1, ny2 - ny1)
            else:
                merged.append(box)

        # We assume max 3 digits for a score (e.g. 100)
        if len(merged) > 3:
            merged = merged[:3]
            
        final_score_str = ""
        for x, y, cw, ch in merged:
            pad = 2
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(w, x + cw + pad)
            y2 = min(h, y + ch + pad)
            
            digit_crop = gray[y1:y2, x1:x2]
            digit_val = self.predict_digit(digit_crop)
            final_score_str += str(digit_val)
            
        return int(final_score_str) if final_score_str else 0

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
