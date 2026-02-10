import sys
import os
# Add backend to path so we can import the splitter
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from tooltip_line_splitter import TooltipLineSplitter
import easyocr
import shutil

def test_pipeline():
    image_path = "data/sample_images/lightarmor_sarajin_gwejuk_refined_majestic_for_male.png"
    temp_dir = "test_output"
    
    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        return

    print(f"Testing OCR on: {image_path}")
    
    # Initialize Splitter
    splitter = TooltipLineSplitter(output_dir=temp_dir)
    
    # Initialize EasyOCR
    print("Loading EasyOCR model...")
    # Setup paths for custom model
    BASE_DIR = os.path.join(os.getcwd(), 'backend')
    MODELS_DIR = os.path.join(BASE_DIR, 'models')
    
    reader = easyocr.Reader(
        ['ko'], 
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_mabinogi'
    )
    
    # 1. Process Image
    print("Splitting lines...")
    # save_visualization=True so we can check the debug image later if needed
    extracted_lines = splitter.process_image(image_path, save_visualization=True)
    
    print(f"Detected {len(extracted_lines)} lines.")
    
    # 2. OCR
    print("\n--- Extracted Text ---")
    for i, line in enumerate(extracted_lines):
        # Check image stats
        import cv2
        img = cv2.imread(line['path'])
        print(f"Line {i+1} Stats: Shape={img.shape}, Mean={img.mean():.1f}")
        
        # Run OCR with details
        results = reader.readtext(line['path'])
        if not results:
             print(f"  Result: [NO TEXT DETECTED]")
        for (bbox, text, prob) in results:
             print(f"  Result: '{text}' (Conf: {prob:.4f})")
        
    print("\n----------------------")
    print(f"Check {temp_dir} for visualization images.")

if __name__ == "__main__":
    test_pipeline()