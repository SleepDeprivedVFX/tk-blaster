from maya import cmds
import sys, os

from python.blaster.ui import blaster_ui as bui
reload(bui)

try:
    from PySide import QtCore, QtGui
    from shiboken import wrapInstance
    from pysideuic import compileUi
except:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance
    from pyside2uic import compileUi
#
# from shotgun_api3 import Shotgun

# import Deadline.DeadlineConnect as Connect
# d = Connect.DeadlineCon('http://deadline.asc-vfx.com', 8082)
# print d.Jobs.GetJob(id='5a5fb6a90fcb4b76c84a8210')
# print d.Jobs.GetJobs()

# playblast  -format image -sequenceTime 0 -clearCache 1 -viewer 1 -showOrnaments 0 -offScreen  -fp 4 -percent 100 -compression "jpg" -quality 70 -widthHeight 960 540;
"""
all_cams = cmds.ls(type='camera')
current_cam = cmds.lookThru(q=True)
print current_cam
cam_states = {}
for cam in all_cams:
    cam_states[cam] = cmds.getAttr('%s.rnd' % cam)
    cmds.setAttr('%s.rnd' % cam, False)
pb_cams = ['fartCam']  # This will be replaced with the camera selection in the UI
for cam in pb_cams:  # This can probably be replaced with a dedicated pb_cams[0] call.
    cmds.setAttr('%s.rnd' % cam, True)
    cmds.lookThru(cam)

    # Ambient Occlusion and amount
    cmds.setAttr("hardwareRenderingGlobals.ssaoEnable", 1)
    cmds.setAttr("hardwareRenderingGlobals.ssaoAmount", 3)

    # Anti-Aliasing
    cmds.setAttr("hardwareRenderingGlobals.multiSampleEnable", 1)

    # Motion Blur
    cmds.setAttr("hardwareRenderingGlobals.motionBlurEnable", 1)

    # Get the active panel for the following settings
    act_panel = cmds.getPanel(wf=True)

    # Turn on lights
    cmds.modelEditor(act_panel, e=True, displayLights='all')

    # Use Default Material
    cmds.modelEditor(act_panel, e=True, udm=False)

    # Display Textures
    cmds.modelEditor(act_panel, e=True, displayTextures=True)

    # Shadows
    cmds.modelEditor(act_panel, e=True, shadows=True)

    # Smooth Shaded
    cmds.modelEditor(act_panel, e=True, da='smoothShaded', ao=False)

    # Viewport Cleanup
    cmds.modelEditor(act_panel, e=True, ca=False)
    cmds.modelEditor(act_panel, e=True, lt=False)
    cmds.modelEditor(act_panel, e=True, j=False)
    cmds.modelEditor(act_panel, e=True, imp=False)

    # Run Playblast
    cmds.playblast(format='image', c='jpg', sqt=0, cc=True, v=True, orn=False, os=True, fp=4, p=100, qlt=75,
                   wh=[1920, 1080])
"""


class blaster(QtWidgets.QWidget):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        self.modelEditor_settings = ['nurbsCurves', 'nurbsSurfaces', 'cv', 'hulls', 'polymeshes', 'hos',
                                     'subdivSurfaces', 'planes', 'lights', 'cameras', 'imagePlane', 'joints',
                                     'ikHandles', 'deformers', 'dynamics', 'particleInstancers', 'fluids',
                                     'hairSystems', 'follicles', 'nCloths', 'nParticles', 'nRigids',
                                     'dynamicConstraints', 'locators', 'dimensions', 'pivots', 'handles', 'textures',
                                     'strokes', 'motionTrails', 'pluginShapes', 'clipGhosts', 'greasePencils']

        self.hardware_params = ['ssaoEnable', 'ssaoAmount', 'multiSampleEnable', 'motionBlurEnable']

        self.viewport_settings = {}
        self.hardware_settings = {}

        self.ui = bui.Ui_Form()
        self.ui.setupUi(self)
        self.ui.blaster_btn.clicked.connect(self.blast_it)
        self.ui.cancel_btn.clicked.connect(self.cancel)
        self.ui.default_material.clicked.connect(self.material_sets)
        self.ui.textured.clicked.connect(self.texture_sets)
        self.ui.wireframe.clicked.connect(self.wireframe)
        self.ui.smooth_shading.clicked.connect(self.smooth_shaded)
        self.ui.cameras.addItems(cmds.ls(type='camera'))
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
            print viewport
            
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

    def clear_current_settings(self):
        self.viewport_settings.clear()
        self.hardware_settings.clear()

    def cancel(self):
        self.clear_current_settings()
        self.close()

    def reset_display(self, viewport=None):
        print self.modelEditor_settings
        for this in self.modelEditor_settings:
            try:
                eval_this = 'cmds.modelEditor("%s", e=True, %s=%s)' % (viewport, this, self.viewport_settings[this])
                eval(eval_this)
                print 'PASS: %s' % eval_this
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
        farm_string = ''
        if settings:
            print settings

            cam = settings['camera']
            print cam
            # set as the active camera, then get the active panel.
            cmds.lookThru(cam)
            active_panel = cmds.getPanel(wf=True)
            if settings['render_farm']:
                build_string = True
            else:
                build_string = False

            print 'SETTINGS LIST'
            print '-' * 24
            for key, val in settings.items():
                print '%s: %s' % (key, val)

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
                    cmds.setAttr('hardwareRenderGlobals.motionBlurEnable', 1)
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
            print farm_string

if __name__ == '__main__':
    try:
        app = QtWidgets.QApplication(sys.argv)
    except:
        app = QtWidgets.QApplication.instance()
    act_panel = cmds.getPanel(wf=True)
    window = blaster()
    window.show()
    sys.exit(app.exec_())
