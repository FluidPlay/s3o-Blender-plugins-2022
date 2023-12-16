import sys
import bpy
import s3o_import

bpy.ops.wm.read_factory_settings(use_empty=True)
s3o_import.load_s3o_file(sys.argv[4])