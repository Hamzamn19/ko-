"""
handwriting_ocr.py — Numeric handwriting score recognizer for classic sheets.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

try:
    import tensorflow as tf
except Exception:  # pragma: no cover - optional dependency
    tf = None


class HandwritingScoreRecognizer:
    def __init__(self):
        self.review_threshold = float(os.getenv("HANDWRITING_REVIEW_THRESHOLD", "0.20"))
        self.max_digits = int(os.getenv("HANDWRITING_MAX_DIGITS", "3"))
        self.engine = "synthetic-knn"
        self.tf_model = None
        self.knn = None

        model_path = Path(os.getenv("HANDWRITING_MODEL_PATH", "models/mnist_gtx_model.h5"))
        if tf is not None and model_path.exists():
            try:
                self.tf_model = tf.keras.models.load_model(str(model_path))
                self.engine = "tensorflow"
                print(f"[HW-OCR] Loaded TensorFlow model: {model_path}")
            except Exception as exc:
                print(f"[HW-OCR] Failed to load TensorFlow model ({model_path}): {exc}")

        if self.tf_model is None:
            self.knn = self._build_synthetic_knn()
            print("[HW-OCR] Using synthetic KNN fallback model")

    def _build_synthetic_knn(self):
        fonts = [
            cv2.FONT_HERSHEY_SIMPLEX,
            cv2.FONT_HERSHEY_DUPLEX,
            cv2.FONT_HERSHEY_TRIPLEX,
            cv2.FONT_HERSHEY_COMPLEX,
        ]
        scales = [0.75, 0.9, 1.05, 1.2]
        thicknesses = [1, 2, 3]
        shifts = [-2, -1, 0, 1, 2]

        samples: List[np.ndarray] = []
        labels: List[int] = []
        canvas_size = 28
        for digit in range(10):
            text = str(digit)
            for font in fonts:
                for scale in scales:
                    for thickness in thicknesses:
                        for dx in shifts:
                            for dy in shifts:
                                canvas = np.zeros((canvas_size, canvas_size), dtype=np.uint8)
                                (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
                                x = max(0, min(canvas_size - tw - 1, (canvas_size - tw) // 2 + dx))
                                y = max(th + 1, min(canvas_size - baseline - 1, (canvas_size + th) // 2 + dy))
                                cv2.putText(
                                    canvas,
                                    text,
                                    (x, y),
                                    font,
                                    scale,
                                    255,
                                    thickness,
                                    cv2.LINE_AA,
                                )
                                samples.append((canvas.astype(np.float32) / 255.0).reshape(-1))
                                labels.append(digit)

        knn = cv2.ml.KNearest_create()
        train_data = np.asarray(samples, dtype=np.float32)
        train_labels = np.asarray(labels, dtype=np.float32)
        knn.train(train_data, cv2.ml.ROW_SAMPLE, train_labels)
        return knn

    def _segment_digits(self, roi: np.ndarray) -> List[np.ndarray]:
        if roi.ndim == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi.copy()

        if gray.size == 0:
            return []

        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        bw = cv2.morphologyEx(
            bw,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
        )
        bw = cv2.morphologyEx(
            bw,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
        )

        contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h, w = bw.shape
        min_area = max(8, int((h * w) * 0.01))
        min_h = max(6, int(h * 0.30))
        boxes: List[Tuple[int, int, int, int]] = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            area = cw * ch
            if area < min_area or ch < min_h or cw < 2:
                continue
            boxes.append((x, y, cw, ch))

        boxes.sort(key=lambda b: b[0])
        if not boxes:
            return []

        merged: List[Tuple[int, int, int, int]] = []
        for box in boxes:
            if not merged:
                merged.append(box)
                continue
            px, py, pw, ph = merged[-1]
            x, y, cw, ch = box
            if x <= (px + pw + 2):
                nx1 = min(px, x)
                ny1 = min(py, y)
                nx2 = max(px + pw, x + cw)
                ny2 = max(py + ph, y + ch)
                merged[-1] = (nx1, ny1, nx2 - nx1, ny2 - ny1)
            else:
                merged.append(box)

        if len(merged) > self.max_digits:
            merged = merged[: self.max_digits]

        digits: List[np.ndarray] = []
        for x, y, cw, ch in merged:
            pad = 2
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(w, x + cw + pad)
            y2 = min(h, y + ch + pad)
            digit_crop = bw[y1:y2, x1:x2]
            if digit_crop.size == 0:
                continue

            # MNIST preprocessing: scale max dimension to 20 pixels
            crop_h, crop_w = digit_crop.shape
            scale_factor = 20.0 / max(crop_h, crop_w)
            new_w = max(1, int(crop_w * scale_factor))
            new_h = max(1, int(crop_h * scale_factor))
            resized_crop = cv2.resize(digit_crop, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # Center it inside a 28x28 canvas
            canvas = np.zeros((28, 28), dtype=np.uint8)
            y_offset = (28 - new_h) // 2
            x_offset = (28 - new_w) // 2
            canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized_crop
            
            # Optional: Calculate center of mass to perfectly center like actual MNIST
            M = cv2.moments(canvas)
            if M['m00'] > 0:
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])
                shift_x = 14 - cx
                shift_y = 14 - cy
                M_trans = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
                canvas = cv2.warpAffine(canvas, M_trans, (28, 28))

            digits.append(canvas)

        return digits

    def _predict_digit(self, digit_img: np.ndarray) -> Tuple[int, float]:
        sample = digit_img.astype(np.float32) / 255.0
        if self.tf_model is not None:
            logits = self.tf_model(sample.reshape(1, 28, 28, 1), training=False)
            probs = np.asarray(logits).reshape(-1)
            if probs.min() < 0.0 or probs.max() > 1.0:
                exp = np.exp(probs - np.max(probs))
                probs = exp / np.sum(exp)
            digit = int(np.argmax(probs))
            confidence = float(probs[digit])
            return digit, max(0.0, min(1.0, confidence))

        vec = sample.reshape(1, -1).astype(np.float32)
        _, result, neighbors, dist = self.knn.findNearest(vec, k=3)
        digit = int(result[0][0])
        neighbor_digits = neighbors[0].astype(int)
        agreement = float(np.mean(neighbor_digits == digit))
        mean_dist = float(np.mean(dist[0])) if dist.size else 0.0
        distance_score = float(np.exp(-mean_dist / 8.0))
        confidence = (0.6 * agreement) + (0.4 * distance_score)
        return digit, max(0.0, min(1.0, confidence))

    def recognize_score(self, roi: np.ndarray, max_points: int) -> dict:
        if roi is None or roi.size == 0:
            return {
                "score": 0,
                "digits": [],
                "confidence": 0.0,
                "uncertainty": 1.0,
                "manual_review_required": True,
                "engine": self.engine,
                "reason": "empty-roi",
            }

        digit_imgs = self._segment_digits(roi)
        if not digit_imgs:
            return {
                "score": 0,
                "digits": [],
                "confidence": 0.0,
                "uncertainty": 1.0,
                "manual_review_required": True,
                "engine": self.engine,
                "reason": "no-digit-detected",
            }

        predictions = [self._predict_digit(img) for img in digit_imgs]
        digits = [int(d) for d, _ in predictions]
        confidences = [float(c) for _, c in predictions]

        raw_score = int("".join(str(d) for d in digits)) if digits else 0
        max_pts = max(0, int(max_points or 0))
        score = max(0, min(raw_score, max_pts)) if max_pts > 0 else max(0, raw_score)

        confidence = float(np.mean(confidences)) if confidences else 0.0
        uncertainty = max(0.0, min(1.0, 1.0 - confidence))
        manual_review_required = uncertainty > self.review_threshold

        return {
            "score": int(score),
            "raw_score": int(raw_score),
            "digits": digits,
            "confidence": round(confidence, 4),
            "uncertainty": round(uncertainty, 4),
            "manual_review_required": manual_review_required,
            "engine": self.engine,
            "reason": "ok",
        }


_RECOGNIZER: HandwritingScoreRecognizer | None = None


def get_handwriting_score_recognizer() -> HandwritingScoreRecognizer:
    global _RECOGNIZER
    if _RECOGNIZER is None:
        _RECOGNIZER = HandwritingScoreRecognizer()
    return _RECOGNIZER

