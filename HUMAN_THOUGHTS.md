## Flow
### 1. User upload image
### 2. Front-end preprocess the image with given options (contrast: 1.0, brightness: 1.0, threshold: 80)
### 3. Server splits the image with our own line split logic
### 4. Server extract the texts by OCRing each splitted image

## Core algorithm and variable factors
What if we implement this service for other games? having different font, different style of tooltip image.
I don't think we can keep all the metrics such as
- Front-end preprocess options
- options for generating train model

Then, I want to separate algorithm & metrics into two parts
One is core algorithm works with all the game no matter what kind of font, graph or tooltip style they have.
The other is variable factors we should figure out and set.

# Business strategy
For measuring required variable factors, we need not just script but service initializer that we can get & set the values with data.

*** Example
#### 1. Prepare few tooltip images from a game.
#### 2. Prepare the game font(but maybe in the future we have to consider the situation that it is unable to get the font)
#### 3. execute command like `gametrader init`
#### 4. it will generate the best metrics, options and script for all required process to serve

## History

### After attempt12, telling claude that the training data are consisted of almost faint image and contains unnecessary horizontally blank. ask to find the way how to match real world image


## TODO
- fix tooltip_general


## Notes
During the early attempts, I asked only to implement OCR with game images. After few attempts, I realized that I could improve how they approach to solve the problem by explaining the solution in very human way.
(Also, theey are capable of implementing what humans are thinking)
I requested to analyze the training images to determine which parts are importants and which parts are not.
With this abstract request, they implemented image split logic which worked like human's eyes did.
It started not to recognize unwanted symbols as text and to generate splitting images without unnecessary wide blank.

At this moment(2026-02-15 12:00PM), we are discussing how we categorize each splitted images and extract only required text.
This strategy not only saves the resource of using OCR but also improves accuracy.

Now I'm asking to implement Mabinogi-specified human-eye efficient OCR.

### demand explicitly rather than abstractly. Always find better instruction even you believe you did
Asking to find header sections lead the AI to search certain fixed coordinates or fixed shape.
The header sections were having black square so I indicated to implement the logic finding black squares and told 'they are headers'.

### AI makes me study harder
I've learned about many image process algorithms to understand what AI is doing.
If I want just a result without understanding, All I need to do is just insert command and wait while hitting enter button.
Which would lead me tons of wasted tokens, time and hurting eyeballs.
I's been required to understand what AI's been doing. AI also get lost and I need to guide.

### Don't be afraid even if you don't unserstand what AI is doing at all
Recognizing problems is good. Asking AI to solve the problem is better. Requesting AI to fix the problems with suggestion is the best.
But even when you're lost and don't understand contexts at all, don't be afraid.
- Start conversation with recognizing problems
- Try to understand the smallest part of what AI changes
- Then suggest after you understand the contexts

Keep asking explanation. ELI5 really helps for the complexed logics.

The dialogs with AI really helps me. It makes me feel that it is not just AI who is learning.(10^-10 slower though)

### Shape to pixels. world of mathematics
column projection does not handle the dimensional issue.
- what if we add 2^y value when column projecting? wouldn't be containing the y position?
flood fill does not handle anti aliased pixels
- what if we search broadly across all directions? Not to detect ※ as a dot

### Try to convey the meaning with more understanding how the AI sees the data
You will get monkey's pawed if you ask the AI to find the white colored 'ㄴ' shape from the image.
Offer the coordinates where the shapes are and define the 'white' with RGB values.
AI try to explain difficult things to me with ELI5 strategy. Human also have to try ELIS(explain like I'm Sheldon)

## Commands

### generate segmentation
for f in data/themes/screenshot_*.png; do base=$(basename "$f" .png); outdir="data/segmentation/$base"; mkdir -p "$outdir"; result=$(python3 scripts/test_segmentation.py "$f" "$outdir/" 2>&1 | grep "^Found"); echo "$base: $result"; done

### Try not to be submerged in the swamp of generalizing
Generalizing is important. It would be super happy if I create an oneline game item trade website with only name of title, font and few configs
But there are too many domain specific features that are not able to apply for all game titles.
I'd rather say, specifying and implementing domain specific features are the actual core values of applications.

Google map is good for in general. it shows everyplace in earth. But I'd rather use navermap in korea because it has a lot of korea specific features.

## Simple script

### fuzzy matching
```
from rapidfuzz import fuzz
import re

# Load dictionary
with open('data/dictionary/reforge.txt') as f:
  entries = [line.strip() for line in f if line.strip()]

# Normalize numbers to N
target = '근성 최소 대미지'
norm = re.sub(r'\d+(?:\.\d+)?', 'N', target)

# Find best match
best = max(entries, key=lambda e: fuzz.ratio(norm, re.sub(r'\d+(?:\.\d+)?', 'N', e)))
score = fuzz.ratio(norm, re.sub(r'\d+(?:\.\d+)?', 'N', best))
print(f'{norm} → {best} (score={score:.0f})')

ranked = sorted(entries, key=lambda e: fuzz.ratio(norm, re.sub(r'\d+(?:\.\d+)?', 'N', e)), reverse=True)
for e in ranked[:5]:
  score = fuzz.ratio(norm, re.sub(r'\d+(?:\.\d+)?', 'N', e))
  print(f'{score:.0f}: {e}')
```

### List ocr_correction
```
import sys
sys.path.insert(0, 'backend')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.connector import _build_database_url
from db.models import OcrCorrection

engine = create_engine(_build_database_url())
db = sessionmaker(bind=engine)()

for row in db.query(OcrCorrection).all():
  print(f"#{row.id}  [{row.status}]  {row.original_text!r} → {row.corrected_text!r}  ({row.session_id}/{row.image_filename})")

db.close()
```

## three pixel code
```
blue 74,149,238
skyblue 190,204,254
yellow 255,252,157
```
