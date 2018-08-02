# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


from sgtk.platform import Application

class blaster(Application):
    """
    Blaster
    A Shotgun and Deadline enabled batch playblast utility designed to free up an artist's machine with tons of power.
    """

    def init_app(self):
        """
        Called as the application is being initialized
        """
        # self._app = sgtk.platform.current_bundle()
        # self.engine = self._app.engine
        # self.logger = self._app.getLogger
        #
        # self.logger.info('Blaster started...')
        self.blaster_payload = self.import_module("blaster")
        # self.logger.info('blaster payload imported.')

        menu_callback = lambda: self.blaster_payload.blaster.show_dialog(self)

        self.engine.register_command("Blaster...", menu_callback)