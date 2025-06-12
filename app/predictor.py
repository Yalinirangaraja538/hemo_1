from PIL import Image
import numpy as np
import tensorflow as tf

# Load the model once (outside function scope to avoid reloading every time)
model = tf.keras.models.load_model(
    r"C:\Users\YaliniRangaraja\OneDrive\Desktop\homodetect\HemoDetect\models\trained_model.h5"
)

def preprocess_image(image_file):
    try:
        image = Image.open(image_file).convert("RGB")  # Ensure 3 channels
        image = image.resize((224, 224))
        image_array = np.array(image) / 255.0  # Normalize
        return np.expand_dims(image_array, axis=0)
    except Exception as e:
        print(f"[ERROR] Failed to preprocess image: {e}")
        raise
def predict_image(image_file):
    try:
        image = preprocess_image(image_file)
        prediction = model.predict(image)[0]

        print(f"[DEBUG] Raw prediction output: {prediction}")  # Debug

        # For single sigmoid output (binary classification)
        if isinstance(prediction, (np.ndarray, list)) and len(prediction) == 1:
            probability = float(prediction[0])
            predicted_class = "Leukemia" if probability >= 0.5 else "Normal"
            confidence = round(probability * 100 if predicted_class == "Leukemia" else (1 - probability) * 100, 2)
        else:
            raise ValueError("Unexpected prediction output shape")

        return predicted_class, confidence

    except Exception as e:
        print(f"[PREDICTION ERROR] {e}")
        return "Error", 0.0
