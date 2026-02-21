import cv2
import numpy as np
from PIL import Image
import torch
from torchvision import transforms

class ResizeNormalize(object):
    def __init__(self, size, interpolation=Image.BICUBIC):
        self.size = size
        self.interpolation = interpolation
        self.toTensor = transforms.ToTensor()

    def __call__(self, img):
        img = img.resize(self.size, self.interpolation)
        img = self.toTensor(img)
        img.sub_(0.5).div_(0.5)
        return img

def compare():
    syn_path = 'backend/ocr/train_data/images/syn_000000.png'
    real_path = 'split_result/images/lightarmor_processed_2_line_001.png'
    
    transform = ResizeNormalize((200, 32))
    
    syn_img = Image.open(syn_path).convert('L')
    real_img = Image.open(real_path).convert('L')
    
    syn_tensor = transform(syn_img)
    real_tensor = transform(real_img)
    
    # Save for manual inspection (or just check stats)
    syn_np = (syn_tensor.numpy()[0] + 1) / 2 * 255
    real_np = (real_tensor.numpy()[0] + 1) / 2 * 255
    
    cv2.imwrite('debug_syn_transformed.png', syn_np)
    cv2.imwrite('debug_real_transformed.png', real_np)
    
    print(f"Syn transformed mean: {syn_np.mean():.2f}")
    print(f"Real transformed mean: {real_np.mean():.2f}")
    
compare()
