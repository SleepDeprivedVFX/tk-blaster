# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk
import os
import sys
import threading
import platform
import logging
from maya import cmds
from datetime import datetime
from glob import glob
import re
import time

# by importing QT from sgtk rather than directly, we ensure that
# the code will be compatible with both PySide and PyQt.
from sgtk.platform.qt import QtCore, QtGui
from .ui.blaster_ui import Ui_Form
logger = sgtk.platform.get_logger(__name__)

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

# ----------------------------------------------------------------------------------------------------------------------
# Deadline Import and Setup
# ----------------------------------------------------------------------------------------------------------------------
if osSystem == 'Windows':
    # This should go into the paths.yml perhaps.  Setup a series of universal paths, and then call them here.
    python_path = 'C:\\Python27\\Lib\\site-packages'
else:
    python_path = '/Volumes/Applications/Python27/Lib/site-packages'
sys.path.append(python_path)

from Deadline import DeadlineConnect as connect
dl = connect.DeadlineCon('http://deadline.asc-vfx.com', 8082)


def show_dialog(app_instance):
    """
    Shows the main dialog window.
    """
    # in order to handle UIs seamlessly, each toolkit engine has methods for launching
    # different types of windows. By using these methods, your windows will be correctly
    # decorated and handled in a consistent fashion by the system. 
    
    # we pass the dialog class to this method and leave the actual construction
    # to be carried out by toolkit.
    app_instance.engine.show_dialog("Blaster...", app_instance, AppDialog)


class AppDialog(QtGui.QWidget):
    """
    Main application dialog window
    """
    
    def __init__(self):
        """
        Constructor
        """
        # first, call the base class and let it do its thing.
        QtGui.QWidget.__init__(self)

        self.modelEditor_settings = ['nurbsCurves', 'nurbsSurfaces', 'cv', 'hulls', 'polymeshes', 'hos',
                                     'subdivSurfaces', 'planes', 'lights', 'cameras', 'imagePlane', 'joints',
                                     'ikHandles', 'deformers', 'dynamics', 'particleInstancers', 'fluids',
                                     'hairSystems', 'follicles', 'nCloths', 'nParticles', 'nRigids',
                                     'dynamicConstraints', 'locators', 'dimensions', 'pivots', 'handles', 'textures',
                                     'strokes', 'motionTrails', 'pluginShapes', 'clipGhosts', 'greasePencils']

        self.hardware_params = ['ssaoEnable', 'ssaoAmount', 'multiSampleEnable', 'motionBlurEnable']

        # most of the useful accessors are available through the Application class instance
        # it is often handy to keep a reference to this. You can get it via the following method:
        self._app = sgtk.platform.current_bundle()
        engine = self._app.engine
        self.sg = engine.sgtk

        # now load in the UI that was created in the UI designer
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # Shotgun and System Details
        self.ctx = self._app.context
        self.project = self.ctx.project
        self.project_name = self.project['name']
        self.project_id = self.project['id']
        self.sg_user_name = self.ctx.user['name']
        self.sg_user_id = self.ctx.user['id']
        self.task = self.ctx.task['name']
        self.task_id = self.ctx.task['id']
        self.entity = self.ctx.entity['name']
        self.entity_type = self.ctx.entity['type']
        self.id = self.ctx.entity['id']
        filters = [
            ['id', 'is', self.sg_user_id]
        ]
        fields = [
            'email',
            'login'
        ]
        find_username = self.sg.shotgun.find_one('HumanUser', filters, fields)
        self.username = find_username['login']
        self.email = find_username['email']

        self.start_frame = cmds.playbackOptions(q=True, min=True)
        self.end_frame = cmds.playbackOptions(q=True, max=True)
        if self.entity_type == 'Shot':
            filters = [
                ['id', 'is', self.id]
            ]
            fields = [
                'sg_head_in',
                'sg_tail_out'
            ]
            self.frame_range = self.sg.shotgun.find_one('Shot', filters, fields)
            if self.frame_range['sg_head_in'] and self.frame_range['sg_tail_out']:
                self.start_frame = self.frame_range['sg_head_in']
                self.end_frame = self.frame_range['sg_tail_out']

        self.viewport_settings = {}
        self.hardware_settings = {}

        self.ui.blaster_btn.clicked.connect(self.blast_it)
        self.ui.cancel_btn.clicked.connect(self.cancel)
        self.ui.default_material.clicked.connect(self.material_sets)
        self.ui.textured.clicked.connect(self.texture_sets)
        self.ui.wireframe.clicked.connect(self.wireframe)
        self.ui.smooth_shading.clicked.connect(self.smooth_shaded)
        self.ui.sg_sync_btn.clicked.connect(self.sg_sync)
        self.ui.time_snyc_btn.clicked.connect(self.time_sync)
        self.ui.start_frame.setValue(self.start_frame)
        self.ui.end_frame.setValue(self.end_frame)
        self.ui.cameras.addItems(cmds.ls(type='camera'))
        self.ui.employee_label.setText(self.sg_user_name)
        self.ui.project_label.setText(self.project_name)
        self.ui.asset_shot_label.setText(self.entity)
        self.ui.task_label.setText(self.task)
        self.ui.blaster_progress.setValue(0)
        self.ui.progress_label.setText('Blaster Progress')

        # ------------------ Deadline -------------------------------
        file_path = cmds.file(q=True, sn=True)
        file_name = os.path.basename(file_path)
        base_name, ext = os.path.splitext(file_name)
        logger.info(file_path)
        self.ui.job_name.setText(base_name)
        self.ui.user.setText(self.username)

        self.set_value()
        self.ui.quality_slider.valueChanged.connect(self.set_value)

        # Find the active panel/camera
        active_view = cmds.getPanel(wf=True)
        active_cam = cmds.modelPanel(active_view, q=True, cam=True)
        act_cam_shape = cmds.listRelatives(active_cam, s=True)[0]
        index = self.ui.cameras.findText(active_cam, QtCore.Qt.MatchFixedString)
        if index >= 0:
            self.ui.cameras.setCurrentIndex(index)
        else:
            index = self.ui.cameras.findText(act_cam_shape, QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.ui.cameras.setCurrentIndex(index)

        pools = self.list_deadline_pools()
        if pools:
            for pool in pools:
                self.ui.pool.addItem(pool)
                if pool == 'playblasts':
                    index = self.ui.pool.findText(pool, QtCore.Qt.MatchFixedString)
                    if index >= 0:
                        self.ui.pool.setCurrentIndex(index)
        
        # via the self._app handle we can for example access:
        # - The engine, via self._app.engine
        # - A Shotgun API instance, via self._app.shotgun
        # - A tk API instance, via self._app.tk

    def list_deadline_pools(self):
        try:
            # pools = ['none', 'maya_vray', 'nuke', 'maya_redshift', 'houdini', 'alembics', 'arnold', 'caching']
            logger.debug('Return Deadline pools.')
            pools = dl.Pools.GetPoolNames()
        except Exception:
            pools = []
        return pools

    def sg_sync(self):
        # This doesn't work yet.  I have to get my head straight.  For whatever reason, I'm over thinking it.
        if self.entity_type == 'Shot':
            filters = [
                ['id', 'is', self.id]
            ]
        fields = [
            'sg_head_in',
            'sg_tail_out'
        ]
        range_data = self.sg.shotgun.find_one(self.entity_type, filters, fields)
        playblast_in = range_data['sg_head_in']
        playblast_out = range_data['sg_tail_out']
        self.ui.start_frame.setValue(playblast_in)
        self.ui.end_frame.setValue(playblast_out)

    def time_sync(self):
        tl_start = cmds.playbackOptions(q=True, min=True)
        tl_stop = cmds.playbackOptions(q=True, max=True)
        self.ui.start_frame.setValue(tl_start)
        self.ui.end_frame.setValue(tl_stop)

    def set_value(self):
        val = self.ui.quality_slider.value()
        self.ui.quality_value_2.setValue(val)

    def wireframe(self):
        wf = self.ui.wireframe.isChecked()
        if wf:
            self.ui.smooth_shading.setChecked(False)

    def smooth_shaded(self):
        ss = self.ui.smooth_shading.isChecked()
        if ss:
            self.ui.wireframe.setChecked(False)

    def material_sets(self):
        default_mat = self.ui.default_material.isChecked()
        if default_mat:
            self.ui.textured.setChecked(False)

    def texture_sets(self):
        textured = self.ui.textured.isChecked()
        if textured:
            self.ui.default_material.setChecked(False)

    def collect_current_settings(self, viewport=None):
        if 'modelPanel' in viewport:
            nurbsCurves = cmds.modelEditor(viewport, q=True, nurbsCurves=True)
            nurbsSurfaces = cmds.modelEditor(viewport, q=True, nurbsSurfaces=True)
            cv = cmds.modelEditor(viewport, q=True, cv=True)
            hulls = cmds.modelEditor(viewport, q=True, hulls=True)
            polymeshes = cmds.modelEditor(viewport, q=True, polymeshes=True)
            hos = cmds.modelEditor(viewport, q=True, hos=True)
            subdivSurfaces = cmds.modelEditor(viewport, q=True, subdivSurfaces=True)
            planes = cmds.modelEditor(viewport, q=True, planes=True)
            lights = cmds.modelEditor(viewport, q=True, lights=True)
            cameras = cmds.modelEditor(viewport, q=True, cameras=True)
            imagePlane = cmds.modelEditor(viewport, q=True, imagePlane=True)
            joints = cmds.modelEditor(viewport, q=True, joints=True)
            ikHandles = cmds.modelEditor(viewport, q=True, ikHandles=True)
            deformers = cmds.modelEditor(viewport, q=True, deformers=True)
            dynamics = cmds.modelEditor(viewport, q=True, dynamics=True)
            particleInstancers = cmds.modelEditor(viewport, q=True, particleInstancers=True)
            fluids = cmds.modelEditor(viewport, q=True, fluids=True)
            hairSystems = cmds.modelEditor(viewport, q=True, hairSystems=True)
            follicles = cmds.modelEditor(viewport, q=True, follicles=True)
            nCloths = cmds.modelEditor(viewport, q=True, nCloths=True)
            nParticles = cmds.modelEditor(viewport, q=True, nParticles=True)
            nRigids = cmds.modelEditor(viewport, q=True, nRigids=True)
            dynamicConstraints = cmds.modelEditor(viewport, q=True, dynamicConstraints=True)
            locators = cmds.modelEditor(viewport, q=True, locators=True)
            dimensions = cmds.modelEditor(viewport, q=True, dimensions=True)
            pivots = cmds.modelEditor(viewport, q=True, pivots=True)
            handles = cmds.modelEditor(viewport, q=True, handles=True)
            textures = cmds.modelEditor(viewport, q=True, textures=True)
            strokes = cmds.modelEditor(viewport, q=True, strokes=True)
            motionTrails = cmds.modelEditor(viewport, q=True, motionTrails=True)
            pluginShapes = cmds.modelEditor(viewport, q=True, pluginShapes=True)
            clipGhosts = cmds.modelEditor(viewport, q=True, clipGhosts=True)
            greasePencils = cmds.modelEditor(viewport, q=True, greasePencils=True)
            displayLights = cmds.modelEditor(viewport, q=True, dl=True)
            displayAppearance = cmds.modelEditor(viewport, q=True, displayAppearance=True)
            displayTextures = cmds.modelEditor(viewport, q=True, displayTextures=True)
            hardwareFog = cmds.modelEditor(viewport,q=True, fogging=True)
            ssaoEnable = cmds.getAttr("hardwareRenderingGlobals.ssaoEnable")
            ssaoAmount = cmds.getAttr("hardwareRenderingGlobals.ssaoAmount")
            multiSampleEnable = cmds.getAttr("hardwareRenderingGlobals.multiSampleEnable")
            motionBlurEnable = cmds.getAttr("hardwareRenderingGlobals.motionBlurEnable")

            self.viewport_settings['nurbsCurves'] = nurbsCurves
            self.viewport_settings['nurbsSurfaces'] = nurbsSurfaces
            self.viewport_settings['cv'] = cv
            self.viewport_settings['hulls'] = hulls
            self.viewport_settings['polymeshes'] = polymeshes
            self.viewport_settings['hos'] = hos
            self.viewport_settings['subdivSurfaces'] = subdivSurfaces
            self.viewport_settings['planes'] = planes
            self.viewport_settings['lights'] = lights
            self.viewport_settings['cameras'] = cameras
            self.viewport_settings['imagePlane'] = imagePlane
            self.viewport_settings['joints'] = joints
            self.viewport_settings['ikHandles'] = ikHandles
            self.viewport_settings['deformers'] = deformers
            self.viewport_settings['dynamics'] = dynamics
            self.viewport_settings['particleInstancers'] = particleInstancers
            self.viewport_settings['fluids'] = fluids
            self.viewport_settings['hairSystems'] = hairSystems
            self.viewport_settings['follicles'] = follicles
            self.viewport_settings['nCloths'] = nCloths
            self.viewport_settings['nParticles'] = nParticles
            self.viewport_settings['nRigids'] = nRigids
            self.viewport_settings['dynamicConstraints'] = dynamicConstraints
            self.viewport_settings['locators'] = locators
            self.viewport_settings['dimensions'] = dimensions
            self.viewport_settings['pivots'] = pivots
            self.viewport_settings['handles'] = handles
            self.viewport_settings['textures'] = textures
            self.viewport_settings['strokes'] = strokes
            self.viewport_settings['motionTrails'] = motionTrails
            self.viewport_settings['pluginShapes'] = pluginShapes
            self.viewport_settings['clipGhosts'] = clipGhosts
            self.viewport_settings['greasePencils'] = greasePencils
            self.viewport_settings['displayAppearance'] = displayAppearance
            self.viewport_settings['displayTextures'] = displayTextures
            self.viewport_settings['displayLights'] = displayLights
            self.viewport_settings['fog'] = hardwareFog

            self.hardware_settings['ssaoEnable'] = ssaoEnable
            self.hardware_settings['ssaoAmount'] = ssaoAmount
            self.hardware_settings['multiSampleEnable'] = multiSampleEnable
            self.hardware_settings['motionBlurEnable'] = motionBlurEnable
            # print 'TEST: %s' % self.viewport_settings
            # print 'Test: %s' % self.hardware_settings
            # self.reset_display(viewport=viewport)
        else:
            print 'Select a proper viewport'

    def return_current_settings(self, viewport=None):
        if 'modelPanel' in viewport:
            print 'viewport is correct'
            print '-' * 120
            print self.viewport_settings
            print '=' * 120
            cmds.modelEditor(viewport, e=True, nurbsCurves=self.viewport_settings['nurbsCurves'])
            print 'nurbsCurves set to: %s' % self.viewport_settings['nurbsCurves']
            cmds.modelEditor(viewport, e=True, nurbsSurfaces=self.viewport_settings['nurbsSurfaces'])
            cmds.modelEditor(viewport, e=True, cv=self.viewport_settings['cv'])
            cmds.modelEditor(viewport, e=True, hulls=self.viewport_settings['hulls'])
            cmds.modelEditor(viewport, e=True, polymeshes=self.viewport_settings['polymeshes'])
            cmds.modelEditor(viewport, e=True, hos=self.viewport_settings['hos'])
            cmds.modelEditor(viewport, e=True, subdivSurfaces=self.viewport_settings['subdivSurfaces'])
            cmds.modelEditor(viewport, e=True, planes=self.viewport_settings['planes'])
            cmds.modelEditor(viewport, e=True, lights=self.viewport_settings['lights'])
            print 'use fuckin lights: %s ' % self.viewport_settings['lights']
            cmds.modelEditor(viewport, e=True, cameras=self.viewport_settings['cameras'])
            cmds.modelEditor(viewport, e=True, imagePlane=self.viewport_settings['imagePlane'])
            cmds.modelEditor(viewport, e=True, joints=self.viewport_settings['joints'])
            cmds.modelEditor(viewport, e=True, ikHandles=self.viewport_settings['ikHandles'])
            cmds.modelEditor(viewport, e=True, deformers=self.viewport_settings['deformers'])
            cmds.modelEditor(viewport, e=True, dynamics=self.viewport_settings['dynamics'])
            cmds.modelEditor(viewport, e=True, particleInstancers=self.viewport_settings['particleInstancers'])
            cmds.modelEditor(viewport, e=True, fluids=self.viewport_settings['fluids'])
            cmds.modelEditor(viewport, e=True, hairSystems=self.viewport_settings['hairSystems'])
            cmds.modelEditor(viewport, e=True, follicles=self.viewport_settings['follicles'])
            cmds.modelEditor(viewport, e=True, nCloths=self.viewport_settings['nCloths'])
            cmds.modelEditor(viewport, e=True, nParticles=self.viewport_settings['nParticles'])
            cmds.modelEditor(viewport, e=True, nRigids=self.viewport_settings['nRigids'])
            cmds.modelEditor(viewport, e=True, dynamicConstraints=self.viewport_settings['dynamicConstraints'])
            cmds.modelEditor(viewport, e=True, locators=self.viewport_settings['locators'])
            cmds.modelEditor(viewport, e=True, dimensions=self.viewport_settings['dimensions'])
            cmds.modelEditor(viewport, e=True, pivots=self.viewport_settings['pivots'])
            cmds.modelEditor(viewport, e=True, handles=self.viewport_settings['handles'])
            cmds.modelEditor(viewport, e=True, textures=self.viewport_settings['textures'])
            cmds.modelEditor(viewport, e=True, strokes=self.viewport_settings['strokes'])
            cmds.modelEditor(viewport, e=True, motionTrails=self.viewport_settings['motionTrails'])
            cmds.modelEditor(viewport, e=True, pluginShapes=self.viewport_settings['pluginShapes'])
            cmds.modelEditor(viewport, e=True, clipGhosts=self.viewport_settings['clipGhosts'])
            cmds.modelEditor(viewport, e=True, greasePencils=self.viewport_settings['greasePencils'])
            cmds.modelEditor(viewport, e=True, displayAppearance=self.viewport_settings['displayAppearance'], ao=False)
            cmds.modelEditor(viewport, e=True, dl=self.viewport_settings['displayLights'])
            cmds.modelEditor(viewport, e=True, displayTextures=self.viewport_settings['displayTextures'])
            cmds.modelEditor(viewport, e=True, fogging=self.viewport_settings['fog'])

            cmds.setAttr("hardwareRenderingGlobals.ssaoEnable", self.hardware_settings['ssaoEnable'])
            cmds.setAttr("hardwareRenderingGlobals.ssaoAmount", self.hardware_settings['ssaoAmount'])
            cmds.setAttr("hardwareRenderingGlobals.multiSampleEnable", self.hardware_settings['multiSampleEnable'])
            cmds.setAttr("hardwareRenderingGlobals.motionBlurEnable", self.hardware_settings['motionBlurEnable'])

    def clear_current_settings(self):
        self.viewport_settings.clear()
        self.hardware_settings.clear()

    def cancel(self):
        self.clear_current_settings()
        self.close()

    def reset_display(self, viewport=None):
        # print self.modelEditor_settings
        for this in self.modelEditor_settings:
            try:
                eval_this = 'cmds.modelEditor("%s", e=True, %s=%s)' % (viewport, this, self.viewport_settings[this])
                eval(eval_this)
                # print 'PASS: %s' % eval_this
            except:
                print 'SHIT: %s' % eval_this

    def blast_it(self):
        self.ui.progress_label.setText('BLASTER ENGAGED!')
        logger.info('BLASTER ENGAGED!')
        act_panel = cmds.getPanel(wf=True)
        settings_list = {}
        self.ui.progress_label.setText('Collecting viewport settings...')
        self.ui.blaster_progress.setValue(2)
        logger.info('Collecting viewport settings...')
        self.collect_current_settings(viewport=act_panel)
        if self.viewport_settings and self.hardware_settings:
            # Get playblast settings
            settings_list['show_ornaments'] = self.ui.show_ornaments.isChecked()
            settings_list['backface_culling'] = self.ui.backface_culling.isChecked()
            settings_list['image_planes'] = self.ui.image_planes.isChecked()
            settings_list['two_sided_lighting'] = self.ui.two_sided_lighting.isChecked()
            settings_list['match_render_output'] = self.ui.match_render_output.isChecked()
            settings_list['use_lights'] = self.ui.use_lights.isChecked()
            settings_list['cast_shadows'] = self.ui.cast_shadows.isChecked()
            settings_list['ambient_occlusion'] = self.ui.ambient_occlusion.isChecked()
            settings_list['motion_blur'] = self.ui.motion_blur.isChecked()
            settings_list['textured'] = self.ui.textured.isChecked()
            settings_list['smooth_shading'] = self.ui.smooth_shading.isChecked()
            settings_list['wireframe'] = self.ui.wireframe.isChecked()
            settings_list['anti_aliasing'] = self.ui.anti_aliasing.isChecked()
            settings_list['render_farm'] = self.ui.farm.isChecked()
            settings_list['render_local'] = self.ui.local.isChecked()
            settings_list['camera'] = self.ui.cameras.currentText()
            settings_list['format'] = self.ui.render_formats.currentText()
            settings_list['scale'] = self.ui.scale.currentText()
            settings_list['sg_connection'] = self.ui.shotgun_connection.isChecked()
            settings_list['publish_shotgun_version'] = self.ui.publish_sg_version.isChecked()
            settings_list['keep_in_pipeline'] = self.ui.keep_in_pipeline.isChecked()
            settings_list['browse'] = self.ui.browse.text()
            settings_list['default_material'] = self.ui.default_material.isChecked()
            settings_list['fog'] = self.ui.fog.isChecked()

            # Get Deadline Settings
            # Next I need to get the Deadline settings, but first I guess I need to make them

            # Run the Blaster Loader which decides how to prep the command line.
            loaded_blaster = self.load_blaster(settings=settings_list, viewport=act_panel)

    def load_blaster(self, settings=None, viewport=None):
        self.ui.progress_label.setText('Loading Blaster...')
        self.ui.blaster_progress.setValue(4)
        logger.info('Loading Blaster...')
        farm_string = ''
        if settings:
            self.ui.progress_label.setText('Setting the camera...')
            self.ui.blaster_progress.setValue(5)
            logger.info('Setting the camera...')
            cam = settings['camera']
            # print cam
            # set as the active camera, then get the active panel.
            cmds.lookThru(cam)
            active_panel = cmds.getPanel(wf=True)

            if settings['render_farm']:
                self.ui.blaster_progress.setValue(6)
                self.ui.progress_label.setText('Farm Blaster engaged!')
                logger.info('Farm Blaster engaged!')
                build_string = True
            else:
                self.ui.blaster_progress.setValue(6)
                self.ui.progress_label.setText('Local Blaster engaged!')
                logger.info('Local Blaster engaged!')
                build_string = False

            # print 'SETTINGS LIST'
            # print '-' * 24
            # for key, val in settings.items():
                # print '%s: %s' % (key, val)

            # SMOOTH SHADING
            # -----------------------------------------------------------------------------------------------
            if settings['smooth_shading']:
                self.ui.blaster_progress.setValue(8)
                self.ui.progress_label.setText('Setting Smooth Shaded!')
                logger.info('Setting Smooth Shaded!')
                if build_string:
                    farm_string += 'modelEditor -e -da "smoothShaded" -ao 0 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, da='smoothShaded', ao=False)
            else:
                self.ui.blaster_progress.setValue(8)
                self.ui.progress_label.setText('Setting Wireframe!')
                logger.info('Setting Wireframe!')
                if build_string:
                    farm_string += 'modelEditor -e -da "wireframe" -ao 0 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, da='wireframe', ao=False)

            # SHADOWS
            # -----------------------------------------------------------------------------------------------
            if settings['cast_shadows']:
                self.ui.blaster_progress.setValue(9)
                self.ui.progress_label.setText('Setting Cast Shadows on!')
                logger.info('Setting Cast Shaddows on!')
                if build_string:
                    farm_string += 'modelEditor -e -shadows 1 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, shadows=True)
            else:
                self.ui.blaster_progress.setValue(9)
                self.ui.progress_label.setText('Setting Cast Shadows off!')
                logger.info('Setting Cast Shaddows off!')
                if build_string:
                    farm_string += 'modelEditor -e -shadows 0 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, shadows=False)

            # DEFAULT MATERIAL
            # -----------------------------------------------------------------------------------------------
            if settings['textured']:
                self.ui.blaster_progress.setValue(10)
                self.ui.progress_label.setText('Setting Textures on!')
                logger.info('Setting Textures on!')
                if build_string:
                    farm_string += 'modelEditor -e -displayTextures 1 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, displayTextures=True)
            else:
                self.ui.blaster_progress.setValue(10)
                self.ui.progress_label.setText('Setting Textures off!')
                logger.info('Setting Textures off!')
                if build_string:
                    farm_string += 'modelEditor -e -displayTextures 0 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, displayTextures=False)

            # DISPLAY TEXTURES
            # -----------------------------------------------------------------------------------------------
            if settings['default_material']:
                self.ui.blaster_progress.setValue(11)
                self.ui.progress_label.setText('Setting Default Material on!')
                logger.info('Setting Default Material on!')
                if build_string:
                    farm_string += 'modelEditor -e -udm 1 %s;' % active_panel
                    farm_string += 'modelEditor -e -displayTextures 0 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, udm=True)
                    cmds.modelEditor(active_panel, e=True, displayTextures=False)
            else:
                self.ui.blaster_progress.setValue(11)
                self.ui.progress_label.setText('Setting Default Material off!')
                logger.info('Setting Default Material off!')
                if build_string:
                    farm_string += 'modelEditor -e -udm 0 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, udm=False)

            # HARDWARE FOG
            # -----------------------------------------------------------------------------------------------
            if settings['fog']:
                self.ui.blaster_progress.setValue(12)
                self.ui.progress_label.setText('Setting Hardware Fog on!')
                logger.info('Setting Hardware Fog on!')
                if build_string:
                    farm_string += 'modelEditor -e -fogging 1 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, fogging=True)
            else:
                self.ui.blaster_progress.setValue(12)
                self.ui.progress_label.setText('Setting Hardware Fog off!')
                logger.info('Setting Hardware Fog off!')
                if build_string:
                    farm_string += 'modelEditor -e -fogging 0 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, fogging=False)

            # LIGHTS
            # -----------------------------------------------------------------------------------------------
            if settings['use_lights']:
                self.ui.blaster_progress.setValue(13)
                self.ui.progress_label.setText('Setting Use Lights on!')
                logger.info('Setting Use Lights on!')
                if build_string:
                    farm_string += 'modelEditor -e -displayLights "all" %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, displayLights='all')
            else:
                self.ui.blaster_progress.setValue(13)
                self.ui.progress_label.setText('Setting Use Lights off!')
                logger.info('Setting Use Lights off!')
                if build_string:
                    farm_string += 'modelEditor -e -displayLights "none" %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, displayLights='none')

            # MOTION BLUR
            # -----------------------------------------------------------------------------------------------
            if settings['motion_blur']:
                self.ui.blaster_progress.setValue(14)
                self.ui.progress_label.setText('Setting Motion Blur on!')
                logger.info('Setting Motion Blur on!')
                if build_string:
                    farm_string += 'setAttr "hardwareRenderingGlobals.motionBlurEnable" 1;'
                else:
                    cmds.setAttr('hardwareRenderingGlobals.motionBlurEnable', 1)
            else:
                self.ui.blaster_progress.setValue(14)
                self.ui.progress_label.setText('Setting Motion Blur off!')
                logger.info('Setting Motion Blur off!')
                if build_string:
                    farm_string += 'setAttr "hardwareRenderingGlobals.motionBlurEnable" 0;'
                else:
                    cmds.setAttr('hardwareRenderingGlobals.motionBlurEnable', 0)

            # AMBIENT OCCLUSION
            # -----------------------------------------------------------------------------------------------
            if settings['ambient_occlusion']:
                self.ui.blaster_progress.setValue(15)
                self.ui.progress_label.setText('Setting Ambient Occlusion on!')
                logger.info('Setting Ambient Occlusion on!')
                if build_string:
                    farm_string += 'setAttr "hardwareRenderingGlobals.ssaoEnable" 1;'
                    farm_string += 'setAttr "hardwareRenderingGlobals.ssaoAmount" 3;'
                else:
                    cmds.setAttr('hardwareRenderingGlobals.ssaoEnable', 1)
                    cmds.setAttr('hardwareRenderingGlobals.ssaoAmount', 3)
            else:
                self.ui.blaster_progress.setValue(15)
                self.ui.progress_label.setText('Setting Ambient Occlusion off!')
                logger.info('Setting Ambient Occlusion off!')
                if build_string:
                    farm_string += 'setAttr "hardwareRenderingGlobals.ssaoEnable" 0;'
                    farm_string += 'setAttr "hardwareRenderingGlobals.ssaoAmount" 3;'
                else:
                    cmds.setAttr('hardwareRenderingGlobals.ssaoEnable', 0)
                    cmds.setAttr('hardwareRenderingGlobals.ssaoAmount', 3)

            # ANTI-ALIASING
            # -----------------------------------------------------------------------------------------------
            if settings['anti_aliasing']:
                self.ui.blaster_progress.setValue(16)
                self.ui.progress_label.setText('Setting Anti-Aliasing on!')
                logger.info('Setting Anti-Aliasing on!')
                if build_string:
                    farm_string += 'setAttr "hardwareRenderingGlobals.multiSampleEnable" 1;'
                else:
                    cmds.setAttr('hardwareRenderingGlobals.multiSampleEnable', 1)
            else:
                self.ui.blaster_progress.setValue(16)
                self.ui.progress_label.setText('Setting Anti-Aliasing off!')
                logger.info('Setting Anti-Aliasing off!')
                if build_string:
                    farm_string += 'setAttr "hardwareRenderingGlobals.multiSampleEnable" 0;'
                else:
                    cmds.setAttr('hardwareRenderingGlobals.multiSampleEnable', 0)

            # VIEWPORT CLEANUP
            # -----------------------------------------------------------------------------------------------
            self.ui.blaster_progress.setValue(20)
            self.ui.progress_label.setText('Doing Viewport cleanup...')
            logger.info('Doing viewport cleanup...')
            cmds.modelEditor(active_panel, e=True, ca=False)
            cmds.modelEditor(active_panel, e=True, lt=False)
            cmds.modelEditor(active_panel, e=True, j=False)
            cmds.modelEditor(active_panel, e=True, imp=False)

            # BUILD PLAYBLAST COMMAND
            # -----------------------------------------------------------------------------------------------
            if build_string:
                self.ui.blaster_progress.setValue(25)
                self.ui.progress_label.setText('Setting up Farm Blaster...')
                logger.info('Setting up Farm Blaster...')
                self.farm_blast(farm_string=farm_string, viewport=viewport)
            else:
                self.ui.blaster_progress.setValue(25)
                self.ui.progress_label.setText('Setting up Local Blaster...')
                logger.info('Setting up Local Blaster...')
                self.local_blast(viewport=viewport)

            # Return to the previous settings.
            self.ui.progress_label.setText('Returning previous viewport settings...')
            logger.info('Returning previous viewport settings...')
            self.ui.blaster_progress.setValue(99)
            self.return_current_settings(viewport=active_panel)
            self.return_current_settings(viewport=viewport)
            self.ui.blaster_progress.setValue(100)
            self.ui.progress_label.setText('Greedo is dead. Han shot first. Your Blaster has fired as well.')
            time.sleep(2)
            self.cancel()

    def submit_to_deadline(self, string=None):
        logger.info('Submitting in Deadline...')
        self.ui.blaster_progress.setValue(70)
        self.ui.progress_label.setText('Submitting to Deadline...')
        all_pools = self.list_deadline_pools()
        job_name = self.ui.job_name.text()
        user = self.ui.user.text()
        priority = int(self.ui.priority.text())
        pool = self.ui.pool.currentText()
        machine_list = self.ui.machine_list.text()
        frames_per_machine = int(self.ui.frames_per_machine.text())
        blacklist = self.ui.blacklist.isChecked()

        # Pasted from here
        # ----------------------------------------------------------------------------
        all_pools = self.list_deadline_pools()

        logger.debug('Setup Deadline Environment and Datetime...')
        self.ui.progress_label.setText('Setup Deadline Environment and Datetime...')
        self.ui.blaster_progress.setValue(72)
        # Stripping out the Turn-Table stuff.  Is the file_name still relevant?
        file_name = cmds.file(q=True, sn=True)
        file_path = os.path.dirname(file_name)

        # I probably need to get the playblast path from Shotgun, if I haven't already.
        # Some of the things below may be building the string... which I already have...
        # First up!  So, if it's an asset, I need maya_asset_playblast otherwise, I need maya_shot_playblast
        path_settings = self.sg.templates['maya_asset_work']
        task = path_settings.get_fields(file_name)
        base_name = os.path.basename(file_name).rsplit('.', 1)[0]

        # Do I need the project?
        project = self.project.lower()

        # This "assets" call is a no go.  I think I can get this data elsewhere if I need it.
        proj_root = '%s%s/assets/%s/%s' % (file_path.split(project)[0], project, task['sg_asset_type'], task['Asset'])
        # {'version': 67, 'sg_asset_type': u'Character', 'Asset': u'Thing3', 'task_name': u'turntable.main',
        #  'extension': u'mb'}

        # This will need a re-fit.
        output_path = '%s/publish/renders/' % proj_root
        version = task['version']

        t = 0

        # I know I won't need layers, but what's in here that I DO need?
        for layer in layers:
            # lyr = str(layer)
            job_info = ''
            plugin_info = ''
            job_path = os.environ['TEMP'] + '\\_job_submissions'
            logger.debug('Checking job submission path...')
            if not os.path.exists(job_path):
                os.mkdir(job_path)
            logger.debug('Setting Job date and time...')
            h = datetime.now().hour
            m = datetime.now().minute
            s = datetime.now().second
            h = '%02d' % h
            m = '%02d' % m
            s = '%02d' % s
            D = datetime.now().day
            D = '%02d' % D
            M = datetime.now().month
            M = '%02d' % M
            Y = datetime.now().year
            d = '%s-%s-%s' % (D, M, Y)
            d_flat = str(d).replace('-', '')
            logger.debug('Creating job and plugin files...')
            ji_filename = '%s_%s%s%s%s%s_jobInfo.job' % (base_name, d_flat, h, m, s, t)
            ji_filepath = job_path + '\\' + ji_filename
            pi_filename = '%s_%s%s%s%s%s_pluginInfo.job' % (base_name, d_flat, h, m, s, t)
            pi_filepath = job_path + '\\' + pi_filename
            job_info_file = open(ji_filepath, 'w+')
            plugin_info_file = open(pi_filepath, 'w+')

            # Create a Shotgun Version for Draft...
            # This may still be mostly good.  I'll follow that path when I come back to it.
            logger.info('Creating Shotgun Version for layer %s...' % lyr)
            draft = self.create_draft_version(version_name=base_name, layer=lyr)

            # Setup JobInfo
            logger.debug('Collecting user, resolution, frames and pool data...')
            user_name = os.environ['USERNAME']

            # The frames will need to be added if it's not in the command string already
            frames = '%s-%s' % (start, end)

            # Not sure if I'll need this yet.
            version_name = '%s_%s' % (base_name, lyr)

            # This may need to be set, but I'm not sure if I have anything in place yet.
            resolutionWidth = int(self.ui.res_width.text())
            resolutionHeight = int(self.ui.res_height.text())
            resolution_scale = self.ui.res_scale.currentText()
            resolution_scale = float(resolution_scale.strip('%'))
            resolution_scale /= 100
            resolutionHeight *= resolution_scale
            resolutionWidth *= resolution_scale

            # The job_info file needs to match the requirements for a regular maya deadline submission.
            logger.debug('Creating Job Info File...')
            job_info += 'Name=%s - %s\n' % (base_name, lyr)
            job_info += 'BatchName=%s\n' % base_name
            job_info += 'UserName=%s\n' % user_name
            job_info += 'Region=none\n'
            job_info += 'Comment=Lazy Siouxsie Automatic Turntable\n'
            job_info += 'Frames=%s\n' % frames
            job_info += 'Pool=%s\n' % pool
            job_info += 'Priority=65\n'
            job_info += 'Blacklist=\n'
            job_info += 'MachineLimit=5\n'
            job_info += 'ScheduledStartDateTime=%s/%s/%s %s:%s\n' % (D, M, Y, h, m)
            job_info += 'ExtraInfo0=%s\n' % task['task_name']
            job_info += 'ExtraInfo1=%s\n' % project
            job_info += 'ExtraInfo2=%s\n' % task['Asset']
            job_info += 'ExtraInfo3=%s\n' % version_name
            job_info += 'ExtraInfo4=Lazy Siouxsie Auto Turntable\n'
            job_info += 'ExtraInfo5=%s\n' % user_name
            # Draft Submission details
            # TODO: Rework the Draft Submission
            # The following needs to be added after the main submission.
            # Essentially, Submit the job, find the version ID that it created, and then amend the Job Properties with
            # the following.  For now, it will just create 2 different versions that don't entirely work right.
            # small price to pay for the moment.
            job_info += 'ExtraInfoKeyValue0=UserName=%s\n' % user_name
            job_info += 'ExtraInfoKeyValue1=DraftFrameRate=24\n'
            job_info += 'ExtraInfoKeyValue2=DraftExtension=mov\n'
            job_info += 'ExtraInfoKeyValue3=DraftCodec=h264\n'
            job_info += 'ExtraInfoKeyValue4=DraftQuality=100\n'
            job_info += 'ExtraInfoKeyValue5=Description=Lazy Siouxsie Turntable Draft\n'
            job_info += 'ExtraInfoKeyValue6=ProjectName=%s\n' % project
            job_info += 'ExtraInfoKeyValue7=EntityName=%s\n' % task['Asset']
            job_info += 'ExtraInfoKeyValue8=EntityType=Asset\n'
            job_info += 'ExtraInfoKeyValue9=DraftType=movie\n'
            job_info += 'ExtraInfoKeyValue10=VersionId=%s\n' % draft['id']
            job_info += 'ExtraInfoKeyValue11=DraftColorSpaceIn=Identity\n'
            job_info += 'ExtraInfoKeyValue12=DraftColorSpaceOut=Identity\n'
            job_info += 'ExtraInfoKeyValue13=VersionName=%s\n' % version_name
            job_info += 'ExtraInfoKeyValue14=TaskId=-1\n'
            job_info += 'ExtraInfoKeyValue15=ProjectId=%s\n' % self.project_id
            job_info += 'ExtraInfoKeyValue16=DraftUploadToShotgun=True\n'
            job_info += 'ExtraInfoKeyValue17=TaskName=%s\n' % task['task_name']
            job_info += 'ExtraInfoKeyValue18=DraftResolution=1\n'
            job_info += 'ExtraInfoKeyValue19=EntityId=%s\n' % self.entity_id
            job_info += 'ExtraInfoKeyValue20=SubmitQuickDraft=True\n'
            # End Draft Submission details
            job_info += 'OverrideTaskExtraInfoNames=False\n'
            job_info += 'MachineName=%s\n' % platform.node()
            job_info += 'Plugin=MayaCmd\n'
            output_file = '%s_%s.####.%s' % (layer, base_name, ext)
            output_directory = '%s%s/%s/v%03d' % (output_path, task['task_name'], layer, version)
            # output_directory = output_directory.replace('/', '\\')
            job_info += 'OutputDirectory0=%s\n' % output_directory
            job_info += 'OutputFilename0=%s\n' % output_file
            job_info += 'EventOptIns='
            job_info_file.write(job_info)
            job_info_file.close()

            # Setup PluginInfo
            logger.debug('Creating PluginInfo file...')
            plugin_info += 'Animation=1\n'
            plugin_info += 'Renderer=%s\n' % renderer
            plugin_info += 'UsingRenderLayers=1\n'
            plugin_info += 'RenderLayer=\n'
            plugin_info += 'RenderHalfFrames=0\n'
            plugin_info += 'FrameNumberOffset=0\n'
            plugin_info += 'LocalRendering=0\n'
            plugin_info += 'StrictErrorChecking=0\n'
            plugin_info += 'MaxProcessors=0\n'
            plugin_info += 'Version=%s\n' % cmds.about(q=True, v=True)
            plugin_info += 'UsingLegacyRenderLayers=0\n'
            if cmds.about(q=True, w64=True):
                win = '64bit'
            else:
                win = '32bit'
            plugin_info += 'Build=%s\n' % win
            plugin_info += 'ProjectPath=%s\n' % proj_root
            plugin_info += 'CommandLineOptions=\n'
            plugin_info += 'ImageWidth=%s\n' % resolutionWidth
            plugin_info += 'ImageHeight=%s\n' % resolutionHeight
            plugin_info += 'OutputFilePath=%s\n' % output_path
            plugin_info += 'OutputFilePrefix=\n'
            plugin_info += 'Camera=%s\n' % camera[0]
            plugin_info += 'Camera0=\nCamera1=%s\n' % camera[0]
            plugin_info += 'Camera2=front\nCamera3=persp\nCamera4=side\nCamera5=top\n'
            plugin_info += 'SceneFile=%s\n' % file_name
            plugin_info += 'IgnoreError211=1\n'
            plugin_info += 'UseOnlyCommandLineOptions=False\n'
            plugin_info_file.write(plugin_info)
            plugin_info_file.close()

            degree = float(degree_slice)
            frame_range = float(end - start + 1)
            slice_mult = (frame_range/2) / 360.00
            slice_frames = int(slice_mult * degree)
            slice_frame = 0
            try:
                self.ui.blaster_progress.setValue(82)
                self.ui.progress_label.setText('Submitting the Job to Deadline...')
                logger.info('Submitting the job to Deadline...')
                submitted = self.dl.Jobs.SubmitJobFiles(ji_filepath, pi_filepath, idOnly=True)
                # TODO: The following example is the basic idea behind submitting the python file:
                # submitted = self.dl.Jobs.SubmitJobFiles(ji_filepath, pi_filepath, aux=[pythonFile], idOnly=True)
                # How that's fully implemented remains to be figured out.

                # Setup slice conditions here, to then suspend specific job tasks.
                if submitted and degree != 0:
                    self.ui.blaster_progress.setValue(83)
                    self.ui.progress_label.setText('Parsing Slices...')
                    logger.info('Parsing slices....')
                    job_id = submitted['_id']
                    tasks = self.dl.Tasks.GetJobTasks(job_id)
                    task_count = len(tasks)
                    task_percent = 12.0 / float(task_count)
                    percent = 84.0
                    task_list = []
                    for tsk in tasks['Tasks']:
                        task_id = int(tsk['TaskID'])
                        percent += task_percent
                        if task_id != slice_frame:
                            task_list.append(task_id)
                        else:
                            self.ui.blaster_progress.setValue(int(percent))
                            self.ui.progress_label.setText('Setting %i Frame to Render...' % task_id)
                            logger.debug('Rendering frame %s' % task_id)
                            slice_frame += slice_frames
                    if task_list:
                        logger.debug('Suspending non-sliced tasks...')
                        self.dl.Tasks.SuspendJobTasks(jobId=job_id, taskIds=task_list)
            except Exception, e:
                submitted = False
                logger.error('JOB SUBMISSION FAILED! %s' % e)
            t += 1

        
    def farm_blast(self, farm_string=None, viewport=None):
        if farm_string:
            # Farm Blast Deadline Setup
            # -----------------------------------------------------------------------------------------------
            self.ui.blaster_progress.setValue(30)
            self.ui.progress_label.setText('Getting farm settings...')
            logger.info('Getting farm settings...')
            file_name = self.ui.browse.text()
            pipeline = self.ui.keep_in_pipeline.isChecked()
            shotgun_publish = self.ui.publish_sg_version.isChecked()
            save_data = None
            st = self.ui.start_frame.value()
            et = self.ui.end_frame.value()
            if pipeline:
                self.ui.progress_label.setText('Saving in pipeline!')
                self.ui.blaster_progress.setValue(35)
                logger.info('Saving in pipeline!')
                save_to = self.save_to_pipeline()
            else:
                self.ui.progress_label.setText('Saving in locally!')
                self.ui.blaster_progress.setValue(35)
                logger.info('Saving locally!')
                if file_name:
                    save_to = file_name
                else:
                    save_to = None
            self.ui.progress_label.setText('Setting outputs...')
            self.ui.blaster_progress.setValue(40)
            logger.info('Setting outputs...')
            output_format = self.ui.render_formats.currentText()
            if output_format == 'mov':
                encoding = self.ui.encoding.currentText()
                output_format = 'qt'
            else:
                encoding = output_format
                output_format = 'image'
            scale = self.ui.scale.currentText()
            scale = int(scale.strip('%'))
            quality = self.ui.quality_value_2.value() * 10
            ornaments = self.ui.show_ornaments.isChecked()
            if ornaments:
                ornaments = 1
            else:
                ornaments = 0
            # playblast  -format image -filename "TST101_010_0010_Animation_v001" -sequenceTime 0 -clearCache 1 -viewer
            # 1 -showOrnaments 1 -offScreen  -fp 4 -percent 100 -compression "png" -quality 70 -widthHeight 1920 1080;
            self.ui.blaster_progress.setValue(55)
            self.ui.progress_label.setText('Creating Blaster Stream...')
            logger.info('Creating Blaster Stream...')
            if save_to:
                farm_string += 'playblast -format %s -filename "%s" -sqt=0 -cc 1 -v 1 -st %s -et %s -orn %s -os ' \
                               '-fp 4 -p %s -qlt %s -c "%s";' % (output_format, save_to, st, et, ornaments, scale,
                                                                 quality, encoding)
            else:
                farm_string += 'playblast -format %s sqt=0 -cc 1 -v 1 -st %s -et %s -orn %s -os 1 -fp 4' \
                               '-p %s -qlt %s -c "%s";' % (output_format, st, et, ornaments, scale, quality, encoding)
            self.ui.progress_label.setText('Blasting to the farm...')
            self.ui.blaster_progress.setValue(65)
            logger.info('Blasting to the farm...')
            self.submit_to_deadline(string=farm_string)

    def save_to_pipeline(self):
        final_path = ''
        print 'Pipeline running'
        # Get the path from the template
        current_file = cmds.file(q=True, sn=True)
        path = os.path.dirname(current_file)
        path = path.replace('\\', '/')
        print self.project_name
        # rel_path = path.split(self.project_name.lower())[1]
        # TODO: This hard-coded path shit needs to go!
        rel_path = path.split('tasks')[0]
        rel_path += 'publish/playblasts/maya/'
        print rel_path
        # Need to build the path name and park it in there.
        base_name = os.path.basename(current_file)
        split_basename = base_name.rsplit('.', 1)
        print split_basename
        root_name = split_basename[0]
        ext = split_basename[1]
        print root_name
        print ext
        version = root_name.rsplit('_', 1)[1]
        rel_path += '%s/' % version
        if not os.path.exists(rel_path):
            os.makedirs(rel_path)
        date_ = str(datetime.date(datetime.now()))
        print date_
        time_ = str(datetime.time(datetime.now()))
        time_ = time_.replace(':', '-').rsplit('.')[0]
        date_stamp = '%s-%s' % (date_, time_)
        playblast_filename = '%s.%s' % (root_name, date_stamp)
        print playblast_filename

        file_type = self.ui.render_formats.currentText()
        playblast_filename = '%s.%s' % (playblast_filename, file_type)
        rel_path = os.path.join(rel_path, playblast_filename)
        rel_path = rel_path.replace('\\', '/').strip('/')

        if self.entity_type == 'Shot':
            template = self.sg.templates['maya_shot_playblast']
        elif self.entity_type == 'Asset':
            template = self.sg.templates['maya_asset_playblast']
        else:
            template = None
        if template:
            settings = template.get_fields(rel_path)
        # TODO: This, apparently wasn't finished, and currently doesn't return anything.  Damn...
        print settings
        return final_path

    def publish_version(self, playblast=None, filename=None, start_time=None):
        print filename
        print 'playblast: %s' % playblast
        if playblast:
            print 'Yo Dude.'
            playblast_filename = os.path.basename(playblast)
            playblast_filename = playblast_filename.rsplit('.', 1)[0]
            if '#' in filename:
                pattern = '#*'
                find_hashes = re.search(pattern, filename)
                print 'HASHES: %s' % find_hashes.group()
                # filename = filename.replace('')
            else:
                print 'I didn\'t find a # in %s' % filename

            data = {
                'project': {'type': 'Project', 'id': self.project_id},
                'description': 'Blaster File: %s' % playblast_filename,
                'sg_status_list': 'rev',
                'code': playblast_filename,
                'entity': {'type': self.entity_type, 'id': self.id},
                'sg_task': {'type': 'Task', 'id': self.task_id},
                'sg_path_to_frames': playblast,
                'user': {'type': 'HumanUser', 'id': self.sg_user_id}
            }

            new_version = self.sg.shotgun.create('Version', data)
            print 'NEW VERSION: %s' % new_version
            version_id = new_version['id']
            if os.path.splitext(playblast)[1] == '.mov':
                self.sg.shotgun.upload('Version', version_id, playblast, 'sg_uploaded_movie')
            else:
                self.sg.shotgun.upload_thumbnail('Version', version_id, filename)

    def local_blast(self, viewport=None):
        '''
        This needs to be passed the save to filename, so it knows where to go.
        It also needs the ability to post itself to Shotgun, and keep things within the system.
        Needs to otherwise behave normally, however, contingencies will need to be made for Shotgun.  For instance,
        I playblast out a JPG sequence locally, how does that get converted to MOV and uploaded to Shotgun?  There may
        actually be a Shotgun-forgiving way to do this.
        '''
        self.ui.blaster_progress.setValue(25)
        self.ui.progress_label.setText('Set filename and pipeline options.')
        logger.info('Set filename and pipeline options.')
        # Check for local file name and if it's not there, leave it blank.
        file_name = self.ui.browse.text()
        pipeline = self.ui.keep_in_pipeline.isChecked()
        shotgun_publish = self.ui.publish_sg_version.isChecked()
        save_data = None
        st = self.ui.start_frame.value()
        et = self.ui.end_frame.value()

        if pipeline:
            self.ui.blaster_progress.setValue(30)
            self.ui.progress_label.setText('Saving in the pipeline...')
            logger.info('Saving in the pipeline...')
            save_to = self.save_to_pipeline()
        else:
            if file_name:
                self.ui.blaster_progress.setValue(30)
                self.ui.progress_label.setText('Saving locally...')
                logger.info('Saving locally...')
                save_to = file_name
            else:
                self.ui.blaster_progress.setValue(30)
                self.ui.progress_label.setText('Not saving anywhere...')
                logger.info('Not saving anywhere...')
                save_to = None

        # self.reset_display(viewport=viewport)
        self.ui.blaster_progress.setValue(40)
        self.ui.progress_label.setText('Setting outputs...')
        logger.info('Setting outputs...')
        output_format = self.ui.render_formats.currentText()
        if output_format == 'mov':
            enocoding = self.ui.encoding.currentText()
            output_format = 'qt'
        else:
            enocoding = output_format
            output_format = 'image'
        # Get Scale
        scale = self.ui.scale.currentText()
        scale = int(scale.strip('%'))

        # Get Quality
        quality = self.ui.quality_value_2.value()

        # Show ornaments
        ornaments = self.ui.show_ornaments.isChecked()

        self.ui.blaster_progress.setValue(60)
        self.ui.progress_label.setText('BLASTING...')
        logger.info('BLASTING...')
        if save_to:
            save_data = cmds.playblast(format=output_format, filename=save_to, sqt=0, cc=True, v=True, st=st,
                                       et=et, orn=ornaments, os=True, fp=4, p=scale, qlt=quality, c=enocoding)
            logger.debug('SAVE DATE RETURNS: %s' % save_data)
        else:
            save_data = cmds.playblast(format=output_format, sqt=0, cc=True, v=True, orn=ornaments, os=True, fp=4,
                                       st=st, et=et, p=scale, qlt=quality, c=enocoding)
            logger.debug('SAVE DATE RETURNS: %s' % save_data)

        if shotgun_publish and save_data:
            self.ui.blaster_progress.setValue(90)
            self.ui.progress_label.setText('Publishing...')
            logger.info('Publishing...')
            self.publish_version(playblast=save_to, filename=save_data, start_time=st)

