# Mass convert *.s3o to *.blend, this needs the s3o_import.py addon installed.
#
# Change IMPORT_DIR and EXPORT_DIR then run "blender -P s3o_batch_convert_script.py",
# this script won't override models with the same name.

import bpy
import os
import s3o_import

IMPORT_DIR = "~/Projekte/techannihilation/TA/objects3d/arm"
EXPORT_DIR = "~/Desktop/TA/objects3d/arm"

def file_iter(path, ext):
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            ext = os.path.splitext(filename)[1]
            if ext.lower().endswith(ext):
                yield os.path.join(dirpath, filename)

def reset_blend():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def convert_recursive(base_path):
    for filepath_src in file_iter(base_path, ".s3o"):
        filepath_dst = os.path.join(EXPORT_DIR, os.path.splitext(os.path.basename(filepath_src))[0] + ".blend")

        if os.path.exists(filepath_dst):
            print("Existing %r -> %r" % (filepath_src, filepath_dst))
            continue

        print("Converting %r -> %r" % (filepath_src, filepath_dst))

        context = bpy.context;
        if context.mode != "OBJECT":
            if not context.scene.objects.active:
                context.scene.objects.active = context.scene.objects[0]
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")

        s3o_import.load_s3o_file(filepath_src)
        bpy.ops.wm.save_as_mainfile(filepath=filepath_dst)

        reset_blend()

if __name__ == "__main__":
    convert_recursive(IMPORT_DIR)