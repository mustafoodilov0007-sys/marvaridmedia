"""🎬 Botning ochilish animatsiyasi: poster kollajidan MP4 yasash."""

import io
import os
import subprocess
import tempfile
import unittest

from app import trailer_anim


@unittest.skipUnless(trailer_anim.available(), "Pillow/ffmpeg yo'q")
class Anim(unittest.TestCase):
    def posters(self, n=5):
        from PIL import Image
        out = []
        for i in range(n):
            b = io.BytesIO()
            Image.new("RGB", (300, 450), (40 + i * 40, 60, 120)).save(b, "JPEG")
            out.append(b.getvalue())
        return out

    def test_builds_mp4(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "a.mp4")
            trailer_anim.build(self.posters(), p, fps=10, dur=1.0)
            info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height,codec_name", "-of", "csv=p=0", p],
                                  capture_output=True, text=True).stdout
            self.assertIn("h264,640,360", info)

    def test_needs_posters(self):
        with self.assertRaises(ValueError):
            trailer_anim.build([b"x", b"y"], "/tmp/none.mp4", fps=5, dur=0.5)


if __name__ == "__main__":
    unittest.main()
