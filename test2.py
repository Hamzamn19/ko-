import tensorflow as tf
import tf2onnx
import onnx
import os

# حمّل النموذج
model = tf.keras.models.load_model("mnist_gtx_model.h5")

# احفظه كـ SavedModel أولاً
saved_model_path = "/tmp/mnist_saved_model"
model.export(saved_model_path)

# حوّل من SavedModel لـ ONNX
onnx_model, _ = tf2onnx.convert.from_tflite(saved_model_path) \
    if False else \
    tf2onnx.convert.from_saved_model(saved_model_path)

onnx.save(onnx_model, "mnist_gtx_model.onnx")
print("Done! ✅")
