import mathutils
import math
import bmesh
import bpy
bl_info = {
    "name": "Unwrap Reset Size",
    "author": "Ben Hopkins",
    "version": (1, 1, 1),
    "blender": (3, 0, 0),
    "location": "View3D > UV > Reset Sized",
    "description": "Resets face UVs with an input size.",
    "warning": "",
    "wiki_url": "",
    "category": "UV",
}


def loopSortValue(loops, nLoop):
    p1 = loops[nLoop].vert.co
    loop2 = nLoop + 1
    if loop2 == len(loops):
        loop2 = 0
    p2 = loops[loop2].vert.co

    value = p1.x + p2.x + 100 * (p1.y + p2.y) + 1000 * (p1.z + p2.z)
    return value


class UV_MT_reset_sized(bpy.types.Operator):
    bl_idname = "view3d.reset_sized"
    bl_label = "Reset Sized"
    bl_options = {'REGISTER', 'UNDO'}

    pixelSize: bpy.props.FloatProperty(
        name="Reset Pixel Length",
        default=6,
        subtype='NONE',
        description="Pixels per meter",
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

        bm = bmesh.from_edit_mesh(mesh)

        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        uv_layer = bm.loops.layers.uv[0]

        for face in bm.faces:
            if not face.select:
                continue

            center = face.calc_center_median()
            loops = face.loops

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
            x = loops[secondBottomLoop].vert.co - \
                loops[firstBottomLoop].vert.co
            x.normalize()

            # get the "y-axis" from the bottom verticies vector
            y = x.cross(face.normal)
            y.normalize()
            y.negate()

            # find texture scale and center of current UV screen area
            offset = [0.5, 0.5]
            scale = self.pixelSize / 128.0
            roundSize = 128
            for area in bpy.context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    currentTexture = area.spaces.active.image
                    scale = self.pixelSize / currentTexture.size[1]
                    roundSize = currentTexture.size[1]
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            offset = region.view2d.region_to_view(
                                region.width / 2, region.height / 2)

            # calculate UVs
            for li in range(nLoops):
                loop = loops[li]
                d = loop.vert.co - center
                u = min(max(round(d.dot(x) * 100), -1), 1) * \
                    scale / 2 + offset[0]
                v = min(max(round(d.dot(y) * 100), -1), 1) * \
                    scale / 2 + offset[1]
                uv = (round(u * roundSize) / roundSize,
                      round(v * roundSize) / roundSize)
                loop[uv_layer].uv = uv

            bmesh.update_edit_mesh(mesh)

        return {'FINISHED'}


# Registration

def menu_func_UV_MT_unwrap_reset_sized(self, context):
    self.layout.operator(UV_MT_reset_sized.bl_idname,
                         text=UV_MT_reset_sized.bl_label)


def register():
    bpy.utils.register_class(UV_MT_reset_sized)
    bpy.types.VIEW3D_MT_uv_map.append(menu_func_UV_MT_unwrap_reset_sized)


def unregister():
    bpy.utils.unregister_class(UV_MT_reset_sized)
    bpy.types.VIEW3D_MT_uv_map.remove(menu_func_UV_MT_unwrap_reset_sized)


if __name__ == "__main__":
    register()
