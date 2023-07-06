#
# Copyright Tristen Georgiou 2023
#
# test app
from fastapi import FastAPI

from tasos.apiauth.api import add_base_endpoints_to_app, add_permission_endpoints_to_app

app = FastAPI()
add_base_endpoints_to_app(app)
add_permission_endpoints_to_app(app)
