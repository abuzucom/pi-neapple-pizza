import os
import unittest

from tools import run_pi_product_validation


class PiProductValidationTest(unittest.TestCase):
    """Verify direct npm invocation remains portable and shell-free."""

    def test_every_validation_uses_the_platform_npm_executable(self):
        expected = "npm.cmd" if os.name == "nt" else "npm"
        self.assertEqual(run_pi_product_validation.NPM_EXECUTABLE, expected)
        for _name, command in run_pi_product_validation.VALIDATIONS:
            with self.subTest(command=command):
                self.assertEqual(command[0], expected)


if __name__ == "__main__":
    unittest.main()
