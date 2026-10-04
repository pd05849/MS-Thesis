"""Render the LIBERO-Object soup scene at 512 px and label every object at its simulated position."""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import OffScreenRenderEnv
from robosuite.utils.camera_utils import get_camera_transform_matrix, project_points_from_world_to_camera

S = 512
suite = benchmark.get_benchmark_dict()["libero_object"]()
task = suite.get_task(0)  # pick up the alphabet soup and place it in the basket
bddl = os.path.join(get_libero_path("bddl_files"), task.problem_folder, task.bddl_file)
env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=S, camera_widths=S)
env.seed(0)
env.reset()
env.set_init_state(suite.get_task_init_states(0)[0])
for _ in range(5):
    obs, _, _, _ = env.step([0.0] * 7)

sim = env.env.sim
M = get_camera_transform_matrix(sim, "agentview", S, S)
img = Image.fromarray(np.ascontiguousarray(obs["agentview_image"][::-1, ::-1]))
d = ImageDraw.Draw(img)
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)

# which floor spots are ever used as pick targets in LIBERO-Object (verified from the 10 BDDL files)
labels = {  # name: (text, color, label offset dx, dy)
    "alphabet_soup_1": ("alphabet soup (spot A)", "lime", 10, -60),
    "salad_dressing_1": ("salad dressing (spot B)", "lime", 40, 40),
    "tomato_sauce_1": ("tomato sauce", "orange", -40, 50),
    "cream_cheese_1": ("cream cheese", "orange", -70, -55),
    "milk_1": ("milk", "orange", 30, 45),
    "butter_1": ("butter", "orange", 10, -95),
    "basket_1": ("basket", "cyan", -30, -70),
}
for name, (text, color, dx, dy) in labels.items():
    pos = sim.data.body_xpos[sim.model.body_name2id(name + "_main")]
    r, c = project_points_from_world_to_camera(pos[None], M, S, S)[0]
    r, c = r, S - 1 - c  # image is mirrored left-right relative to the projection
    d.ellipse([c - 6, r - 6, c + 6, r + 6], outline=color, width=3)
    tw = d.textlength(text, font=font)
    x = min(max(c + dx - tw / 2, 4), S - tw - 4)
    y = min(max(r + dy, 4), S - 24)
    d.line([c, r, x + tw / 2, y + 10], fill=color, width=2)
    d.rectangle([x - 3, y, x + tw + 3, y + 20], fill=(0, 0, 0))
    d.text((x, y + 1), text, fill=color, font=font)
d.rectangle([0, S - 46, S, S], fill=(0, 0, 0))
d.text((8, S - 44), "green = spots LIBERO-Object always picks from (A or B)", fill="lime", font=font)
d.text((8, S - 24), "orange = spots no LIBERO-Object task ever picks from", fill="orange", font=font)
env.close()
img.save("soup_scene_annotated.jpg", quality=92)
print("saved", img.size)
