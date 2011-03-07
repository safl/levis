#!/usr/bin/env python
import unittest, os
import pubsub

class TestKeyParsing(unittest.TestCase):

    def setUp(self):
        self.key = "Type=win_events.Representation=string.Compression=False.Result=False"

        self.data_struct = {'hej': [1,2,3,4], 'der': [3,2,1], 'jam': {'hej':'igen', 'der': [[1,2,3], [1,2,3], [1,2,3], [1,2,3], ]}}

    #
    # Test the parsing of routing-keys.
    #
    def test_parse(self):

        kd = pubsub.key_to_attr(self.key)

        self.assertEqual(len(kd), 4)
        self.assertTrue(kd.has_key('Type'))
        self.assertTrue(kd.has_key('Representation'))
        self.assertTrue(kd.has_key('Compression'))
        self.assertTrue(kd.has_key('Result'))

        self.assertEqual(kd['Type'], 'win_events')
        self.assertEqual(kd['Representation'], 'string')
        self.assertEqual(kd['Compression'], 'False')
        self.assertEqual(kd['Result'], 'False')

    def test_parse_empty(self):

        kd = pubsub.key_to_attr("")

        self.assertEqual(len(kd), 0)

    def test_parse_noequal(self):

        kd = pubsub.key_to_attr("Type=win_events.Representation")

        self.assertEqual(len(kd), 1)

    def test_parse_dotnoright(self):

        kd = pubsub.key_to_attr("Type=win_events.Representation=string.")

        self.assertEqual(len(kd), 2)

    def test_parse_dotnoleft(self):

        kd = pubsub.key_to_attr(".Type=win_events.Representation=string")

        self.assertEqual(len(kd), 2)

    def test_parse_noleft(self):

        kd = pubsub.key_to_attr("Type=win_events.=string")
        self.assertEqual(len(kd), 1)

    def test_parse_noright(self):

        kd = pubsub.key_to_attr("Type=win_events.Representation=")
        self.assertEqual(len(kd), 1)

class TestMessageMarshalling(unittest.TestCase):

    def setUp(self):
        self.data_struct = {'hej': [1,2,3,4], 'der': [3,2,1], 'jam': {'hej':'igen', 'der': [[1,2,3], [1,2,3], [1,2,3], [1,2,3], ]}}

    # Test message packing
    def test_pack(self):
        self.assertEqual(self.data_struct, pubsub.unpack(pubsub.pack(self.data_struct)))

    def test_pack_none(self):
        self.assertEqual(None, pubsub.unpack(pubsub.pack(None)))

    def test_pack_empty_list(self):
        self.assertEqual([], pubsub.unpack(pubsub.pack([])))

    def test_pack_empty_struct(self):
        self.assertEqual({}, pubsub.unpack(pubsub.pack({})))

    def test_serialize(self):
        self.assertEqual(self.data_struct, pubsub.deserialize(pubsub.serialize(self.data_struct)))

    def test_compress(self):
        self.assertEqual(self.data_struct, pubsub.deserialize(pubsub.decompress(pubsub.compress(pubsub.serialize(self.data_struct)))))

if __name__ == '__main__':
    unittest.main()
