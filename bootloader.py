# -*- coding: utf-8 -*-
import logging

from pony.orm import Database
from jinja2 import Environment, FileSystemLoader

db = Database()

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger('PyPon')

template_env = Environment(
    loader=FileSystemLoader(searchpath='templates'), 
    auto_reload=True)

ws_router = None
connections = set()