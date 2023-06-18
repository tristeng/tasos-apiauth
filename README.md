# Tasos API Authentication Library
![python package](https://github.com/tristeng/tasos-apiauth/actions/workflows/python-package.yml/badge.svg)  

A re-usable library that implements authentication, users, groups and permission handling for FastAPI. This library
is meant to allow a FastAPI developer to get up and running quickly with functions to register, authenticate and manage
groups and permissions for a new web application. It currently supports JSON Web Tokens (JWT) for authentication and 
depends on [SqlAlchemy](https://www.sqlalchemy.org/) for database management and access. This library is written using 
asyncio.

**NOTE: This is a work in progress and is not ready for production use.**

## Installation
Coming soon...

## Quick Start
Pre-requisites:
- Python 3.11+
- [Poetry](https://python-poetry.org/) for package management
- [Alembic](https://alembic.sqlalchemy.org/en/latest/) for database migrations
- [aiosqlite](https://aiosqlite.omnilib.dev/en/stable/) or your async database of choice (any SQLAlchemy supported 
database should work)
- [Uvicorn](https://www.uvicorn.org/) for running the app

To try this library out in its current state, clone the repository locally and use [Poetry](https://python-poetry.org/)
to install the project as a dependency in your own project, e.g. if you clone the repository adjacent to your project, 
you can run the following:
```bash
poetry add ../tasos-apiauth/
```

Also install the other dependencies:
```bash
poetry add uvicorn aiosqlite alembic
```

Create a .env file in the root of your project and fill in the values (or set them in your environment):
```dotenv
APIAUTH_SECRET_KEY=***REDACTED***
APIAUTH_ALGORITHM=HS256
APIAUTH_ACCESS_TOKEN_EXPIRE_MINUTES=15
APIAUTH_DATABASE_URL=sqlite+aiosqlite:///./demo.db?check_same_thread=false
```

You can generate your secret key with the following command:
```bash
generate with openssl rand -hex 32
```
or
```bash
python -c 'import secrets; print(secrets.token_hex(32))'
```

Initialize alembic for asyncio:
```bash
alembic init -t async alembic
```

Edit the `alembic.ini` file and set the `sqlalchemy.url` to the same value as `APIAUTH_DATABASE_URL` in your .env file. 

Edit the `alembic/env.py` file and add the following (and as you develop your app, add any other models you create)):
```python
from tasos.apiauth.model import Base

target_metadata = Base.metadata
```

and run the migrations:
```bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

Create an admin user for yourself with the included CLI, and follow the prompts to choose a password:
```bash
python -m tasos.apiauth.utils newuser you@website.com --admin
```

Create a main.py file in the root of your project and add the following:
```python
from tasos.apiauth.api import app

# modify the app as needed, adding new endpoints, adding startup and shutdown events, etc.
```

Run the app:
```bash
uvicorn main:app --reload
```

You should now be able to navigate to http://localhost:8000/docs to see the Swagger UI and use its interactive features
to interact with the API. You can also navigate to http://localhost:8000/redoc to see the ReDoc UI.
