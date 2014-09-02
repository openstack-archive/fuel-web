#!/usr/bin/env python
import os
import sys

current_directory = os.path.dirname(__file__)
sys.path.append(current_directory)

from tasklib import cli
cli.main()
