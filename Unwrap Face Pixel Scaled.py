bl_info = {
    "name": "Unwrap Face Pixel Scaled",
    "author": "Ben Hopkins",
    "version": (1, 3),
    "blender": (3, 0, 0),
    "location": "View3D > UV > Unwrap Pixel",
    "description": "Unwraps a face with the desired pixel scale.",
    "warning": "",
    "wiki_url": "",
    "category": "UV",
}

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
    
    buffer: bpy.props.FloatProperty(
        name="Buffer",
        default=4,
        subtype='NONE',
        description="Offset between UV faces",
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
        bm.faces.ensure_lookup_table()
        uv_layer = bm.loops.layers.uv[0]

        multifaceOffset = 0
        for face in bm.faces:
            if not face.select:
                continue
            
            center = face.calc_center_median()
            loops = face.loops
            
            # find the bottom two vertices
            nLoops = len(loops)
            firstBottomLoop = 0
            bottomValue = loopSortValue(loops, 0)
            for li in range(nLoops):
                testValue = loopSortValue(loops, li)
                if testValue < bottomValue:
                    bottomValue = testValue
                    firstBottomLoop = li
            
            # the "x-axis" is the bottom vertices vector
            secondBottomLoop = firstBottomLoop + 1
            if secondBottomLoop == len(loops):
                secondBottomLoop = 0
            x = loops[secondBottomLoop].vert.co - loops[firstBottomLoop].vert.co
            x.normalize()
            
            # get the "y-axis" from the bottom vertices vector
            y = x.cross(face.normal)
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
                                halfScale = self.pixelScale / 2
                                offset = [math.floor(offset[0] * halfScale) / halfScale, math.floor(offset[1] * halfScale) / halfScale]
            
            # calculate UVs
            maxU = 0
            for li in range(nLoops):
                loop = loops[li]
                d = loop.vert.co - center
                if self.correctForScale:
                    d.x *= objectScale.x
                    d.y *= objectScale.y
                    d.z *= objectScale.z
                u = d.dot(x) * scale + offset[0] + multifaceOffset
                v = d.dot(y) * scale + offset[1]
                uv =   (round(u * roundSize) / roundSize,
                        round(v * roundSize) / roundSize)
                loop[uv_layer].uv = uv
                maxU = max(maxU, d.dot(x) * scale)
            multifaceOffset += 2 * maxU + self.buffer / currentTexture.size[1]
            if(self.buffer == 0):
                multifaceOffset = 0
            
            bmesh.update_edit_mesh(mesh)
        
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
