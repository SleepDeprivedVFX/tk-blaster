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

# by importing QT from sgtk rather than directly, we ensure that
# the code will be compatible with both PySide and PyQt.
from sgtk.platform.qt import QtCore, QtGui
from .ui.blaster_ui import Ui_Form

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
        self.sg_user_name = self.ctx.user['name']
        self.sg_user_id = self.ctx.user['id']
        self.task = self.ctx.task['name']
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
        self.set_value()
        self.ui.quality_slider.valueChanged.connect(self.set_value)

        # Build a still frame image of the viewport for the UI
        temp_dir = os.environ['temp']
        temp = temp_dir + '/viewport.jpg'

        cmds.refresh(cv=True, fe="jpg", fn=temp)

        preview = self.ui.preview
        # preview.fitInView(440, 450, 350, 230)
        scene = QtGui.QGraphicsScene()
        pixmap = QtGui.QPixmap(temp)
        pixmap = pixmap.scaledToWidth(300)
        scene.addPixmap(pixmap)
        # scene.setSceneRect(440, 450, 350, 230)
        preview.setScene(scene)
        preview.fitInView(440, 450, 350, 230)

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
        act_panel = cmds.getPanel(wf=True)
        settings_list = {}
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

            # Get Deadline Settings
            # Next I need to get the Deadline settings, but first I guess I need to make them

            # Run the Blaster Loader which decides how to prep the command line.
            loaded_blaster = self.load_blaster(settings=settings_list, viewport=act_panel)

    def load_blaster(self, settings=None, viewport=None):
        print viewport
        farm_string = ''
        if settings:
            # print settings

            cam = settings['camera']
            # print cam
            # set as the active camera, then get the active panel.
            cmds.lookThru(cam)
            active_panel = cmds.getPanel(wf=True)
            print active_panel
            if settings['render_farm']:
                build_string = True
            else:
                build_string = False

            # print 'SETTINGS LIST'
            # print '-' * 24
            # for key, val in settings.items():
                # print '%s: %s' % (key, val)

            # Smooth Shading
            if settings['smooth_shading']:
                if build_string:
                    farm_string += 'modelEditor -e -da "smoothShaded" -ao 0 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, da='smoothShaded', ao=False)
            else:
                if build_string:
                    farm_string += 'modelEditor -e -da "wireframe" -ao 0 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, da='wireframe', ao=False)

            # Shadows
            if settings['cast_shadows']:
                if build_string:
                    farm_string += 'modelEditor -e -shadows 1 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, shadows=True)
            else:
                if build_string:
                    farm_string += 'modelEditor -e -shadows 0 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, shadows=False)

            # Default Material
            if settings['textured']:
                if build_string:
                    farm_string += 'modelEditor -e -displayTextures 1 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, displayTextures=True)
            else:
                if build_string:
                    farm_string += 'modelEditor -e -displayTextures 0 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, displayTextures=False)

            # Display Textures
            if settings['default_material']:
                if build_string:
                    farm_string += 'modelEditor -e -udm 1 %s;' % active_panel
                    farm_string += 'modelEditor -e -displayTextures 0 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, udm=True)
                    cmds.modelEditor(active_panel, e=True, displayTextures=False)
            else:
                if build_string:
                    farm_string += 'modelEditor -e -udm 0 %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, udm=False)

            # Lights
            if settings['use_lights']:
                if build_string:
                    farm_string += 'modelEditor -e -displayLights "all" %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, displayLights='all')
            else:
                if build_string:
                    farm_string += 'modelEditor -e -displayLights "none" %s;' % active_panel
                else:
                    cmds.modelEditor(active_panel, e=True, displayLights='none')

            # Motion Blur
            if settings['motion_blur']:
                if build_string:
                    farm_string += 'setAttr "hardwareRenderGlobals.enableMotionBlur" 1;'
                else:
                    cmds.setAttr('hardwareRenderGlobals.enableMotionBlur', 1)
            else:
                if build_string:
                    farm_string += 'setAttr "hardwareRenderGlobals.enableMotionBlur" 0;'
                else:
                    cmds.setAttr('hardwareRenderGlobals.motionBlurEnable', 0)

            # Ambient Occlusion
            if settings['ambient_occlusion']:
                if build_string:
                    farm_string += 'setAttr "hardwareRenderingGlobals.ssaoEnable" 1;'
                    farm_string += 'setAttr "hardwareRenderingGlobals.ssaoAmount" 3;'
                else:
                    cmds.setAttr('hardwareRenderingGlobals.ssaoEnable', 1)
                    cmds.setAttr('hardwareRenderingGlobals.ssaoAmount', 3)
            else:
                if build_string:
                    farm_string += 'setAttr "hardwareRenderingGlobals.ssaoEnable" 0;'
                    farm_string += 'setAttr "hardwareRenderingGlobals.ssaoAmount" 3;'
                else:
                    cmds.setAttr('hardwareRenderingGlobals.ssaoEnable', 0)
                    cmds.setAttr('hardwareRenderingGlobals.ssaoAmount', 3)

            # Anti-Aliasing
            if settings['anti_aliasing']:
                if build_string:
                    farm_string += 'setAttr "hardwareRenderingGlobals.multiSampleEnable" 1;'
                else:
                    cmds.setAttr('hardwareRenderingGlobals.multiSampleEnable', 1)
            else:
                if build_string:
                    farm_string += 'setAttr "hardwareRenderingGlobals.multiSampleEnable" 0;'
                else:
                    cmds.setAttr('hardwareRenderingGlobals.multiSampleEnable', 0)

            # Viewport Cleanup
            cmds.modelEditor(active_panel, e=True, ca=False)
            cmds.modelEditor(active_panel, e=True, lt=False)
            cmds.modelEditor(active_panel, e=True, j=False)
            cmds.modelEditor(active_panel, e=True, imp=False)

            # Build playblast command.
            if build_string:
                self.farm_blast(farm_string=farm_string, viewport=viewport)
            else:
                self.local_blast(viewport=viewport)

            # Return to the previous settings.
            self.return_current_settings(viewport=active_panel)
        
    def farm_blast(self, farm_string=None, viewport=None):
        if farm_string:
            print farm_string
            # self.reset_display(viewport=viewport)

    def local_blast(self, viewport=None):
        print 'Local Blast'
        '''
        This needs to be passed the save to filename, so it knows where to go.
        It also needs the ability to post itself to Shotgun, and keep things within the system.
        Needs to otherwise behave normally, however, contingencies will need to be made for Shotgun.  For instance,
        I playblast out a JPG sequence locally, how does that get converted to MOV and uploaded to Shotgun?  There may
        actually be a Shotgun-forgiving way to do this.
        '''
        # self.reset_display(viewport=viewport)
        cmds.playblast(format='image', c='jpg', sqt=0, cc=True, v=True, orn=False, os=True, fp=4, p=100, qlt=75,
                       wh=[1920, 1080])

