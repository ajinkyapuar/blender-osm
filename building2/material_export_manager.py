import os
from time import time
import bpy
from manager import Manager
from util.blender import loadSceneFromFile
from util.blender_extra.material import createMaterialFromTemplate, setImage


_exportTemplateFilename = "building_material_templates.blend"

_doorFaceWidthPx = 1028


class Exporter:
    
    # a directory where textures generated by the Compositor File Output node are placed
    tmpTextureDir = None
    
    def __init__(self, bldgMaterialsDirectory, sceneName):
        self.bldgMaterialsDirectory = bldgMaterialsDirectory
        exportTemplateFilename = os.path.join(bldgMaterialsDirectory, _exportTemplateFilename)
        self.setTemplateScene(exportTemplateFilename, sceneName)
    
    def cleanup(self):
        #bpy.data.scenes.remove(self.scene)
        self.scene = None
        tmpTextureDir = Exporter.tmpTextureDir
        if tmpTextureDir:
            os.removedirs(tmpTextureDir)
            Exporter.tmpTextureDir = None
    
    def setTemplateScene(self, exportTemplateFilename, sceneName):
        scenes = bpy.data.scenes
        scene = scenes.get(sceneName)
        if scene:
            # perform a quick sanity check here
            if not scene.use_nodes:
                scene = None
        if not scene:
            scene = loadSceneFromFile(exportTemplateFilename, sceneName)
        self.scene = scene
    
    def verifyPath(self, textureDir):
        if not os.path.exists(textureDir):
            os.makedirs(textureDir)
    
    def setTmpTextureDir(self, textureDir):
        if not Exporter.tmpTextureDir:
            # use the number of seconds as the name of the subdirectory
            numSeconds = round(time())
            while True:
                tmpTextureDir = os.path.join(textureDir, str(numSeconds))
                if os.path.exists(tmpTextureDir):
                    numSeconds += 1
                else:
                    os.makedirs(tmpTextureDir)
                    Exporter.tmpTextureDir = tmpTextureDir
                    break
    
    def setColor(self, textColor, nodes, nodeName):
        color = Manager.getColor(textColor)
        nodes[nodeName].outputs[0].default_value = (color[0], color[1], color[2], 1.)

    def makeCommonPreparations(self, textureFilename, textureDir, textColor, claddingTextureInfo):
        self.verifyPath(textureDir)
        self.setTmpTextureDir(textureDir)
        nodes = self.scene.node_tree.nodes
        fileOutputNode = nodes["File Output"]
        fileOutputNode.base_path = Exporter.tmpTextureDir
        fileOutputNode.file_slots[0].path = os.path.splitext(textureFilename)[0]
        # cladding texture
        setImage(
            claddingTextureInfo["name"],
            os.path.join(self.bldgMaterialsDirectory, claddingTextureInfo["path"]),
            nodes,
            "cladding_texture"
        )
        # cladding color
        self.setColor(textColor, nodes, "cladding_color")
        return nodes
    
    def setScaleNode(self, nodes, nodeName, scaleX, scaleY):
        scaleInputs = nodes[nodeName].inputs
        scaleInputs[1].default_value = scaleX
        scaleInputs[2].default_value = scaleY
    
    def setTranslateNode(self, nodes, nodeName, translateX, translateY):
        translateInputs = nodes[nodeName].inputs
        translateInputs[1].default_value = translateX
        translateInputs[2].default_value = translateY
    
    def renderTexture(self, textureFilename, textureDir):
        tmpTextureDir = Exporter.tmpTextureDir
        bpy.ops.render.render(scene=self.scene.name)
        os.replace(
            # the texture file is the only file in <tmpTextureDir>
            os.path.join(tmpTextureDir, os.listdir(tmpTextureDir)[0]),
            os.path.join(textureDir, textureFilename)
        )


class FacadeExporter(Exporter):
    
    def makeTexture(self, textureFilename, textureDir, textColor, facadeTextureInfo, claddingTextureInfo, uvs):
        nodes = self.makeCommonPreparations(textureFilename, textureDir, textColor, claddingTextureInfo)
        # facade texture
        setImage(
            facadeTextureInfo["name"],
            os.path.join(self.bldgMaterialsDirectory, facadeTextureInfo["path"]),
            nodes,
            "facade_texture"
        )
        # scale for the cladding texture
        scaleFactor = claddingTextureInfo["textureWidthM"]/\
            claddingTextureInfo["textureWidthPx"]*\
            (facadeTextureInfo["windowRpx"]-facadeTextureInfo["windowLpx"])/\
            facadeTextureInfo["windowWidthM"]
        self.setScaleNode(nodes, "Scale", scaleFactor, scaleFactor)
        # render the resulting texture
        self.renderTexture(textureFilename, textureDir)


class CladdingExporter(Exporter):

    def makeTexture(self, textureFilename, textureDir, textColor, claddingTextureInfo):
        self.makeCommonPreparations(textureFilename, textureDir, textColor, claddingTextureInfo)
        # render the resulting texture
        self.renderTexture(textureFilename, textureDir)


class DoorExporter(Exporter):

    def makeTexture(self, textureFilename, textureDir, textColor, doorTextureInfo, claddingTextureInfo, uvs):
        nodes = self.makeCommonPreparations(textureFilename, textureDir, textColor, claddingTextureInfo)
        faceWidthM = uvs[1][0] - uvs[0][0]
        faceHeightM = uvs[2][1] - uvs[1][1]
        faceWidthPx = _doorFaceWidthPx
        faceHeightPx = faceHeightM / faceWidthM * faceWidthPx
        # the size of the empty image
        image = nodes["empty_image"].image
        image.generated_width = faceWidthPx
        image.generated_height = faceHeightPx
        # facade texture
        setImage(
            doorTextureInfo["name"],
            os.path.join(self.bldgMaterialsDirectory, doorTextureInfo["path"]),
            nodes,
            "door_texture"
        )
        # scale for the door texture
        scaleY = doorTextureInfo["textureHeightM"]/doorTextureInfo["textureHeightPx"]*faceHeightPx/faceHeightM
        self.setScaleNode(
            nodes,
            "door_scale",
            doorTextureInfo["textureWidthM"]/doorTextureInfo["textureWidthPx"]*faceWidthPx/faceWidthM,
            scaleY
        )
        # translate for the door texture
        self.setTranslateNode(
            nodes,
            "door_translate",
            0,
            (scaleY*doorTextureInfo["textureHeightPx"] - faceHeightPx)/2
        )
        # scale for the cladding texture
        scaleFactor = claddingTextureInfo["textureWidthM"]/claddingTextureInfo["textureWidthPx"]*\
            faceWidthPx/faceWidthM
        self.setScaleNode(
            nodes,
            "cladding_scale",
            scaleFactor,
            scaleFactor
        )
        # render the resulting texture
        self.renderTexture(textureFilename, textureDir)


class MaterialExportManager:
    
    def __init__(self, bldgMaterialsDirectory):
        self.init(bldgMaterialsDirectory)
    
    def init(self, bldgMaterialsDirectory):
        self.facadeExporter = FacadeExporter(bldgMaterialsDirectory, "compositing_facade")
        self.claddingExporter = CladdingExporter(bldgMaterialsDirectory, "compositing_cladding")
        self.doorExporter = DoorExporter(bldgMaterialsDirectory, "compositing_door")
    
    def cleanup(self):
        self.facadeExporter.cleanup()
        self.facadeExporter = None
        self.claddingExporter.cleanup()
        self.claddingExporter = None
        self.doorExporter.cleanup()
        self.doorExporter = None