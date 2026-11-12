import unittest

from simulation import Simulation, heading_error


class SimulationTests(unittest.TestCase):
    def run_for(self, sim, seconds):
        for _ in range(round(seconds / 0.02)):
            sim.step(0.02)

    def test_disarmed_thrust_is_zero_in_every_mode(self):
        for mode in Simulation.MODES:
            with self.subTest(mode=mode):
                sim = Simulation()
                sim.arm(True)
                sim.set_mode(mode)
                sim.target_depth = 20
                sim.target_heading = 150
                sim.operator_input(1, 1, 1, 1)
                sim.step(0.02)
                self.assertTrue(any(sim.thrust))
                sim.arm(False)
                self.assertEqual(sim.thrust, [0.0] * 4)
                self.run_for(sim, 2)
                self.assertEqual(sim.thrust, [0.0] * 4)

    def test_watchdog_cuts_actual_thrust_after_one_second(self):
        sim = Simulation()
        sim.arm(True)
        sim.operator_input(1, 0, 0, 0)
        self.run_for(sim, 0.98)
        self.assertGreater(sim.thrust[0], 0)
        self.run_for(sim, 0.04)
        self.assertEqual(sim.thrust, [0.0] * 4)
        self.assertTrue(sim.watchdog)

    def test_thruster_delay_and_drag(self):
        sim = Simulation()
        sim.arm(True)
        sim.operator_input(1, 0, 0, 0)
        sim.step(0.02)
        self.assertGreater(sim.thrust[0], 0)
        self.assertLess(sim.thrust[0], 0.2)
        self.run_for(sim, 0.4)
        speed = sim.velocity[0]
        sim.arm(False)
        self.run_for(sim, 2)
        self.assertGreater(sim.velocity[0], 0)
        self.assertLess(sim.velocity[0], speed)

    def test_depth_hold_converges(self):
        sim = Simulation()
        sim.set_mode("Depth Hold")
        sim.target_depth = 8
        sim.arm(True)
        self.run_for(sim, 40)
        self.assertAlmostEqual(sim.state.depth, 8, delta=0.05)

    def test_heading_hold_crosses_north_by_shortest_route(self):
        sim = Simulation()
        sim.state.yaw = 359
        sim.target_heading = 1
        sim.set_mode("Heading Hold")
        sim.arm(True)
        sim.step(0.02)
        self.assertGreater(sim.thrust[3], 0)
        self.run_for(sim, 20)
        self.assertAlmostEqual(heading_error(1, sim.state.yaw), 0, delta=0.1)

    def test_all_manual_axes_move(self):
        for axis in range(4):
            with self.subTest(axis=axis):
                sim = Simulation()
                sim.arm(True)
                command = [0] * 4
                command[axis] = 1
                for _ in range(40):
                    sim.operator_input(*command)
                    sim.step(0.02)
                self.assertGreater(sim.velocity[axis], 0)
                if axis == 0:
                    self.assertGreater(sim.state.north, 0)
                elif axis == 1:
                    self.assertGreater(sim.state.east, 0)
                elif axis == 2:
                    self.assertGreater(sim.state.depth, 2)
                else:
                    self.assertGreater(sim.state.yaw, 35)

    def test_depth_stays_within_bounds(self):
        sim = Simulation()
        sim.arm(True)
        for _ in range(2000):
            sim.operator_input(0, 0, -1, 0)
            sim.step(0.02)
        self.assertEqual(sim.state.depth, 0)
        self.assertEqual(sim.velocity[2], 0)

    def test_rearming_does_not_restore_previous_command(self):
        sim = Simulation()
        sim.arm(True)
        sim.operator_input(1, 1, 1, 1)
        sim.step(0.02)
        sim.arm(False)
        sim.arm(True)
        sim.step(0.02)
        self.assertEqual(sim.thrust, [0.0] * 4)

    def test_mode_switch_clears_manual_command(self):
        sim = Simulation()
        sim.arm(True)
        sim.operator_input(1, 0, 0, 0)
        sim.step(0.02)
        sim.set_mode("Depth Hold")
        sim.step(0.02)
        self.assertEqual(sim.thrust[0], 0)
        sim.set_mode("Manual")
        sim.step(0.02)
        self.assertEqual(sim.thrust, [0.0] * 4)


if __name__ == "__main__":
    unittest.main()
