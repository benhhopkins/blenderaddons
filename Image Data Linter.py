# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Image Data Linter",
    "description": "Save or pack all modified images when saving the file",
    "author": "brockmann",
    "version": (0, 0, 1),
    "blender": (2, 80, 0),
    "location": "",
    "category": "Development"
}

import bpy
from bpy.app.handlers import persistent


class ImageDataLinterPrefs(bpy.types.AddonPreferences):

    bl_idname = __name__

    save: bpy.props.BoolProperty(
        name="Save modified Images",
        description="Save modified images when saving the blend",
        default=True)

    pack: bpy.props.BoolProperty(
        name="Pack un-saved Images",
        description="Pack un-saved images when saving the blend",
        default=False)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "save", toggle=True, icon="DISK_DRIVE")
        layout.prop(self, "pack", toggle=True, icon="PACKAGE")
        layout.separator()


@persistent
def pack_dirty_images(dummy):
    if bpy.context.preferences.addons[__name__].preferences.pack:
        for i in bpy.data.images:
            if i.is_dirty:
                i.pack()
                print("Packed:", i.name)

@persistent
def save_mod_images(dummy):
    if bpy.context.preferences.addons[__name__].preferences.save:
        """ Save all modified images """
        if any(i.is_dirty for i in bpy.data.images):
            bpy.ops.image.save_all_modified()


def register():
    bpy.utils.register_class(ImageDataLinterPrefs)
    bpy.app.handlers.save_pre.append(save_mod_images)
    bpy.app.handlers.save_pre.append(pack_dirty_images)

def unregister():
    bpy.app.handlers.save_pre.remove(pack_dirty_images)
    bpy.app.handlers.save_pre.remove(save_mod_images)
    bpy.utils.unregister_class(ImageDataLinterPrefs)

if __name__ == "__main__":
    register()
