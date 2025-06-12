from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import numpy as np

# Load model only once
model = load_model('models/trained_model.h5')
classes = ['Normal', 'Leukemia']

def preprocess_image(img_path):
    """Preprocess an image for prediction (resizing + normalization)."""
    img = image.load_img(img_path, target_size=(224, 224))
    img_array = image.img_to_array(img) / 255.0
    return img_array

def predict_image(img_path):
    """Predict class from image path directly."""
    img_array = preprocess_image(img_path)
    img_array = np.expand_dims(img_array, axis=0)
    prediction = model.predict(img_array)
    return classes[np.argmax(prediction)]

def predict(image_array):
    """Predict class from preprocessed image array."""
    img_array = np.expand_dims(image_array, axis=0)
    prediction = model.predict(img_array)[0]
    predicted_class = classes[np.argmax(prediction)]  # Return label not number
    confidence = np.max(prediction) * 100  # Confidence in percentage
    return predicted_class, confidence
