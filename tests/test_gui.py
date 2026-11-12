"""Offscreen Qt regression: sustained drawing, mode controls and clean shutdown."""
import importlib.util
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 not installed")
class GuiTests(unittest.TestCase):
    def test_render_modes_and_shutdown(self):
        from PySide6 import __version__
        if sys.version_info < (3, 12) and tuple(map(int, __version__.split(".")[:2])) >= (6, 12):
            self.skipTest("Use Python 3.12 for the installed PySide6 6.12 runtime")
        import shiboken6
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from main import Dashboard

        app = QApplication.instance() or QApplication([])
        window = Dashboard()
        try:
            window.show()
            window.toggle_arm()
            self.assertTrue(window.sim.state.armed)
            window.mode.setCurrentText("Depth Hold")
            self.assertTrue(window.depth_target.isEnabled())
            window.depth_target.setValue(8)
            self.assertEqual(window.sim.target_depth, 8)
            window.mode.setCurrentText("Heading Hold")
            self.assertTrue(window.heading_target.isEnabled())
            self.assertFalse(window.depth_target.isEnabled())
            window.heading_target.setValue(120)
            self.assertEqual(window.sim.target_heading, 120)
            # The previous Python 3.10/Qt combination aborted after ~6 seconds.
            QTimer.singleShot(15000, app.quit)
            app.exec()
            self.assertGreater(window.sim.state.elapsed, 10)
            self.assertFalse(window.grab().isNull())
            window.disarm()
            self.assertEqual(window.sim.thrust, [0.0] * 4)
        finally:
            app.removeEventFilter(window)
            window.physics_timer.stop()
            window.ui_timer.stop()
            window.close()
            shiboken6.delete(window)


if __name__ == "__main__":
    unittest.main()
