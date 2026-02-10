import string
import argparse

import torch
import torch.backends.cudnn as cudnn
import torch.utils.data
import torch.nn.functional as F

import sys
import os
import cv2
import numpy as np

# Add the training repo to path so we can import its modules
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TRAIN_REPO_PATH = os.path.join(PROJECT_ROOT, 'deep-text-recognition-benchmark')
sys.path.append(TRAIN_REPO_PATH)

from utils import CTCLabelConverter, AttnLabelConverter
from dataset import ResizeNormalize, NormalizePAD, AlignCollate, tensor2im
from model import Model

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def test(opt):
    # Prepare model
    if 'CTC' in opt.Prediction:
        converter = CTCLabelConverter(opt.character)
    else:
        converter = AttnLabelConverter(opt.character)
    
    opt.num_class = len(converter.character)

    if opt.rgb:
        opt.input_channel = 3
    
    model = Model(opt)
    model = torch.nn.DataParallel(model).to(device)

    # Load weights
    print(f'Loading weights from {opt.saved_model}')
    model.load_state_dict(torch.load(opt.saved_model, map_location=device))
    model.eval()

    # Prepare Image
    # We need to process the image similar to 'demo.py'
    AlignCollate_demo = AlignCollate(imgH=opt.imgH, imgW=opt.imgW, keep_ratio_with_pad=opt.PAD)
    
    # Load image
    if not os.path.exists(opt.image_folder):
        print(f"Image not found: {opt.image_folder}")
        return

    # Check if it's a file or folder
    image_paths = []
    if os.path.isdir(opt.image_folder):
        for root, dirs, files in os.walk(opt.image_folder):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    image_paths.append(os.path.join(root, file))
    else:
        image_paths.append(opt.image_folder)

    # Run Inference
    print(f"Running inference on {len(image_paths)} images...")
    
    with torch.no_grad():
        for image_path in image_paths:
            try:
                if opt.rgb:
                    image = Image.open(image_path).convert('RGB')
                else:
                    image = Image.open(image_path).convert('L')
                
                # Transform
                w, h = image.size
                ratio = w / float(h)
                if math.ceil(opt.imgH * ratio) > opt.imgW:
                    resized_w = opt.imgW
                else:
                    resized_w = math.ceil(opt.imgH * ratio)
                
                # Simple resize for demo (copying minimal logic from dataset.py)
                transform = ResizeNormalize((opt.imgW, opt.imgH))
                image_tensor = transform(image)
                image_tensor = image_tensor.unsqueeze(0).to(device)
                
                # Predict
                batch_size = 1
                text_for_pred = torch.LongTensor(batch_size, opt.batch_max_length + 1).fill_(0).to(device)
                
                if 'CTC' in opt.Prediction:
                    preds = model(image_tensor, text_for_pred)
                    preds_size = torch.IntTensor([preds.size(1)] * batch_size)
                    _, preds_index = preds.max(2)
                    # preds_index = preds_index.view(-1)
                    preds_str = converter.decode(preds_index, preds_size)
                else:
                    preds = model(image_tensor, text_for_pred, is_train=False)
                    _, preds_index = preds.max(2)
                    preds_str = converter.decode(preds_index, preds_size)

                print(f'{image_path:20s} => {preds_str[0]}')
            except Exception as e:
                print(f"Error processing {image_path}: {e}")

if __name__ == '__main__':
    # Default Config matching our training
    import math
    from PIL import Image
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--image_folder', required=True, help='path to image_file or image_folder')
    parser.add_argument('--saved_model', required=True, help="path to saved_model to evaluation")
    parser.add_argument('--batch_max_length', type=int, default=25, help='maximum-label-length')
    parser.add_argument('--imgH', type=int, default=32, help='the height of the input image')
    parser.add_argument('--imgW', type=int, default=100, help='the width of the input image')
    parser.add_argument('--rgb', action='store_true', help='use rgb input')
    parser.add_argument('--character', type=str, default='0123456789abcdefghijklmnopqrstuvwxyz', help='character label')
    parser.add_argument('--sensitive', action='store_true', help='for sensitive character mode')
    parser.add_argument('--PAD', action='store_true', help='whether to keep ratio then pad for image resize')
    
    # Model Architecture
    parser.add_argument('--Transformation', type=str, default='TPS', help='Transformation stage. None|TPS')
    parser.add_argument('--FeatureExtraction', type=str, default='ResNet', help='FeatureExtraction stage. VGG|RCNN|ResNet')
    parser.add_argument('--SequenceModeling', type=str, default='BiLSTM', help='SequenceModeling stage. None|BiLSTM')
    parser.add_argument('--Prediction', type=str, default='CTC', help='Prediction stage. CTC|Attn')
    parser.add_argument('--num_fiducial', type=int, default=20, help='number of fiducial points of TPS-STN')
    parser.add_argument('--input_channel', type=int, default=1, help='the number of input channel of Feature extractor')
    parser.add_argument('--output_channel', type=int, default=512, help='the number of output channel of Feature extractor')
    parser.add_argument('--hidden_size', type=int, default=256, help='the size of the LSTM hidden state')

    opt = parser.parse_args()

    # Load characters from file if not provided
    CHAR_FILE = os.path.join(PROJECT_ROOT, 'backend', 'unique_chars.txt')
    if os.path.exists(CHAR_FILE):
        with open(CHAR_FILE, 'r', encoding='utf-8') as f:
             # Preserve space character!
             opt.character = f.read().replace('\n', '')
    
    test(opt)
