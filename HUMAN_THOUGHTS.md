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
