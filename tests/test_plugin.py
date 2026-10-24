import struct
import unittest
from tools.build_plugin import build,LOCAL_FORM_ID

class PluginTests(unittest.TestCase):
    def test_single_nonconstant_float_global_and_declared_master(self):
        data=build()
        kind,size,flags,form,*_=struct.unpack_from('<4sIIIIHH',data)
        self.assertEqual((kind,flags,form),(b'TES4',0,0))
        self.assertEqual(struct.unpack_from('<I',data,34)[0],2) # GLOB + GRUP
        self.assertIn(b'MAST\x0b\x00Skyrim.esm\0',data[:24+size])
        offset=24+size
        group,group_size,label,group_type,*_=struct.unpack_from('<4sI4sIHHHH',data,offset)
        self.assertEqual((group,label,group_type),(b'GRUP',b'GLOB',0))
        self.assertEqual(offset+group_size,len(data))
        kind,size,flags,form,*_=struct.unpack_from('<4sIIIIHH',data,offset+24)
        self.assertEqual((kind,flags,form),(b'GLOB',0,0x01000000|LOCAL_FORM_ID))
        self.assertEqual(offset+48+size,len(data))
        self.assertTrue(data.endswith(b'FNAM\x01\x00fFLTV\x04\x00'+struct.pack('<f',0)))
