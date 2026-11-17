"""Render the noodle shop's assembly steps in Blender, one PNG per step.

Run this through Blender, not python.exe:

    blender -b -P output/render_video_blender.py -- --start-frame 80 --end-frame 80

Why Blender and not LeoCAD: LeoCAD's executable is unsigned and the machine's
code integrity policy refuses to load it. Blender's official build is signed
and runs fine, so this is the renderer that survives the environment.

The add-on does the heavy lifting: one import honours every `0 STEP` marker and
keys part visibility into the timeline, so step N is simply frame N+1.
"""
import argparse
import os
import sys
from pathlib import Path

# Resolve every path next to this script so the pipeline stays movable: output/
# holds the add-on source, the flattened model and the frame directory.
HERE = Path(__file__).resolve().parent

ADDON_SRC = str(HERE / "tools" / "addons_src")
DEFAULT_MPD = str(HERE / "build-video" / "noodle-flat.mpd")
DEFAULT_LIB = os.environ.get("LDRAW_DIR") or str(Path.home() / "ldraw" / "ldraw")
DEFAULT_OUT = str(HERE / "build-video" / "frames")

sys.path.insert(0, ADDON_SRC)

import bpy  # noqa: E402
import io_scene_importldraw  # noqa: E402

# Cyan reads as "freshly placed" on every colour the model uses, and stays
# distinct from both the grey backdrop and the model's own palette.
GLOW_TINT = (0.25, 0.95, 1.0)


def blender_args():
    """Everything after the '--' Blender passes through."""
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else []


def setup_scene(scene, args):
    """Cycles on CPU: no GPU dependency, so it works headless."""
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False

    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs[0].default_value = (0.82, 0.85, 0.9, 1.0)
        background.inputs[1].default_value = 0.55


def frame_model(scene, view=(1.0, 1.0, 0.8)):
    """Point an orthographic camera at the model from the given direction.

    The add-on maps LDraw (x, y, z) to Blender (x, z, -y): LDraw's +Z
    shopfront lands on Blender +Y and LDraw's down-facing +Y becomes Blender
    -Z. Viewing from Blender (+x, +y, +z) therefore reads the shopfront from
    the right and above, like a build guide illustration.
    """
    from mathutils import Vector

    # step visibility is keyed to the timeline; on frame 1 nearly everything
    # is hidden and the depsgraph would measure an empty model. Jump to the
    # finished frame first.
    scene.frame_set(scene.frame_end)

    # the add-on places parts as collection instances over ~30 shared meshes,
    # so plain object bounds measure the templates, not the model. Walk the
    # depsgraph's object instances instead: that is where the real geometry is.
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()

    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for instance in depsgraph.object_instances:
        obj = instance.object
        if obj.type != "MESH":
            continue
        matrix = instance.matrix_world
        for vertex in obj.data.vertices:
            world = matrix @ vertex.co
            lo = Vector(map(min, lo, world))
            hi = Vector(map(max, hi, world))
    centre = (lo + hi) / 2
    extent = (hi - lo).length
    print(f"BOUNDS lo={tuple(round(v, 3) for v in lo)} hi={tuple(round(v, 3) for v in hi)} diag={extent:.3f}")

    camera = bpy.data.objects.get("Camera")
    if camera is None:
        camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
        scene.collection.objects.link(camera)
    if camera.animation_data is not None:
        camera.animation_data_clear()
    camera.data.type = "ORTHO"
    # a three-quarter view projects the diagonal of the footprint, so scale
    # against the full bounding-box diagonal, not the largest single axis
    camera.data.ortho_scale = extent * 1.2
    camera.data.clip_start = 0.1
    camera.data.clip_end = 1e6

    camera.location = centre + Vector(view).normalized() * extent * 4
    look = centre - camera.location
    camera.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    return centre, extent


def setup_lighting(scene, centre, extent):
    """Key + fill + rim suns over a soft world; Cycles handles the rest."""
    from mathutils import Vector

    rig = [
        ("Key", (0.4, -0.55, -0.7), 3.2),   # front-right-top, from the shopfront side
        ("Fill", (-0.6, -0.35, -0.5), 0.9),  # left front, softens the shadows
        ("Rim", (0.2, 0.7, -0.6), 1.6),      # behind, separates the model from the sky
    ]
    for name, direction, energy in rig:
        light = bpy.data.lights.new(name, type="SUN")
        light.energy = energy
        light.angle = 0.26
        obj = bpy.data.objects.new(name, light)
        scene.collection.objects.link(obj)
        obj.location = centre
        obj.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()


def visible_parts():
    """Names of the part meshes the depsgraph actually draws on this frame.

    Step visibility is keyed to the timeline, so the evaluated depsgraph is the
    honest source: it carries only what the frame shows.
    """
    bpy.context.view_layer.update()
    return {instance.object.name
            for instance in bpy.context.evaluated_depsgraph_get().object_instances
            if instance.object.type == "MESH"}


def emissive_clone(source, strength):
    """A copy of *source* that also emits in the highlight tint.

    Parts are surfaced by reusable node groups shared across every material, so
    editing a group would light up unrelated parts too. Cloning the material
    yields a private node tree; mixing the original shader with a tinted
    emission marks the part no matter what colour it is -- an emission in the
    part's own colour proved invisible on the pale-grey baseplates.
    """
    clone = source.copy()
    tree = clone.node_tree
    if tree is None:
        return clone

    output = next((n for n in tree.nodes if n.type == "OUTPUT_MATERIAL"), None)
    group = next((n for n in tree.nodes if n.type == "GROUP"), None)
    surface = output.inputs.get("Surface") if output else None
    original = group.outputs.get("Shader") if group else None
    if surface is None or original is None:
        return clone

    emission = tree.nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*GLOW_TINT, 1.0)
    emission.inputs["Strength"].default_value = strength
    mix = tree.nodes.new("ShaderNodeAddShader")

    tree.links.new(original, mix.inputs[0])
    tree.links.new(emission.outputs["Emission"], mix.inputs[1])
    tree.links.new(mix.outputs["Shader"], surface)
    return clone


def glow_parts(parts, strength, cache):
    """Swap *parts* onto emissive clones; return what to put back.

    Parts of the same model share one mesh datablock, and material slots
    default to linking through it -- writing there recolours every other part
    of the same type as well. Override per object instead, and revert right
    after the frame is written so no glow leaks into later steps.
    """
    changed = {}
    for obj in parts:
        swaps = []
        for slot in obj.material_slots:
            source = slot.material
            if source is None:
                continue
            glow = cache.get(source.name)
            if glow is None:
                glow = emissive_clone(source, strength)
                cache[source.name] = glow
            swaps.append((slot, slot.link, source))
            slot.link = "OBJECT"
            slot.material = glow
        if swaps:
            changed[obj] = swaps
    return changed


def restore_parts(changed):
    """Put the original material links back after a highlighted frame."""
    for obj, swaps in changed.items():
        for slot, link, original in swaps:
            slot.link = link
            slot.material = original


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mpd", default=DEFAULT_MPD)
    ap.add_argument("--lib", default=DEFAULT_LIB)
    ap.add_argument("--outdir", default=DEFAULT_OUT)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=960)
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--start-frame", type=int, default=2,
                    help="step N lives on frame N+1")
    ap.add_argument("--end-frame", type=int, default=80)
    ap.add_argument("--glow", type=float, default=2.0,
                    help="emission strength on the parts this step introduces; "
                         "0 disables highlighting altogether")
    args = ap.parse_args(blender_args())

    io_scene_importldraw.register()

    bpy.ops.import_scene.importldraw(
        filepath=args.mpd,
        ldrawPath=args.lib,
        animateSteps=True,
        framesPerStep=1,
        expandSubmodels=True,
        submodelCollections=False,
        flatten=False,
        useLogoStuds=True,
        addEnvironment=False,
        transparentBackground=False,
        positionCamera=False,
        cameraBorderPercentage=0.01,
        bevelEdges=False,
        importCameras=False,
        smoothParts=True,
    )

    scene = bpy.context.scene
    setup_scene(scene, args)
    centre, extent = frame_model(scene)
    setup_lighting(scene, centre, extent)

    # Blender resolves render.filepath against its own notion of the .blend
    # directory rather than the process cwd, so a relative --outdir quietly
    # writes nowhere when no .blend has been saved. Pin it to an absolute path.
    outdir = Path(args.outdir)
    if not outdir.is_absolute():
        outdir = Path.cwd() / outdir
    outdir.mkdir(parents=True, exist_ok=True)

    frames = list(range(args.start_frame, args.end_frame + 1))
    print(f"RENDER stages visible: {len(scene.timeline_markers)}")
    print(f"RENDER frames to draw: {len(frames)} -> {outdir}")

    # Whatever was already drawn before our first frame counts as built, so
    # starting mid-sequence does not light up everything that came before it.
    scene.frame_set(max(args.start_frame - 1, 1))
    built = visible_parts()
    glow_cache = {}
    for index, frame in enumerate(frames, start=1):
        scene.frame_set(frame)
        lit = {}
        if args.glow > 0:
            fresh = visible_parts() - built
            built |= fresh
            lit = glow_parts([bpy.data.objects[name] for name in sorted(fresh)],
                             args.glow, glow_cache)
        scene.render.filepath = str(outdir / f"step-{index:03}.png")
        bpy.ops.render.render(write_still=True)
        restore_parts(lit)
        print(f"RENDER step-{index:03}.png  (frame {frame}, {len(lit)} new parts)")
    print("RENDER done")


if __name__ == "__main__":
    main()
