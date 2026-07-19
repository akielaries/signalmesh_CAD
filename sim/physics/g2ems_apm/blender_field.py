# render the EMS field glowing over the APM board, headless blender.
# usage:
#   blender -b -P blender_field.py -- --still 96 --out out/apm_blender_still.png
#   blender -b -P blender_field.py -- --anim --out out/anim/frame_
# board is laid out in board-relative mm (1 blender unit = 1 mm).

import bpy, sys, os, math, glob

# ---- args after '--' ----
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def argval(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default
STILL = argval("--still")                       # frame index for a single image
ANIM = "--anim" in argv
OUT = argval("--out", "out/apm_blender.png")

HERE = os.path.dirname(os.path.abspath(__file__))
COPPER = argval("--copper", os.path.join(HERE, "ems/geometry/In1_Cu.png"))
FIELD_DIR = argval("--field-dir", os.path.join(HERE, "simulation_images/0/In1_Cu_masked"))
os.makedirs(os.path.dirname(os.path.join(HERE, OUT)) or ".", exist_ok=True)

def _ext(flag, default):
    v = argval(flag)
    return tuple(float(x) for x in v.split(",")) if v else default

# physical extents (mm), board-relative. pass via --board-extent / --field-extent.
BOARD = _ext("--board-extent", (0.0, 72.55, 0.0, 104.49))   # xmin,xmax,ymin,ymax
FIELD = _ext("--field-extent", (-2.40, 79.45, -2.40, 106.95))
field_frames = sorted(glob.glob(os.path.join(FIELD_DIR, "*.png")),
                      key=lambda p: int(''.join(filter(str.isdigit, os.path.basename(p)))))
NFR = len(field_frames)

# ---- clean scene ----
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def quad(name, ext, z):
    xmin, xmax, ymin, ymax = ext
    me = bpy.data.meshes.new(name)
    verts = [(xmin, ymin, z), (xmax, ymin, z), (xmax, ymax, z), (xmin, ymax, z)]
    faces = [(0, 1, 2, 3)]
    me.from_pydata(verts, [], faces)
    me.uv_layers.new(name="UV")
    uvl = me.uv_layers[0].data
    for i, uv in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uvl[i].uv = uv
    me.update()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob

# ---- board plane: copper as a dim base color on a dark board ----
board = quad("Board", BOARD, 0.0)
bm = bpy.data.materials.new("BoardMat"); bm.use_nodes = True
nt = bm.node_tree; nt.nodes.clear()
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = bpy.data.images.load(COPPER); tex.image.colorspace_settings.name = "Non-Color"
# darken copper -> board look
mult = nt.nodes.new("ShaderNodeMixRGB"); mult.blend_type = "MULTIPLY"; mult.inputs[0].default_value = 1.0
mult.inputs[2].default_value = (0.05, 0.10, 0.07, 1)    # dark green board tint
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.inputs["Roughness"].default_value = 0.55
out = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(tex.outputs["Color"], mult.inputs[1])
nt.links.new(mult.outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
board.data.materials.append(bm)

# ---- field plane: emission color-ramped, transparent where weak ----
fplane = quad("Field", FIELD, 2.0)
fm = bpy.data.materials.new("FieldMat"); fm.use_nodes = True
# eevee-next (blender 4.2+/5.x) uses surface_render_method; older uses blend_method
if hasattr(fm, "surface_render_method"):
    fm.surface_render_method = "BLENDED"
if hasattr(fm, "blend_method"):
    try: fm.blend_method = "BLEND"
    except Exception: pass
nt = fm.node_tree; nt.nodes.clear()
ftex = nt.nodes.new("ShaderNodeTexImage")
img = bpy.data.images.load(field_frames[int(STILL) if STILL is not None else 0])
img.colorspace_settings.name = "Non-Color"
ftex.image = img
if ANIM:
    img.source = "SEQUENCE"
    ftex.image_user.frame_duration = NFR
    ftex.image_user.frame_start = 1
    ftex.image_user.use_auto_refresh = True
# color ramp: value -> turbo-ish emission color
ramp = nt.nodes.new("ShaderNodeValToRGB")
cr = ramp.color_ramp
cr.elements[0].position = 0.0; cr.elements[0].color = (0.0, 0.0, 0.35, 1)
cr.elements[1].position = 1.0; cr.elements[1].color = (1.0, 0.05, 0.0, 1)
for pos, col in [(0.35, (0.0, 0.4, 1.0, 1)), (0.6, (0.1, 1.0, 0.4, 1)), (0.8, (1.0, 0.85, 0.0, 1))]:
    e = cr.elements.new(pos); e.color = col
emis = nt.nodes.new("ShaderNodeEmission")
strength = nt.nodes.new("ShaderNodeMath"); strength.operation = "MULTIPLY"; strength.inputs[1].default_value = 2.5
# alpha: hard knee so weak field is fully transparent (bare board shows) and only
# real field glows -- avoids the pastel wash
aramp = nt.nodes.new("ShaderNodeValToRGB")
ac = aramp.color_ramp
ac.elements[0].position = 0.42; ac.elements[0].color = (0, 0, 0, 1)
ac.elements[1].position = 0.92; ac.elements[1].color = (1, 1, 1, 1)
transp = nt.nodes.new("ShaderNodeBsdfTransparent")
mix = nt.nodes.new("ShaderNodeMixShader")
out = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(ftex.outputs["Color"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], emis.inputs["Color"])
nt.links.new(ftex.outputs["Color"], strength.inputs[0])
nt.links.new(strength.outputs["Value"], emis.inputs["Strength"])
nt.links.new(ftex.outputs["Color"], aramp.inputs["Fac"])
nt.links.new(aramp.outputs["Color"], mix.inputs["Fac"])
nt.links.new(transp.outputs["BSDF"], mix.inputs[1])
nt.links.new(emis.outputs["Emission"], mix.inputs[2])
nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
fplane.data.materials.append(fm)

# ---- world: near-black ----
world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.01, 0.01, 0.012, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0

# ---- fill light so the board reads ----
ld = bpy.data.lights.new("Key", "AREA"); ld.energy = 1.1e5; ld.size = 120
lo = bpy.data.objects.new("Key", ld); scene.collection.objects.link(lo)
lo.location = (36, 40, 130); lo.rotation_euler = (math.radians(25), 0, 0)

# ---- camera: 3/4 aerial over the board ----
cam = bpy.data.cameras.new("Cam"); camo = bpy.data.objects.new("Cam", cam)
scene.collection.objects.link(camo); scene.camera = camo
cx, cy = 36.0, 52.0
camo.location = (cx, cy - 95, 140)
# aim at board center
import mathutils
d = mathutils.Vector((cx, cy, 0)) - mathutils.Vector(camo.location)
camo.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cam.lens = 55

# ---- render settings ----
try:
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
except Exception:
    scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1100
scene.render.resolution_y = 1500
scene.render.film_transparent = False
try:
    scene.eevee.taa_render_samples = 64
except Exception:
    pass
# compositor glare for the glow/bloom look (best-effort; API differs across versions)
def add_glare():
    ng = bpy.data.node_groups.new("Comp", "CompositorNodeTree")
    rl = ng.nodes.new("CompositorNodeRLayers")
    glare = ng.nodes.new("CompositorNodeGlare"); glare.glare_type = "FOG_GLOW"
    try:
        glare.threshold = 0.2; glare.size = 7
    except Exception:
        pass
    comp = ng.nodes.new("CompositorNodeComposite")
    ng.links.new(rl.outputs["Image"], glare.inputs["Image"])
    ng.links.new(glare.outputs["Image"], comp.inputs["Image"])
    return ng
try:
    if hasattr(scene, "compositing_node_group"):        # blender 5.x
        scene.compositing_node_group = add_glare()
    else:                                               # blender <=4.x
        scene.use_nodes = True
        cnt = scene.node_tree; cnt.nodes.clear()
        rl = cnt.nodes.new("CompositorNodeRLayers")
        glare = cnt.nodes.new("CompositorNodeGlare"); glare.glare_type = "FOG_GLOW"
        glare.threshold = 0.2; glare.size = 7
        comp = cnt.nodes.new("CompositorNodeComposite")
        cnt.links.new(rl.outputs["Image"], glare.inputs["Image"])
        cnt.links.new(glare.outputs["Image"], comp.inputs["Image"])
except Exception as e:
    print("glare skipped:", e)

if ANIM:
    scene.render.image_settings.file_format = "PNG"
    for i, fp in enumerate(field_frames):
        img_i = bpy.data.images.load(fp)
        img_i.colorspace_settings.name = "Non-Color"
        ftex.image = img_i
        scene.render.filepath = os.path.join(HERE, OUT + "%04d.png" % i)
        bpy.ops.render.render(write_still=True)
        bpy.data.images.remove(img_i)
    print("wrote %d animation frames to %s" % (NFR, os.path.join(HERE, OUT)))
else:
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = os.path.join(HERE, OUT)
    bpy.ops.render.render(write_still=True)
    print("wrote", scene.render.filepath)
