"""Standalone subprocess entry point for offscreen mesh rendering.

This is executed as a separate process (``python _mesh_render_worker.py ...``)
rather than in-process for two reasons:

1. On macOS, pyrender/pyglet create the OpenGL context via Cocoa, which aborts
   the whole process if done on a non-main thread (conversions run on a
   background worker thread). A subprocess gets its own main thread.
2. A native OpenGL crash is contained in the child process instead of taking
   down the API server.

The script intentionally avoids importing project modules so it can run with
only the rendering dependencies on the path.
"""
import sys


def _look_at(eye, target, up, np):
    """Build a camera-to-world pose matrix looking from ``eye`` toward ``target``."""
    forward = eye - target
    forward = forward / np.linalg.norm(forward)
    right = np.cross(up, forward)
    right_norm = np.linalg.norm(right)
    if right_norm < 1e-8:
        right = np.array([1.0, 0.0, 0.0])
    else:
        right = right / right_norm
    new_up = np.cross(forward, right)

    pose = np.eye(4)
    pose[:3, 0] = right
    pose[:3, 1] = new_up
    pose[:3, 2] = forward
    pose[:3, 3] = eye
    return pose


def render(input_file: str, input_type: str, output_file: str, output_type: str, size: int) -> None:
    import numpy as np
    import pyrender
    import trimesh
    from PIL import Image

    mesh = trimesh.load(input_file, file_type=input_type, force='mesh')
    if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
        raise RuntimeError("Input mesh has no faces to render.")

    scene = pyrender.Scene(
        bg_color=[0.0, 0.0, 0.0, 0.0],
        ambient_light=[0.4, 0.4, 0.4],
    )
    scene.add(pyrender.Mesh.from_trimesh(mesh, smooth=False))

    centroid = mesh.bounding_box.centroid
    radius = float(np.linalg.norm(mesh.bounding_box.extents)) * 0.5
    if radius <= 0.0:
        radius = 1.0

    yfov = np.pi / 4.0
    distance = (radius / np.tan(yfov / 2.0)) * 1.4
    direction = np.array([1.0, 1.0, 1.0])
    direction = direction / np.linalg.norm(direction)
    eye = centroid + direction * distance
    pose = _look_at(eye, centroid, np.array([0.0, 0.0, 1.0]), np)

    camera = pyrender.PerspectiveCamera(yfov=yfov, aspectRatio=1.0)
    scene.add(camera, pose=pose)
    scene.add(
        pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0),
        pose=pose,
    )

    renderer = pyrender.OffscreenRenderer(size, size)
    try:
        color, _ = renderer.render(scene, flags=pyrender.RenderFlags.RGBA)
    finally:
        renderer.delete()

    image = Image.fromarray(color, 'RGBA')

    if output_type == 'jpeg':
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        background.save(output_file, 'JPEG', quality=95)
    elif output_type == 'webp':
        image.save(output_file, 'WEBP')
    else:
        image.save(output_file, 'PNG')


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print(
            "usage: _mesh_render_worker.py INPUT INPUT_TYPE OUTPUT OUTPUT_TYPE SIZE",
            file=sys.stderr,
        )
        return 2

    _, input_file, input_type, output_file, output_type, size = argv
    try:
        render(input_file, input_type, output_file, output_type, int(size))
    except Exception as exc:  # noqa: BLE001 - report any failure to the parent
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
