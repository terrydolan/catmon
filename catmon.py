#!/usr/bin/python

"""Monitor the cat flap using a raspberry pi and peripherals.

    On cat entry, detected using reed switch connected to rpi GPIO:
        1. Take picture 
        2. Upload picture to google drive folder
        3. Tweet picture

    Detect entry using magnet on cat flap door moving past reed switch
    connected to GPIO.

    Take picture using picamera module.

    Upload pic to google drive using pydrive wrapper to google drive API.

    Tweet pic using tweepy wrapper to twitter API.

    Private google and twitter app authentication keys in config files.

    Uses logging module for key events.

    Store key data in config file.
    

    Author: Terry Dolan
    
    References (just some of the sources that have helped with this project):
    GPIO interrupts: http://raspi.tv/2013/how-to-use-interrupts...
    GPIO interference: http://www.raspberrypi.org/forums/viewtopic.php?t=53548
    Gdrive: http://stackoverflow.com/questions/22555433/pydrive-and-google-drive-automate-verification-process
    Twitter: http://raspi.tv/2013/how-to-create-a-twitter-app-on-the-raspberry-pi-with-python-tweepy-part-1#app
    Event logging: http://www.blog.pythonlibrary.org/2012/08/02/python-101-an-intro-to-logging/
    Config files: http://www.blog.pythonlibrary.org/2013/10/25/python-101-an-intro-to-configparser/

    To Do:
    Refactor as class to avoid use of globals?
    Avoid taking picture when cat exits? Could use time taken to pass reed switch.
    Use RFID reader to identify a chipped cat?
"""

import RPi.GPIO as GPIO
import picamera
import httplib2
import sys
import os
import tweepy
import time
import logging
import logging.config
import catmon_logger_config # dict with catmon logger config
from oauth2client.client import SignedJwtAssertionCredentials
from datetime import datetime
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from configparser import ConfigParser

def secs_diff(newer_datetime, older_datetime):
    """Return difference in seconds between given datetimes."""
    return (newer_datetime - older_datetime).total_seconds()


def switch_status(pin):
    """Return high if GPIO is high else return low."""
    return 'high' if GPIO.input(pin) == GPIO.HIGH else 'low'


def reed_switch_event_handler(switch_pin):
    """Handle events when reed switch on switch_pin is activated."""

    # define globals
    global gcredentials
    global gdrive_target_folder
    global gdrive_target_folder_id
    global twitter_api 
    global twitter_account_name
    global camera
    global logger
    global TWEET_ON
    global GDRIVE_ON

    # define constants
    TWEET_BOILER_PLATE_TEXT = 'auto-tweet from catmon:'
    # define a camera delay tuning parameter to ensure a good cat pic
    CAM_DELAY = 0.47 # wait this many seconds before taking pic


    # log event handler start and event time
    logger.info('>event handler: started, switch on pin {} is {} -------'.format(switch_pin,
                                                                                 switch_status(switch_pin)))
    event_time = datetime.now()
    logger.info('>event handler: new event at {}'.format(event_time))
    
    # generate image filename and capture image using pi cam
    logger.info('>event handler: capturing image...')
    image_file = datetime.now().strftime('%Y-%m-%d_%H%M%S') + '.jpg'
    if CAM_DELAY > 0: # add the delay, if set 
        time.sleep(CAM_DELAY)
        camera.capture(image_file)
        logger.info('>event handler: pic taken {}'.format(image_file))

    # upload image to gdrive
    if GDRIVE_ON:
        if gcredentials.access_token_expired:
            logger.info('>event handler: gdrive access token expired, refreshing...')
            gcredentials.refresh(httplib2.Http())

        gdrive_api = GoogleDrive(gauth)
        logger.info('>event handler: uploading image {} to gdrive folder {}...'.format(image_file,
                                                                                       gdrive_target_folder))
        this_file = gdrive_api.CreateFile({'parents': [{'kind': 'drive#fileLink',
                                                        'id': gdrive_target_folder_id}]})
        this_file.SetContentFile(image_file) # Read file and set it as the content of this instance
        this_file.Upload()

    # tweet image with text
    if TWEET_ON:
        tweet_text = '{} {}'.format(TWEET_BOILER_PLATE_TEXT, image_file)
        logger.info('>event handler: {} tweeting {} (with image)...'.format(twitter_account_name,
                                                                            tweet_text))
        twitter_api.update_with_media(image_file, status=tweet_text)

    logger.info('>event handler: complete, switch on pin {} is {} -------'.format(switch_pin,
                                                                                  switch_status(switch_pin)))
    
    return


def main():
    """Main program."""
    
    # define globals
    global gdrive_api
    global gcredentials
    global gauth
    global gdrive_target_folder
    global gdrive_target_folder_id
    global twitter_api
    global twitter_account_name
    global camera
    global logger
    global TWEET_ON
    global GDRIVE_ON
    
    # define constants
    CONFIG_FILE = 'catmon.ini' # name of the catmon ini file containing the config data
    LOGGER_NAME = 'catmon' # name of catmon logger in logger config file
    GPIO.setmode(GPIO.BCM) # choose BCM convention (rather than BOARD)
    REED_SWITCH_INPUT_PIN = 23 # selected gpio pin for reed switch input
    REED_SWITCH_BOUNCE_TIME = 400 # ignore switch activation for this many ms
    EVENT_GAP = 5 # ignore subsequent events for this many seconds after initial event
    CAM_RESOLUTION = (640, 480) # default resolution of 2592 x 1944 is not required
    CAM_VFLIP = True # vertical flip set True as using camera module mount with tripod
    CAM_SHUTTER_SPEED = 16000 # default is ~32000, reduced to minimise blur
    CAM_BRIGHTNESS = 55 # default is 50, increased to compensate for increased shutter speed
    CAM_CONTRAST = 5 # default is 0, increased to compensate for increased brightness 
    GDRIVE_ON = True # True if update to google drive is on
    TWEET_ON = True # True if tweeting is on on
    
    # set up logging and log start
    logging.config.dictConfig(catmon_logger_config.dictLogConfig)
    logger = logging.getLogger(LOGGER_NAME)
    logger.info('started catmon at {} ========================'.format(datetime.now()))
   
    logger.info('setting up GPIO for reed switch...')
    # set reed switch pin as input
    # note: using 100K ohm pull down resistor and 1K ohm protection resistor on breadboard
    GPIO.setup(REED_SWITCH_INPUT_PIN, GPIO.IN)
    logger.info('reed switch set-up, switch is {}'.format(switch_status(REED_SWITCH_INPUT_PIN)))
    
    # set-up camera
    logger.info('setting up camera...')
    camera = picamera.PiCamera() 
    camera.resolution = CAM_RESOLUTION
    camera.vflip = CAM_VFLIP
    camera.shutter_speed = CAM_SHUTTER_SPEED
    camera.brightness = CAM_BRIGHTNESS
    camera.constrast = CAM_CONTRAST

    # open the catmon config file and parse
    logger.info('open config file and parse...')
    script_location = sys.argv[0] # assume same location as this script
    base_path = os.path.dirname(os.path.abspath(script_location))
    config_path = os.path.join(base_path, CONFIG_FILE)
    if os.path.exists(config_path):
        cfg = ConfigParser()
        cfg.read(config_path)
    else:
        logger.error("unexpected error: config file '{}' not found. Exiting!".format(CONFIG_FILE))
        sys.exit(1)
    
    # set-up access to google drive
    if GDRIVE_ON:
        logger.info('google drive update is on, setting up...')
        # read the key gdrive info from the config file
        svc_user_id = cfg.get('gdrive', 'svc_user_id') # email address of authorised user
        svc_key_file = cfg.get('gdrive', 'svc_key_file')
        svc_scope = cfg.get('gdrive', 'svc_scope')
        gdrive_target_folder = cfg.get('gdrive', 'gdrive_target_folder')
        gdrive_target_folder_id = cfg.get('gdrive', 'gdrive_target_folder_id')

        # set gdrive credentials and authenticate
        svc_key = open(svc_key_file, 'rb').read() # p12 key for service
        gcredentials = SignedJwtAssertionCredentials(svc_user_id, svc_key,
                                                     scope=svc_scope)
        gcredentials.authorize(httplib2.Http())
        gauth = GoogleAuth()
        gauth.credentials = gcredentials
    else:
        logger.info('google drive update is off')

    # set-up access to twitter
    if TWEET_ON:
        logger.info('twitter update is on, setting up...')
        # read the key twitter info from the config file
        consumer_key = cfg.get('twitter', 'consumer_key')
        consumer_secret = cfg.get('twitter', 'consumer_secret')
        access_token = cfg.get('twitter', 'access_token')
        access_token_secret = cfg.get('twitter', 'access_token_secret')
        twitter_account_name = cfg.get('twitter', 'account_name') 

        # authenticate using twitter OAuth process and create the api
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)  
        auth.set_access_token(access_token, access_token_secret)  
        twitter_api = tweepy.API(auth)
    else:
        logger.info('twitter update is off')

    # wait for reed switch activation
    try:
        prev_event_time = None
        while True:
            try:
                logger.info('') # add blank line to help make log file easy to read
                logger.info('waiting for reed switch (pin {}) to activate event handler...'.format(REED_SWITCH_INPUT_PIN))
                GPIO.wait_for_edge(REED_SWITCH_INPUT_PIN, GPIO.RISING, REED_SWITCH_BOUNCE_TIME)

                # switch activated, check that reed switch pin is high
                # this is required to filter out 'short-lived' electrical interference switch events
                event_time = datetime.now()
                logger.debug('switch activated, switch is {}'.format(switch_status(REED_SWITCH_INPUT_PIN)))
                logger.debug('previous event time is {}'.format(prev_event_time))
                if GPIO.input(REED_SWITCH_INPUT_PIN) == GPIO.LOW:
                    # switch should be high, so ignore event
                    logger.info('false alarm at {}: switch is low, so ignore event'.format(event_time))
                    continue

                # check event time and call reed switch event handler
                # ignore the event if it is within the defined 'event gap'
                if prev_event_time is None: # first call
                    reed_switch_event_handler(REED_SWITCH_INPUT_PIN)
                    prev_event_time = event_time
                else:
                    secs_since_previous_event = secs_diff(event_time, prev_event_time)
                    if secs_since_previous_event < EVENT_GAP: # ignore event
                        logger.info('ignore event at {}, within {}s of previous event'.format(event_time,
                                                                                              EVENT_GAP))
                    else:
                        reed_switch_event_handler(REED_SWITCH_INPUT_PIN)
                        prev_event_time = event_time
            except:
                raise
    except KeyboardInterrupt: # trap a CTRL+C keyboard interrupt
        logger.info('keyboard interrupt at {}'.format(datetime.now()))
    except:
        logger.exception('unexpected error')
        raise
    finally:
        logger.info('GPIO cleanup and exit...')
        GPIO.cleanup()  

    return


if __name__ == "__main__":
    main()
    
