# Mass optimize *.s3o, this needs the s3o_import.py s3o_export_2022.py addons installed.
#
# this script won't override models with the same name.

import sys
import bpy
import os
import s3o_import
import s3o_export_2022

def find_obj():
    for obj in bpy.data.objects:
        if 'SpringRadius' in obj.name or 'SpringHeight' in obj.name:
            continue

        if obj.parent == None and (obj.type == 'EMPTY' or obj.type == 'MESH'):
            return obj

    return None

def file_iter(path, par_ext):
    for dirpath, _, filenames in os.walk(path):
        for filename in filenames:
            ext = os.path.splitext(filename)[1]
            if ext.lower() == par_ext:
                yield os.path.join(dirpath, filename)

def reset_blend():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def convert(par_filename : str):
    reset_blend()

    area_type = 'VIEW_3D' # change this to use the correct Area Type context you want to process in
    areas  = [area for area in bpy.context.window.screen.areas if area.type == area_type]

    if len(areas) <= 0:
        raise Exception(f"Make sure an Area of type {area_type} is open or visible in your screen!")

    with bpy.context.temp_override(
        window=bpy.context.window,
        scene=bpy.context.scene,
        selected_objects=bpy.context.selected_objects,
        area=areas[0],
        region=[region for region in areas[0].regions if region.type == 'WINDOW'][0],
        screen=bpy.context.window.screen
    ):
        #
        # Import
        context = bpy.context;
        if context.mode != "OBJECT":
            if not context.scene.objects.active:
                context.scene.objects.active = context.scene.objects[0]
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")

        s3o_import.load_s3o_file(par_filename)

        # Force redraw before save.
        # bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        
        #
        # Save
        my_obj = find_obj()
        if my_obj == None:
            raise Exception("No object found")
        
        texture1_name = "texture1.dds"
        texture2_name = "texture1.dds"

        if "s3o_texture1" in my_obj:
            texture1_name = my_obj["s3o_texture1"]
        if "s3o_texture2" in my_obj:
            texture2_name = my_obj["s3o_texture2"]

        print("Optimizing %r, with texture1 %r, texture2: %r" % (par_filename, texture1_name, texture2_name))

        # setting active object if there is no active object
        if bpy.context.mode != "OBJECT":
            # if there is no object in the scene, only "OBJECT" mode is provided
            # if not context.scene.objects.active:
            # 	context.scene.objects.active = context.scene.objects[0]
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")

        # bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

        s3o_export_2022.save_s3o_file(
            par_filename, 
            bpy.context,
            use_mesh_modifiers=True,
            use_remove_base_plate=True,
            use_triangles=True,
            remove_suffix=False,
            texture1_name=texture1_name, 
            texture2_name=texture2_name)

if __name__ == "__main__":
    convert(sys.argv[5])