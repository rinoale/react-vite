import os
import lmdb
import cv2
import numpy as np

def checkImageIsValid(imageBin):
    if imageBin is None:
        return False
    imageBuf = np.frombuffer(imageBin, dtype=np.uint8)
    img = cv2.imdecode(imageBuf, cv2.IMREAD_GRAYSCALE)
    imgH, imgW = img.shape[0], img.shape[1]
    if imgH * imgW == 0:
        return False
    return True

def writeCache(env, cache):
    with env.begin(write=True) as txn:
        for k, v in cache.items():
            txn.put(k.encode(), v)

def createDataset(inputPath, outputPath):
    """
    Create LMDB dataset for training.
    inputPath: directory containing 'images' and 'labels' subdirectories.
    outputPath: directory to save the LMDB database.
    """
    os.makedirs(outputPath, exist_ok=True)
    env = lmdb.open(outputPath, map_size=1099511627776) # 1TB
    cache = {}
    cnt = 1
    
    image_dir = os.path.join(inputPath, 'images')
    label_dir = os.path.join(inputPath, 'labels')
    
    # List all label files
    label_files = sorted([f for f in os.listdir(label_dir) if f.endswith('.txt')])
    
    print(f"Found {len(label_files)} samples.")
    
    for i, label_file in enumerate(label_files):
        # Get filename without extension
        base_name = os.path.splitext(label_file)[0]
        image_file = base_name + ".png" # Assuming png
        
        image_path = os.path.join(image_dir, image_file)
        label_path = os.path.join(label_dir, label_file)
        
        if not os.path.exists(image_path):
            print(f"Warning: Image {image_file} not found. Skipping.")
            continue
            
        with open(image_path, 'rb') as f:
            imageBin = f.read()
            
        if not checkImageIsValid(imageBin):
            print(f"Warning: Image {image_file} is not valid. Skipping.")
            continue
            
        with open(label_path, 'r', encoding='utf-8') as f:
            label = f.read().strip()
            
        if not label:
             print(f"Warning: Label empty for {label_file}. Skipping.")
             continue

        imageKey = 'image-%09d' % cnt
        labelKey = 'label-%09d' % cnt
        cache[imageKey] = imageBin
        cache[labelKey] = label.encode()
        
        if cnt % 1000 == 0:
            writeCache(env, cache)
            cache = {}
            print(f'Written {cnt} / {len(label_files)}')
            
        cnt += 1
        
    nSamples = cnt - 1
    cache['num-samples'] = str(nSamples).encode()
    writeCache(env, cache)
    print(f'Created dataset with {nSamples} samples')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='Input directory containing images/ and labels/')
    parser.add_argument('--output', required=True, help='Output LMDB directory')
    args = parser.parse_args()
    
    createDataset(args.input, args.output)
