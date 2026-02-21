import cv2
import sys

path = "data/sample_images/lightarmor_sarajin_gwejuk_refined_majestic_for_male.png"
img = cv2.imread(path)
if img is None:
    print("Image not found")
    sys.exit(1)

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
print(f"Shape: {img.shape}")
print(f"Mean Brightness: {gray.mean()}")
print(f"Min: {gray.min()}, Max: {gray.max()}")
