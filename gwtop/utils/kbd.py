#!/usr/bin/python

__author__ = 'pcuzner@redhat.com'

import sys
import tty
from select import select


class NotTTYException(Exception): pass


class TerminalFile:
    """
    Terminal handling class, enabling keyboard scanning

    Based on 203830-checking-for-a-keypress-without-stop-the-execution
    from http://code.activestate.com/recipes/
    """

    def __init__(self, infile):
        if not infile.isatty():
            raise NotTTYException()
        self.file = infile

        # prepare for getch
        self.save_attr = tty.tcgetattr(self.file)
        newattr = self.save_attr[:]
        newattr[3] &= ~tty.ECHO & ~tty.ICANON
        tty.tcsetattr(self.file, tty.TCSANOW, newattr)

    def __del__(self):
        # restoring stdin
        import tty  # required this import here
        tty.tcsetattr(self.file, tty.TCSADRAIN, self.save_attr)

    def reset(self):
        tty.tcsetattr(self.file, tty.TCSADRAIN, self.save_attr)

    def getch(self):
        if select([self.file], [], [], 0)[0]:
            c = self.file.read(1)
        else:
            c = ''
        return c


if __name__=="__main__":
    s = TerminalFile(sys.stdin)
    print("Press q to quit...")
    i = 0
    while s.getch() != "q":
        sys.stdout.write("%08d\r"%i)
        i += 1
    print("-- END --")
