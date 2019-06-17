bl_info = {
    "name": "View to Face",
    "author": "Ben Hopkins",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > View > Viewpoint > View Face",
    "description": "Point view towards the current face with better roll.",
    "warning": "",
    "wiki_url": "",
    "category": "Viewpoint",
}


import bpy
import bmesh
import math
import mathutils

class VIEW_MT_view_face(bpy.types.Operator):
    """Point view towards the current face"""
    bl_idname = "view3d.view_face"
    bl_label = "View Face"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH')

    def execute(self, context):
        data = context.object.data
        if not data.is_editmode:
            self.report({'INFO'}, 'Must be in edit mode')
            return {'CANCELLED'}

        obj = context.active_object
        rv3d = context.space_data.region_3d        
        bm = bmesh.from_edit_mesh(data)
        
        if bm.faces.active is not None:
            # position the view
            v = obj.matrix_world @ bm.faces.active.calc_center_median()
            rv3d.view_location = v
            
            # rotate the view            
            direction = -bm.faces.active.normal
            print(direction)
            rot_quat = direction.to_track_quat('-Z', 'Y')
            rv3d.view_rotation = rot_quat
            print(rv3d.view_rotation.to_euler())
            
            # set view distance
            rv3d.view_distance = 1
            rv3d.view_camera_zoom = 0
            rv3d.view_perspective = 'ORTHO'
        else:
            self.report({'INFO'}, 'Must have face selected')
            return {'CANCELLED'}       
        
        return {'FINISHED'}


# Registration

def menu_func_VIEW_MT_view_face(self, context):
    self.layout.operator(VIEW_MT_view_face.bl_idname,
                        text=VIEW_MT_view_face.bl_label)


def register():
    bpy.utils.register_class(VIEW_MT_view_face)
    bpy.types.VIEW3D_MT_view_viewpoint.append(menu_func_VIEW_MT_view_face)


def unregister():
    bpy.utils.unregister_class(VIEW_MT_view_face)
    bpy.types.VIEW3D_MT_view_viewpoint.remove(menu_func_VIEW_MT_view_face)


if __name__ == "__main__":
    register()
