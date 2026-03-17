#!/usr/bin/env python3
import os

ENV = {}
STATE = {"verbose": False}
for k, v in os.environ.items():
    ENV[k] = v
