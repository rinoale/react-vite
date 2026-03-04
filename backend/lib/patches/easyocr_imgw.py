"""Utilities for EasyOCR integration with custom model.

Patches EasyOCR's recognize() to:
1. Use fixed imgW from the model yaml (not dynamic per-image width)
2. Skip EasyOCR's first resize in get_image_list() — only crop bounding boxes,
   letting AlignCollate handle the single resize (matching training exactly)

Without this patch, inference applies TWO resizes (cv2.LANCZOS then PIL.BICUBIC)
while training applies only ONE (PIL.BICUBIC). The double resampling introduces
artifacts that degrade recognition accuracy.
"""

import os
from pathlib import Path
import yaml
import numpy as np
from easyocr.recognition import get_text

# Default fallback values when yaml doesn't specify dimensions.
# Normally set by each model's yaml; these are last-resort safety nets.
_DEFAULT_IMG_WIDTH = 600
_DEFAULT_IMG_HEIGHT = 32


def _crop_boxes(horizontal_list, free_list, img_cv_grey):
    """Crop bounding boxes from image WITHOUT resizing.

    Replaces EasyOCR's get_image_list() which crops AND resizes
    (introducing a spurious first resize). AlignCollate inside get_text()
    will handle the single resize, matching the training pipeline.
    """
    y_max, x_max = img_cv_grey.shape
    image_list = []

    for box in horizontal_list:
        x_min = max(0, box[0])
        x_end = min(box[1], x_max)
        y_min = max(0, box[2])
        y_end = min(box[3], y_max)
        crop = img_cv_grey[y_min:y_end, x_min:x_end]
        if crop.shape[0] == 0 or crop.shape[1] == 0:
            continue
        coord = [[x_min, y_min], [x_end, y_min], [x_end, y_end], [x_min, y_end]]
        image_list.append((coord, crop))

    for box in free_list:
        from easyocr.utils import four_point_transform
        rect = np.array(box, dtype="float32")
        crop = four_point_transform(img_cv_grey, rect)
        if crop.shape[0] == 0 or crop.shape[1] == 0:
            continue
        image_list.append((box, crop))

    return image_list


def patch_reader_imgw(reader, models_dir, recog_network):
    """Patch EasyOCR reader for training-matched inference.

    Fixes two mismatches between EasyOCR inference and training:
    1. Uses fixed imgW from yaml (training uses fixed, EasyOCR uses dynamic)
    2. Skips first resize in get_image_list() so only AlignCollate resizes
       (training does single PIL.BICUBIC resize; unpatched EasyOCR does
       cv2.LANCZOS then PIL.BICUBIC — double resampling degrades quality)

    Args:
        reader: EasyOCR Reader instance (already initialized)
        models_dir: Directory containing the yaml config
        recog_network: Name of the custom network config
    """
    yaml_path = os.path.join(models_dir, f'{recog_network}.yaml')
    config = yaml.safe_load(Path(yaml_path).read_text())

    fixed_imgW = config.get('imgW', config.get('network_params', {}).get('imgW', _DEFAULT_IMG_WIDTH))
    imgH = config.get('imgH', _DEFAULT_IMG_HEIGHT)

    def patched_recognize(img_cv_grey, horizontal_list=None, free_list=None,
                          decoder='greedy', beamWidth=5, batch_size=1,
                          workers=0, allowlist=None, blocklist=None, detail=1,
                          rotation_info=None, paragraph=False,
                          contrast_ths=0.1, adjust_contrast=0.5, filter_ths=0.003,
                          y_ths=0.5, x_ths=1.0, reformat=True, output_format='standard'):
        from easyocr.utils import reformat_input

        if reformat:
            img, img_cv_grey = reformat_input(img_cv_grey)

        if allowlist:
            ignore_char = ''.join(set(reader.character) - set(allowlist))
        elif blocklist:
            ignore_char = ''.join(set(blocklist))
        else:
            ignore_char = ''.join(set(reader.character) - set(reader.lang_char))

        if reader.model_lang in ['chinese_tra', 'chinese_sim']:
            decoder = 'greedy'

        if (horizontal_list is None) and (free_list is None):
            y_max, x_max = img_cv_grey.shape
            horizontal_list = [[0, x_max, 0, y_max]]
            free_list = []

        # Crop without resizing — AlignCollate does the single resize
        image_list = _crop_boxes(horizontal_list, free_list or [], img_cv_grey)

        result = get_text(reader.character, imgH, fixed_imgW, reader.recognizer, reader.converter,
                          image_list, ignore_char, decoder, beamWidth, batch_size,
                          contrast_ths, adjust_contrast, filter_ths, workers, reader.device)

        if detail == 0:
            return [item[1] for item in result]
        elif output_format == 'dict':
            return [{'boxes': item[0], 'text': item[1], 'confident': item[2]} for item in result]
        else:
            return result

    reader.recognize = patched_recognize
    return fixed_imgW
