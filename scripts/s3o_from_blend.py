import bpy

def find_obj():
    for obj in bpy.data.objects:
        if 'SpringRadius' in obj.name:
            continue
        if 'SpringHeight' in obj.name:
            continue

        if obj.parent == None and (obj.type == 'EMPTY' or obj.type == 'MESH'):
            return obj

    return None

def convert(filepath_dst : str):
    my_obj = find_obj()
    if my_obj == None:
        raise Exception("No object found")
    
    texture1_name = "texture1.dds"
    texture2_name = "texture1.dds"

    if "s3o_texture1" in my_obj:
        texture1_name = my_obj["s3o_texture1"]
    if "s3o_texture2" in my_obj:
        texture2_name = my_obj["s3o_texture2"]

    # setting active object if there is no active object
    if bpy.context.mode != "OBJECT":
        # if there is no object in the scene, only "OBJECT" mode is provided
        # if not context.scene.objects.active:
        # 	context.scene.objects.active = context.scene.objects[0]
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")

    bpy.ops.export_scene.s3o(filepath=filepath_dst, use_triangles=True, texture1_name=texture1_name, texture2_name=texture2_name)


if __name__ == "__main__":
    import sys
    convert(sys.argv[6])