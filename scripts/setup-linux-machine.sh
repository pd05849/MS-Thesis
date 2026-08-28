#!/usr/bin/env bash
# Post-install setup for a fresh Ubuntu 24.04 (Noble) machine used for
# LeRobot + OARbot thesis work. Run once, from a normal user account:
#
#   bash setup-linux-machine.sh
#
# Priority order: LeRobot first (this machine's main job), lab ROS stack
# second. Safe to re-run; every step is idempotent.
#
# LeRobot lives in a plain python venv at ~/lerobot-venv, deliberately
# NOT conda: on the Windows machine an auto-activated conda base env
# hijacked CMake's python and broke the ROS message build. A venv is
# only active when you source it, so the two worlds cannot collide.
# Check the current LeRobot install docs after running this:
#   https://huggingface.co/docs/lerobot/installation

set -euo pipefail

info() { printf "\n=== %s\n" "$1"; }

info "Checking we are on Ubuntu 24.04 (Noble)"
. /etc/os-release
if [ "${VERSION_CODENAME:-}" != "noble" ]; then
  echo "WARNING: expected Ubuntu noble (24.04), found '${VERSION_CODENAME:-unknown}'."
  echo "ROS2 Jazzy binaries only exist for noble. Continue anyway? [y/N]"
  read -r reply; [ "$reply" = "y" ] || exit 1
fi

info "System update"
sudo apt update && sudo apt upgrade -y

info "Base tools (git, build, python venv, media, network, time sync)"
sudo apt install -y git curl wget build-essential cmake python3-pip \
  python3-venv python3-dev python3-empy python3-lark ffmpeg \
  net-tools iputils-ping chrony openssh-client

# ---------------------------------------------------------------------
# PART 1 — LeRobot (primary purpose of this machine)
# ---------------------------------------------------------------------

info "Serial port access for the SO-101 arms (takes effect after logout)"
sudo usermod -aG dialout "$USER"

info "LeRobot: clone + venv + editable install"
mkdir -p ~/dev && cd ~/dev
[ -d lerobot ] || git clone https://github.com/huggingface/lerobot.git
[ -d ~/lerobot-venv ] || python3 -m venv ~/lerobot-venv
# shellcheck disable=SC1090
source ~/lerobot-venv/bin/activate
python -m pip install --upgrade pip
cd ~/dev/lerobot
# 'feetech' extra = SO-101 servo bus driver. Add others later as needed
# (e.g. 'pip install -e ".[smolvla]"' for the VLA baseline).
pip install -e ".[feetech]"
deactivate

info "Convenience alias: 'lerobot-env' activates the venv"
add_line() { grep -qxF "$1" ~/.bashrc || echo "$1" >> ~/.bashrc; }
add_line "alias lerobot-env='source ~/lerobot-venv/bin/activate'"

# ---------------------------------------------------------------------
# PART 2 — ROS 2 Jazzy + lab stack (to talk to the OARbots)
# ---------------------------------------------------------------------

info "ROS2 Jazzy repository"
sudo apt install -y software-properties-common
sudo add-apt-repository -y universe
if [ ! -f /usr/share/keyrings/ros-archive-keyring.gpg ]; then
  sudo curl -sSL -o /usr/share/keyrings/ros-archive-keyring.gpg \
    https://raw.githubusercontent.com/ros/rosdistro/master/ros.key
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update

info "ROS2 Jazzy desktop + dev tools + CycloneDDS (the OARbot middleware)"
sudo apt install -y ros-jazzy-desktop ros-dev-tools ros-jazzy-rmw-cyclonedds-cpp

info "Shell environment (~/.bashrc)"
add_line "source /opt/ros/jazzy/setup.bash"
add_line "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp"   # OARbots use Cyclone, not FastDDS
add_line "export ROS_DOMAIN_ID=0"                          # robots bridge onto domain 0
add_line "[ -f ~/ros2_ws/install/setup.bash ] && source ~/ros2_ws/install/setup.bash"

info "Lab repositories -> ~/ros2_ws/src"
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src
[ -d kinova-ros2 ] || git clone --depth 1 https://github.com/rpiRobotics/kinova-ros2
[ -d oarbots ]     || git clone --depth 1 https://github.com/rpirobotics/oarbots
mkdir -p pol_thesis
[ -f pol_thesis/README.md ] || cat > pol_thesis/README.md <<'EOF'
# pol_thesis — Pol del Castillo, MS thesis work

My own packages, separate from the lab stack (../oarbots, ../kinova-ros2
are untouched clones). Planned: SO-101 leader -> Kinova teleop bridge,
LeRobot episode recorder, bag->dataset converter, replay node, policy
inference node.
EOF

info "Building kinova_msgs (custom Kinova message types)"
# Build with NO python venv/conda active — CMake would pick that python
# and fail with 'No module named em'. This is why LeRobot uses a venv
# that is only active on demand.
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select kinova_msgs

info "Verification"
source ~/ros2_ws/install/setup.bash
echo "ros2:        $(ros2 --version 2>/dev/null || echo MISSING)"
echo "RMW:         ${RMW_IMPLEMENTATION:-unset}"
echo "kinova_msgs: $(ros2 interface show kinova_msgs/msg/PoseVelocity >/dev/null 2>&1 \
  && echo OK || echo MISSING)"
echo "lerobot:     $(~/lerobot-venv/bin/python -c 'import lerobot; print(lerobot.__version__)' \
  2>/dev/null || echo MISSING)"

cat <<'EOF'

=== Done. Next steps (manual, in order) ===

1. Log out and back in  (activates the 'dialout' serial group).

2. LeRobot with the SO-101 leader arm — in a NEW terminal:
       lerobot-env                    # activates the venv
       lerobot-find-port              # plug/unplug to identify the port
   then calibrate per the docs (a calibration file already exists on the
   Windows machine at C:\Users\guill\lerobot — copy it over if wanted):
       https://huggingface.co/docs/lerobot/so101

3. Lab robots — at the lab, on the CII8218-oarbots Wi-Fi:
       ros2 daemon stop && ros2 topic list
   Expect /oarbot_blue/... and /oarbot_silver/... topics. Native Linux
   should discover by multicast with no extra DDS config; if not, pin
   the interface via a cyclonedds.xml + CYCLONEDDS_URI.

4. Time sync (laptop clock was ~1 s off the robot; matters at deployment):
       sudo systemctl enable --now chrony
EOF
