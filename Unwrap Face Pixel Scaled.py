bl_info = {
    "name": "Unwrap Face Pixel Scaled",
    "author": "Ben Hopkins",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > UV > Unwrap Pixel",
    "description": "Unwraps a face with the desired pixel scale.",
    "warning": "",
    "wiki_url": "",
    "category": "Viewpoint",
}


import bpy
import bmesh
import math
import mathutils

class UV_MT_unwrap_pixel(bpy.types.Operator):
    """Point view towards the current face"""
    bl_idname = "view3d.unwrap_pixel"
    bl_label = "Unwrap Pixel"
    bl_options = {'REGISTER', 'UNDO'}
    
    pixelScale: bpy.props.FloatProperty(
        name="Pixel Scale",
        default=32,
        subtype='NONE',
        description="Pixels per meter",
    )
    
    textureSizeMeters: bpy.props.FloatProperty(
        name="Texture Size (meters)",
        default=4,
        subtype='NONE',
        description="Size of one side of the texture in meters",
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH')

    def execute(self, context):
        mesh = context.object.data
        if not mesh.is_editmode:
            self.report({'INFO'}, 'Must be in edit mode')
            return {'CANCELLED'}

        obj = context.edit_object
        bm = bmesh.from_edit_mesh(mesh)

#        rv3d = context.space_data.region_3d
        
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        uv_layer = bm.loops.layers.uv[0]
        
        if bm.faces.active is not None:
            active = bm.faces.active
            center = active.calc_center_median()
            nLoops = len(bm.faces.active.loops)
            n = active.normal
            print('normal:')
            print(n)
            i = n.to_3d()
            eul = mathutils.Euler((0, math.radians(90.0), math.radians(90.0)), 'XYZ')
            i.rotate(eul)
            i = n.cross(i)
            print('i:')
            print(i)
            j = n.to_3d()
            eul = mathutils.Euler((math.radians(90.0), 0, math.radians(90.0)), 'XYZ')
            j.rotate(eul)
            j = n.cross(j)
            print('j:')
            print(j)
            for li in range(nLoops):
                loop = active.loops[li]
                vert = loop.vert
                d = vert.co - center
                u = d.dot(i) * (self.textureSizeMeters / self.pixelScale)
                v = d.dot(j) * (self.textureSizeMeters / self.pixelScale)
                uv = (u, v)
                print(uv)
                active.loops[li][uv_layer].uv = uv
            
            '''
            active.loops[0][uv_layer].uv = (0, 0)
            active.loops[1][uv_layer].uv = (0, 1)
            active.loops[2][uv_layer].uv = (1, 1)
            active.loops[3][uv_layer].uv = (1, 0)
            '''
        else:
            self.report({'INFO'}, 'Must have face selected')
            return {'CANCELLED'}
        
        bmesh.update_edit_mesh(mesh, True)
        
        return {'FINISHED'}


# Registration

def menu_func_UV_MT_unwrap_pixel(self, context):
    self.layout.operator(UV_MT_unwrap_pixel.bl_idname,
                        text=UV_MT_unwrap_pixel.bl_label)


def register():
    bpy.utils.register_class(UV_MT_unwrap_pixel)
    bpy.types.VIEW3D_MT_uv_map.append(menu_func_UV_MT_unwrap_pixel)


def unregister():
    bpy.utils.unregister_class(UV_MT_unwrap_pixel)
    bpy.types.VIEW3D_MT_uv_map.remove(menu_func_UV_MT_unwrap_pixel)


if __name__ == "__main__":
    register()
