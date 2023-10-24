"""Catmon logging base definition."""

import logging
import logging.config
import catmon_logger_config # dict with catmon logger config

LOGGER_NAME = 'catmon' # name of catmon logger in logger config file

logging.config.dictConfig(catmon_logger_config.dictLogConfig)
logger = logging.getLogger(LOGGER_NAME)