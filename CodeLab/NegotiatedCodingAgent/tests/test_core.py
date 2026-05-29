from pathlib import Path
import tempfile
import unittest

from negotiated_agent.writer import write_implementation


class WriterTests(unittest.TestCase):
    def test_writes_files_under_implementation_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            written = write_implementation(
                root,
                "```text path=README.md\nhello\n```",
            )
            self.assertEqual(written, [root / "implementation" / "README.md"])
            self.assertEqual(written[0].read_text(encoding="utf-8"), "hello\n")

    def test_accepts_redundant_implementation_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            written = write_implementation(
                root,
                "```text path=implementation/README.md\nhello\n```",
            )
            self.assertEqual(written, [root / "implementation" / "README.md"])

    def test_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                write_implementation(
                    Path(temp),
                    "```text path=../outside.txt\nbad\n```",
                )


if __name__ == "__main__":
    unittest.main()

