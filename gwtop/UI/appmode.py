#!/usr/bin/env python

__author__ = 'paul'
import threading


class AppMode(threading.Thread):
    """
    Class handling the ncurses interface, displaying the aggregated performance metrics
    """

    def __init__(self):
        threading.Thread.__init__(self)
        pass
