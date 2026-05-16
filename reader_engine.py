import cv2
import numpy as np
import os
from typing import List, Tuple, Dict, Any

# Note: We assume tensorflow/keras is installed for model loading
# and cv2 for image processing.

class ReaderEngine:
    def __init__(self, model_path: str = "mnist_gtx_model.h5"):
        self.model_path = model_path
        self.model = None
        
    def load_model(self):
        """Loads the MNIST model lazily."""
        if self.model is None and os.path.exists(self.model_path):
            import tensorflow as tf
            self.model = tf.keras.models.load_model(self.model_path)
        return self.model

    # --- 1. Handwritten OCR System ---

    def preprocess_mnist_style(self, roi: np.ndarray) -> np.ndarray:
        """
        The Secret Sauce: Prepares a handwritten digit ROI for the MNIST model.
        1. Binary Threshold (Otsu)
        2. Morphological Cleanup
        3. Resize to 20x20
        4. Pad to 28x28
        5. Center of Mass at (14, 14)
        """
        # Convert to grayscale if needed
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi

        # 1. Binary Thresholding (Otsu) - Inverting so digit is white on black background
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # 2. Morphological operations (OPEN/CLOSE 2x2)
        kernel = np.ones((2, 2), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # 3. Crop to actual content (bounding box of the digit)
        coords = cv2.findNonZero(binary)
        if coords is None:
            return np.zeros((28, 28), dtype=np.float32)
            
        x, y, w, h = cv2.boundingRect(coords)
        digit_roi = binary[y:y+h, x:x+w]

        # 4. Resize longest side to 20px maintaining aspect ratio
        if w > h:
            new_w = 20
            new_h = int(h * (20 / w))
        else:
            new_h = 20
            new_w = int(w * (20 / h))
        
        # Ensure at least 1px
        new_w, new_h = max(1, new_w), max(1, new_h)
        resized_digit = cv2.resize(digit_roi, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # 5. Place in 28x28 black canvas
        canvas = np.zeros((28, 28), dtype=np.uint8)
        # Initial placement (top-left of center)
        start_x = (28 - new_w) // 2
        start_y = (28 - new_h) // 2
        canvas[start_y:start_y+new_h, start_x:start_x+new_w] = resized_digit

        # 6. The Secret Ingredient: Center of Mass (Mass Centering)
        # Shift the digit so its center of mass is at (14, 14)
        M = cv2.moments(canvas)
        if M["m00"] != 0:
            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]
            
            # Calculate shift needed to bring (cx, cy) to (14, 14)
            shift_x = 14 - cx
            shift_y = 14 - cy
            
            # Apply affine transformation (shift)
            trans_mat = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
            canvas = cv2.warpAffine(canvas, trans_mat, (28, 28))

        # Normalize for model input [0.0, 1.0]
        final_img = canvas.astype(np.float32) / 255.0
        return final_img

    def predict_digit(self, roi: np.ndarray) -> int:
        """Processes and predicts a single digit ROI."""
        model = self.load_model()
        if model is None:
            return -1
            
        processed = self.preprocess_mnist_style(roi)
        # Reshape for model input (Batch, Width, Height, Channel)
        input_data = processed.reshape(1, 28, 28, 1)
        
        prediction = model.predict(input_data, verbose=0)
        return int(np.argmax(prediction))

    # --- 2. Student ID System (Hybrid OMR) ---

    def apply_clahe(self, image: np.ndarray) -> np.ndarray:
        """Normalizes lighting using CLAHE."""
        if len(image.shape) == 3:
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            limg = cv2.merge((cl, a, b))
            return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            return clahe.apply(image)

    def calibrate_luma(self, image: np.ndarray, white_ref_roi: np.ndarray, black_ref_roi: np.ndarray) -> Dict[str, float]:
        """Calculates reference luma values from calibration squares."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        white_val = np.mean(white_ref_roi)
        black_val = np.mean(black_ref_roi)
        grey_val = (white_val + black_val) / 2.0
        
        return {
            "white": white_val,
            "black": black_val,
            "grey": grey_val
        }

    def scan_omr_circle(self, gray_image: np.ndarray, x: int, y: int, radius: int, luma_refs: Dict[str, float]) -> bool:
        """
        Scans an OMR circle using:
        1. Dynamic local search for centering.
        2. 3x Upscaling for precision.
        3. Hybrid Fill Ratio + Luma Ratio formula.
        """
        # Crop 10% inward as per advice to avoid lines
        padding = int(radius * 0.1)
        roi_x = max(0, x - radius + padding)
        roi_y = max(0, y - radius + padding)
        roi_w = (radius * 2) - (2 * padding)
        roi_h = (radius * 2) - (2 * padding)
        
        roi = gray_image[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        
        # 1. Upscale 3x (INTER_CUBIC)
        upscaled = cv2.resize(roi, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        
        # 2. Local Centering: Find the darkest mass nearby
        # (Simplified: find min intensity point and adjust)
        _, _, min_loc, _ = cv2.minMaxLoc(upscaled)
        # In a real system, we'd shift a circular mask to this local minimum
        
        # 3. Calculate Pixel Ratio (Filling)
        # Threshold using the grey reference value
        _, binary = cv2.threshold(upscaled, luma_refs["grey"], 255, cv2.THRESH_BINARY_INV)
        pixel_ratio = np.sum(binary == 255) / binary.size
        
        # 4. Calculate Luma Ratio (Darkness)
        # (Inverse normalized: 1.0 = pitch black, 0.0 = paper white)
        avg_luma = np.mean(upscaled)
        luma_ratio = (luma_refs["white"] - avg_luma) / (luma_refs["white"] - luma_refs["black"])
        luma_ratio = np.clip(luma_ratio, 0, 1)
        
        # 5. The Final Formula: (Pixel_Ratio * 0.4) + (Luma_Ratio * 0.6)
        final_score = (pixel_ratio * 0.4) + (luma_ratio * 0.6)
        
        return final_score > 0.55

    # --- Utility ---

    def crop_roi_safely(self, image: np.ndarray, x: int, y: int, w: int, h: int, margin_pct: float = 0.1) -> np.ndarray:
        """Crops an ROI and shrinks it by margin_pct to avoid outer lines."""
        offset_x = int(w * margin_pct)
        offset_y = int(h * margin_pct)
        
        new_x = x + offset_x
        new_y = y + offset_y
        new_w = w - (2 * offset_x)
        new_h = h - (2 * offset_y)
        
        return image[new_y:new_y+new_h, new_x:new_x+new_w]
