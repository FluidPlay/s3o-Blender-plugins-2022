import bmesh
import bpy
import mathutils
from mathutils import Matrix
import time
from bpy.props import BoolProperty, StringProperty  # , EnumProperty
import os
import struct
from math import radians

# from struct import calcsize, unpack

# import BPyImage ==> bpy.ops.image
# import BPyMessages ==> bpy.msgbus ?
# ImportHelper is a helper class, defines filename and invoke() function which calls the file selector
from bpy_extras.io_utils import ExportHelper, orientation_helper, axis_conversion

# from Blender import Mesh, Object, Material, Image, Texture, Lamp, Mathutils, Window
# from Blender.Mathutils import Vector

bl_info = {
	"name": "Export Spring S3O Object (.s3o)",
	"author": "Jez Kabanov and Breno 'MaDDoX' Azevedo <jlcercos@gmail.com> and <maddox.br@gmail.com>",
	"version": (0, 7, 1),
	"blender": (3, 10, 0),
	"location": "File > Export > Spring S3O Object (.s3o)",
	"description": "Exports a file in the Spring S3O format",
	"warning": "",
	"wiki_url": "https://springrts.com/wiki/About_s3o",
	"tracker_url": "http://springrts.com",
	"support": "COMMUNITY",
	"category": "Import-Export",
}

try:
	os.SEEK_SET
except AttributeError:
	os.SEEK_SET, os.SEEK_CUR, os.SEEK_END = range(3)


def folder_root(folder, name):
	"""Case-insensitive recursive folder root extraction.
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
		The folder path (case-sensitive), None if it is not possible to find the
		root folder in the provided path.
	"""
	index = folder.lower().find(name.lower())
	if index == -1:
		return None
	return folder[:index]


def find_in_folder(folder, name):
	"""Case-insensitive file/folder search tool
	Parameters
	==========
	folder : string
		Folder where the file should be looked for
	name : string
		Name of the file (case will be ignored)

	Returns
	=======
	filename : string
		The file name (case-sensitive), None if the file cannot be found.
	"""
	for filename in os.listdir(folder):
		if filename.lower() == name.lower():
			return filename
	return None


def read_string(file, offset):
	file.seek(offset, os.SEEK_SET)
	string = ''
	c = file.read(1)
	while c != '' and c != '\0':
		string += c
		c = file.read(1)

	return string


# Example usage: apply_transform(bpy.context.object, use_location=False, use_rotation=True, use_scale=True)
def apply_transform(obj, use_location=False, use_rotation=False, use_scale=False):
	mb = obj.matrix_basis
	I = Matrix()
	loc, rot, scale = mb.decompose()

	# rotation
	T = Matrix.Translation(loc)
	# R = rot.to_matrix().to_4x4()
	R = mb.to_3x3().normalized().to_4x4()
	S = Matrix.Diagonal(scale).to_4x4()

	transform = [I, I, I]
	basis = [T, R, S]

	def swap(i):
		transform[i], basis[i] = basis[i], transform[i]

	if use_location:
		swap(0)
	if use_rotation:
		swap(1)
	if use_scale:
		swap(2)

	M = transform[0] @ transform[1] @ transform[2]
	if hasattr(obj.data, "transform"):
		obj.data.transform(M)
	for c in obj.children:
		c.matrix_local = M @ c.matrix_local

	obj.matrix_basis = basis[0] @ basis[1] @ basis[2]

class s3o_header(object):
	binary_format = '<12sI5f4I'  # .encode()
	magic = b'Spring unit'  # char [12] "Spring unit\0"
	version = 0  # uint = 0
	radius = 0.0  # float: radius of collision sphere
	height = 0.0  # float: height of whole object
	midx = 0.0  # float offset from origin
	midy = 0.0  #
	midz = 0.0  #
	rootPieceOffset = 0  # offset of root piece
	collisionDataOffset = 0  # offset of collision data, 0 = no data
	texture1Offset = 0  # offset to filename of 1st texture
	texture2Offset = 0  # offset to filename of 2nd texture

	def save(self, file):
		s = struct.pack(self.binary_format,
						self.magic,
						self.version,
						self.radius,
						self.height,
						self.midx,
						self.midy,
						self.midz,
						self.rootPieceOffset,
						self.collisionDataOffset,
						self.texture1Offset,
						self.texture2Offset
						)
		print(s)
		file.write(s)


class s3o_piece(object):
	binary_format = "<10I3f"

	mesh = None # #
	parent = None   # # ''
	name = ''
	verts = []
	polygons = []
	children = []

	nameOffset = 0  # uint
	numChildren = 0  # uint
	childrenOffset = 0  # uint
	numVerts = 0  # uint
	vertsOffset = 0  # uint
	vertType = 0  # uint
	primitiveType = 0  # 0 = tri, 1 = tristrips, 2 = quads
	vertTableSize = 0  # number of indexes in vert table
	vertTableOffset = 0
	collisionDataOffset = 0
	xoffset = 0.0
	yoffset = 0.0
	zoffset = 0.0

	def write_primitives(self, file):
		# check if they're all quads, if so we can save it as quads rather than tris
		allquads = True
		for f in self.polygons:
			if len(f) != 4:
				allquads = False
				break

		if allquads:
			self.primitiveType = 2
			for f in self.polygons:
				data = struct.pack("<4I", f[0], f[1], f[2], f[3])
				file.write(data)
		else:
			self.primitiveType = 0
			for f in self.polygons:
				data = struct.pack("<3I", f[0], f[1], f[2])
				file.write(data)

	# Takes a piece (initially, the root piece, then recurses children)
	def save(self, file):
		print("saving piece [" + self.name + "]")

		startpos = file.tell()
		# seek forward the size of a piece header
		file.seek(struct.calcsize(self.binary_format), os.SEEK_CUR)
		# write name
		self.nameOffset = file.tell()
		file.write(self.name.encode() + b"\0")  # # self.name -- TODO: wip - encode("UTF-8")
		# (self, s: Union[bytes, bytearray])

		# write vert table
		self.vertTableOffset = file.tell()
		self.write_primitives(file)
		if self.primitiveType == 2:
			self.vertTableSize = len(self.polygons) * 4
		else:
			self.vertTableSize = len(self.polygons) * 3

		# write verts
		self.vertsOffset = file.tell()
		for v in self.verts:
			v.save(file)

		self.numVerts = len(self.verts)

		self.numChildren = len(self.children)
		print("saving " + str(self.numChildren) + " children")
		childOffsetList = []
		# save children
		for c in self.children:
			childOffsetList.append(file.tell())
			c.save(file)
		# write child offset list
		self.childrenOffset = file.tell()
		for c in childOffsetList:
			data = struct.pack("<I", c)
			file.write(data)

		# record end pos
		endpos = file.tell()

		# jump back to the beginning
		file.seek(startpos, os.SEEK_SET)

		# write piece header
		data = struct.pack(self.binary_format,
						   self.nameOffset,
						   self.numChildren,
						   self.childrenOffset,
						   self.numVerts,
						   self.vertsOffset,
						   self.vertType,
						   self.primitiveType,
						   self.vertTableSize,
						   self.vertTableOffset,
						   self.collisionDataOffset,
						   self.xoffset,
						   self.yoffset,
						   self.zoffset)
		file.write(data)

		# jump back to the end ready for the next piece
		file.seek(endpos, os.SEEK_SET)
		print("done [" + self.name + "]")

	def get_verts(self):
		tmp_verts = []
		for i in range(0, len(self.verts)):
			tmp_verts.append([self.verts[i].xpos, self.verts[i].ypos, self.verts[i].zpos])
		return tmp_verts


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

	def save(self, file):
		data = struct.pack(self.binary_format,
						   self.xpos,
						   self.ypos,
						   self.zpos,
						   self.xnormal,
						   self.ynormal,
						   self.znormal,
						   self.texu,
						   self.texv)
		file.write(data)


def asciiz(s):
	n = 0
	while ord(s[n]) != 0:
		n = n + 1
	return s[0:n]

def ProcessPiece(piece, scene):  # Empty or Mesh, will recurse through children
	obj = piece.mesh

	if obj.type == 'EMPTY' or obj.type == 'MESH':  # or: in {'MESH'} etc
		### Apply scale/rotation
		apply_transform(obj, use_location=False, use_rotation=True, use_scale=True)
			#obj.data.transform(obj.matrix_world)
			#obj.data.update()
			#matrix = Matrix.Identity(4)
			#obj.matrix_world = matrix
			#objLoc = obj.matrix_world @ obj.location
		localPos = obj.matrix_local #local x = [0][3], y = [1][3], z = [2][3]
		piece.xoffset = -localPos[0][3] # -obj.location[0] #objLoc[0]
		piece.yoffset = localPos[2][3] # obj.location[2] #objLoc[1]
		piece.zoffset = localPos[1][3] # obj.location[1] #objLoc[2]

	#########################################
	# For 3D meshes, export the geometry
	#########################################
	if obj.type == 'MESH':
		bpy.context.view_layer.objects.active = obj
		mesh = obj.data

		mesh.update()
		# bpy.ops.object.mode_set(mode='EDIT')
		# bmesh.update_edit_mesh(mesh)  # , True
		# bpy.ops.object.mode_set(mode='OBJECT')

		# Split polygons by UV islands (to prevent the shared/synced UVs issue in S3Os)
		# From: https://blender.stackexchange.com/questions/73647/python-bmesh-for-loop-breaking-trying-to-split-mesh-via-uv-islands
		bpy.ops.object.mode_set(mode='EDIT')
		bm = bmesh.from_edit_mesh(mesh)
		bm.select_mode = {'FACE'}
		faceGroups = []
		bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
		save_sync = scene.tool_settings.use_uv_select_sync
		scene.tool_settings.use_uv_select_sync = True
		faces = set(bm.faces[:])
		while faces:
			bpy.ops.mesh.select_all(action='DESELECT')
			face = faces.pop()
			face.select = True
			bpy.ops.uv.select_linked()
			selected_faces = {f for f in faces if f.select}
			selected_faces.add(face)  # this or bm.faces above?
			faceGroups.append(selected_faces)
			faces -= selected_faces
		scene.tool_settings.use_uv_select_sync = save_sync
		for g in faceGroups:
			bpy.ops.mesh.select_all(action='DESELECT')
			for f in g:
				f.select = True
			bpy.ops.mesh.split()
		mesh.update()
		bpy.ops.object.mode_set(mode='OBJECT')


		# piece.verts = []
		# piece.polygons = []
		if not len(obj.data.uv_layers):
			print("UV coordinates not found! Did you unwrap this object?") # Auto-unwrapping.")
			#TODO: Auto-unwrap to avoid errors
			# bpy.ops.object.mode_set(mode='OBJECT')
			# bpy.ops.uv.smart_project()
		else:
			mesh.calc_loop_triangles()
			uv_layer = mesh.uv_layers.active.data

			#print ("offsets: "+str(piece.xoffset)+", "+str(piece.yoffset)+", "+str(piece.zoffset))
			#objLoc = obj.matrix_world.decompose()  # obj.matrix_world @ obj.location
			#print ("objLoc: "+str(objLoc[0][0])+", "+str(objLoc[1][0])+", "+str(objLoc[2][0]))
			for v in mesh.vertices:
				#v_co = mathutils.Vector((v.co.x + objLoc[0][0], v.co.y + objLoc[2][0], v.co.z + objLoc[1][0]))
				#v_co = obj.matrix_world @ v_co      # apply world rotation to vertex pos
				vert = s3o_vert()
				vert.xpos = -v.co.x # v_co.x # + objLoc[0][0]
				vert.ypos = v.co.z # v_co.y # + objLoc[1][0]
				vert.zpos = v.co.y # v_co.z # + objLoc[2][0] # piece.zoffset
				vert.xnormal = v.normal.x
				vert.ynormal = v.normal.y
				vert.znormal = v.normal.z
				piece.verts.append(vert)
			print("Exported " + str(len(piece.verts)) + " verts")
			for tri in mesh.loop_triangles:     # polygons
				faceIndices = []
				for loop_index in tri.loops:     # loop_indices # range(poly.loop_start, poly.loop_start + poly.loop_total):
					loop = mesh.loops[loop_index]
					vIndex = loop.vertex_index
					faceIndices.append(vIndex)
					# get uvs
					piece.verts[vIndex].texu = uv_layer[loop_index].uv.x  # poly.uv[i].x
					piece.verts[vIndex].texv = uv_layer[loop_index].uv.y  # poly.uv[i].y
				piece.polygons.append(faceIndices)
			piece.numVerts = len(piece.verts)
			piece.vertTableSize = len(piece.polygons)

	# Recurse through children |=> piece.children[idx] = [piece,...]
	for idx, childPiece in enumerate(piece.children):
		piece.children[idx] = ProcessPiece(childPiece, scene)

	return piece


def apply_modifiers(obj):
	ctx = bpy.context.copy()
	ctx['object'] = obj
	for _, m in enumerate(obj.modifiers):
		try:
			ctx['modifier'] = m
			bpy.ops.object.modifier_apply(ctx, modifier=m.name)
		except RuntimeError:
			print(f"Error applying {m.name} to {obj.name}, removing it instead.")
			obj.modifiers.remove(m)

	for m in obj.modifiers:
		obj.modifiers.remove(m)


def save_s3o_file(s3o_filename,
                  context,
                  use_selection=False,
                  use_mesh_modifiers=False,
                  use_triangles=False,
                  ):

	######
	print("")
	print("Use selection: " + str(use_selection)
	      + ", Use meshmods: " + str(use_mesh_modifiers)
	      + ", Use triangles: " + str(use_triangles)
	      )

	objdir = os.path.dirname(s3o_filename)
	rootdir = folder_root(objdir, "objects3d")
	texsdir = ""
	# TODO: Add support for textures dir (texsdir)
	if rootdir is None:
		texsdir = objdir
	else:
		texsdir = os.path.join(rootdir, find_in_folder(rootdir, 'unittextures'))

	header = s3o_header()

	scene = context.scene  # Blender.Scene.GetCurrent()

	# get the texture name to save into the header
	# # material = Material.Get('SpringMat')
	# # textures = material.getTextures()
	# # We're just assigning default texture names now. Easy to change in UpSpring.
	header.texture1 = "texture1"  # os.path.basename(textures[0].tex.image.getFilename())
	header.texture2 = "texture2"  # os.path.basename(textures[1].tex.image.getFilename())
	# print("texture1: " + header.texture1)
	# print("texture2: " + header.texture2)

	foundRadius = False
	foundHeight = False

	# # Default Values (if no 'SpringRadius' or 'SpringHeight' objects are found)
	header.radius = 50
	header.midx = 0
	header.midy = 0
	header.midz = 0

	# get the radius from the SpringRadius empty sphere size
	pieces = []
	parentChildren = {}   # dictionary
	for obj in bpy.data.objects:
		if 'SpringRadius' in obj.name:
			header.radius = obj.empty_display_size # dimensions[0]  # getSize()
			header.midx = -obj.location[0]  # getLocation()
			header.midy = obj.location[2]
			header.midz = obj.location[1]
			foundRadius = True
			continue
		if 'SpringHeight' in obj.name:
			header.height = obj.location[2]
			foundHeight = True
			continue

		if use_selection and obj != bpy.context.object:
			continue
		if obj.type == 'ARMATURE':
			continue

		if use_mesh_modifiers:
			apply_modifiers(obj)

		if use_triangles:
			mesh = obj.data
			# First make the target object active, then switch to Edit mode
			bpy.context.view_layer.objects.active = obj
			bpy.ops.object.mode_set(mode='EDIT')
			bm = bmesh.from_edit_mesh(mesh)
			bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
			bmesh.update_edit_mesh(mesh) #, True
			bpy.ops.object.mode_set(mode='OBJECT')

		# #TODO: Remove. Brute Force test
		# origin = bpy.data.objects['SceneRoot']
		# origin.rotation_euler[0] = radians(-90)     # ZXY rotation order
		# origin.rotation_euler[1] = radians(180)     # ZXY rotation order

		piece = s3o_piece()
		#########################################
		# go through all mesh objects and empties, then convert them to s3o_pieces and set origins (as offsets)
		#########################################
		if obj.type == 'EMPTY' or obj.type == 'MESH':  # or: in {'MESH'} etc
			# TODO: Add undo for each destructive operation
			piece.mesh = obj  # # Test
			piece.name = obj.name
			piece.verts = []
			piece.polygons = []
			print("-----------------------------")
			print("Parsing [" + obj.name + "]")
			piece.primitiveType = 0
			piece.vertType = 0
			piece.numVerts = 0
			piece.vertTableSize = 0
			if obj.parent:  # getParent()
				piece.parent = obj.parent # # .name
				# initialize the parent piece into the children dict, if needed
				if piece.parent.name not in parentChildren:
					parentChildren[piece.parent.name] = []
				parentChildren[piece.parent.name].append(piece)    # then append this piece
				print("    Child of " + piece.parent.name)
			else:
				piece.parent = None  # ''

		if obj.type == 'EMPTY' or obj.type == 'MESH':  # or: in {'MESH'} etc
			# Finally, append the (valid) piece to the list of pieces
			pieces.append(piece)

	# # No longer aborts if these objects weren't found.
	if not foundRadius:
		print("Could not find SpringRadius object. Using Default Values.")
	if not foundHeight:
		print("Could not find SpringHeight object. Using Default Value.")

	# # find the piece with no parent and set it as the Root
	rootPiece = None
	for p in pieces:
		if p.name in parentChildren:    # if it's a parent of another piece
			p.children = parentChildren[p.name]   # copy/assign the 'children' array stored in parentChildren for that parent
		if p.parent is None and ('SpringRadius' not in p.name) and ('SpringHeight' not in p.name): #p.parent == ''
			rootPiece = p
			print("Root = [" + rootPiece.name + "]")

	if rootPiece is None:
		print("No root object found. Aborting")
		return

	try:
		file = open(s3o_filename, "wb")
	except IOError:
		print("Cannot open " + s3o_filename + " for writing")
		return

	# skip forward the size of the header, we'll come back later to write the header
	file.seek(struct.calcsize(header.binary_format), os.SEEK_CUR)

	# Do the required geometric manipulations to the hierarchy of pieces
	rootPiece = ProcessPiece(rootPiece, scene)

	header.rootPieceOffset = file.tell()
	rootPiece.save(file)

	# save the texture names and write their offsets in the header
	if header.texture1:
		header.texture1Offset = file.tell()
		file.write(header.texture1.encode() + b'\0')  # #
	if header.texture2:
		header.texture2Offset = file.tell()
		file.write(header.texture2.encode() + b'\0')  # #

	# jump back to the beginning to save the header
	file.seek(0, os.SEEK_SET)
	header.save(file)
	file.close()

	return

#@orientation_helper(axis_forward='Z', axis_up='Y') - not needed, we only export Y-up, Z-forward
class ExportS3O(bpy.types.Operator, ExportHelper):
	"""Export a file in the Spring S3O format (.s3o)"""
	bl_idname = "export_scene.s3o"  # important since it's how bpy.ops.export_scene.osm is constructed
	bl_label = "Export Spring S3O"
	bl_options = {"UNDO"}

	# ExportHelper mixin class uses this
	filename_ext = ".s3o"

	filter_glob: StringProperty(
		default="*.s3o",
		options={"HIDDEN"},
	)

	use_selection: BoolProperty(
		name="Selection Only",
		description="Export selected objects only",
		default=False,
	)

	use_mesh_modifiers: BoolProperty(
		name="Apply Modifiers",
		description="Applies the Modifiers",
		default=True,
	)

	use_triangles: BoolProperty(            # convert_to_tris
		name="Convert quads to triangles",
		description="Convert the mesh's quads and n-gons to triangles",
		default=True
	)

	def execute(self, context):
		# Convert all properties into a dictionary, to be passed by ** (unpack)
		# keywords = self.as_keywords(ignore=("axis_forward",
		# 									"axis_up",
		# 									"filter_glob",
		# 									))
		# global_matrix = axis_conversion(to_forward=self.axis_forward,
		# 								to_up=self.axis_up,
		# 								).to_4x4()
		# keywords["global_matrix"] = global_matrix
		# keywords["use_global_matrix"] = self.axis_forward != 'Y' or self.axis_up != 'Z'

		start_time = time.time()
		print("\n######################")
		print("#### Begin Export ####")
		print("######################\n")


		# setting active object if there is no active object
		if context.mode != "OBJECT":
			# if there is no object in the scene, only "OBJECT" mode is provided
			# if not context.scene.objects.active:
			# 	context.scene.objects.active = context.scene.objects[0]
			bpy.ops.object.mode_set(mode="OBJECT")
		bpy.ops.object.select_all(action="DESELECT")

		# # ====== Actually export the s3o file
		save_s3o_file( self.filepath, context,
		               self.use_selection,
		               self.use_mesh_modifiers,
		               self.use_triangles,
		               )

		bpy.ops.object.select_all(action="DESELECT")

		print("\n######################")
		print("Ding! Export Complete in %s seconds" % (time.time() - start_time))
		print("######################\n\n")
		return {"FINISHED"}

	def invoke(self, context, event):
		wm = context.window_manager

		# File selector
		wm.fileselect_add(self)  # will run self.execute()
		return {'RUNNING_MODAL'}


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
	self.layout.operator(ExportS3O.bl_idname, text="Spring Object (.s3o)")


def register():
	bpy.utils.register_class(ExportS3O)
	try:
		bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
	except AttributeError:
		# Blender < 2.80
		bpy.types.INFO_MT_file_export.append(menu_func_export)


def unregister():
	bpy.utils.unregister_class(ExportS3O)
	try:
		bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
	except AttributeError:
		# Blender < 2.80
		bpy.types.INFO_MT_file_export.remove(menu_func_export)


# This allows you to run the script directly from blenders text editor
# to test the addon without having to install it.
if __name__ == "__main__":
	register()
