import cv2
import numpy as np
import math
import os
import shutil
from typing import Union, Dict, List

def calculate_shannon_entropy(image_input: Union[str, np.ndarray], threshold: float = 7.7) -> Dict[str, Union[bool, float]]:

    # 1. Read and validate the image
    if isinstance(image_input, str):
        img = cv2.imread(image_input)
        if img is None:
            raise ValueError(f"Could not load image from path: {image_input}")
    elif isinstance(image_input, np.ndarray):
        img = image_input
        if img.size == 0:
            raise ValueError("Provided image array is empty.")
    else:
        raise ValueError("image_input must be a string (file path) or a numpy.ndarray.")

    # 2. Convert to Grayscale
    if len(img.shape) == 3:
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    elif len(img.shape) == 2:
        gray_img = img
    else:
        raise ValueError("Unsupported image shape. Expected a 2D or 3D array.")
        
    if np.max(gray_img) == np.min(gray_img):
        return {'is_suitable': False, 'entropy_value': 0.0}

    # 3. Calculate the histogram and entropy
    hist = cv2.calcHist([gray_img], [0], None, [256], [0, 256])
    total_pixels = gray_img.shape[0] * gray_img.shape[1]
    probabilities = hist.flatten() / total_pixels
    
    entropy = 0.0
    for p in probabilities:
        if p > 0:
            entropy -= p * math.log2(p)
            
    return {
        'is_suitable': bool(entropy >= threshold),
        'entropy_value': float(entropy)
    }

def process_directory(source_dir: str, target_dir: str, threshold: float = 7.7):

    # Ensure target directory exists
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"Created target directory: {target_dir}")

    # Supported extensions
    valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
    
    # Get all image files
    files = [f for f in os.listdir(source_dir) if f.lower().endswith(valid_extensions)]
    total_files = len(files)
    
    print(f"Found {total_files} images in {source_dir}. Starting analysis (Threshold: {threshold})...")
    
    suitable_count = 0
    
    for i, filename in enumerate(files, 1):
        file_path = os.path.join(source_dir, filename)
        
        try:
            result = calculate_shannon_entropy(file_path, threshold)
            
            if result['is_suitable']:
                shutil.copy2(file_path, os.path.join(target_dir, filename))
                suitable_count += 1
                status = "SUITABLE [Copied]"
            else:
                status = "UNSUITABLE"
                
            # Basic progress log every 10 images or at the end
            if i % 10 == 0 or i == total_files:
                print(f"[{i}/{total_files}] Processing... Current success: {suitable_count}")
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")


    print("ANALYSIS SUMMARY")

    print(f"Total Images Scanned: {total_files}")
    print(f"Suitable Images Found: {suitable_count}")
    print(f"Unsuitable Images: {total_files - suitable_count}")
    print(f"Target Directory: {os.path.abspath(target_dir)}")


if __name__ == "__main__":

    SOURCE_FOLDER = "ALASKA_V2"
    TARGET_FOLDER = "suitable_covers"
    THRESHOLD = 7.7 # You can lower this to 6.8 if you want more images
    
    # Run batch process
    if os.path.exists(SOURCE_FOLDER):
        process_directory(SOURCE_FOLDER, TARGET_FOLDER, THRESHOLD)
    else:
        print(f"Error: Source directory '{SOURCE_FOLDER}' not found.")
