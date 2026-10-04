# Humanoid challenge — working notes (staging area)

Scratch space for the Humanoid "Robot Learning Research" challenge (deadline Fri 9 Oct 2026,
23:59 BST; target submission 2 pm ET). This folder is a staging area on a feature branch only;
the real submission will live in its own public repo.

## The project in one paragraph

LIBERO-trained VLAs seem to replay what they memorised for a scene instead of reading the
instruction. Test it on a "twin" pair: the LIBERO kitchen (KITCHEN_SCENE3) where `smolvla_libero`
was trained on *"turn on the stove and put the moka pot on it"* (LIBERO-10 task 2), versus the
never-seen *"turn on the stove and put the frying pan on it"* (LIBERO-90 task 21). The scene
files are identical apart from the goal and object of interest, and LIBERO-90 ships 50 human
teleop demos of the frying-pan version. Then teach the new instruction from ~15 phone clips of
a real pan going onto a real stove, and compare against those 50 robot demos.

## Status (Sun 4 Oct)

| Check | Result |
|---|---|
| LeRobot (0.6.2 source build) + LIBERO on the Ubuntu laptop, GPU rendering | works |
| Kitchen tasks present (`libero_10` #2 moka, `libero_90` #21 frying pan) | yes |
| LIBERO-90 frying-pan human demos | 50 demos; demo 0 = 287 steps (~14 s) |
| Human demo order | turns the knob first (clockwise), then grabs the pan by the handle |
| Sanity: `smolvla_libero` on LIBERO-Object task 0, 10 episodes | 7/10 |
| Moka pot (trained instruction), 3 episodes | 2/3 |
| Frying pan (never-seen instruction), 10 episodes | 0/10; never picked up the pan, sometimes the moka pot, often missed the knob |

Lessons:

- Always pass `--policy.n_action_steps=10 --policy.num_steps=10` (the default 50-step open-loop
  chunks gave 0% even on the trained task). Do not force `--env.observation_height/width`.
- `520` / `400` are LeRobot's episode time limits for `libero_10` / `libero_90`, not speeds.
- Eval videos are saved at 80 fps (4x real time); watch with `mpv --speed=0.25`.
- First LIBERO import asks for a dataset path: answer `n`.

## Plan for the week

| Day | Work |
|---|---|
| Mon | Logger runs (both instructions, 10x each); print markers; film 15-20 pan-to-stove clips; build phone-to-robot-demo converter; convert the 50 LIBERO-90 frying-pan demos |
| Tue | Fine-tune `smolvla_libero` on the DGX Spark: (P) phone-derived demos + 50 moka demos, (T) 50 robot demos + 50 moka demos |
| Wed | Evaluate both on both instructions with the logger |
| Thu | README, figures, GIFs, walkthrough video; feature freeze |
| Fri | Polish and submit by 2 pm ET |

## Scripts (`scripts/`)

| Script | What it does |
|---|---|
| `check_kitchen_render.py` | Renders the moka and frying-pan kitchen tasks to PNGs |
| `replay_demo.py` | Replays one LIBERO-90 frying-pan human demo (state playback + action replay) to MP4 |
| `eval_with_log.py` | `lerobot-eval` drop-in that logs per episode: success, stove on, first object picked up |
| `watch_eval.py` | `lerobot-eval` drop-in that shows the front camera live in a window |
| `render_scenes.py`, `render_all_parallel.py`, `make_sheets.py` | Render the first frame of all 130 LIBERO tasks and build contact sheets (images not committed: this repo routes images through Git LFS) |
| `annotate_soup.py` | Labels the LIBERO-Object soup scene by which floor spots are ever picked from |

Standard eval command (laptop, inside the LeRobot env):

```bash
MUJOCO_GL=egl python scripts/eval_with_log.py \
  --policy.path=HuggingFaceVLA/smolvla_libero \
  --policy.n_action_steps=10 --policy.num_steps=10 \
  --env.type=libero --env.task=libero_90 --env.task_ids='[21]' \
  --eval.n_episodes=10 --eval.batch_size=1 \
  --output_dir=./eval_logs/pan_10ep
```

## Related work to cite

LangGap (IROS 2026, same-scene instruction swaps on LIBERO Spatial/Object/Goal, not LIBERO-10),
LIBERO-PRO, LIBERO-Plus, GloVLA (geometric transport + local VLA; no public code), MimicGen,
R2R2R, X-Sim, H2RBench.
