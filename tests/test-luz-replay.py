"""Request identifiers and rollback handling."""
import sys
from unittest.mock import patch
from itertools import count
sys.path.insert(0,"src")
import BombillaLocal as local

a = local.ProtocoloLuz("127.0.0.1", "a7"*16)
b = local.ProtocoloLuz("127.0.0.1", "a7"*16)
assert a._create_request("status", None)["id"] != b._create_request("status", None)["id"]
with patch.object(local, "REQUEST_IDS", count(2**31-1)):
    assert a._create_request("status", None)["id"] == 2**31-1
    try:
        a._create_request("status", None)
    except local.DeviceException:
        pass
    else:
        raise AssertionError("Wrapped identifier")

from subprocess import check_output
code = "import sys;sys.path.insert(0,'src');from BombillaLocal import ProtocoloLuz;print(ProtocoloLuz()._create_request('status',None)['id'])"
starting_ids = [int(check_output([sys.executable,"-B","-c",code], timeout=8)) for _ in range(2)]
assert len(set(starting_ids)) == 2
