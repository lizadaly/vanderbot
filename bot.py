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
from collections import namedtuple

from colormath.color_objects import sRGBColor, LabColor
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000

from PIL import Image, ImageFont, ImageDraw

from secret import *
from config import *

from colors import *
from utils import *

class Match(object):
    """A "matching" color from the source image. 
       color_obj: An instance of colormath.color_objects.LabColor suitable for color math
       num_points: The number of points in the source image represented by this color 
       freq: The frequency of that color in the source image, as a percentage"""
    
    def __init__(self, tile, color_obj, num_points, freq=None):
        self.tile = tile
        self.color_obj = color_obj
        self.num_points = num_points
        self.freq = freq

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
        num_points = c2[1]
        best_match = None
        best_match_value = 1000.0
        for c1 in color_map:
            delta_e = delta_e_cie2000(color_map[c1], color)
            if delta_e < best_match_value:
                best_match_value = delta_e
                best_match = c1
        match = Match(tile=best_match, color_obj=color_map[best_match], num_points=num_points, freq=None)
        matches.append(match)
        del color_map[best_match]
        
    return matches


def allocate_colors(matches):
    """For the array of matching colors, build a new array that represents their relative allocations.
    As a side effect, modifies `matches` to add the percentages to each color.
    """
    allocations = []
    
    # Allocate the colors by percentage to individual tiles
    total_points = sum([int(m.num_points) for m in matches])

    # Derive the percentage representation in the color set, throwing out any that are too rarely
    # represented to be displayable in our 10x10 grid
    for m in matches:
        alloc = int(m.num_points / total_points * 100)
        m.freq = alloc 
        if alloc > 0:
            allocations.append(alloc)

    return allocations

def generate_tiles(allocations):
    # Now build a weighted list of tiles
    tiles = []
    for index, al in enumerate(allocations):
        for _ in range(0, al):
            tiles.append(matches[index].tile)

    print("Created an array of {} tiles".format(len(tiles)))
    print(set(tiles))
    
    return tiles

def build_grid(matches, tiles):
    """Build a 10x10 grid of the resulting colors; returns a canvas object with the images laid out"""

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


def draw_card(grid_img, names):
    """Draw the main card, paste on the grid, and set up the text"""
    card = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), color=(255,255,255))

    # Draw the background, randomly flipping it for recto/verso variety
    bg = Image.open('images/bg.jpg')
    bg = bg.rotate(random.choice([0, 180]))
    card.paste(bg)

    # Place the grid on the canvas
    card.paste(grid_img, box=(0,0))

    # Draw the header
    draw = ImageDraw.Draw(card)    
    header_font = ImageFont.truetype('fonts/' + FONT, size=HEADER_FONT_SIZE)
    header_height = draw_text_center(draw, text="COLOR ANALYSIS FROM JAPANESE BROCADE",
                                     width=CARD_WIDTH,
                                     ypos=CARD_MARGIN + (GRID_HEIGHT * TILE_WIDTH),
                                     fill=FONT_COLOR,
                                     font=header_font)

    font = ImageFont.truetype('fonts/' + FONT, size=FONT_SIZE)
    names.sort(key = lambda x: x[1])
    names.reverse()
    
    for i, name in enumerate(names):
        label = name[0]
        number = str(name[1])
        width, height = draw.textsize(label, font=font)
        x = TABLE_MARGIN 
        y = CARD_MARGIN + (GRID_HEIGHT * TILE_WIDTH) + header_height + (i * height)
        draw.text((x, y), name[0], fill=FONT_COLOR, font=font)

        # Now draw the related number, aligned right this time
        number_width = draw.textsize(number, font=font)[0]
        x = CARD_WIDTH - (TABLE_MARGIN) - number_width 
        draw.text((x, y), str(name[1]), fill=FONT_COLOR, font=font)       
        
    return card

def generate_color_name_list(matches, colorfile=COLORFILE):

    # Sort them by frequency (highest to lowest) so we allocate the "best" names to the
    # most-represented colors
    matches.sort(key = lambda x: x.freq)
    matches.reverse()
    
    matching_names = []
    color_names = named_colorset(colorfile) 
    for c1 in matches:
        color = c1.color_obj
        best_match = None
        best_match_value = 1000.0
        for c2 in color_names:
            delta_e = delta_e_cie2000(c2['obj'], color)
            if delta_e < best_match_value:
                best_match_value = delta_e
                best_match = c2
        matching_names.append((best_match['color'], c1.freq))
        color_names.remove(best_match)
        
    return matching_names
    
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
    names = generate_color_name_list(matches)    
    card = draw_card(grid, names)
    
    card.show()
    
#    tweet = search(word, api)
#    if tweet:
#        tweet = '“' + tweet + '”'
#        author = random.choice(AUTHORS)
#        card = generate_image(tweet, author)
#        if card:
#            post_tweet(tweet, card, author)
