# Copyright (c) 2017 Adam Benson
#
__author__ = 'Adam Benson'
__version__ = '1.0.7'

import sgtk
import threading
import json
import urllib, urllib2
import sys, os, platform, time
import logging

from sgtk.platform.qt import QtCore, QtGui

from ui import blaster_ui

from functools import partial

sg_engine = sgtk.platform.engine
path_from_engine = sg_engine

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

# I need to learn how to use this logger info.  It currently doesn't work.
app_log = sgtk.platform.get_logger('Blaster Engine: %s' % sg_engine)

# Connect Logging
logger = logging.getLogger('blaster')
logger.debug('Blaster dialog activated.')


def show_dialog(app_instance):
    """
    Shows the main dialog window.
    """
    # in order to handle UIs seamlessly, each toolkit engine has methods for launching
    # different types of windows. By using these methods, your windows will be correctly
    # decorated and handled in a consistent fashion by the system. 
    
    # we pass the dialog class to this method and leave the actual construction
    # to be carried out by toolkit.
    app_instance.engine.show_dialog("Blaster", app_instance, AppDialog)


class AppDialog(QtGui.QWidget):
    """
    Main application dialog window
    """
    
    def __init__(self, timesheet_id=None, jobcode_id=None):
        """
        Constructor
        """
        # first, call the base class and let it do its thing.
        QtGui.QWidget.__init__(self)
        
        # now load in the UI that was created in the UI designer
        self.ui = blaster_ui.Ui_Form()
        self.ui.setupUi(self)
        
        # most of the useful accessors are available through the Application class instance
        # it is often handy to keep a reference to this. You can get it via the following method:
        self._app = sgtk.platform.current_bundle()

        # via the self._app handle we can for example access:
        # - The engine, via self._app.engine
        # - A Shotgun API instance, via self._app.shotgun
        # - A tk API instance, via self._app.tk 


