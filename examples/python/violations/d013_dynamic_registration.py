"""Deliberately broken: the host discovers components instead of naming them."""

import importlib


def build():
    return importlib.import_module("orders.service")
