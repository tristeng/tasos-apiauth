#
# Copyright Tristen Georgiou 2023
#
from fastapi import FastAPI

from tasos.apiauth.api import add_all_endpoints_to_app

# create your app as you like
app = FastAPI(
    title="Tasos API Auth",
    description="A FastAPI authentication and authorization library",
    version="0.1.0",
)

# add the endpoints to your app
add_all_endpoints_to_app(app)

# from this directory, run `uvicorn sample:app --reload`
