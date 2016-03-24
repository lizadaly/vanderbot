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

from PIL import Image, ImageFont, ImageDraw

from secret import *
from config import *

from colors import *
from utils import *

plaintext_re = re.compile(r'^[A-Za-z ]*$')


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

    font = ImageFont.truetype('fonts/' + random.choice(FONTS), size=font_size)
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

def identify_colors(tile_dir):
    for filename in os.listdir(tile_dir):
        _file = tile_dir + '/' + filename
        primary = colorz(_file)
        for m in primary:
            shutil.copy(_file, m.replace('#', '') + '.png')

    
if __name__ == '__main__':
    api = _auth()
    colors = colorz('images/googlelogo.png')
    identify_colors('tiles')
    
#    tweet = search(word, api)
#    if tweet:
#        tweet = '“' + tweet + '”'
#        author = random.choice(AUTHORS)
#        card = generate_image(tweet, author)
#        if card:
#            post_tweet(tweet, card, author)
