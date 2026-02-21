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

## Commands

### generate segmentation
for f in data/themes/screenshot_*.png; do base=$(basename "$f" .png); outdir="data/segmentation/$base"; mkdir -p "$outdir"; result=$(python3 scripts/test_segmentation.py "$f" "$outdir/" 2>&1 | grep "^Found"); echo "$base: $result"; done

### Try not to be submerged in the swamp of generalizing
Generalizing is important. It would be super happy if I create an oneline game item trade website with only name of title, font and few configs
But there are too many domain specific features that are not able to apply for all game titles.
I'd rather say, specifying and implementing domain specific features are the actual core values of applications.

Google map is good for in general. it shows everyplace in earth. But I'd rather use navermap in korea because it has a lot of korea specific features.
