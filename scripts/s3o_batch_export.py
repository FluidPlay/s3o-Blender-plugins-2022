# exports each root-level object into its own file
# will remove root-level objects prefixes, if there is/are underscore(s) in its name (eg: armaca_2_base => armaca_2)
# HOW-TO: -1: Make sure all object hierarchies to be exported are in the root
#         - No single parent as usual in s3os, apply transformation then delete it if any, to auto-unparent all children
# -2: Set up text1name and text2name variables below
# -3: Copy-paste this script in any script window, click on "Run"

import bpy
import os

text1name = "corota_tex1.dds"
text2name = "corota_tex2.dds"

bpy.ops.object.select_all(action='DESELECT')

# export to source blend file location
basedir = os.path.dirname(bpy.data.filepath)

if not basedir:
    raise Exception("Blend file is not saved")

root_objs = []
for obj in bpy.data.objects:
    if obj.parent is None:
        root_objs.append(obj)					# Store in root_objs table


def select_with_children(obj):
    obj.select_set(True)
    for child in obj.children:
        select_with_children(child)
        #child.select_set(True)


for obj in root_objs:
    print("\t#### Bulk-parsing: "+obj.name+"\t")
    select_with_children(obj)
    obj_name = bpy.path.clean_name(obj.name)
    org_name = obj_name
    split_name = obj_name.split("_")
    split_name_len = len(split_name)
    if split_name_len > 1:
        obj_name = ""
        rootName = split_name[-1]               # Last element (eg: _base within armaca_base)
        for i in range(split_name_len):
            if i < (split_name_len - 1):
                if i > 0:
                    obj_name = obj_name + "_"
                obj_name = obj_name + split_name[i]
        # print("\tOrg obj name: " + obj.name + ", file name: " + file_name + ", root: "+rootName)
        obj.name = rootName
    file_name = os.path.join(basedir, obj_name)
    bpy.ops.export_scene.s3o(filepath=file_name+".s3o", use_selection=True, texture1_name=text1name, texture2_name=text2name)
    obj.name = org_name                         # restore original name (if it has underscores)
    bpy.ops.object.select_all(action='DESELECT')
