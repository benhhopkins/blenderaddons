bl_info = {
    "name": "Unwrap Face Pixel Scaled",
    "author": "Ben Hopkins",
    "version": (1, 2),
    "blender": (2, 80, 0),
    "location": "View3D > UV > Unwrap Pixel",
    "description": "Unwraps a face with the desired pixel scale.",
    "warning": "",
    "wiki_url": "",
    "category": "UV",
}

# TODO: Unwrap multiple faces together

import bpy
import bmesh
import math
import mathutils

def loopSortValue(loops, nLoop):
        p1 = loops[nLoop].vert.co
        loop2 = nLoop + 1
        if loop2 == len(loops):
            loop2 = 0
        p2 = loops[loop2].vert.co
    
        value = p1.x + p2.x + 100 * (p1.y + p2.y) + 1000 * (p1.z + p2.z)
        return value

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
    
    correctForScale: bpy.props.BoolProperty(
        name="Correct for unapplied Object Scale",
        default=True,
        subtype='NONE',
        description="Corrects the UVs as if the object has a scale of 1.",
    )

    alignedToGrid: bpy.props.BoolProperty(
        name="Aligned to Grid",
        default=True,
        subtype='NONE',
        description="Align the generated UVs to the pixel scale",
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

        objectScale = context.edit_object.scale
        if objectScale.x != 1.0 and objectScale.y != 1.0 and objectScale.z != 1.0:
            self.report({'WARNING'}, 'Warning: Object scale is not 1.0!')

        bm = bmesh.from_edit_mesh(mesh)
        
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        uv_layer = bm.loops.layers.uv[0]
        
        if bm.faces.active is None:
            self.report({'INFO'}, 'Must have face selected')
            return {'CANCELLED'}

        active = bm.faces.active
        center = active.calc_center_median()
        loops = active.loops
        
        # find the bottom two verticies
        nLoops = len(loops)
        firstBottomLoop = 0
        bottomValue = loopSortValue(loops, 0)
        for li in range(nLoops):
            testValue = loopSortValue(loops, li)
            if testValue < bottomValue:
                bottomValue = testValue
                firstBottomLoop = li
        
        # the "x-axis" is the bottom verticies vector
        secondBottomLoop = firstBottomLoop + 1
        if secondBottomLoop == len(loops):
            secondBottomLoop = 0
        x = loops[secondBottomLoop].vert.co - loops[firstBottomLoop].vert.co
        x.normalize()
        
        # get the "y-axis" from the bottom verticies vector
        y = x.cross(active.normal)
        y.normalize()
        y.negate()
        
        # find texture scale and center of current UV screen area
        offset = [0.5, 0.5]
        scale = self.pixelScale / 128.0
        roundSize = 128.0
        for area in bpy.context.screen.areas :
            if area.type == 'IMAGE_EDITOR':
                currentTexture = area.spaces.active.image
                scale = self.pixelScale / currentTexture.size[1]
                roundSize = currentTexture.size[1]
                for region in area.regions:
                    if region.type == 'WINDOW':
                        offset = region.view2d.region_to_view(region.width / 2, region.height / 2)
                        if self.alignedToGrid:
                            offset = [math.floor(offset[0] * self.pixelScale) / self.pixelScale, math.floor(offset[1] * self.pixelScale) / self.pixelScale]
        
        # calculate UVs
        for li in range(nLoops):
            loop = loops[li]
            d = loop.vert.co - center
            if self.correctForScale:
                d.x *= objectScale.x
                d.y *= objectScale.y
                d.z *= objectScale.z
            u = d.dot(x) * scale + offset[0]
            v = d.dot(y) * scale + offset[1]
            uv =   (round(u * roundSize) / roundSize,
                    round(v * roundSize) / roundSize)
            loop[uv_layer].uv = uv            
        
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
