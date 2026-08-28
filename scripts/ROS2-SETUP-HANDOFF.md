# Handoff: set up ROS 2 Jazzy + OARbot lab stack on this machine

**For the assistant reading this:** you are on Pol del Castillo's fresh
Ubuntu machine. This document is the full context plus the exact steps.
Work through it top to bottom, confirming with Pol before each
state-changing command (his standing preference — propose, then act).

---

## 1. Context

**Who/what.** Pol is doing an MS thesis: *Learning from Demonstration
for Complex Tasks — VLA control of OARbot* (RPI). Robots are two
**OARbots**: Clearpath Dingo omni base + **Kinova Jaco Gen2 6-DOF arm**
(`j2n6s300`) + Azure Kinect + Bota force-torque sensor, running **ROS 2
Jazzy**. Plan: collect teleoperated demonstrations → train ACT, then
SmolVLA / GR00T N1.5 → run policies on the robot.

**This machine's job.** Dell Alienware laptop, freshly wiped to Ubuntu
24.04 LTS. It is the **LeRobot + robot-side machine**: teleoperation,
demonstration recording, dataset conversion, and policy inference.
Training happens elsewhere (DGX Spark). Thesis writing/PM lives on a
separate Windows laptop.

**Already done on this machine (do not redo):**
- Ubuntu 24.04.4 LTS installed (full wipe, UEFI, user `polete`).
- NVIDIA driver **595.84**, RTX 3050 Laptop GPU (~4 GB VRAM).
- Python **3.12.3** (system).
- Build/media deps installed: `ffmpeg cmake build-essential python3-dev
  python3-venv pkg-config git libav*-dev libsw*-dev`.
- **LeRobot installed**: repo at `~/lerobot`, venv at `~/lerobot-venv`,
  `pip install -e ".[all]"`. Verified: `torch 2.11.0+cu130`,
  `cuda True`, `lerobot 0.6.2`.
- `sudo usermod -aG dialout $USER` has been run (serial access for the
  SO-101 leader arm; needs a logout/login to take effect).

**Still to do (this document):** ROS 2 Jazzy, the lab repos, the
`kinova_msgs` build, and the tooling list in §4.

---

## 2. Critical gotchas (learned the hard way — do not rediscover these)

1. **CycloneDDS, NOT Fast DDS.** The OARbots use
   `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`. Fast DDS is used on Pol's
   *other* project (Isaac Sim / SO-101) — never mix them.
2. **`ROS_DOMAIN_ID=0`.** Each robot runs internally on its own domain
   (Blue = 2, Silver = 1) and a **domain bridge** re-publishes
   everything onto domain 0 with `/oarbot_blue/…` and `/oarbot_silver/…`
   prefixes. Client machines stay on 0.
3. **Never build ROS packages with a conda/venv environment active.**
   CMake prefers `CONDA_PREFIX`/venv Python over the system one and the
   message build fails with a cryptic `ModuleNotFoundError: No module
   named 'em'`. This cost hours on the Windows machine. LeRobot lives
   in a venv *precisely* so it is inert unless explicitly activated —
   keep it that way; do not install conda.
   If a build fails this way: `deactivate`, open a clean shell, rebuild.
4. **`ros2 daemon stop` after any network change.** The CLI caches
   discovery in a background daemon; a stale daemon reports an empty
   topic list even when everything works.
5. **Firewalls block DDS discovery.** On the Windows/WSL machine the
   blocker was an inbound-UDP rule. Ubuntu's `ufw` is off by default,
   so this should be a non-issue — but if topics don't appear and
   `ufw status` says active, allow UDP 7400–7500.

---

## 3. Install ROS 2 Jazzy

```bash
# Repository
sudo apt update && sudo apt install -y software-properties-common curl
sudo add-apt-repository -y universe
sudo curl -sSL -o /usr/share/keyrings/ros-archive-keyring.gpg \
  https://raw.githubusercontent.com/ros/rosdistro/master/ros.key
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update

# ROS 2 Jazzy desktop (includes RViz2 + rqt) + build tools + CycloneDDS
sudo apt install -y ros-jazzy-desktop ros-dev-tools ros-jazzy-rmw-cyclonedds-cpp
```

Shell environment — append to `~/.bashrc` (check for duplicates first):

```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=0
[ -f ~/ros2_ws/install/setup.bash ] && source ~/ros2_ws/install/setup.bash
```

Sanity check in a **new** shell: `ros2 --version`, then
`ros2 run demo_nodes_cpp talker` in one terminal and
`ros2 topic echo /chatter` in another.

---

## 4. Tooling

```bash
# ROS-side
sudo apt install -y ros-jazzy-plotjuggler-ros    # time-series plots of topics/bags — the daily QC tool
# General
sudo apt install -y git-lfs tmux htop nvtop
git lfs install
```

- **PlotJuggler** — verifying recorded demonstrations are clean (smooth
  joint trajectories, no dropped frames, sane gripper timing).
- **git-lfs** — Pol's thesis repo uses LFS; cloning without it yields
  broken placeholder files.
- **tmux** — several ROS nodes in one SSH session at the lab.
- **nvtop/htop** — confirm policy inference actually uses the GPU.

**VS Code** (`.deb` from https://code.visualstudio.com/ or
`sudo snap install code --classic`).
**Foxglove Studio** (`.deb` from https://foxglove.dev/download) — visual
bag inspection, camera + joint plots side by side. Optional but liked
by the SO-101 community.

---

## 5. Lab repositories + `kinova_msgs`

Both repos are cloned read-only as reference; Pol's own work goes in a
separate `pol_thesis` folder so it is clearly distinguishable.

```bash
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src
git clone --depth 1 https://github.com/rpiRobotics/kinova-ros2
git clone --depth 1 https://github.com/rpirobotics/oarbots
mkdir -p pol_thesis
```

Build **only** the message package (the full driver needs Kinova's USB
SDK and only belongs on the robot's helper laptop). **No venv active:**

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select kinova_msgs
source install/setup.bash
ros2 interface show kinova_msgs/msg/PoseVelocity   # must print 6 float32 fields
```

Why this matters: the Kinova command topics use custom message types.
Without `kinova_msgs` built locally, `ros2 topic echo` on them fails
with "The message type ... is invalid", and you cannot record or send
arm commands.

If the build fails with `No module named 'em'`, install
`python3-empy python3-lark` and confirm no venv/conda is active.

---

## 6. Connecting to the robots (at the lab)

Wi-Fi **`CII8218-oarbots`** (password on paper near the router). Robots
must be powered up in the documented boot order (batteries → Dingo →
arm → helper laptop → NUC → tablet).

```bash
ros2 daemon stop && ros2 topic list
```

Expect ~49 topics prefixed `/oarbot_blue/…` (and `/oarbot_silver/…` if
Silver is on). Seeing **only** `/parameter_events` and `/rosout` means
discovery is failing, not that the robots are silent.

Native Linux should discover by multicast with no extra DDS config. If
it does not: create `~/.ros/cyclonedds.xml` pinning the Wi-Fi interface
(and optionally unicast `<Peers>` with the robot IPs), then
`export CYCLONEDDS_URI=file://$HOME/.ros/cyclonedds.xml`.

### Verified interface facts (measured 2026-08-27)

| What | Topic / value |
|---|---|
| All joints (4 wheels + 6 arm + 6 finger), `sensor_msgs/JointState` | `/oarbot_blue/joint_states` @ ~10 Hz |
| Arm-only joint state | `/oarbot_blue/kinova/j2n6s300_driver/out/joint_state` (radians) |
| Arm command (what the teleop tablet publishes) | `…/in/cartesian_velocity`, `kinova_msgs/PoseVelocity`, ~119 Hz **only while the deadman is held** |
| Arm + gripper command | `…/in/cartesian_velocity_with_fingers`, `PoseVelocityWithFingers` (6 twist floats + `fingers_closure_percentage`) |
| Base command | `/oarbot_blue/dingo/cmd_vel`, `TwistStamped` |
| Camera | `/oarbot_blue/azure_kinect/rgb/image_raw`, 1920×1080 @ ~15 fps on-robot but only **~3.4 Hz over Wi-Fi** (no compressed topics) |

**Consequences already decided:** demonstrations must be recorded **on
the robot's helper laptop**, not over Wi-Fi. The Kinova driver requires
velocity commands at **exactly 100 Hz** (its DSP loops every 10 ms);
publishing stops ⇒ motion stops. Commands are **deg/s** while joint
states are **radians** — convert in exactly one place.

**Safety:** any `ros2 topic pub` to an `in/…` topic moves the real arm
and bypasses the tablet deadman. Only ever do this with Pol present and
a hand on the E-stop, with small values and a bounded message count
(`-t 150`).

---

## 7. What comes next (not part of this setup)

1. Finish LeRobot: `lerobot-find-port`, then
   `lerobot-calibrate --teleop.type=so101_leader --teleop.port=… --teleop.id=…`
   for the SO-101 **leader** arm (already assembled; motor IDs already
   set — skip `lerobot-setup-motors`).
2. Build a **teleop bridge** in `~/ros2_ws/src/pol_thesis`: SO-101
   leader joints → forward kinematics → scaled end-effector twist →
   publish `PoseVelocityWithFingers` at 100 Hz, leader jaw →
   `fingers_closure_percentage`. Rationale: the SpaceMouse is hard to
   control and the tablet's gripper path is unreliable. Note the leader
   is 5-DOF and the Jaco is 6-DOF, so this is **task-space retargeting**,
   not joint mapping — one tool-orientation axis stays fixed.
3. Recording pipeline: `ros2 bag record` per episode on the helper
   laptop → offline converter to LeRobotDataset → open-loop replay test
   → ACT → SmolVLA.

**Locked decision (2026-08-25):** teleop is Cartesian; training action
labels are **joint positions at t+Δ derived from achieved states**, not
raw teleop commands. Raw bags are kept forever as source of truth.
