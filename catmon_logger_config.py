"""catmon logging config."""

dictLogConfig = {
    'version': 1,
    'handlers': {
        'basicHandler':{
            'class': 'logging.FileHandler',
            'level': 'INFO',
            'formatter': 'myFileFormatter',
            'filename': 'catmon.log'
        },
        'fileHandler':{
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'myFileFormatter',
            'filename': 'catmon.log',
            'maxBytes': 1048576,
            'backupCount': 5,
            'encoding': 'utf8'
        },
        'consoleHandler': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'myConsoleFormatter'
        }
    },        
    'loggers': {
        'catmon': {
            'handlers': ['fileHandler', 'consoleHandler'],
            'level': 'INFO'
        }
    },
    'formatters': {
        'myFileFormatter': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'myConsoleFormatter': {
            'format': '%(name)s - %(levelname)s - %(message)s'
        }
    }
}
