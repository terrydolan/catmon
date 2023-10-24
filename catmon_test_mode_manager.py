# Catmon test mode manager

import glob
import os
import random
import shutil

# set-up logger
from catmon_logger import logger
# set-up child logger so ctmm can be clearly seen in the log
logger_ctmm = logger.getChild('ctmm') 


###############################################################################
# Define Class

class CatmonTestModeManager:
    """CatmonTestModeManager manages catmon test modes.

    Catmon changes behaviour based on these modes, allowing testing
    without standard connected components such as GPIO / reed switch and
    camera pointed at catflap.

    Modes:
    mode_no_gpio:
        - allow testing of catmon without a GPIO connection
        - single run only
        - allows camera and other functions to be tested
    mode_sim_cam_image:
        - allow testing of catmon using a simulated cat image
        - default is to select image randomly from ./images/unseen*
        - typically used with mode_no_gpio set to True
        
    Variables:
    mode_no_gpio: Boolean; set via __init__; default: False
    mode_sim_cam_image: Boolean; set via __init__; default: False
    is_testing: Boolean; derived, set to True if any mode* is True
    
    Usage example:
    test_d = {'mode_no_gpio': True, 'mode_sim_cam_image': False}
    ctmm = CatmonTestModeManager(**test_d)   
    
    """
    
    # define prefix for any generated test files
    test_file_prefix = 'test_'
    
    # define the default image pattern
    image_pattern_default = './images/unseen*'
    
    def __init__(self,
                 mode_no_gpio=False,
                 mode_sim_cam_image=False):
        """Initialise class with given test modes."""
        init_params = (mode_no_gpio, mode_sim_cam_image)
        self.mode_no_gpio = mode_no_gpio
        self.mode_sim_cam_image = mode_sim_cam_image
        self.is_testing = True if any(init_params) else False
        logger_ctmm.info(
            'initialised: mode_no_gpio={}, mode_sim_cam_image={}, is_testing={}'
            .format(self.mode_no_gpio, self.mode_sim_cam_image, self.is_testing))

    def get_test_image(self, image_pattern=None, copy_to_cwd=True):
        """Return a random test image for the given file pattern.
        
        If image_pattern is not set then use default pattern.
        
        If copy_to_cwd is True: copy the test image to the current
        working directory with a prefix, if it doesn't already exist.
        """
        logger_ctmm.debug(f"get_test_image: {image_pattern=}, {copy_to_cwd=}")
        if not image_pattern:
            image_pattern = self.image_pattern_default
            logger_ctmm.debug(f"get_test_image: image pattern default set: {image_pattern=}")
        
        image_list = glob.glob(image_pattern)      
        if not image_list:
            logger_ctmm.debug(f"get_test_image: no file found for {image_pattern=}")
            return None
        else:
            image_choice = random.choice(image_list)
            logger_ctmm.debug(f"get_test_image: {image_choice=}")
        
        if copy_to_cwd:
            base_image_name = os.path.basename(image_choice)
            test_image_name = f"{self.test_file_prefix}{base_image_name}"
            if not os.path.exists(test_image_name):
                shutil.copy(image_choice, test_image_name)
                logger_ctmm.debug(f"get_test_image: image {base_image_name=} copied to cwd as {test_image_name}")
            else:
                logger_ctmm.debug(f"get_test_image: image {test_image_name=} already exists in cwd")
                
            return test_image_name
        else:
            return image_choice


if __name__ == "__main__":
    # test basic use of class
    test_d = {'mode_no_gpio': True, 'mode_sim_cam_image': False}
    ctmm = CatmonTestModeManager(**test_d)
        
    print(
        f"{ctmm.mode_no_gpio=}, "
        f"{ctmm.mode_sim_cam_image=}, "
        f"{ctmm.is_testing=}",
        f"{ctmm.test_file_prefix=}"
        )
    
    print(f"random image 1, no copy: {ctmm.get_test_image(copy_to_cwd=False)=}")
    print(f"random image 2, no copy: {ctmm.get_test_image(copy_to_cwd=False)=}")
    print()
    print(f"random image 3, with copy: {ctmm.get_test_image()=}")
    print(f"random image 4, with copy: {ctmm.get_test_image()=}")
    print()
    print(f"random image 5, with copy: {ctmm.get_test_image(image_pattern='./images/2023*.jpg')=}")
    print(f"random image 6, with copy: {ctmm.get_test_image('./images/unseen_boo*')=}")
    print()
    print(f"random image 7, not found: {ctmm.get_test_image(image_pattern='nofilelikethis*')=}")
    
        