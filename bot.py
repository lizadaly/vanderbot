import urllib
import pprint
import json
import random
import sys
import tweepy
import tempfile
import os.path
import re
import shutil
import pprint
from colormath.color_objects import sRGBColor, LabColor
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000

from PIL import Image, ImageFont, ImageDraw

from secret import *
from config import *

from colors import *
from utils import *

def _auth():
    """Authorize the service with Twitter"""
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.secure = True
    auth.set_access_token(access_token, access_token_secret)
    return tweepy.API(auth)

def post_tweet(tweet, card, author):
    """Post to twitter with the given tweet and card image as attachment"""
    byline = '—' + author['name']
    with tempfile.TemporaryFile() as fp:
        card.save(fp, format='PNG')

        print("Posting message {}".format(tweet))
        api.update_with_media('quote.png', status=tweet + byline, file=fp)

def generate_image(tweet, author):
    """Given a tweet and a random author, generate a new twitter card"""
    im = Image.open('images/' + random.choice(author['images']))
    card = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), color=(0,0,0))
    card.paste(im, (card.width - im.width, 0))
    draw = ImageDraw.Draw(card)

    # Take the base font size and make it smaller for larger tweets
    if len(tweet) < 20:
        font_size = int(FONT_SIZE * 1.25)
    elif len(tweet) > 200:
        font_size = int(FONT_SIZE * .75)
    else:
        font_size = FONT_SIZE

    font = ImageFont.truetype('fonts/' + FONT, size=font_size)
    max_width = CARD_WIDTH / 1.8
    draw_word_wrap(draw, tweet,
                   max_width=max_width,
                   xpos=CARD_MARGIN,
                   ypos=CARD_MARGIN,
                   fill=(255, 255, 255),
                   font=font)

    byline = '—' + author['name']
    draw_word_wrap(draw, byline,
                   max_width=CARD_WIDTH,
                   xpos=CARD_MARGIN,
                   ypos=CARD_HEIGHT - CARD_MARGIN - font.getsize("a")[1],
                   fill=(255,255,153),
                   font=font)
    return card


def build_color_map(tile_dir):
    color_map = {}
    for filename in os.listdir(tile_dir):
        _file = tile_dir + '/' + filename
        primary = colorz(_file, n=1)
        for m in primary:
            c = sRGBColor(*m[0], is_upscaled=True)
            lab_c = convert_color(c, LabColor)
            color_map[_file] = lab_c
    return color_map

def identify_colors(tile_dir, colors_to_match):
    matches = []
    print("Building color map...")
    color_map = build_color_map(tile_dir)
    print("Comparing {} color map values...".format(len(color_map)))
    for c2 in colors_to_match:
        color = c2[0]
        freq = c2[1]
        best_match = None
        best_match_value = 1000.0
        for c1 in color_map:
            delta_e = delta_e_cie2000(color_map[c1], color)
            if delta_e < best_match_value:
                best_match_value = delta_e
                best_match = c1
        matches.append((best_match, freq))
        del color_map[best_match]


    return matches


def allocate_colors(matches):
    """For the array of matching colors, build a new array that represents their relative allocations."""
    tiles = []
    
    # Allocate the colors by percentage to individual tiles
    total_points = sum([int(p[1]) for p in matches])
    allocations = []
    
    # Derive the percentage representation in the color set, throwing out any that are too rarely
    # represented to be displayable in our 10x10 grid
    for m in matches:
        alloc = int(m[1] / total_points * 100)
        if alloc > 0:
            allocations.append(alloc)

    return allocations

def generate_tiles(allocations):
    # Now build a weighted list of tiles
    tiles = []
    for index, al in enumerate(allocations):
        for _ in range(0, al):
            tiles.append(matches[index][0])

    print("Created an array of {} tiles".format(len(tiles)))
    print(set(tiles))
    
    return tiles

def build_grid(matches, tiles):
    """Build a 10x10 grid of the resulting colors"""

    # Set up the grid
    grid_img = Image.new('RGB', (GRID_WIDTH * TILE_WIDTH, GRID_HEIGHT * TILE_WIDTH), color=(255,255,255))
    for row in range(0, GRID_WIDTH):
        for col in range(0, GRID_HEIGHT):
            tile = tiles[-1]
            im = Image.open(tile)
            im = rotate_randomly(im)
            grid_img.paste(im, box=(row * TILE_WIDTH, col * TILE_WIDTH))
            if len(tiles) > 1:
                tiles.pop()
    grid_img = rotate_randomly(grid_img)
    return grid_img


def draw_card(grid_img, allocations):
    card = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), color=(255,255,255))

    # Draw the background, randomly flipping it for recto/verso variety
    bg = Image.open('images/bg.jpg')
    bg = bg.rotate(random.choice([0, 180]))
    card.paste(bg)

    # Place the grid on the canvas
    card.paste(grid_img, box=(0,0))

    # Draw the header
    font = ImageFont.truetype('fonts/' + FONT, size=HEADER_FONT_SIZE)
    draw = ImageDraw.Draw(card)

    
    draw_text_center(draw, text="COLOR ANALYSIS FROM JAPANESE BROCADE",
                     width=CARD_WIDTH,
                     ypos=CARD_MARGIN + (GRID_HEIGHT * TILE_WIDTH),
                     fill=(80, 80, 80),
                     font=font)  
    return card
    
if __name__ == '__main__':
    api = _auth()

    input_image = sys.argv[1]
    
    colors = colorz(input_image, n=5)
    colors_lab = [(convert_color(sRGBColor(*c[0], is_upscaled=True), LabColor), c[1]) for c in colors]

    matches = identify_colors('tiles', colors_lab)
    print("Found {} matches".format(len(matches)))
    
    allocations = allocate_colors(matches)
    tiles = generate_tiles(allocations)
    
    grid = build_grid(matches, tiles)

    card = draw_card(grid, allocations)
    card.show()
    
#    tweet = search(word, api)
#    if tweet:
#        tweet = '“' + tweet + '”'
#        author = random.choice(AUTHORS)
#        card = generate_image(tweet, author)
#        if card:
#            post_tweet(tweet, card, author)
