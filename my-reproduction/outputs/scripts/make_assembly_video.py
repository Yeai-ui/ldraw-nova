"""Turn the assembled noodle shop into a step-by-step building film.

The deliverable model is deliberately modular: ``noodle-main.ldr`` places
``noodle-ground.ldr`` and ``noodle-upper.ldr`` as submodels so the lower floor
can be lifted off. That is the right structure for a model you want to take
apart, but the wrong one for instructions: a renderer collapses each submodel
into the single step that places it, so the 240-odd parts of the two floors
would pop into existence at once.

So this script flattens first. It walks every placement to world coordinates,
keeps the source order that already runs bottom-up with structure before
decoration, re-cuts that into five-part steps, and emits a single-file model
whose ``0 STEP`` markers a renderer can turn into cumulative frames. Nothing
here touches the deliverable; it only reads it.

Two renderers are supported. The default is Blender: its official build is
digitally signed, so unlike LeoCAD it survives this machine's application
control policy. One headless Blender session renders every step -- the add-on
keys part visibility to the timeline, so step N is simply frame N+1 -- and
ffmpeg stitches the PNG sequence into an MP4. Pass ``--renderer leocad`` for the
older path, which needs LeoCAD itself to be allowed to run.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# This script lives in output/, so put the repository root on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEFAULT_SOURCE = Path('output/noodleshop.mpd')
DEFAULT_OUTDIR = Path('output/build-video')


def load_root(path, parts):
    """Load a built model and refuse to guess past a broken one."""
    from ldraw_tools.validation import validate_file

    model, diagnostics = validate_file(str(path), parts)
    errors = [d for d in diagnostics if d['severity'] == 'error']
    if errors:
        raise SystemExit(f'{len(errors)} errors in {path}; build it first')
    return model


def flatten(model, per_step):
    """Write one cumulative step model; return its path and the step count."""
    from ldraw import Model, Piece
    from ldraw.lines import Comment

    occurrences = list(model.iter_occurrences(expand_submodels=True,
                                              include_steps=False))
    chunks = [occurrences[start:start + per_step]
              for start in range(0, len(occurrences), per_step)]
    flat = Model(name='noodle-flat.ldr')
    flat.add(Comment('// flattened assembly sequence: one step per 0 STEP marker'))
    for index, chunk in enumerate(chunks):
        if index:
            flat.add_step()
        for occurrence in chunk:
            flat.add(Piece.place(occurrence.reference,
                                 colour=occurrence.piece.colour,
                                 position=occurrence.position,
                                 matrix=occurrence.matrix))
    text = flat.to_ldraw()
    if not flat.submodels:
        text = f'0 FILE {flat.name}\n{text}\n0 NOFILE'
    text = text.replace('\r\n', '\n').replace('\n', '\r\n') + '\r\n'
    return text, len(chunks), len(occurrences)


def find_blender(root):
    """Pick the portable Blender unpacked under output/tools, newest first."""
    found = sorted((root / 'output' / 'tools' / 'blender').glob('*/blender.exe'))
    return found[-1] if found else None


def render_with_blender(exe, flat, library, frames_dir, steps,
                        width, height, samples):
    """Render every step in one Blender session.

    Step N lives on frame N+1: frame 1 is empty and each step's parts appear on
    its own frame, so the add-on's step animation handles the accumulation for
    us. Stale frames are dropped first, so a partial run cannot leak into the
    sequence.
    """
    for stale in frames_dir.glob('step-*.png'):
        stale.unlink()
    script = Path(__file__).resolve().parent / 'render_video_blender.py'
    cmd = [str(exe), '-b', '-P', str(script), '--',
           '--mpd', str(flat), '--lib', str(library),
           '--outdir', str(frames_dir),
           '--start-frame', '2', '--end-frame', str(steps + 1),
           '--width', str(width), '--height', str(height),
           '--samples', str(samples)]
    subprocess.run(cmd, check=True)


def stitch(frames_pattern, out, fps, tail, scale=None):
    """ffmpeg: hold each step 1/fps seconds, then hold the finished model."""
    import imageio_ffmpeg

    filters = []
    if scale:
        filters.append(f'scale={scale}')
    filters.append(f'tpad=stop_mode=clone:stop_duration={tail}')
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-y',
           '-framerate', str(fps), '-i', str(frames_pattern),
           '-vf', ','.join(filters),
           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '30', str(out)]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    ap.add_argument('--outdir', type=Path, default=DEFAULT_OUTDIR)
    ap.add_argument('--per-step', type=int, default=5,
                    help='parts per assembly step (default: %(default)s)')
    ap.add_argument('--views', nargs='+', default=['home'],
                    help='viewpoints, leocad renderer only')
    ap.add_argument('--fps', type=float, default=2.0,
                    help='seconds each step is held is 1/fps')
    ap.add_argument('--tail', type=float, default=3.0,
                    help='seconds to hold the finished model')
    ap.add_argument('--renderer', choices=('blender', 'leocad'), default='blender',
                    help='blender (signed, default) or leocad (may be blocked)')
    ap.add_argument('--blender', type=Path, default=None,
                    help='path to blender.exe (auto-detected under output/tools)')
    ap.add_argument('--width', type=int, default=1280)
    ap.add_argument('--height', type=int, default=960)
    ap.add_argument('--samples', type=int, default=32,
                    help='Cycles samples per frame; higher means cleaner')
    ap.add_argument('--limit', type=int, default=0,
                    help='render only the first N steps (quick preview)')
    ap.add_argument('--dry-run', action='store_true',
                    help='flatten and report without rendering')
    args = ap.parse_args()

    from ldraw_tools.common import atomic_write, get_parts, library_path

    parts = get_parts()
    args.outdir.mkdir(parents=True, exist_ok=True)
    model = load_root(args.source, parts)
    text, steps, occurrences = flatten(model, args.per_step)
    print(f'flattened {occurrences} parts into {steps} steps '
          f'({args.per_step} parts each)')
    if args.dry_run:
        order = list(model.iter_occurrences(expand_submodels=True,
                                            include_steps=False))
        for occurrence in (order[0], order[len(order) // 2], order[-1]):
            print(f'  {occurrence.source_model.name:20} -> {occurrence.reference}')
        return

    flat = args.outdir / 'noodle-flat.mpd'
    atomic_write(flat, text)
    print(f'wrote {flat}')

    if args.renderer == 'blender':
        exe = args.blender or find_blender(Path(__file__).resolve().parents[1])
        if exe is None or not Path(exe).exists():
            raise SystemExit('no blender.exe found; pass --blender <path>')
        total = min(steps, args.limit) if args.limit else steps
        frames_dir = args.outdir / 'frames'
        frames_dir.mkdir(parents=True, exist_ok=True)
        print(f'rendering {total} steps with Blender (frames 2..{total + 1}) ...')
        render_with_blender(exe, flat, library_path(), frames_dir,
                            total, args.width, args.height, args.samples)
        out = args.outdir / 'noodle-assembly.mp4'
        stitch(frames_dir / 'step-%03d.png', out, args.fps, args.tail)
    else:
        from ldraw_tools.external import render_steps

        print(f'rendering {steps} frames for {args.views} ...')
        render_steps(flat, library_path(), args.outdir,
                     steps=list(range(1, steps + 1)),
                     views=args.views, timeout=3600)
        view = args.views[0]
        out = args.outdir / f'noodle-assembly-{view}.mp4'
        stitch(args.outdir / f'step-%03d-{view}.png',
               out, args.fps, args.tail, scale='1000:750')
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
