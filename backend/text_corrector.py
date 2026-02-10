from rapidfuzz import process, fuzz
import os

class TextCorrector:
    def __init__(self, dictionary_path=None):
        self.dictionary = []
        if dictionary_path and os.path.exists(dictionary_path):
            self.load_dictionary(dictionary_path)
        else:
            print(f"Warning: Dictionary not found at {dictionary_path}")

    def load_dictionary(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            # Filter out empty lines and strip whitespace
            self.dictionary = [line.strip() for line in f if line.strip()]
        print(f"TextCorrector loaded {len(self.dictionary)} entries.")

    def correct(self, text, cutoff_score=80):
        """
        Finds the best match in the dictionary.
        Returns: (corrected_text, score)
        If no match above cutoff_score, returns (original_text, 0)
        """
        if not text or not self.dictionary:
            return text, 0

        # process.extractOne returns (match, score, index)
        # Using token_sort_ratio handles mixed word order better, 
        # but for exact game strings, ratio or weighted_ratio is often better.
        result = process.extractOne(text, self.dictionary, scorer=fuzz.ratio)
        
        if result:
            match, score, _ = result
            if score >= cutoff_score:
                return match, score
        
        return text, 0

# Singleton instance setup (can be initialized in main.py)
# corrector = TextCorrector()
