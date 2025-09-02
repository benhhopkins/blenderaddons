bl_info = {
    "name": "Vertex Color From Normals",
    "author": "Ben Hopkins",
    "version": (1, 0),
    "blender": (4, 1, 0),
    "location": "3D View Edit Mode > Vertex > VColor From Normals",
    "description": "Assigns vertex colors along a gradient according to their normal angle.",
    "warning": "",
    "wiki_url": "",
    "category": "mesh",
}

import bpy
import bmesh
import math
import mathutils
from mathutils import Vector

class MESH_OT_vcolor_normals(bpy.types.Operator):
    """Assigns vertex colors along a gradient according to their normal angle"""
    bl_idname = "mesh.vcolor_normals"
    bl_label = "VColor Normals"
    bl_options = {'REGISTER', 'UNDO'}
    
    smoothAngle: bpy.props.FloatProperty(
        name="Smooth Angle",
        default=30,
        subtype='NONE',
        description="Smooth vertex colors when angle between faces is less, in degrees",
    )
    
    color0 : bpy.props.FloatVectorProperty(
        subtype='COLOR', 
        min=0.0, 
        max=1.0,
        default=(1.0, 1.0, 1.0),
        size=3)
        
    color1 : bpy.props.FloatVectorProperty(
        subtype='COLOR', 
        min=0.0, 
        max=1.0,
        default=(0.8, 0.8, 0.8),
        size=3)
        
    color2 : bpy.props.FloatVectorProperty(
        subtype='COLOR', 
        min=0.0, 
        max=1.0,
        default=(0.5, 0.5, 0.5),
        size=3)

    def execute(self, context):
        # Get the active object and ensure it's in edit mode
        obj = context.active_object
        if obj is None or obj.type != 'MESH' or obj.mode != 'EDIT':
            return

        bm = bmesh.from_edit_mesh(obj.data)
        vertex_color_layer_name = "Col"
        if vertex_color_layer_name not in bm.loops.layers.color:
            bm.loops.layers.color.new(vertex_color_layer_name)
        vertex_color_layer = bm.loops.layers.color["Col"]

        up = Vector((0, 0, 1))
        color0 = Vector((self.color0[0], self.color0[1], self.color0[2]))
        color1 = Vector((self.color1[0], self.color1[1], self.color1[2]))
        color2 = Vector((self.color2[0], self.color2[1], self.color2[2]))
                    
        for v in bm.verts:
            if not v.select:
                continue
            for l in v.link_loops:
                face_normal = l.face.normal
                if math.degrees(face_normal.angle(v.normal)) < self.smoothAngle:
                    angle = v.normal.angle(up) # soft angle - use vertex normal to blend color
                else:
                    angle = face_normal.angle(up) # hard angle - use face normal for sharp color
                value = angle / math.pi
                vColor = color0
                if value < 0.5:
                    vColor = color0.lerp(color1, value * 2)
                else:
                    vColor = color1.lerp(color2, (value - 0.5) * 2)
                l[vertex_color_layer] = [vColor.x, vColor.y, vColor.z, 1]
                
        bmesh.update_edit_mesh(obj.data)
        
        return {'FINISHED'}


# Registration

def menu_func_MESH_OT_vcolor_normals(self, context):
    self.layout.operator(MESH_OT_vcolor_normals.bl_idname,
                        text=MESH_OT_vcolor_normals.bl_label)


def register():
    bpy.utils.register_class(MESH_OT_vcolor_normals)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(menu_func_MESH_OT_vcolor_normals)


def unregister():
    bpy.utils.unregister_class(MESH_OT_vcolor_normals)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(menu_func_MESH_OT_vcolor_normals)


if __name__ == "__main__":
    register()
