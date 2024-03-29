#!BPY
import bpy
import bmesh
from mathutils import Vector
# ImportHelper is a helper class, defines filename and invoke() function which calls the file selector
from bpy_extras.io_utils import ImportHelper

import os
import struct


# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "Import Spring S3O (.s3o)",
    "author": "Jez Kabanov and Jose Luis Cercos-Pita <jlcercos@gmail.com> and Darloth",
    "version": (0, 7, 2),
    "blender": (3, 6, 0),
    "location": "File > Import > Spring (.s3o)",
    "description": "Import a file in the Spring S3O format",
    "warning": "",
    "wiki_url": "https://springrts.com/wiki/Assimp",
    "tracker_url": "http://springrts.com",
    "support": "COMMUNITY",
    "category": "Import-Export",
}

try:
    os.SEEK_SET
except AttributeError:
    os.SEEK_SET, os.SEEK_CUR, os.SEEK_END = range(3)


def read_string(fhandle, offset):
    fhandle.seek(offset, os.SEEK_SET)
    string = ''
    c = fhandle.read(1)
    while(c != b'' and c != b'\x00'):
        string += c.decode('ascii')
        c = fhandle.read(1)
    return string


def folder_root(folder, name):
    """Case insensitive recursive folder root extraction.

    This function returns the parent path which contains the desired subfolder.
    For instance, providing the path:
    
    /home/user/.spring/.spring/games/s44.sdd/objects3d/GER/

    and the target folder name "objects3d", it returns:

    /home/user/.spring/.spring/games/s44.sdd/

    Parameters
    ==========
    
    folder : string
        Folder where the parent should be looked for
    name : string
        Name of the file/folder which root is desired (case will be ignored)

    Returns
    =======

    root : string
        The folder path (case sensitive), None if it is not possible to find the
        root folder in the provided path.
    """
    index = folder.lower().find(name.lower())
    if index == -1:
        return None
    if index == 0:
        return os.getcwd()
    return folder[:index]


def find_in_folder(folder, name):
    """Case insensitive file/folder search tool
    
    Parameters
    ==========
    
    folder : string
        Folder where the file should be looked for
    name : string
        Name of the file (case will be ignored)

    Returns
    =======

    filename : string
        The file name (case sensitive), None if the file cannot be found.
    """
    for filename in os.listdir(folder):
        if filename.lower() == name.lower():
            return filename
    return None


class s3o_header(object):
    binary_format = "<12sI5f4I"

    magic = 'Spring unit'  # char [12] "Spring unit\0"
    version = 0    # uint = 0
    radius = 0.0 # float: radius of collision sphere
    height = 0.0 # float: height of whole object
    midx = 0.0 # float offset from origin
    midy = 0.0 #
    midz = 0.0 #
    rootPieceOffset = 0 # offset of root piece
    collisionDataOffset = 0 # offset of collision data, 0 = no data
    texture1Offset = 0 # offset to filename of 1st texture
    texture2Offset = 0 # offset to filename of 2nd texture

    def load(self, fhandle):
        tmp_data = fhandle.read(struct.calcsize(self.binary_format))
        data = struct.unpack(self.binary_format, tmp_data)
        self.magic = data[0].decode('ascii').replace('\x00', '').strip()
        if(self.magic != 'Spring unit'):
            raise IOError("Not a Spring unit file: '" + self.magic + "'")
            return
        self.version = data[1]
        if(self.version != 0):
            raise ValueError('Wrong file version: ' + self.version)
            return
        self.radius = data[2]
        self.height = data[3]
        self.midx = -data[4]
        self.midy = data[5]
        self.midz = data[6]
        self.rootPieceOffset = data[7]
        self.collisionDataOffset = data[8]

        self.texture1Offset = data[9]
        if(self.texture1Offset == 0):
            self.texture1 = ''
        else:
            self.texture1 = read_string(fhandle, self.texture1Offset)

        self.texture2Offset = data[10]
        if(self.texture2Offset == 0):
            self.texture2 = ''
        else:
            self.texture2 = read_string(fhandle, self.texture2Offset)
        return


def remove_doubles(verts):
    """I would say (J.L. Cercos-Pita aka SanguinarioJoe) this is an upspring
    fault. Anyway, it is happening that the imported models have duplicated
    vertices, i.e. vertices that are in the same exact position, and have the
    same exact normal. It should be noticed that for the sake of the mesh
    representation, those vertices can be merged.
    Unfortunatelly, Blender is not dealing ok with such inconsistent mesh, so it
    is correcting the normals after a wide variety of operations, like entering
    in edit mode, or exporting the mesh.
    Thus, this method is checking and merging the vertexes with the same
    position AND NORMAL. It is also returning a dictionary to translate the
    original vertice indexes onto the new ones
    """
    def find_vert(verts, vert):
        def equal(a, b, tol=1E-6):
            return abs(a - b) < tol
        def equal_verts(a, b):
            return equal(a.xpos, b.xpos) and \
                   equal(a.ypos, b.ypos) and \
                   equal(a.zpos, b.zpos) and \
                   equal(a.xnormal, b.xnormal) and \
                   equal(a.ynormal, b.ynormal) and \
                   equal(a.znormal, b.znormal)
        for i, v in enumerate(verts):
            if equal_verts(v, vert):
                return i
        return None

    new_verts = []
    indexes = list(range(len(verts)))
    for i,v in enumerate(verts):
        j = find_vert(new_verts, v)
        if j is None:
            indexes[i] = len(new_verts)
            new_verts.append(v)
        else:
            indexes[i] = j

    return new_verts, indexes

class s3o_piece(object):
    binary_format = "<10I3f"

    name = ''
    verts = []
    faces = []
    parent = '' 
    children = []

    nameOffset = 0 # uint
    numChildren = 0 # uint
    childrenOffset = 0 # uint
    numVerts = 0 # uint
    vertsOffset = 0 # uint
    vertType = 0 # uint
    primitiveType = 0 # 0 = tri, 1 = tristrips, 2 = quads
    vertTableSize = 0 # number of indexes in vert table
    vertTableOffset = 0
    collisionDataOffset = 0
    xoffset = 0.0
    yoffset = 0.0
    zoffset = 0.0

    def load(self, fhandle, offset, material, tex1 : str = "", tex2 : str = ""):
        fhandle.seek(offset, os.SEEK_SET)
        tmp_data = fhandle.read(struct.calcsize(self.binary_format))
        data = struct.unpack(self.binary_format, tmp_data)

        self.nameOffset = data[0]
        self.numChildren = data[1]
        self.childrenOffset = data[2]
        self.numVerts = data[3]
        self.vertsOffset = data[4]
        self.vertType = data[5]
        self.primitiveType = data[6]
        self.vertTableSize = data[7]
        self.vertTableOffset = data[8]
        self.collisionDataOffset = data[9]
        self.xoffset = -1*data[10]
        self.yoffset = data[12]
        self.zoffset = data[11]

        # load self
        # get name
        fhandle.seek(self.nameOffset, os.SEEK_SET)
        self.name = read_string(fhandle, self.nameOffset)

        # load verts
        self.verts = []
        for i in range(0, self.numVerts):
            vert = s3o_vert()
            vert.load(fhandle, self.vertsOffset + (i * struct.calcsize(vert.binary_format)))
            self.verts.append(vert)
        # We want to keep the original vertices because of the UVs information
        self.unique_verts, self.vertids = remove_doubles(self.verts)

        # load primitives
        fhandle.seek(self.vertTableOffset, os.SEEK_SET)
        self.faces = []
        if(self.primitiveType == 0): # triangles
            i = 0
            while(i < self.vertTableSize):
                tmp = fhandle.read(4 * 3)
                data = struct.unpack("<3I", tmp)
                face = [ int(data[0]), int(data[1]), int(data[2]) ]
                self.faces.append(face)
                i += 3
        elif(self.primitiveType == 1): # tristrips
            raise TypeError('Tristrips are unsupported so far')
        elif(self.primitiveType == 2): # quads
            i = 0
            while(i < self.vertTableSize):
                tmp = fhandle.read(4 * 4)
                data = struct.unpack("<4I", tmp)
                face = [ int(data[0]), int(data[1]), int(data[2]), int(data[3]) ]
                self.faces.append(face)
                i += 4
        else:
            raise TypeError('Unknown primitive type: ' + self.primitiveType)

        # if it has no verts or faces create an EMPTY instead
        if(self.numVerts == 0):
            existing_objects = bpy.data.objects[:]
            bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
            self.ob = set(bpy.data.objects).difference(existing_objects).pop()            
            self.ob.name = self.name
        else:
            bm = bmesh.new()
            for v in self.unique_verts:
                bm.verts.new((v.xpos, v.ypos, v.zpos))
                bm.verts.ensure_lookup_table()
                bm.verts[-1].normal = Vector((v.xnormal, v.ynormal, v.znormal))
            for f in self.faces:
                try:
                    bm.faces.new([bm.verts[self.vertids[i]] for i in f])
                except ValueError:
                    pass
                except IndexError:
                    pass
                bm.faces.ensure_lookup_table()
                uv_layer = bm.loops.layers.uv.verify()
                # If size of faces != 0 then
                if len(bm.faces) > 0:
                    for i, loop in enumerate(bm.faces[-1].loops):
                        uv = loop[uv_layer].uv
                        uv[0] = self.verts[f[i]].texu
                        uv[1] = self.verts[f[i]].texv

            self.mesh = bpy.data.meshes.new(self.name)
            bm.to_mesh(self.mesh)
            self.ob = bpy.data.objects.new(self.name, self.mesh)
            try:
                #collection = bpy.data.collections.new(self.name)
                collection = bpy.context.view_layer.active_layer_collection.collection
                #bpy.context.scene.collection.children.link(collection)
                collection.objects.link(self.ob)
            except AttributeError:
                # Blender < 2.80
                bpy.context.scene.objects.link(self.ob)
            try:
                bpy.context.scene.update()
            except AttributeError:
                # Blender > 2.80
                # The scene doesn't seem to need specifically updating in the latest 2.80
                pass
            try:
                self.ob.select_set(True)
            except AttributeError:
                # Blender < 2.80
                bpy.context.scene.objects.active = self.ob                

            if hasattr(self.ob, "use_auto_smooth"):
                self.ob.use_auto_smooth = False
                # bpy.context.object.data.auto_smooth_angle = 0.785398 # 45 degrees, better than 30 for low poly stuff.

            matidx = len(self.ob.data.materials)
            self.ob.data.materials.append(material) 

            for face in self.mesh.polygons:
                face.material_index = matidx
    
        if tex1 != "" and tex2 != "":
            self.ob["s3o_texture1"] = tex1
            self.ob["s3o_texture2"] = tex2

        if(self.parent):
            self.ob.parent = self.parent.ob
        self.ob.location = [self.xoffset, self.yoffset, self.zoffset]
        self.ob.rotation_mode = 'ZXY'

        # load children
        if(self.numChildren > 0):
            # childrenOffset contains DWORDS containing offsets to child pieces
            fhandle.seek(self.childrenOffset, os.SEEK_SET)
            for i in range(0, self.numChildren):
                tmp = fhandle.read(4)
                offset = fhandle.tell()
                data = struct.unpack("<I", tmp)
                childOffset = data[0]
                child = s3o_piece()
                child.parent = self
                child.load(fhandle, childOffset, material)
                self.children.append(child)
                fhandle.seek(offset, os.SEEK_SET)
        return


class s3o_vert(object):
    binary_format = "<8f"
    xpos = 0.0
    ypos = 0.0
    zpos = 0.0
    xnormal = 0.0
    ynormal = 0.0
    znormal = 0.0
    texu = 0.0
    texv = 0.0

    def load(self, fhandle, offset):
        fhandle.seek(offset, os.SEEK_SET)
        tmp_data = fhandle.read(struct.calcsize(self.binary_format))
        data = struct.unpack(self.binary_format, tmp_data)

        self.xpos = -1*data[0]
        self.ypos = data[2]
        self.zpos = data[1]
        self.xnormal = -1*data[3]
        self.ynormal = data[5]
        self.znormal = data[4]
        self.texu = data[6]
        self.texv = data[7]


def new_material_legacy(tex1, tex2, texsdir, name="Material"):
    mat = bpy.data.materials.new(name=name + '.mat')
    mat.diffuse_color = (1.0, 1.0, 1.0)
    mat.diffuse_shader = 'LAMBERT'
    mat.diffuse_intensity = 1.0
    mat.specular_color = (1.0, 1.0, 1.0)
    mat.specular_shader = 'COOKTORR'
    mat.specular_intensity = 0.5
    mat.ambient = 1.0
    mat.alpha = 1.0
    mat.emit = 0.0
    if tex1 and find_in_folder(texsdir, tex1):
        fname = find_in_folder(texsdir, tex1)
        image = bpy.data.images.load(os.path.join(texsdir, fname))
        tex = bpy.data.textures.new(name + '.color', type='IMAGE')
        tex.image = image
        mtex = mat.texture_slots.add()
        mtex.texture = tex
        mtex.texture_coords = 'UV'
        mtex.uv_layer = 'UVMap'
        mtex.use_map_color_diffuse = True 
        mtex.diffuse_color_factor = 1.0
        mtex.mapping = 'FLAT'
    if tex2 and find_in_folder(texsdir, tex2):
        fname = find_in_folder(texsdir, tex2)
        image = bpy.data.images.load(os.path.join(texsdir, fname))
        tex = bpy.data.textures.new(name + '.alpha', type='IMAGE')
        tex.image = image
        mtex = mat.texture_slots.add()
        mtex.texture = tex
        mtex.texture_coords = 'UV'
        mtex.uv_layer = 'UVMap'
        mtex.use_map_color_diffuse = False 
        mtex.use_map_specular = True
        mtex.specular_factor = 1.0
        mtex.mapping = 'FLAT'

    return mat


def new_material(tex1, tex2, texsdir, name="Material"):
    # Check if we should fallback to legacy mode
    major, minor, _ = bpy.app.version
    if major == 2 and minor < 80:
        return new_material_legacy(tex1, tex2, texsdir, name)

    mat = bpy.data.materials.new(name=name + '.mat')
    mat.use_nodes = True
    
    # shader_mix = mat.node_tree.nodes.new("ShaderNodeMixShader")
    # input_group = mat.node_tree.nodes.new('NodeGroupInput')

    principled = mat.node_tree.nodes["Principled BSDF"]
    principled.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    if(tex1 or tex2):
        # set up a single UV mapping node and plug texture coordinate UV map into it.
        mapping_node = mat.node_tree.nodes.new('ShaderNodeMapping')

        tex_coord_node = mat.node_tree.nodes.new('ShaderNodeTexCoord')
        mat.node_tree.links.new(mapping_node.inputs['Vector'],
                                tex_coord_node.outputs['UV'])
    
    if tex1 and find_in_folder(texsdir, tex1):
        #load diffuse texture, plug in UV mapping, link to base color.
        fname = find_in_folder(texsdir, tex1)
        image = bpy.data.images.load(os.path.join(texsdir, fname))
        image.alpha_mode = 'CHANNEL_PACKED' #spring uses alpha as teamcolor
        tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex_node.image = image

        # apply green as default self teamcolor
        mix_node = mat.node_tree.nodes.new('ShaderNodeMixRGB')
        mix_node.blend_type='MIX'

        mix_node.inputs['Color2'].default_value = (0, 1.0, 0.0, 1.0)
        mat.node_tree.links.new(mix_node.inputs['Color1'], tex_node.outputs['Color'])
        mat.node_tree.links.new(mix_node.inputs['Fac'], tex_node.outputs['Alpha'])

        mat.node_tree.links.new(principled.inputs['Base Color'], mix_node.outputs['Color'])
        mat.node_tree.links.new(tex_node.inputs['Vector'], mapping_node.outputs['Vector'])
        
    if tex2 and find_in_folder(texsdir, tex2):
        # load reflectivity / emission / data texture, plug in same UV map, 
        # set to non colour data and link to appropriate data.
        fname = find_in_folder(texsdir, tex2)
        image = bpy.data.images.load(os.path.join(texsdir, fname))
        # The alpha for this file is one bit, but is actual true alpha and 
        # applies to both textures once ingame
        image.alpha_mode = 'STRAIGHT' 
        image.colorspace_settings.name = 'Non-Color'
        image.colorspace_settings.is_data = True
        
        # setup texture node associated with new image.
        tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex_node.image = image
        #old pre May ~13th, when tex nodes could still have colour spaces associated.
        #tex_node.color_space = 'NONE' 
        
        # add RGB separation node and hook up associated channels and alpha channel.  
        # R is emission, G is reflectivity (inverse roughness) and 
        # B is undefined by default.
        # split_rgb_node = mat.node_tree.nodes.new('ShaderNodeSeparateRGB')
        # mat.node_tree.links.new(split_rgb_node.inputs['Image'], tex_node.outputs['Color'])
        
        # mat.node_tree.links.new(principled.inputs['Emission'], split_rgb_node.outputs['R'])
        
        # inverter_node = mat.node_tree.nodes.new('ShaderNodeInvert')
        # mat.node_tree.links.new(principled.inputs['Roughness'], inverter_node.outputs['Color'])
        # mat.node_tree.links.new(inverter_node.inputs['Color'], split_rgb_node.outputs['G'])
        
        # mat.node_tree.links.new(tex_node.inputs['Vector'], mapping_node.outputs['Vector'])
    return mat


def load_s3o_file(s3o_filename, BATCH_LOAD=False):
    basename = os.path.splitext(os.path.basename(s3o_filename))[0]
    objdir = os.path.dirname(s3o_filename)
    rootdir = folder_root(objdir, "objects3d")
    if rootdir is None:
        texsdir = objdir
    else:
        texsdir = os.path.join(rootdir, find_in_folder(rootdir, 'unittextures'))

    fhandle = open(s3o_filename, "rb")

    header = s3o_header()
    header.load(fhandle)

    mat = new_material(header.texture1, header.texture2, texsdir, name=basename)

    rootPiece = s3o_piece()
    rootPiece.load(fhandle, header.rootPieceOffset, mat, header.texture1, header.texture2)

    # create collision sphere
    existing_objects = bpy.data.objects[:]
    bpy.ops.object.empty_add(type="SPHERE",
                             location=(header.midx, header.midz, header.midy),
                             radius=header.radius)
    new_object = set(bpy.data.objects).difference(existing_objects).pop()
    new_object.name = basename + '.SpringRadius'

    existing_objects = bpy.data.objects[:]
    bpy.ops.object.empty_add(type="ARROWS",
                             location=(header.midx, header.midz, header.midy),
                             radius=10.0)
    new_object = set(bpy.data.objects).difference(existing_objects).pop()
    new_object.name = basename + '.SpringRadius'

    fhandle.close()
    return


class ImportS3O(bpy.types.Operator, ImportHelper):
    """Import a file in the Spring S3O format (.s3o)"""
    bl_idname = "import_scene.s3o"  # important since its how bpy.ops.import_scene.osm is constructed
    bl_label = "Import Spring S3O"
    bl_options = {"UNDO"}

    # ImportHelper mixin class uses this
    filename_ext = ".s3o"

    filter_glob = bpy.props.StringProperty(
        default="*.s3o",
        options={"HIDDEN"},
    )

    def execute(self, context):
        # setting active object if there is no active object
        if context.mode != "OBJECT":
            # if there is no object in the scene, only "OBJECT" mode is provided
            if not context.scene.objects.active:
                context.scene.objects.active = context.scene.objects[0]
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        
        load_s3o_file(self.filepath)
        
        bpy.ops.object.select_all(action="DESELECT")
        return {"FINISHED"}


# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(ImportS3O.bl_idname, text="Spring (.s3o)")


def register():
    bpy.utils.register_class(ImportS3O)
    try:
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    except AttributeError:
        # Blender < 2.80
        bpy.types.INFO_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportS3O)
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except AttributeError:
        # Blender < 2.80
        bpy.types.INFO_MT_file_import.remove(menu_func_import)


# This allows you to run the script directly from blenders text editor
# to test the addon without having to install it.
if __name__ == "__main__":
    register()
