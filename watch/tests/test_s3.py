"""AWS rasmiy hujjatidagi namunalar bilan imzo to'g'riligini tekshiradi:  python -m unittest discover tests"""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import s3  # noqa: E402

AK, SK = "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
T = dt.datetime(2013, 5, 24, 0, 0, 0, tzinfo=dt.timezone.utc)


class SigV4(unittest.TestCase):
    def test_presigned_get(self):
        url = s3.presign("GET", "examplebucket.s3.amazonaws.com", "/test.txt", {}, AK, SK, "us-east-1", 86400, now=T)
        self.assertTrue(url.endswith("X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404"))

    def test_header_signature(self):
        h = s3.sign_headers("GET", "examplebucket.s3.amazonaws.com", "/test.txt", {}, b"", AK, SK, "us-east-1",
                            {"range": "bytes=0-9"}, now=T)
        self.assertTrue(h["authorization"].endswith("f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"))


if __name__ == "__main__":
    unittest.main()
