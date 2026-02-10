try:
    from easyocr.model import Model
    print("Success importing Model from easyocr.model")
except ImportError as e:
    print(f"Failed: {e}")

try:
    import easyocr.model
    print("Success importing easyocr.model")
except ImportError as e:
    print(f"Failed: {e}")
