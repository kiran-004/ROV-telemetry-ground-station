"""Dependency-free ROV physics and control. Distances are metres, angles degrees."""
from dataclasses import dataclass
import math


def clamp(value, low=-1.0, high=1.0):
    return max(low, min(high, value))


def heading_error(target, current):
    """Shortest signed turn, including across north (359 -> 1 = +2)."""
    return (target - current + 180.0) % 360.0 - 180.0


@dataclass
class Telemetry:
    armed: bool = False
    mode: str = "Manual"
    elapsed: float = 0.0
    north: float = 0.0
    east: float = 0.0
    depth: float = 2.0
    yaw: float = 35.0
    roll: float = 0.0
    pitch: float = 0.0
    voltage: float = 16.8


class Simulation:
    MODES = ("Manual", "Depth Hold", "Heading Hold")
    INPUT_TIMEOUT = 1.0
    RESPONSE_TIME = 0.22

    def __init__(self):
        self.state = Telemetry()
        self.target_depth = 2.0
        self.target_heading = 35.0
        self.command = [0.0] * 4  # surge, sway, down, clockwise yaw
        self.thrust = [0.0] * 4
        self.velocity = [0.0] * 4
        self.last_input = -math.inf
        self.watchdog = False

    def arm(self, enabled):
        self.state.armed = bool(enabled)
        # Fresh input is required after arming; disarming bypasses actuator lag.
        self.command = [0.0] * 4
        self.thrust = [0.0] * 4
        self.last_input = -math.inf
        self.watchdog = False

    def set_mode(self, mode):
        if mode not in self.MODES:
            raise ValueError(f"Unknown mode: {mode}")
        self.state.mode = mode
        self.command = [0.0] * 4
        self.thrust = [0.0] * 4
        self.last_input = -math.inf
        self.watchdog = False

    def operator_input(self, surge, sway, heave, yaw):
        if self.state.armed and self.state.mode == "Manual":
            self.command = [clamp(v) for v in (surge, sway, heave, yaw)]
            self.last_input = self.state.elapsed
            self.watchdog = False

    def step(self, dt):
        if not 0.0 < dt <= 0.1:
            raise ValueError("Use a simulation time step in (0, 0.1] seconds")
        s = self.state
        s.elapsed += dt
        desired = [0.0] * 4
        hard_zero = not s.armed
        if s.armed:
            if s.mode == "Manual":
                self.watchdog = s.elapsed - self.last_input >= self.INPUT_TIMEOUT
                if self.watchdog:
                    hard_zero = True
                    self.command = [0.0] * 4
                else:
                    desired = self.command.copy()
            elif s.mode == "Depth Hold":
                # PD control: position error supplies force, velocity damps overshoot.
                desired[2] = clamp(0.85 * (self.target_depth - s.depth)
                                   - 0.95 * self.velocity[2])
            else:
                desired[3] = clamp(0.035 * heading_error(self.target_heading, s.yaw)
                                   - 0.035 * self.velocity[3])
        if hard_zero:
            self.thrust = [0.0] * 4
        else:
            alpha = 1.0 - math.exp(-dt / self.RESPONSE_TIME)
            self.thrust = [actual + alpha * (target - actual)
                           for actual, target in zip(self.thrust, desired)]

        # First-order drag plus actuator response; yaw velocity is degrees/second.
        for i, force in enumerate((1.4, 1.1, 1.0, 70.0)):
            drag = (0.9, 1.1, 1.2, 1.8)[i]
            self.velocity[i] += (force * self.thrust[i] - drag * self.velocity[i]) * dt
        angle = math.radians(s.yaw)
        s.north += (self.velocity[0] * math.cos(angle)
                    - self.velocity[1] * math.sin(angle)) * dt
        s.east += (self.velocity[0] * math.sin(angle)
                   + self.velocity[1] * math.cos(angle)) * dt
        s.depth += self.velocity[2] * dt
        if s.depth <= 0.0 or s.depth >= 100.0:
            s.depth = clamp(s.depth, 0.0, 100.0)
            self.velocity[2] = 0.0
        s.yaw = (s.yaw + self.velocity[3] * dt) % 360.0
        s.roll += (8.0 * self.thrust[1] - s.roll) * min(1.0, dt * 3.0)
        s.pitch += (-6.0 * self.thrust[0] - s.pitch) * min(1.0, dt * 3.0)
        load = sum(abs(v) for v in self.thrust)
        s.voltage = max(12.0, s.voltage - dt * (0.0003 + load * 0.0008))
