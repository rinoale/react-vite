---
name: ground-truth-generator
description: Generates high-fidelity ground truth text for OCR training by visually transcribing images. Includes strict protocols for state tracking and logic integrity.
---

# Ground Truth Generator

This skill guides the agent in creating accurate ground truth text files from images. This is essential for training and validating OCR models.

## Core Mandates

### 1. Integrity of Stable Dependencies
- **NO BLIND MODIFICATIONS**: If a script (e.g., `tooltip_line_splitter.py`) is reported as "working" in one context (like a test script) but fails in a new script you wrote, **you must assume the bug is in your new code**. 
- **Debug the Integration**: Compare the inputs (File Path vs. Image Array) and method calls between the working and failing contexts before even considering a change to production logic.

### 2. Mandatory Verification Chain (Real World Batches)
To prevent index drift and hallucinations during line-by-line transcription:
1. **List First**: Call `list_directory` on the `images/` folder to confirm the exact range and filenames.
2. **Explicit Mapping**: For every transcription batch, strictly follow this format in your thought process and output:
   - `Reading [exact_filename]: [Visual content]`
   - `Saving [exact_filename.txt]: [Content]`
3. **Save Verification**: After writing a batch of labels, you **MUST** verify the files exist on disk using `list_directory` before declaring the batch complete or moving to the next.

### 3. Visual Accuracy & Hallucination Guard
- **Individual Reads**: You must call `read_file` for **EVERY** single image. 
- **No Guessing**: Never "skip ahead" or guess text based on previous lines, general game knowledge, or overall tooltip context.
- **Verbatim**: Transcribe exactly as pixels appear. Prioritize visual evidence over "what it should say."

---

## Workflow

### 1. File Accessibility
- Try to read the file path directly.
- If blocked by ignore patterns, copy the image to the project root with a temporary name, read it, and then delete the copy.

### 2. Real World Image Pipeline
1. **Preprocessing & Splitting**: Run the preparation script to mimic frontend processing.
   ```bash
   python3 scripts/prepare_real_world_data.py <path_to_image> --output real_world_data
   ```
2. **Directory Inspection**: Call `list_directory` on `real_world_data/<image_name>/images/`.
3. **Transcription Batching**:
   - Call `read_file` for a batch (e.g., 5 files).
   - Write corresponding `.txt` files to `real_world_data/<image_name>/labels/`.
   - **Verify** existence of labels with `list_directory`.

## Example Usage (Correct Protocol)

**User**: "Process real world image `data/sample_images/item.png`."

**Agent Action**:
1. `python3 scripts/prepare_real_world_data.py data/sample_images/item.png --output real_world_data`
2. `list_directory dir_path="real_world_data/item/images/"`
3. `read_file` (Batch 1-5)
4. `write_file` (Labels 1-5)
5. `list_directory dir_path="real_world_data/item/labels/"` (Verify)
