bl_info = {
    "name": "Coplanar by 3 Verts",
    "author": "NirenYang[BlenderCN]",
    "version": (0, 2),
    "blender": (2, 80, 0),
    "location": "3d view - toolbar",
    "description": "Make vertices coplanar using a plane defined by the first/last three selected verts. Updated to work in 2.8 by benhhopkins.",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "mesh",
}
import bpy
import bmesh
from mathutils.geometry import intersect_line_plane
from mathutils.geometry import distance_point_to_plane
from mathutils.geometry import normal
    
enum_ref = [( 'first', 'First', 'Defined by the first three selected verts' ),
            ( 'last', 'Last', 'Defined by the last three selected verts' )]
class MESH_OT_3points_flat_trim(bpy.types.Operator):
    """
    Manually pick three vertices to define the reference plane
    """
    bl_idname = 'mesh.3points_flat_trim'
    bl_label = 'Coplanar by 3 Verts'
    bl_options = {'REGISTER', 'UNDO'}
    
    ref_order: bpy.props.EnumProperty(name='Reference Plane', description='Use the first/last three selected vertices to define the reference plane', items=enum_ref, default="last")
    filter_distance: bpy.props.FloatProperty(name='Filter Distance', description='Only affects vertices further than this distance', default=0.0, precision=3, min=0.0)
    
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH')
        
    def execute(self, context):
        C = context
        D = bpy.data
        ob = C.active_object
        
        #if bpy.app.debug != True:
        #    bpy.app.debug = True
        #    if C.active_object.show_extra_indices != True:
        #        C.active_object.show_extra_indices = True
        if ob.mode == 'OBJECT':
            me = C.object.data
            bm = bmesh.new()
            bm.from_mesh(me)
        else:
            obj = C.edit_object
            me = obj.data
            bm = bmesh.from_edit_mesh(me)
        bm.select_history.validate()
        if len(bm.select_history) < 3:
            self.report({'INFO'}, 'Pick three vertices first')
            return {'CANCELLED'}
        
        points3Index = []
        points3 = []
        _ordering = bm.select_history if self.ref_order=="first" else list(bm.select_history)[::-1]
        for i in _ordering:
            if len(points3) >= 3:
                break
            elif isinstance(i, bmesh.types.BMVert):
                points3.append(i.co)
                points3Index.append(i.index)
        print(points3Index)
        if len(points3) < 3:
            self.report({'INFO'}, 'At least three vertices are needed being selected')
            return {'CANCELLED'}
        
            
        points3Normal = normal(*points3)
        for v in bm.verts:
            if v.select and v.index not in points3Index:
                _move = True
                if self.filter_distance > 0.0:
                    _move = abs(distance_point_to_plane(v.co, points3[0], points3Normal)) < self.filter_distance
                if _move == True:
                    v.co = intersect_line_plane(v.co, v.co+points3Normal, points3[0], points3Normal)
        if ob.mode == 'OBJECT':
            bm.to_mesh(me)
            bm.free()
        else:
            bmesh.update_edit_mesh(me, True)
            
        return {'FINISHED'}
        
def menu_func_MESH_OT_3points_flat_trim(self, context):
    self.layout.operator(MESH_OT_3points_flat_trim.bl_idname,
                        text=MESH_OT_3points_flat_trim.bl_label)
def register():   
    bpy.utils.register_class(MESH_OT_3points_flat_trim) 
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(menu_func_MESH_OT_3points_flat_trim)
    
def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(menu_func_MESH_OT_3points_flat_trim)
    bpy.utils.unregister_class(MESH_OT_3points_flat_trim)
    
 

if __name__ == "__main__":
    register()