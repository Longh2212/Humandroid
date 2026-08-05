import numpy as np
from math import sin, cos, radians


# ==========================================================
# InMoov Right Arm DH Forward Kinematics + Inverse Kinematics
#
# Robot coordinate:
#   X: up
#   Y: left
#   Z: forward
#
# Right arm:
#   X thường âm vì tay thấp hơn gốc
#   Y thường âm vì tay phải nằm bên phải robot
#   Z dương là đưa tay ra phía trước
#
# Unit:
#   cm
#
# Original DH table is for LEFT ARM:
#
# i   alpha(i-1)   a(i-1)   d_i        theta_i
# 1   0            0        0          theta1
# 2   pi/2         0        l2+l3      -pi/2 + theta2
# 3   -pi/2        0        l4         theta3
# 4   -pi/2        0        l5         theta4
# 5   pi/2         0        l6         theta5
# 6   -pi/2        0        l7         0
#
# Left arm offset:
#   x_left = px + 24
#   y_left = py + 7
#   z_left = pz
#
# Convert to RIGHT ARM by mirror:
#   x_right = -(px + 24)
#   y_right = -(py + 7)
#   z_right = pz
#
# Therefore:
#   FK [0,0,0,0,0] should be [-56.5, -26.5, 0]
# ==========================================================


class InMoovRightArmDH:
    def __init__(self):
        # ==================================================
        # Lengths in cm
        # ==================================================
        self.L0 = 24.0
        self.L1 = 7.0
        self.L2 = 5.5
        self.L3 = 9.0
        self.L4 = 3.5
        self.L5 = 25.0
        self.L6 = 29.0
        self.L7 = 9.0

        # ==================================================
        # Offset before mirror
        # ==================================================
        self.offset = np.array(
            [24.0, 7.0, 0.0],
            dtype=float
        )

        # ==================================================
        # Joint limits in degrees
        #
        # q1: shoulder yaw
        # q2: shoulder pitch
        # q3: shoulder roll
        # q4: elbow
        # q5: wrist
        # ==================================================
        self.joint_limits = [
            (-30.0, 0.0),    # q1
            (-80.0, 70.0),   # q2
            (0.0, 180.0),    # q3
            (0.0, 70.0),     # q4
            (-80.0, 0.0),    # q5
        ]

        # ==================================================
        # Servo mapping config
        # Giữ theo code cũ của bạn
        # ==================================================
        self.servo_config = {
            3: {
                "joint": 0,
                "joint_min": 0,
                "joint_max": -30,
                "servo_min": 120,
                "servo_max": 150,
                "invert": True,
            },
            4: {
                "joint": 1,
                "joint_min": -80,
                "joint_max": 70,
                "servo_min": 0,
                "servo_max": 150,
                "invert": True,
            },
            5: {
                "joint": 2,
                "joint_min": 0,
                "joint_max": 180,
                "servo_min": 0,
                "servo_max": 150,
                "invert": True,
            },
            6: {
                "joint": 3,
                "joint_min": 0,
                "joint_max": 70,
                "servo_min": 110,
                "servo_max": 180,
                "invert": True,
            },
            7: {
                "joint": 4,
                "joint_min": 0,
                "joint_max": -80,
                "servo_min": 0,
                "servo_max": 180,
                "invert": False,
            },
        }

    # ======================================================
    # Basic math
    # ======================================================

    def clamp(self, value, a, b):
        low = min(a, b)
        high = max(a, b)
        return max(low, min(high, value))

    def clamp_joints(self, q):
        q = np.array(q, dtype=float)

        for i, (low, high) in enumerate(self.joint_limits):
            q[i] = self.clamp(
                q[i],
                low,
                high
            )

        return q

    def norm(self, v):
        return float(np.linalg.norm(v))

    # ======================================================
    # Servo mapping
    # ======================================================

    def joint_to_servo(self, joint_angle, cfg):
        j_min = cfg["joint_min"]
        j_max = cfg["joint_max"]

        s_min = cfg["servo_min"]
        s_max = cfg["servo_max"]

        joint_angle = self.clamp(
            joint_angle,
            j_min,
            j_max
        )

        t = (joint_angle - j_min) / (j_max - j_min)

        if cfg["invert"]:
            servo_angle = s_max + t * (s_min - s_max)
        else:
            servo_angle = s_min + t * (s_max - s_min)

        servo_angle = self.clamp(
            servo_angle,
            s_min,
            s_max
        )

        return int(round(servo_angle))

    def joints_to_servos(self, joints):
        servos = {}

        for servo_id, cfg in self.servo_config.items():
            joint_id = cfg["joint"]
            joint_angle = joints[joint_id]

            servos[servo_id] = self.joint_to_servo(
                joint_angle,
                cfg
            )

        return servos

    def servo_to_joint(self, servo_angle, cfg):
        j_min = cfg["joint_min"]
        j_max = cfg["joint_max"]

        s_min = cfg["servo_min"]
        s_max = cfg["servo_max"]

        servo_angle = self.clamp(
            servo_angle,
            s_min,
            s_max
        )

        if cfg["invert"]:
            t = (servo_angle - s_max) / (s_min - s_max)
        else:
            t = (servo_angle - s_min) / (s_max - s_min)

        joint_angle = j_min + t * (j_max - j_min)

        return float(joint_angle)

    def servos_to_joints(self, servos):
        joints = [0.0] * 5

        for servo_id, cfg in self.servo_config.items():
            if servo_id not in servos:
                continue

            joint_id = cfg["joint"]

            joints[joint_id] = self.servo_to_joint(
                servos[servo_id],
                cfg
            )

        return joints

    # ======================================================
    # Standard DH Transform
    #
    # A_i = RotX(alpha_i-1)
    #       * TransX(a_i-1)
    #       * TransZ(d_i)
    #       * RotZ(theta_i)
    #
    # With your table, a(i-1) = 0 for all joints.
    # ======================================================

    def dh_transform(self, alpha, a, d, theta):
        ca = cos(alpha)
        sa = sin(alpha)
        ct = cos(theta)
        st = sin(theta)

        return np.array(
            [
                [ct, -st, 0.0, a],
                [st * ca, ct * ca, -sa, -d * sa],
                [st * sa, ct * sa, ca, d * ca],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=float
        )

    # ======================================================
    # Coordinate transform
    #
    # Original left-arm DH output:
    #   x_left = px + 24
    #   y_left = py + 7
    #   z_left = pz
    #
    # Right-arm robot coordinate:
    #   x_right = -(px + 24)
    #   y_right = -(py + 7)
    #   z_right = pz
    # ======================================================

    def dh_pos_to_robot_pos(self, p_dh):
        return np.array(
            [
                -(p_dh[0] + self.offset[0]),
                -(p_dh[1] + self.offset[1]),
                p_dh[2] + self.offset[2],
            ],
            dtype=float
        )

    def robot_pos_to_dh_pos(self, p_robot):
        return np.array(
            [
                -p_robot[0] - self.offset[0],
                -p_robot[1] - self.offset[1],
                p_robot[2] - self.offset[2],
            ],
            dtype=float
        )

    # ======================================================
    # DH table
    # ======================================================

    def get_dh_table(self, joints):
        q = self.clamp_joints(joints)

        q1 = radians(q[0])
        q2 = radians(q[1])
        q3 = radians(q[2])
        q4 = radians(q[3])
        q5 = radians(q[4])

        dh_table = [
            # alpha       a    d                 theta
            [0.0,         0.0, 0.0,              q1],
            [np.pi / 2,   0.0, self.L2 + self.L3, -np.pi / 2 + q2],
            [-np.pi / 2,  0.0, self.L4,          q3],
            [-np.pi / 2,  0.0, self.L5,          q4],
            [np.pi / 2,   0.0, self.L6,          q5],
            [-np.pi / 2,  0.0, self.L7,          0.0],
        ]

        return dh_table

    # ======================================================
    # Forward Kinematics by DH
    # ======================================================

    def forward_kinematics_dh(self, joints):
        """
        Input:
            joints = [q1, q2, q3, q4, q5]
            unit: degree

        Return:
            palm position in robot coordinate.
        """

        q = self.clamp_joints(joints)

        dh_table = self.get_dh_table(q)

        T = np.eye(4)

        points_dh = []
        points_robot = []

        for alpha, a, d, theta in dh_table:
            A = self.dh_transform(
                alpha,
                a,
                d,
                theta
            )

            T = T @ A

            p_dh = T[:3, 3].copy()
            p_robot = self.dh_pos_to_robot_pos(p_dh)

            points_dh.append(p_dh)
            points_robot.append(p_robot)

        palm_robot = points_robot[-1]

        return {
            "joints": {
                0: float(q[0]),
                1: float(q[1]),
                2: float(q[2]),
                3: float(q[3]),
                4: float(q[4]),
            },
            "palm": palm_robot,
            "points": {
                "joint_1": points_robot[0],
                "joint_2": points_robot[1],
                "joint_3": points_robot[2],
                "joint_4": points_robot[3],
                "joint_5": points_robot[4],
                "palm": points_robot[5],
            },
            "points_dh": {
                "joint_1": points_dh[0],
                "joint_2": points_dh[1],
                "joint_3": points_dh[2],
                "joint_4": points_dh[3],
                "joint_5": points_dh[4],
                "palm": points_dh[5],
            },
            "T": T,
            "R": T[:3, :3],
        }

    def fk_position(self, joints):
        fk = self.forward_kinematics_dh(joints)
        return fk["palm"]

    # ======================================================
    # Numerical Jacobian
    #
    # J: 3 x 5
    # Output unit:
    #   cm / degree
    # ======================================================

    def numerical_jacobian(self, q, delta=0.1):
        q = np.array(q, dtype=float)

        J = np.zeros(
            (3, 5),
            dtype=float
        )

        for i in range(5):
            dq = np.zeros(5)
            dq[i] = delta

            q_plus = self.clamp_joints(q + dq)
            q_minus = self.clamp_joints(q - dq)

            p_plus = self.fk_position(q_plus)
            p_minus = self.fk_position(q_minus)

            J[:, i] = (p_plus - p_minus) / (2.0 * delta)

        return J

    # ======================================================
    # Inverse Kinematics by DH FK + Damped Least Squares
    #
    # This IK solves position only:
    #   target = [x, y, z]
    #
    # Orientation is not constrained.
    # ======================================================

    def solve_dh(
        self,
        x,
        y,
        z,
        initial_joints=None,
        max_iter=700,
        tolerance=2.0,
        damping=0.8,
        max_step_deg=4.0,
    ):
        target = np.array(
            [x, y, z],
            dtype=float
        )

        # Vì chỉ giải XYZ, robot có nhiều nghiệm.
        # Thử nhiều tư thế ban đầu để tránh kẹt nghiệm xấu.
        if initial_joints is None:
            initial_candidates = [
                [0, 0, 0, 0, 0],
                [0, 0, 90, 20, 0],
                [-10, 0, 90, 30, 0],
                [-20, 10, 90, 40, -10],
                [-30, 20, 90, 50, -20],
                [-10, -30, 90, 40, 0],
                [-20, -50, 90, 60, -20],
                [0, 30, 90, 20, 0],
            ]
        else:
            initial_candidates = [initial_joints]

        best = None
        best_error = 1e9

        for q_start in initial_candidates:
            q = self.clamp_joints(q_start)

            for _ in range(max_iter):
                current = self.fk_position(q)

                error_vec = target - current
                error = self.norm(error_vec)

                if error < tolerance:
                    break

                J = self.numerical_jacobian(q)

                JT = J.T

                A = J @ JT + (damping ** 2) * np.eye(3)

                try:
                    dq = JT @ np.linalg.solve(
                        A,
                        error_vec
                    )
                except np.linalg.LinAlgError:
                    dq = JT @ np.linalg.pinv(A) @ error_vec

                dq_norm = self.norm(dq)

                if dq_norm > max_step_deg:
                    dq = dq / dq_norm * max_step_deg

                q = q + dq
                q = self.clamp_joints(q)

            fk = self.forward_kinematics_dh(q)
            palm = fk["palm"]

            final_error = self.norm(
                palm - target
            )

            if final_error < best_error:
                best_error = final_error
                best = {
                    "q": q.copy(),
                    "fk": fk,
                    "error": final_error,
                }

        q = best["q"]
        fk = best["fk"]

        q_int = [
            int(round(q[0])),
            int(round(q[1])),
            int(round(q[2])),
            int(round(q[3])),
            int(round(q[4])),
        ]

        # Tính lại sau khi làm tròn joint
        fk_int = self.forward_kinematics_dh(q_int)
        palm_int = fk_int["palm"]

        error_after_round = self.norm(
            palm_int - target
        )

        success = error_after_round <= tolerance

        servos = self.joints_to_servos(q_int)

        return {
            "success": success,
            "target": np.round(target, 2).tolist(),
            "joints": {
                0: q_int[0],
                1: q_int[1],
                2: q_int[2],
                3: q_int[3],
                4: q_int[4],
            },
            "servos": servos,
            "points": {
                name: np.round(pos, 2).tolist()
                for name, pos in fk_int["points"].items()
            },
            "palm": np.round(palm_int, 2).tolist(),
            "error_cm": round(
                float(error_after_round),
                3
            ),
        }

    # ======================================================
    # Test helpers
    # ======================================================

    def print_fk(self, joints):
        fk = self.forward_kinematics_dh(joints)

        print()
        print("FK result")
        print("Joints:", joints)
        print("Palm:", np.round(fk["palm"], 2).tolist())
        print("Points:")

        for name, pos in fk["points"].items():
            print(
                " ",
                name,
                ":",
                np.round(pos, 2).tolist()
            )

    def print_ik(self, x, y, z):
        result = self.solve_dh(
            x,
            y,
            z
        )

        print()
        print("IK result")
        print("Success:", result["success"])
        print("Target:", result["target"])
        print("Joints:", result["joints"])
        print("Servos:", result["servos"])
        print("Palm:", result["palm"])
        print("Error cm:", result["error_cm"])
        print("Points:")

        for name, pos in result["points"].items():
            print(
                " ",
                name,
                ":",
                pos
            )


# ==========================================================
# Main test
# ==========================================================

if __name__ == "__main__":
    robot = InMoovRightArmDH()

    print("===================================")
    print("InMoov Right Arm DH FK + IK")
    print("Coordinate:")
    print("  X: up")
    print("  Y: left")
    print("  Z: forward")
    print()
    print("Right arm expected:")
    print("  FK [0, 0, 0, 0, 0]")
    print("  Palm should be about [-56.5, -26.5, 0]")
    print("===================================")

    # Quick check
    robot.print_fk(
        [0, 0, 0, 0, 0]
    )

    while True:
        print()
        print("Choose mode:")
        print("  1: FK - input q1 q2 q3 q4 q5")
        print("  2: IK - input x y z")
        print("  q: quit")

        mode = input("Mode: ").strip().lower()

        if mode in ["q", "quit", "exit"]:
            break

        if mode == "1":
            text = input(
                "Nhap q1 q2 q3 q4 q5, vi du: 0 0 0 0 0: "
            )

            try:
                joints = list(
                    map(
                        float,
                        text.split()
                    )
                )

                if len(joints) != 5:
                    print("Can nhap dung 5 goc joint.")
                    continue

                robot.print_fk(joints)

            except Exception as e:
                print("Error:", e)

        elif mode == "2":
            text = input(
                "Nhap x y z, vi du: -56.5 -26.5 0: "
            )

            try:
                x, y, z = map(
                    float,
                    text.split()
                )

                robot.print_ik(
                    x,
                    y,
                    z
                )

            except Exception as e:
                print("Error:", e)

        else:
            print("Mode khong hop le.")