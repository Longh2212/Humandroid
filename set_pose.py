from Manager.Manager_Robot import RobotController
import yaml

POSE_FILE = "config_pose.yaml"

controller = RobotController()
controller.clear_buffer()

SERVO_GROUPS = {
    "right_arm": [3, 4, 5, 6, 7],
    "left_arm": [19, 20, 21, 22, 23],
    "right_hand": [8, 9, 10, 11, 12],
    "left_hand": [24, 25, 26, 27, 28]
}


def load_yaml():
    try:
        with open(POSE_FILE, "r") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def save_yaml(data):
    with open(POSE_FILE, "w") as f:
        yaml.dump(data, f)


def save_id(servo_id: int):
    last_angle = None

    while True:
        angle = input("Nhập góc (hoặc 's' để lưu): ").strip()

        if angle == "s":
            break

        angle = int(angle)
        controller.move_servo(servo_id, angle)
        controller.read_response()

        last_angle = angle

    return servo_id, last_angle


def save_pose(group_name, values, pose_name):
    data = load_yaml()

    data.setdefault("poses", {})
    data["poses"].setdefault(group_name, {})

    pose = {
        sid: val
        for sid, val in values.items()
        if val is not None
    }

    data["poses"][group_name][pose_name] = pose

    save_yaml(data)

    print(f"[SAVE] {group_name} -> {pose_name}")
while True:
    print("\n---------")
    print("0.right_arm, 1.left_arm, 2.right_hand, 3.left_hand")

    choice = input("Chọn nhóm (q để thoát): ").strip()

    if choice == "q":
        break

    group_map = {
        "0": "right_arm",
        "1": "left_arm",
        "2": "right_hand",
        "3": "left_hand"
    }

    if choice not in group_map:
        print("Nhóm không hợp lệ!")
        continue

    group_name = group_map[choice]
    servo_list = SERVO_GROUPS[group_name]

    values = {}

    print(f"Điều khiển group: {group_name}")

    for sid in servo_list:
        print(f"\nServo ID: {sid}")
        sid, angle = save_id(sid)
        values[sid] = angle
    pose_name = input("Nhập tên pose: ").strip()

    save_pose(group_name, values, pose_name)
