# Copyright (c) 2017 Adam Benson
# 
__author__ = 'Adam Benson'
__version__ = '0.0.1'

from sgtk.platform import Application
import sgtk
import threading
import json
import urllib, urllib2
import sys, os, platform, time
import logging
import subprocess
import re
from datetime import datetime, timedelta

# ----------------------------------------------------------------------------------------------------------------------
# Global Variables
# ----------------------------------------------------------------------------------------------------------------------

# Define system variables
osSystem = platform.system()

if osSystem == 'Windows':
    base = '//hal'
    env_user = 'USERNAME'
    computername = 'COMPUTERNAME'
else:
    base = '/Volumes'
    env_user = 'USER'
    computername = 'HOSTNAME'


# Setup Logging....


class blaster(Application):
    """
    Blaster
    A Shotgun and Deadline enabled batch playblast utility designed to free up an artist's machine with tons of power.
    """

    def init_app(self):
        """
        Called as the application is being initialized
        """
        self._app = sgtk.platform.current_bundle()
        self.engine = self._app.engine
        self.logger = self._app.getLogger

        self.logger.info('Blaster started...')
        self.blaster_payload = self.import_module("blaster")
        self.logger.info('blaster payload imported.')
