bl_info = {
    "name": "Unwrap Face Pixel Scaled",
    "author": "Ben Hopkins",
    "version": (1, 8),
    "blender": (3, 0, 0),
    "location": "View3D > UV > Unwrap Pixel",
    "description": "Unwraps faces to pixel scale, Follow Active Quads, attaches Triangles, and snaps UVs to texture pixels.",
    "warning": "",
    "wiki_url": "",
    "category": "UV",
}

import bpy
import bmesh
import math
import mathutils
from collections import deque


FLAT_ANGLE = math.radians(3.0)


def loopSortValue(loops, nLoop):
    p1 = loops[nLoop].vert.co
    loop2 = nLoop + 1
    if loop2 == len(loops):
        loop2 = 0
    p2 = loops[loop2].vert.co

    value = p1.x + p2.x + 100 * (p1.y + p2.y) + 1000 * (p1.z + p2.z)
    return value


def scaledCo(co, objectScale, correctForScale):
    p = co.copy()
    if correctForScale:
        p.x *= objectScale.x; p.y *= objectScale.y; p.z *= objectScale.z
    return p


def editorImageSize(context):
    """Size of the image shown in the first UV/Image editor, used when a face's material has no image."""
    for area in context.screen.areas:
        if area.type == 'IMAGE_EDITOR' and area.spaces.active.image:
            size = area.spaces.active.image.size
            if size[0] > 0 and size[1] > 0:
                return size[0], size[1]
    return 128, 128


def editorViewCenter(context):
    for area in context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            for region in area.regions:
                if region.type == 'WINDOW':
                    return region.view2d.region_to_view(region.width / 2, region.height / 2)
    return (0.5, 0.5)


def faceTextureSize(obj, face, fallback):
    """Pixel size of the first image texture in the face's material."""
    slots = obj.material_slots
    if face.material_index < len(slots):
        mat = slots[face.material_index].material
        if mat and mat.use_nodes and mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image and node.image.size[0] > 0 and node.image.size[1] > 0:
                    return node.image.size[0], node.image.size[1]
    return fallback


def faceAxes(face, method, objectScale, correctForScale):
    loops = face.loops
    nLoops = len(loops)
    if method == 'BOTTOM':
        firstBottomLoop = 0
        bottomValue = loopSortValue(loops, 0)
        for li in range(nLoops):
            testValue = loopSortValue(loops, li)
            if testValue < bottomValue:
                bottomValue = testValue
                firstBottomLoop = li
        secondBottomLoop = (firstBottomLoop + 1) % nLoops
        x = scaledCo(loops[secondBottomLoop].vert.co, objectScale, correctForScale) - scaledCo(loops[firstBottomLoop].vert.co, objectScale, correctForScale)
    else:  # LONGEST
        x = mathutils.Vector((1.0, 0.0, 0.0))
        longest = -1.0
        for li in range(nLoops):
            edgeVec = scaledCo(loops[(li + 1) % nLoops].vert.co, objectScale, correctForScale) - scaledCo(loops[li].vert.co, objectScale, correctForScale)
            if edgeVec.length_squared > longest:
                longest = edgeVec.length_squared
                x = edgeVec
    x.normalize()
    y = x.cross(face.normal)
    y.normalize()
    y.negate()
    return x, y


def projectFaces(faces, basisFace, uvLayer, scaleU, scaleV, method, objectScale, correctForScale):
    """Planar projection of faces onto the basis face's axes, centered on the basis face."""
    x, y = faceAxes(basisFace, method, objectScale, correctForScale)
    center = scaledCo(basisFace.calc_center_median(), objectScale, correctForScale)
    for face in faces:
        for loop in face.loops:
            d = scaledCo(loop.vert.co, objectScale, correctForScale) - center
            loop[uvLayer].uv = (d.dot(x) * scaleU, d.dot(y) * scaleV)


def forceRectangle(face, uvLayer):
    """Averages the UVs of a quad into an axis-aligned rectangle."""
    if len(face.loops) != 4:
        return
    rawUVs = [loop[uvLayer].uv.copy() for loop in face.loops]
    uSorted = sorted(uv.x for uv in rawUVs)
    vSorted = sorted(uv.y for uv in rawUVs)
    uLow, uHigh = (uSorted[0] + uSorted[1]) / 2.0, (uSorted[2] + uSorted[3]) / 2.0
    vLow, vHigh = (vSorted[0] + vSorted[1]) / 2.0, (vSorted[2] + vSorted[3]) / 2.0
    uMid, vMid = (uSorted[1] + uSorted[2]) / 2.0, (vSorted[1] + vSorted[2]) / 2.0
    for loop, uv in zip(face.loops, rawUVs):
        loop[uvLayer].uv = (uLow if uv.x < uMid else uHigh, vLow if uv.y < vMid else vHigh)


def attachTriangle(tri, uvLayer, anchors, objectScale, correctForScale):
    """Unfolds a triangle off the longest edge it shares with an already-unwrapped face. Returns that face or None."""
    longestSq = -1.0
    bestEdge = None
    bestFace = None
    for edge in tri.edges:
        linked = [f for f in edge.link_faces if f != tri and f.index in anchors]
        if linked:
            lengthSq = (scaledCo(edge.verts[1].co, objectScale, correctForScale) - scaledCo(edge.verts[0].co, objectScale, correctForScale)).length_squared
            if lengthSq > longestSq:
                longestSq = lengthSq
                bestEdge = edge
                bestFace = linked[0]
    if not bestEdge:
        return None

    l1 = next(l for l in tri.loops if l.edge == bestEdge)
    l2 = l1.link_loop_next
    l3 = l2.link_loop_next
    anchorL1 = next((l for l in bestFace.loops if l.vert == l1.vert), None)
    anchorL2 = next((l for l in bestFace.loops if l.vert == l2.vert), None)
    if not anchorL1 or not anchorL2:
        return None

    u1 = anchorL1[uvLayer].uv.copy()
    u2 = anchorL2[uvLayer].uv.copy()
    l1[uvLayer].uv = u1
    l2[uvLayer].uv = u2

    p1 = scaledCo(l1.vert.co, objectScale, correctForScale)
    p2 = scaledCo(l2.vert.co, objectScale, correctForScale)
    p3 = scaledCo(l3.vert.co, objectScale, correctForScale)
    edge3d = p2 - p1
    len3d = edge3d.length
    if len3d < 1e-6:
        return None

    # Local 2D basis on the triangle's plane, mapped onto the shared UV edge
    x3d = edge3d / len3d
    n3d = edge3d.cross(p3 - p1).normalized()
    y3d = n3d.cross(x3d).normalized()
    toP3 = p3 - p1
    dx = toP3.dot(x3d)
    dy = toP3.dot(y3d)

    edge2d = u2 - u1
    len2d = edge2d.length
    x2d = edge2d / len2d if len2d > 1e-9 else mathutils.Vector((1, 0))
    y2d = mathutils.Vector((-x2d.y, x2d.x))
    l3[uvLayer].uv = u1 + (dx * x2d + dy * y2d) * (len2d / len3d)
    return bestFace


def connectedGroups(faces, canCross=lambda edge, a, b: True):
    """Splits faces into edge-connected groups."""
    allowed = {f.index for f in faces}
    seen = set()
    groups = []
    for face in faces:
        if face.index in seen:
            continue
        group = [face]
        seen.add(face.index)
        stack = [face]
        while stack:
            current = stack.pop()
            for edge in current.edges:
                for other in edge.link_faces:
                    if other.index in allowed and other.index not in seen and canCross(edge, current, other):
                        seen.add(other.index)
                        group.append(other)
                        stack.append(other)
        groups.append(group)
    return groups


def uvIslands(faces, uvLayer):
    """Groups faces that share UV-continuous edges."""
    index = {f.index: i for i, f in enumerate(faces)}
    parent = list(range(len(faces)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for face in faces:
        for loop in face.loops:
            for other in loop.edge.link_faces:
                if other == face or other.index not in index:
                    continue
                otherLoop = next(l for l in other.loops if l.edge == loop.edge)
                a1, a2 = loop[uvLayer].uv, loop.link_loop_next[uvLayer].uv
                if otherLoop.vert == loop.vert:
                    b1, b2 = otherLoop[uvLayer].uv, otherLoop.link_loop_next[uvLayer].uv
                else:
                    b1, b2 = otherLoop.link_loop_next[uvLayer].uv, otherLoop[uvLayer].uv
                if (a1 - b1).length < 1e-5 and (a2 - b2).length < 1e-5:
                    parent[find(index[face.index])] = find(index[other.index])

    islands = {}
    for face in faces:
        islands.setdefault(find(index[face.index]), []).append(face)
    return list(islands.values())


def snapAxisValues(values):
    """Maps pixel coordinates to whole pixels, keeping distinct grid lines at least one pixel apart."""
    mapping = {}
    clusterStart = None
    previous = None
    for value in sorted(set(values)):
        snapped = round(value)
        if previous is not None:
            if value - clusterStart < 0.5:
                snapped = previous
            elif snapped <= previous:
                snapped = previous + 1
        if snapped != previous:
            clusterStart = value
        mapping[value] = snapped
        previous = snapped
    return mapping


def snapIslandToPixels(island, uvLayer, width, height):
    """Rounds every UV in an island onto the texture's pixel grid, so face edges sit on pixel boundaries."""
    loops = [loop for face in island for loop in face.loops]
    us = [round(loop[uvLayer].uv.x * width, 4) for loop in loops]
    vs = [round(loop[uvLayer].uv.y * height, 4) for loop in loops]
    uMap = snapAxisValues(us)
    vMap = snapAxisValues(vs)
    for loop, u, v in zip(loops, us, vs):
        loop[uvLayer].uv = (uMap[u] / width, vMap[v] / height)


def translateIslandToPixel(island, uvLayer, width, height):
    """Moves an island by a sub-pixel amount so its corner lands on the pixel grid."""
    minU = min(loop[uvLayer].uv.x for face in island for loop in face.loops)
    minV = min(loop[uvLayer].uv.y for face in island for loop in face.loops)
    du = round(minU * width) / width - minU
    dv = round(minV * height) / height - minV
    for face in island:
        for loop in face.loops:
            loop[uvLayer].uv = (loop[uvLayer].uv.x + du, loop[uvLayer].uv.y + dv)


def cutClosedGroup(group):
    """Marks a seam along a path between the two farthest vertices so a closed group can be unwrapped. Returns the seam edges."""
    edges = {e for f in group for e in f.edges}
    groupFaces = set(group)
    if not all(sum(1 for f in e.link_faces if f in groupFaces) == 2 for e in edges):
        return []
    verts = list({v for f in group for v in f.verts})
    start, end = max(((a, b) for a in verts for b in verts), key=lambda ab: (ab[0].co - ab[1].co).length)
    previous = {start: None}
    queue = deque([start])
    while queue:
        v = queue.popleft()
        if v == end:
            break
        for edge in v.link_edges:
            if edge in edges:
                other = edge.other_vert(v)
                if other not in previous:
                    previous[other] = (v, edge)
                    queue.append(other)
    seam = []
    v = end
    while previous.get(v):
        v, edge = previous[v]
        seam.append(edge)
    for edge in seam:
        edge.seam = True
    return seam


def uvArea(face, uvLayer):
    uvs = [loop[uvLayer].uv for loop in face.loops]
    return sum(abs((uvs[i] - uvs[0]).cross(uvs[i + 1] - uvs[0])) / 2 for i in range(1, len(uvs) - 1))


class UV_MT_unwrap_pixel(bpy.types.Operator):
    """Unwrap face to pixel scale"""
    bl_idname = "view3d.unwrap_pixel"
    bl_label = "Unwrap Pixel"
    bl_options = {'REGISTER', 'UNDO'}

    pixelScale: bpy.props.FloatProperty(
        name="Pixel Scale",
        default=32,
        subtype='NONE',
        description="Pixels per meter",
    )

    alignmentMethod: bpy.props.EnumProperty(
        name="Alignment",
        description="Choose how to orient the face on the UV map",
        items=[
            ('LONGEST', "Longest Edge", "Align the longest edge horizontally"),
            ('BOTTOM', "Bottom Edge", "Align the bottom-most edge horizontally")
        ],
        default='LONGEST'
    )

    forceRectangle: bpy.props.BoolProperty(
        name="Force Rectangle",
        default=False,
        description="Averages the positions of the vertices to force the UVs into a perfect rectangle (Quads only)",
    )

    followActiveQuads: bpy.props.BoolProperty(
        name="Follow Active Quads",
        default=False,
        description="Pixel-scales one face per connected quad group (the active face where it belongs), then uses Follow Active Quads on each group. Flat ngons and triangle fans are projected, other triangles are attached or unwrapped",
    )

    snapToPixels: bpy.props.BoolProperty(
        name="Snap to Pixels",
        default=True,
        description="Rounds every UV to the texture's pixel grid so face edges line up with pixel boundaries",
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

    packUVs: bpy.props.BoolProperty(
        name="Pack Overlapping UVs",
        default=True,
        description="Automatically separates overlapping UV islands while preserving pixel scale",
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH')

    def execute(self, context):
        obj = context.object
        mesh = obj.data
        if not mesh.is_editmode:
            self.report({'INFO'}, 'Must be in edit mode')
            return {'CANCELLED'}

        objectScale = context.edit_object.scale
        if objectScale.x != 1.0 or objectScale.y != 1.0 or objectScale.z != 1.0:
            self.report({'WARNING'}, 'Warning: Object scale is not 1.0!')

        self.fallbackSize = editorImageSize(context)
        self.viewCenter = editorViewCenter(context)

        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        if not bm.loops.layers.uv:
            self.report({'WARNING'}, "Mesh has no UV map.")
            return {'CANCELLED'}

        selectedIndices = [f.index for f in bm.faces if f.select]
        activeIndex = bm.faces.active.index if bm.faces.active and bm.faces.active.select else None
        if not selectedIndices:
            self.report({'INFO'}, "No faces selected.")
            return {'CANCELLED'}

        if self.followActiveQuads:
            self.unwrapFollowActive(context, obj, mesh, selectedIndices, activeIndex)
        else:
            self.unwrapFaces(obj, mesh, selectedIndices)

        # restore the user's selection
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            f.select = False
        for i in selectedIndices:
            bm.faces[i].select = True
        if activeIndex is not None:
            bm.faces.active = bm.faces[activeIndex]
        bmesh.update_edit_mesh(mesh)

        if self.packUVs:
            self.packIslands(context, obj, mesh, selectedIndices)

        return {'FINISHED'}

    # --- helpers that depend on operator settings ---

    def textureSize(self, obj, face):
        return faceTextureSize(obj, face, self.fallbackSize)

    def origin(self, width, height):
        u, v = self.viewCenter
        if self.alignedToGrid:
            u = math.floor(u * width) / width
            v = math.floor(v * height) / height
        return u, v

    def unwrapFaces(self, obj, mesh, selectedIndices):
        """Each selected face becomes its own pixel-scaled island, laid out left to right from the view center."""
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        uvLayer = bm.loops.layers.uv.active
        objectScale = obj.scale
        islands = []
        multifaceOffset = 0.0
        for i in selectedIndices:
            face = bm.faces[i]
            width, height = self.textureSize(obj, face)
            projectFaces([face], face, uvLayer, self.pixelScale / width, self.pixelScale / height, self.alignmentMethod, objectScale, self.correctForScale)
            if self.forceRectangle:
                forceRectangle(face, uvLayer)
            originU, originV = self.origin(width, height)
            us = [loop[uvLayer].uv.x for loop in face.loops]
            for loop in face.loops:
                loop[uvLayer].uv = (loop[uvLayer].uv.x + originU + multifaceOffset, loop[uvLayer].uv.y + originV)
            if self.snapToPixels:
                snapIslandToPixels([face], uvLayer, width, height)
            if self.buffer != 0:
                multifaceOffset += math.ceil((max(us) - min(us)) * width) / width + self.buffer / width
            islands.append([face])
        bmesh.update_edit_mesh(mesh)
        return islands

    def unwrapFollowActive(self, context, obj, mesh, selectedIndices, activeIndex):
        objectScale = obj.scale
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        uvLayer = bm.loops.layers.uv.active
        selected = [bm.faces[i] for i in selectedIndices]
        islandIndices = []

        # 1. Flat ngons and coplanar triangle fans are projected as single islands
        flatDone = set()
        nonQuads = [f for f in selected if len(f.verts) != 4]
        for face in nonQuads:
            if face.index in flatDone:
                continue
            group = connectedGroups([f for f in nonQuads if f.index not in flatDone],
                                    lambda edge, a, b, n=face.normal: b.normal.angle(n, 1.0) < FLAT_ANGLE)
            group = next(g for g in group if face in g)
            if len(face.verts) > 4 or len(group) > 1:
                width, height = self.textureSize(obj, face)
                basis = max(group, key=lambda f: f.calc_area())
                projectFaces(group, basis, uvLayer, self.pixelScale / width, self.pixelScale / height, self.alignmentMethod, objectScale, self.correctForScale)
                flatDone.update(f.index for f in group)
                islandIndices.append([f.index for f in group])
        bmesh.update_edit_mesh(mesh)

        # 2. Each connected quad group: pixel-scale its start face, then Follow Active Quads
        quads = [f for f in selected if len(f.verts) == 4]
        quadGroups = [[f.index for f in g] for g in connectedGroups(quads)]
        anchors = set()
        for groupIndices in quadGroups:
            bm = bmesh.from_edit_mesh(mesh)
            bm.faces.ensure_lookup_table()
            uvLayer = bm.loops.layers.uv.active
            group = [bm.faces[i] for i in groupIndices]
            start = bm.faces[activeIndex] if activeIndex in groupIndices else max(group, key=lambda f: f.calc_area())
            width, height = self.textureSize(obj, start)
            projectFaces([start], start, uvLayer, self.pixelScale / width, self.pixelScale / height, self.alignmentMethod, objectScale, self.correctForScale)
            if self.forceRectangle:
                forceRectangle(start, uvLayer)
            if len(group) > 1:
                for f in bm.faces:
                    f.select = False
                for f in group:
                    f.select = True
                bm.faces.active = start
                bmesh.update_edit_mesh(mesh)
                try:
                    bpy.ops.uv.follow_active_quads(mode='LENGTH_AVERAGE')
                except Exception as e:
                    self.report({'WARNING'}, f"Follow Active Quads failed: {e}")
            else:
                bmesh.update_edit_mesh(mesh)
            anchors.update(groupIndices)
            islandIndices.append(list(groupIndices))

        # 3. Attach remaining triangles to unwrapped neighbours, repeating so triangle chains follow
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        uvLayer = bm.loops.layers.uv.active
        islandOf = {i: n for n, island in enumerate(islandIndices) for i in island}
        pending = [i for i in selectedIndices if i not in flatDone and len(bm.faces[i].verts) != 4]
        progress = True
        while pending and progress:
            progress = False
            remaining = []
            for i in pending:
                anchor = attachTriangle(bm.faces[i], uvLayer, anchors, objectScale, self.correctForScale)
                if anchor is None:
                    remaining.append(i)
                else:
                    anchors.add(i)
                    islandOf[i] = islandOf[anchor.index]
                    islandIndices[islandOf[i]].append(i)
                    progress = True
            pending = remaining
        bmesh.update_edit_mesh(mesh)

        # 4. Leftover triangles: single faces are projected, connected groups are unwrapped (cut open if closed)
        leftoverGroups = [[f.index for f in g] for g in connectedGroups([bm.faces[i] for i in pending])]
        for groupIndices in leftoverGroups:
            bm = bmesh.from_edit_mesh(mesh)
            bm.faces.ensure_lookup_table()
            uvLayer = bm.loops.layers.uv.active
            group = [bm.faces[i] for i in groupIndices]
            width, height = self.textureSize(obj, group[0])
            if len(group) == 1:
                projectFaces(group, group[0], uvLayer, self.pixelScale / width, self.pixelScale / height, self.alignmentMethod, objectScale, self.correctForScale)
                bmesh.update_edit_mesh(mesh)
            else:
                self.unwrapGroup(mesh, groupIndices, width, height)
            islandIndices.append(list(groupIndices))

        # 5. Lay the islands out left to right from the view center and snap them to pixels
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        uvLayer = bm.loops.layers.uv.active
        islands = [[bm.faces[i] for i in island] for island in islandIndices]
        cursor = 0.0
        for island in islands:
            width, height = self.textureSize(obj, island[0])
            originU, originV = self.origin(width, height)
            minU = min(l[uvLayer].uv.x for f in island for l in f.loops)
            maxU = max(l[uvLayer].uv.x for f in island for l in f.loops)
            minV = min(l[uvLayer].uv.y for f in island for l in f.loops)
            du = originU + cursor - minU
            dv = originV - minV
            for f in island:
                for l in f.loops:
                    l[uvLayer].uv = (l[uvLayer].uv.x + du, l[uvLayer].uv.y + dv)
            if self.snapToPixels:
                snapIslandToPixels(island, uvLayer, width, height)
            if self.buffer != 0:
                cursor += math.ceil((maxU - minU) * width) / width + self.buffer / width
        bmesh.update_edit_mesh(mesh)
        return islands

    def unwrapGroup(self, mesh, groupIndices, width, height):
        """Angle-based unwrap of a triangle group, rescaled to the pixel scale."""
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        group = [bm.faces[i] for i in groupIndices]
        seam = cutClosedGroup(group)
        seamIndices = [e.index for e in seam]
        for f in bm.faces:
            f.select = False
        for f in group:
            f.select = True
        bmesh.update_edit_mesh(mesh)
        bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.0)

        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        uvLayer = bm.loops.layers.uv.active
        for i in seamIndices:
            bm.edges[i].seam = False
        group = [bm.faces[i] for i in groupIndices]
        area3d = sum(f.calc_area() for f in group)
        area2d = sum(uvArea(f, uvLayer) for f in group)
        if area2d > 1e-12:
            k = self.pixelScale / height * math.sqrt(area3d / area2d)
            for f in group:
                for l in f.loops:
                    l[uvLayer].uv = (l[uvLayer].uv.x * k * height / width, l[uvLayer].uv.y * k)
        bmesh.update_edit_mesh(mesh)

    def packIslands(self, context, obj, mesh, selectedIndices):
        # Find an Image Editor area to build a context override
        # (select_overlap and pack require the script to "think" it's in the UV Editor)
        overrideKwargs = {}
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    overrideKwargs['window'] = window
                    overrideKwargs['screen'] = window.screen
                    overrideKwargs['area'] = area
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            overrideKwargs['region'] = region
                            break
                    break
            if 'area' in overrideKwargs:
                break

        if 'area' not in overrideKwargs:
            self.report({'WARNING'}, "An open UV/Image Editor window is required to pack overlapping UVs.")
            return

        marginFraction = self.buffer / self.fallbackSize[1]
        try:
            with context.temp_override(**overrideKwargs):
                bpy.ops.uv.select_all(action='DESELECT')
                bpy.ops.uv.select_overlap()
                bpy.ops.transform.translate(value=(0.1, 0.1, 0.0))
                bpy.ops.uv.select_all(action='SELECT')
                bpy.ops.uv.pack_islands(margin=marginFraction, scale=False, margin_method='ADD', shape_method='CONVEX', rotate=False, udim_source='ORIGINAL_AABB')
        except Exception as e:
            self.report({'WARNING'}, f"Overlap separation or packing failed: {e}")
            return

        # Packing moves islands by fractions of a pixel; nudge each back onto the grid
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        uvLayer = bm.loops.layers.uv.active
        for island in uvIslands([bm.faces[i] for i in selectedIndices], uvLayer):
            width, height = self.textureSize(obj, island[0])
            translateIslandToPixel(island, uvLayer, width, height)
        bmesh.update_edit_mesh(mesh)


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
