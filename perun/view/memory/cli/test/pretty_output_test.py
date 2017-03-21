""" This is testing module for pretty_output.py module """
import unittest
import perun.view.memory.cli.pretty_output as testing

__author__ = 'Radim Podola'


class TestGetPrettyCallTrace(unittest.TestCase):
    __test_trace = [{
              "line": 0,
              "source": "unreachable",
              "function": "valloc"
            },
            {
              "line": 75,
              "source": "/home/user/dev/test.c",
              "function": "main"
            },
            {
              "line": 0,
              "source": "unreachable",
              "function": "__libc_start_main"
            },
            {
              "line": 0,
              "source": "unreachable",
              "function": "_start"
            }]


    def test_correct_output_no_margin_no_indent(self):
        """ Testing correct output without indentation and margin. """
        res = testing.get_pretty_call_trace(self.__test_trace,
                                            indent=0, margin=0)
        self.assertEqual(res, 'valloc()  in  unreachable:0\n'
                              'main()  in  /home/user/dev/test.c:75\n'
                              '__libc_start_main()  in  unreachable:0\n'
                              '_start()  in  unreachable:0\n')


    def test_correct_output_no_indent_w_margin(self):
        """ Testing correct output without indentation. """
        res = testing.get_pretty_call_trace(self.__test_trace,
                                            indent=0, margin=2)
        self.assertEqual(res, '  valloc()  in  unreachable:0\n'
                              '  main()  in  /home/user/dev/test.c:75\n'
                              '  __libc_start_main()  in  unreachable:0\n'
                              '  _start()  in  unreachable:0\n')


    def test_correct_output_no_margin_w_indent(self):
        """ Testing correct output without margin. """
        res = testing.get_pretty_call_trace(self.__test_trace,
                                            indent=2, margin=0)
        self.assertEqual(res, 'valloc()  in  unreachable:0\n'
                              '  main()  in  /home/user/dev/test.c:75\n'
                              '    __libc_start_main()  in  unreachable:0\n'
                              '      _start()  in  unreachable:0\n')


    def test_correct_output_w_margin_w_indent(self):
        """ Testing correct output with indentation and margin. """
        res = testing.get_pretty_call_trace(self.__test_trace,
                                            indent=1, margin=2)
        self.assertEqual(res, '  valloc()  in  unreachable:0\n'
                              '   main()  in  /home/user/dev/test.c:75\n'
                              '    __libc_start_main()  in  unreachable:0\n'
                              '     _start()  in  unreachable:0\n')


    def test_empty_trace(self):
        """ Testing response to empty trace record. """
        res = testing.get_pretty_call_trace([])
        self.assertEqual(res, '')


class TestGetPrettyResources(unittest.TestCase):
    __test_resources = [{
          "subtype": "malloc",
          "trace": [
            {
              "line": 0,
              "source": "unreachable",
              "function": "malloc"
            },
            {
              "line": 45,
              "source": "/home/user/dev/test.c",
              "function": "main"
            }
          ],
          "uid": {
            "line": 45,
            "source": "/home/user/dev/test.c",
            "function": "main"
          },
          "amount": 0,
          "type": "memory",
          "address": 13374016
        },
        {
            "subtype": "malloc",
            "trace": [
                {
                    "line": 0,
                    "source": "unreachable",
                    "function": "malloc"
                },
                {
                    "line": 45,
                    "source": "/home/user/dev/test.c",
                    "function": "main"
                }
            ],
            "uid": {
                "line": 45,
                "source": "/home/user/dev/test.c",
                "function": "main"
            },
            "amount": 4,
            "type": "memory",
            "address": 13374016
        }
    ]


    def test_correct_output_no_indent(self):
        """ Testing correct output without indentation. """
        res = testing.get_pretty_resources(self.__test_resources,
                                           unit='B', indent=0)
        self.assertEqual(res, '#1 malloc: 0B at 13374016\n'
                              'by\n'
                              '   malloc()  in  unreachable:0\n'
                              '   main()  in  /home/user/dev/test.c:45\n\n'
                              '#2 malloc: 4B at 13374016\n'
                              'by\n'
                              '   malloc()  in  unreachable:0\n'
                              '   main()  in  /home/user/dev/test.c:45')


    def test_correct_output_unit(self):
        """ Testing correct output unit. """
        res = testing.get_pretty_resources(self.__test_resources,
                                           unit='TUNIT', indent=0)
        self.assertEqual(res, '#1 malloc: 0TUNIT at 13374016\n'
                              'by\n'
                              '   malloc()  in  unreachable:0\n'
                              '   main()  in  /home/user/dev/test.c:45\n\n'
                              '#2 malloc: 4TUNIT at 13374016\n'
                              'by\n'
                              '   malloc()  in  unreachable:0\n'
                              '   main()  in  /home/user/dev/test.c:45')


    def test_correct_output_w_indent(self):
        """ Testing correct output with indentation. """
        res = testing.get_pretty_resources(self.__test_resources,
                                           unit='', indent=3)
        self.assertEqual(res, '#1 malloc: 0 at 13374016\n'
                              'by\n'
                              '   malloc()  in  unreachable:0\n'
                              '      main()  in  /home/user/dev/test.c:45\n\n'
                              '#2 malloc: 4 at 13374016\n'
                              'by\n'
                              '   malloc()  in  unreachable:0\n'
                              '      main()  in  /home/user/dev/test.c:45')


    def test_empty_resources(self):
        """ Testing response to empty resources record. """
        res = testing.get_pretty_resources([], '')
        self.assertEqual(res, '')


if __name__ == '__main__':
    unittest.main()
