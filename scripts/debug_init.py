import sys
import os
import torch.nn as nn

sys.path.append(os.path.abspath("backend/models"))

try:
    import custom_mabinogi
    
    print("Test 1: calling Model() with kwargs (EasyOCR style)")
    model1 = custom_mabinogi.Model(
        Transformation='TPS',
        FeatureExtraction='ResNet', 
        SequenceModeling='BiLSTM',
        Prediction='CTC',
        input_channel=1,
        output_channel=512,
        hidden_size=256,
        num_class=50
    )
    print("Success: Model initialized with kwargs")

    print("\nTest 2: calling Model(opt)")
    class Opt:
        def __init__(self):
            self.Transformation = 'TPS'
            self.FeatureExtraction = 'ResNet'
            self.SequenceModeling = 'BiLSTM'
            self.Prediction = 'CTC'
            self.num_fiducial = 20
            self.imgH = 32
            self.imgW = 100
            self.input_channel = 1
            self.output_channel = 512
            self.hidden_size = 256
            self.num_class = 50
            self.batch_max_length = 25
    opt = Opt()
    model2 = custom_mabinogi.Model(opt)
    print("Success: Model initialized with opt")

except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()