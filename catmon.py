#!/usr/bin/python

"""Monitor the cat flap using a raspberry pi and peripherals.

    On cat entry, detected using reed switch connected to rpi GPIO:
        1. Take picture
        2. Classify picture as Boo, Simba or Unknown
        2. Upload picture to Google drive folder
        3. Tweet picture with classification

    Detect entry using magnet on cat flap door moving past reed switch
    connected to GPIO.

    Take picture using picamera module.

    Classify picture using catmonic.

    Upload pic to Google drive using pydrive wrapper to Google drive API.

    Tweet pic using tweepy wrapper to Twitter APIs.

    Private Google and Twitter app authentication keys in config files.

    Uses logging module for key events.

    Store key data in config file.

    Author: Terry Dolan

    References (just some of the sources that have helped with the initial development, circa 2015):
    - GPIO interrupts: http://raspi.tv/2013/how-to-use-interrupts...
    - GPIO interference: http://www.raspberrypi.org/forums/viewtopic.php?t=53548
    - Gdrive: http://stackoverflow.com/questions/22555433/pydrive-and-google-drive-automate-verification-process
    - Twitter: http://raspi.tv/2013/how-to-create-a-twitter-app-on-the-raspberry-pi-with-python-tweepy-part-1#app
    - Event logging: http://www.blog.pythonlibrary.org/2012/08/02/python-101-an-intro-to-logging/
    - Config files: http://www.blog.pythonlibrary.org/2013/10/25/python-101-an-intro-to-configparser/

    To Do:
    - Automatically place a very dark image in the auto_discard_images folder

    catmon2 changes Aug-Oct 2023 
    - primary aim: enhance to include catmonic image classifier; requires port to raspberrypi 3b+ with 64-bit OS
    1. Use picamera2 instead of picamera, given picamera doesn't work on rpi 64-bit os
    2. Simplify camera config: set camera quality; do not set shutter_speed, vlip, brightness and contrast
    3. Create CatmonTestModeManager class to support testing of catmon (see catmon_test_mode_manager.py)
    4. Add CatmonTestModeManager.mode_no_gpio to allow testing without GPIO board
    5. Change image file name to include a test prefix if testing, so test images can be easily identified
    6. Add image classification using catmonic
    7. Change catmonic to allow change location of model, with default as ./models
    8. Change catmonic-app/catmonic_cli_app.py to use model in ../models
    9. Add CatmonTestModeManager.mode_sim_cam_image() to allow testing of classifier with simulated cat images
    10.Update to use Twitter v1 api to upload media and Twitter v2 api for sending tweets
    11. Update logging framework to create catmon_logger.py and import in all modules
    12. Add child logger for event handler
    13. Refactor catmon as a class to remove use of globals; split out additional methods to make more readable
    14. Send to gdrive folder based on classification
    15. Tune lighting and picamera2 params to get best results from camera and catmonic
    16. Use latest catmonic module with improved handling of model file

"""

###############################################################################
# Define code meta data
__author__ = "Terry Dolan"
__maintainer__ = "Terry Dolan"
__copyright__ = "Terry Dolan"
__license__ = "MIT"
__email__ = "terry8dolan@gmail.com"
__status__ = "Beta"
__version__ = "2.0.0"
__updated__ = "October 2023"

###############################################################################
# Import standard library, third-party and local modules

import time
from configparser import ConfigParser
from datetime import datetime

import httplib2
import picamera2
import RPi.GPIO as GPIO
import tweepy
from libcamera import controls
from libcamera import Transform
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

import catmonic.catmonic as catmonic  # import folder.file as myModule
from catmon_test_mode_manager import CatmonTestModeManager
from catmon_logger import logger


###############################################################################
# Define global constants

CONFIG_FILE = 'catmon.ini'  # name of the catmon ini file containing the config data
GPIO.setmode(GPIO.BCM)  # choose BCM convention (rather than BOARD)
REED_SWITCH_INPUT_PIN = 23  # selected gpio pin for reed switch input
REED_SWITCH_BOUNCE_TIME = 400  # ignore switch activation for this many ms
EVENT_GAP = 5  # ignore subsequent events for this many seconds after initial event
TWEET_BOILER_PLATE_TEXT = 'Auto-tweet from catmon2:'  # common text for all tweets

# picamera2 settings
# ref: https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf
# - build-date: 2023-04-06, build-version: 196adb6-clean
CAM_RESOLUTION = (640, 480)  # default resolution of 2592 x 1944 is not required
CAM_HORIZONTAL_FLIP = True  # horizontal flip
CAM_DELAY = 0.99  # camera delay tuning param, wait this many seconds before taking pic
CAM_QUALITY = 95  # 95 is max JPG quality
CAM_AE_ENABLE = True  # enable auto-exposure 
CAM_AW_ENABLE = True  # enable auto-white-balance
CAM_AE_EXP_MODE = controls.AeExposureModeEnum.Short  # short exposure to avoid blur
# # set camera alternative values, if required (used during tuning)
# CAM_BRIGHTNESS = 0.3  # -1.0 to 1.0, normal is 0.0
# CAM_CONTRAST: 2.0  # 0.0 to 32.0, normal is 1.0
# CAM_EXP_TIME: 28000  # AeExposureMode Normal is 66638, Short is 33302
# CAM_EXP_VALUE: 1.8  # -8.0 to 8.0, +ve values increase the target brightness
# CAM_NOISE_RED_MODE = controls.draft.NoiseReductionModeEnum.HighQuality  # selects a suitable noise reduction mode

# switch off catmon capability using the following variables
GDRIVE_ON = True  # True if update to Google drive is on; default is True
TWEET_ON = True  # True if tweeting is on; default is True
CLASSIFY_ON = True  # True if classification of catmon images is on; default is True


###############################################################################
# Set-up test mode

# change catmon behaviour using catmon test mode manager, if required
test_choice = {'mode_no_gpio': False, 'mode_sim_cam_image': False}  # no test, default
# test_choice = {'mode_no_gpio': True, 'mode_sim_cam_image': False}  # test cam without gpio

# instantiate catmon test mode manager object with test modes
logger.info('initialise CatmonTestModeManager()...')
catmon_tester = CatmonTestModeManager(**test_choice)


###############################################################################
# Define Class

class Catmon:
    def __init__(self):

        logger.info('started catmon at {} ========================'
                    .format(datetime.now()))
         
        # set-up GPIO pin as input
        logger.info('setting up GPIO for reed switch...')
        self.setup_reed_switch()
        logger.info('reed switch set-up, switch input pin {} is {}'
                    .format(REED_SWITCH_INPUT_PIN,
                            self.switch_status(REED_SWITCH_INPUT_PIN)))
        
        # set-up camera
        logger.info('setting up camera...')
        self.camera = self.setup_camera()

        # set-up catmon config parser
        logger.info('parse config file...')
        self.cfg = self.setup_config_parser()
        
        # set-up catmon image classifier
        if CLASSIFY_ON:
            logger.info('classify is on, setting up...')
            self.catmonic_clf = self.setup_classifier()
        else:
            logger.info('classify is off')
        
        # set-up access to Google drive api, credentials and folders
        if GDRIVE_ON:
            logger.info('google drive update is on, setting up...')
            (self.gauth,
             self.gcredentials,
             self.gdrive_folders_dict) = self.setup_gdrive()
        else:
            logger.info('google drive update is off')

        # set-up access to Twitter v1 api, v2 api and account name
        if TWEET_ON:
            logger.info('twitter update is on, setting up...')
            (self.twitter_v1api, self.twitter_v2api,
             self.twitter_account_name) = self.setup_twitter()
        else:
            logger.info('twitter update is off')
            
        # start reed switch event loop and handle GPIO pin events
        try:
            logger.info('start reed switch event loop...')
            self.reed_switch_event_loop()
        except KeyboardInterrupt:  # trap a CTRL+C keyboard interrupt
            logger.info('keyboard interrupt at {}'.format(datetime.now()))
            raise
        except Exception as e:
            logger.exception(f'unexpected error {e}')
            raise
        finally:
            logger.info('GPIO cleanup, camera stop and exit...')
            GPIO.cleanup()
            self.camera.stop()

    @staticmethod
    def setup_reed_switch():
        """Set-up reed switch GPIO pin input."""
        # note: using 100K ohm pull down resistor and
        # 1K ohm protection resistor on breadboard
        GPIO.setup(REED_SWITCH_INPUT_PIN, GPIO.IN)

    @staticmethod
    def setup_camera():
        """Set-up camera object."""

        # instantiate the camera object
        camera = picamera2.Picamera2()

        # set the base config for still image
        config = camera.create_still_configuration(
            main={"size": CAM_RESOLUTION},
            transform=Transform(hflip=CAM_HORIZONTAL_FLIP)  # horizontal flip image to match previous camera
            )
        camera.configure(config)

        # set the image quality and additional controls
        camera.options["quality"] = CAM_QUALITY
        camera.set_controls({
            "AeEnable": CAM_AE_ENABLE,
            "AeExposureMode": CAM_AE_EXP_MODE,  
            "AwbEnable": CAM_AW_ENABLE
            })

        # start the camera with the defined config
        camera.start()

        # capture meta data
        metadata = camera.capture_metadata()
        logger.debug(f"camera metadata: {metadata}")

        return camera

    @staticmethod
    def setup_config_parser():
        """Set-up catmon config parser object."""
        # instantiate config parser and parse the config file
        cfg = ConfigParser()
        if not cfg.read(CONFIG_FILE):
            logger.error("unexpected error: could not parse config file '{}'"
                         .format(CONFIG_FILE))
            raise ValueError("unexpected error: could not parse config file '{}'"
                             .format(CONFIG_FILE))

        return cfg

    @staticmethod
    def setup_classifier():
        """Setup catmon image classifier object."""
        # Instantiate the catmonic classifier object
        catmonic_clf = catmonic.Catmonic()
            
        return catmonic_clf

    def setup_gdrive(self):
        """Set-up access to Google drive api, credentials and folders."""
        # read Google Drive user_id, key_file and scope from config file
        svc_user_id = self.cfg.get('gdrive', 'svc_user_id')  # email address of authorised user
        svc_key_file = self.cfg.get('gdrive', 'svc_key_file')
        svc_scope = self.cfg.get('gdrive', 'svc_scope')
        
        # read gdrive folders info from config file and add to folders dictionary
        gdrive_folders = ['gdrive_default_folder', 'gdrive_default_folder_id',
                          'gdrive_boo_folder', 'gdrive_boo_folder_id',
                          'gdrive_simba_folder', 'gdrive_simba_folder_id',
                          'gdrive_unknown_folder', 'gdrive_unknown_folder_id',
                          'gdrive_auto_discard_folder', 'gdrive_auto_discard_folder_id']
        gdrive_folders_dict = {
            folder: self.cfg.get('gdrive', folder) for folder in gdrive_folders}

        # set gdrive credentials and authenticate
        gcredentials = ServiceAccountCredentials.from_p12_keyfile(
            svc_user_id,
            svc_key_file,
            scopes=svc_scope)
        gcredentials.authorize(httplib2.Http())
        gauth = GoogleAuth()
        gauth.credentials = gcredentials

        return gauth, gcredentials, gdrive_folders_dict

    def setup_twitter(self):
        """Set-up access to Twitter v1 api, v2 api and account name."""
        # read the key Twitter info from the config file
        consumer_key = self.cfg.get('twitter', 'consumer_key')
        consumer_secret = self.cfg.get('twitter', 'consumer_secret')
        access_token = self.cfg.get('twitter', 'access_token')
        access_token_secret = self.cfg.get('twitter', 'access_token_secret')
        twitter_account_name = self.cfg.get('twitter', 'account_name')

        # v1.1 authenticate using Twitter OAuth process and create the api
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(access_token, access_token_secret)
        twitter_v1api = tweepy.API(auth)
        
        # v2 authenticate using Twitter OAuth2 process and create the api
        twitter_v2api = tweepy.Client(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_token_secret=access_token_secret)
            
        return twitter_v1api, twitter_v2api, twitter_account_name
            
    def reed_switch_event_loop(self):
        """Wait for reed switch event and handle."""
        prev_event_time = None
        while True:
            try:                
                # check test mode 
                if catmon_tester.mode_no_gpio:
                    # testing without GPIO, simulate single call to the reed switch event handler
                    logger.info(
                        "override catmon behaviour and break: "
                        f"{catmon_tester.mode_no_gpio=}")
                    self.reed_switch_event_handler(REED_SWITCH_INPUT_PIN)
                    break
                    
                logger.info('waiting for reed switch (pin {}) to activate event handler...'
                            .format(REED_SWITCH_INPUT_PIN))
                GPIO.wait_for_edge(REED_SWITCH_INPUT_PIN,
                                   GPIO.RISING,
                                   REED_SWITCH_BOUNCE_TIME)

                # switch activated, check that reed switch pin is high
                # this is required to filter out 'short-lived' electrical interference switch events
                event_time = datetime.now()
                logger.debug('switch activated, switch is {}'
                             .format(self.switch_status(REED_SWITCH_INPUT_PIN)))
                logger.debug('previous event time is {}'.format(prev_event_time))
                if GPIO.input(REED_SWITCH_INPUT_PIN) == GPIO.LOW:
                    # switch should be high, so ignore event
                    logger.info('false alarm at {}: switch is low, so ignore event'
                                .format(event_time))
                    continue

                # check event time and call reed switch event handler
                # ignore the event if it is within the defined 'event gap'
                if prev_event_time is None:  # first call
                    self.reed_switch_event_handler(REED_SWITCH_INPUT_PIN)
                    prev_event_time = event_time
                else:
                    secs_since_previous_event = self.secs_diff(
                        event_time, prev_event_time)
                    if secs_since_previous_event < EVENT_GAP:  # ignore event
                        logger.info('ignore event at {}, within {}s of previous event'
                                    .format(event_time, EVENT_GAP))
                    else:
                        self.reed_switch_event_handler(REED_SWITCH_INPUT_PIN)
                        prev_event_time = event_time
            except Exception as e:
                logger.error(f"unexpected error {e}")
                raise

    def reed_switch_event_handler(self, switch_pin):
        """Handle events when reed switch on switch_pin is activated."""
        
        # set-up child logger so events can be clearly seen in the log
        logger_eh = logger.getChild('event')

        # log event handler start and event time
        logger_eh.info('started, switch on pin {} is {} -------'
                       .format(switch_pin,
                               self.switch_status(switch_pin)))
        event_time = datetime.now()
        logger_eh.info('new event at {}'.format(event_time))
        
        # generate image filename
        image_file_prefix = catmon_tester.test_file_prefix \
            if catmon_tester.is_testing else ''
        image_file = (
            f"{image_file_prefix}{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.jpg")
        logger_eh.debug((
            f"generated image filename {image_file=}, "
            f"{image_file_prefix=}, {catmon_tester.is_testing=}"))
        
        # capture image using pi cam and save to file
        logger_eh.info('capturing image and save to file...')
        if CAM_DELAY > 0:  # add the delay, if set 
            time.sleep(CAM_DELAY)
        im_metadata = self.camera.capture_file(image_file)
        logger_eh.debug(f"image metadata: {im_metadata}")
        logger_eh.info(
            f"estimated image brightness (Lux) is {im_metadata['Lux']:.2f}, "
            f"image ExposureTime is {im_metadata['ExposureTime']}ms")
        logger_eh.info('pic taken {}'.format(image_file))
         
#         # temporarily capture image as np array, to see if quality improves
#         np_array = self.camera.capture_array("main")
#         logger_eh.info(f"np_array shape: {np_array.shape}")
#         from PIL import Image as im
#         im.fromarray(np_array).save(
#             f"array_{image_file}", quality=95, subsampling=0)
        
        # check test mode
        if catmon_tester.mode_sim_cam_image:
            # override image file, use simulated test image of cat
            logger_eh.info(
                f"override catmon behaviour: {catmon_tester.mode_sim_cam_image=}")
            pattern = None  # this default pattern matches 3 unseen images: boo, simba and unknown
#             pattern = './images/2023*.jpg'  # this pattern matches 2 unseen images: boo and simba
            image_file = catmon_tester.get_test_image(image_pattern=pattern)
            if image_file:
                logger_eh.info(f"simulated cat image: {image_file=}")
            else:
                raise ValueError("unexpected error, no image file found for pattern")
        
        # classify image
        if CLASSIFY_ON:
            logger_eh.info('classify image using classifier...')
            # open the PIL image using the given image path
            pil_image = self.open_image(image_file)

            # classify the image using catmonic
            # assign the classification label, probability and model_name
            cfn_label, cfn_probability, cfn_model_name = (
                self.catmonic_clf.predict_catmon_image(pil_image))
            logger_eh.info(
                f"classification: {cfn_label}, {cfn_probability:.2%} ({cfn_model_name})")
        else:
            cfn_label, cfn_probability, cfn_model_name = (None, None, None)

        # upload image to gdrive
        if GDRIVE_ON:
            logger_eh.info('upload image to gdrive using api...')
            if self.gcredentials.access_token_expired:
                logger_eh.info('gdrive access token expired, refreshing...')
                self.gcredentials.refresh(httplib2.Http())

            gdrive_api = GoogleDrive(self.gauth)
            
            # set target folder info
            if CLASSIFY_ON:
                # set folder for classification data
                (gdrive_target_folder,
                 gdrive_target_folder_id) = self.get_gdrive_folder_for_cfn(cfn_label)
            else:
                # use default foldere
                gdrive_target_folder = self.gdrive_folders_dict['gdrive_default_folder']
                gdrive_target_folder_id = self.gdrive_folders_dict['gdrive_default_folder_id']

            logger_eh.info('uploading image {} to gdrive folder {}...'
                           .format(image_file, gdrive_target_folder))
            this_file = gdrive_api.CreateFile(
                {'parents': [{'kind': 'drive#fileLink',
                              'id': gdrive_target_folder_id}]})
            this_file.SetContentFile(image_file)  # Read file and set it as the content of this instance
            this_file.Upload()

        # tweet image with text
        if TWEET_ON:
            logger_eh.info('tweet image with text using api')
            # create tweet text
            if CLASSIFY_ON:
                # create tweet_text using classification data
                tweet_text = self.get_tweet_text_for_cfn(
                    cfn_label=cfn_label,
                    cfn_model_name=cfn_model_name,
                    cfn_probability=cfn_probability,
                    image_file=image_file,
                    event_time=event_time) 
                logger_eh.debug(f"tweet text with classification:\n{tweet_text}")
            else:
                # no classification, so keep tweet text simple
                tweet_text = f"{TWEET_BOILER_PLATE_TEXT} {image_file}"
                logger_eh.debug(f"tweet text, no classification:\n{tweet_text}")
            
            logger_eh.info('{} tweeting {} (with image)...'
                           .format(self.twitter_account_name,
                                   tweet_text.replace('\n', ' ')))
            
            # upload media using Twitter's v1 api
            media = self.twitter_v1api.media_upload(filename=image_file)
            media_id = media.media_id
            
            # send tweet with media using Twitter's v2 api
            self.twitter_v2api.create_tweet(text=tweet_text,
                                            media_ids=[media_id])

        logger_eh.info('complete, switch on pin {} is {} -------'
                       .format(switch_pin,
                               self.switch_status(switch_pin)))
        
    def get_gdrive_folder_for_cfn(self, cfn_label):
        """Return gdrive target folder name and id for given classification label."""
        
        # determine folders
        if cfn_label == 'boo':
            gdrive_target_folder = self.gdrive_folders_dict['gdrive_boo_folder']
            gdrive_target_folder_id = self.gdrive_folders_dict['gdrive_boo_folder_id']
        elif cfn_label == 'simba':
            gdrive_target_folder = self.gdrive_folders_dict['gdrive_simba_folder']
            gdrive_target_folder_id = self.gdrive_folders_dict['gdrive_simba_folder_id']
        elif cfn_label == 'unknown':
            # TO DO: if dark image then send to auto_discard folder
            gdrive_target_folder = self.gdrive_folders_dict['gdrive_unknown_folder']
            gdrive_target_folder_id = self.gdrive_folders_dict['gdrive_unknown_folder_id']
        else:
            raise ValueError(f'cfn_label {cfn_label} not recognised')
            
        return gdrive_target_folder, gdrive_target_folder_id    
        
    @staticmethod
    def get_tweet_text_for_cfn(cfn_label,
                               cfn_model_name,
                               cfn_probability,
                               image_file,
                               event_time):
        """Return specific tweet text for given classification data."""
        # determine greeting
        if event_time.hour < 12:
            greeting = 'Good morning'
        elif 12 <= event_time.hour < 18:
            greeting = 'Good afternoon'
        else:
            greeting = 'Good evening'
            
        if event_time.day == 25 and event_time.month == 12:
            greeting = greeting + " and Happy Christmas"
        
        # determine text
        if cfn_label == 'boo':
            text = (
                f"{greeting} Boo, aka Fluff Bag!\n\n"
                f"Catmonic (using {cfn_model_name}) says the likelihood of Boo is {cfn_probability:.1%}\n\n"
                f"{TWEET_BOILER_PLATE_TEXT} {image_file}"
                )
        elif cfn_label == 'simba':
            text = (
                f"{greeting} Simba, aka Mr Handsome!\n\n"
                f"Catmonic (using {cfn_model_name}) says the likelihood of Simba is {cfn_probability:.1%}\n\n"
                f"{TWEET_BOILER_PLATE_TEXT} {image_file}"
                )
        elif cfn_label == 'unknown':
            text = (
                f"{greeting} cat of mystery!\n\n"
                f"Catmonic (using {cfn_model_name}) says the likelihood is {cfn_probability:.1%}\n\n"
                f"{TWEET_BOILER_PLATE_TEXT} {image_file}"
                )
        else:
            raise ValueError(f'cfn_label {cfn_label} not recognised')
            
        return text

    @staticmethod
    def open_image(image_path):
        """Return PIL image for given image file path."""
        try:
            image = Image.open(image_path)
            return image
        except IOError as e:
            logger.error(f"Error opening image: {e}")
            return None

    @staticmethod
    def secs_diff(newer_datetime, older_datetime):
        """Return difference in seconds between given datetimes."""
        return (newer_datetime - older_datetime).total_seconds()

    @staticmethod
    def switch_status(pin):
        """Return high if GPIO is high else return low."""
        return 'high' if GPIO.input(pin) == GPIO.HIGH else 'low'


###############################################################################
# Define main function


def main():
    """Main program."""
    
    # instantiate catmon object
    # starts reed switch event loop and handles events
    Catmon()


if __name__ == "__main__":
    main()
    
