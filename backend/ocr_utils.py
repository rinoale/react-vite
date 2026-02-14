"""Utilities for EasyOCR integration with custom model.

Patches EasyOCR's recognize() to use a fixed imgW from the model yaml,
instead of computing dynamic max_width per image. This ensures inference
uses the same imgW as training, eliminating squash factor mismatch.
"""

import os
import yaml
from easyocr.recognition import get_text
from easyocr.utils import get_image_list


def patch_reader_imgw(reader, models_dir, recog_network='custom_mabinogi'):
    """Patch EasyOCR reader to use fixed imgW from yaml during inference.

    EasyOCR computes dynamic max_width per image based on aspect ratio,
    which varies wildly (576-1056px for our data). Training uses a fixed
    imgW, so inference must match.

    Args:
        reader: EasyOCR Reader instance (already initialized)
        models_dir: Directory containing the yaml config
        recog_network: Name of the custom network config
    """
    yaml_path = os.path.join(models_dir, f'{recog_network}.yaml')
    with open(yaml_path, 'r', encoding='utf-8') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    fixed_imgW = config.get('imgW', config.get('network_params', {}).get('imgW', 600))
    imgH = config.get('imgH', 32)

    original_recognize = reader.recognize

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

        # Process each box with FIXED imgW instead of dynamic max_width
        result = []
        for bbox in horizontal_list:
            h_list = [bbox]
            f_list = []
            image_list, _dynamic_width = get_image_list(h_list, f_list, img_cv_grey, model_height=imgH)
            result0 = get_text(reader.character, imgH, fixed_imgW, reader.recognizer, reader.converter,
                               image_list, ignore_char, decoder, beamWidth, batch_size,
                               contrast_ths, adjust_contrast, filter_ths, workers, reader.device)
            result += result0
        for bbox in free_list:
            h_list = []
            f_list = [bbox]
            image_list, _dynamic_width = get_image_list(h_list, f_list, img_cv_grey, model_height=imgH)
            result0 = get_text(reader.character, imgH, fixed_imgW, reader.recognizer, reader.converter,
                               image_list, ignore_char, decoder, beamWidth, batch_size,
                               contrast_ths, adjust_contrast, filter_ths, workers, reader.device)
            result += result0

        if detail == 0:
            return [item[1] for item in result]
        elif output_format == 'dict':
            return [{'boxes': item[0], 'text': item[1], 'confident': item[2]} for item in result]
        else:
            return result

    reader.recognize = patched_recognize
    return fixed_imgW
