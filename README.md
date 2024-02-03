# Tasos API Authentication Library
![python package](https://github.com/tristeng/tasos-apiauth/actions/workflows/python-package.yml/badge.svg)  

A re-usable library that implements authentication, users, groups and permission handling for FastAPI. This library
is meant to allow a FastAPI developer to get up and running quickly with functions to register, authenticate and manage
groups and permissions for a new web application. It currently supports JSON Web Tokens (JWT) for authentication and 
depends on [SqlAlchemy](https://www.sqlalchemy.org/) for database management and access. This library is written using 
asyncio.

**NOTE: This is a work in progress and is not ready for production use.**

## Motivation
I wanted to create a library that would allow me to quickly setup authentication and authorization for a new web 
application. I also wanted to test out [GitHub Copilot](https://github.com/features/copilot) - this code and portions of
the README were generated with Copilot's AI assistance.

## Installation
The latest stable version can be found on pypi.org and can be installed with the package manager of your choice, e.g.
for Poetry:
```shell
poetry add tasos-apiauth
```

## Quick Start
Pre-requisites:
- Python 3.11+
- [Poetry](https://python-poetry.org/) for package management
- [Alembic](https://alembic.sqlalchemy.org/en/latest/) for database migrations
- [aiosqlite](https://aiosqlite.omnilib.dev/en/stable/) or your async database of choice (any SQLAlchemy supported 
database should work)
- [Uvicorn](https://www.uvicorn.org/) for running the app

To try this library out in its current state, use [Poetry](https://python-poetry.org/) to install the project as a 
dependency in your own project, e.g. you can run the following:
```bash
poetry add https://github.com/tristeng/tasos-apiauth.git
```

Create a .env file in the root of your project and fill in the values (or set them in your environment):
```dotenv
APIAUTH_SECRET_KEY=***REDACTED***
APIAUTH_ALGORITHM=HS256
APIAUTH_ACCESS_TOKEN_EXPIRE_MINUTES=15
APIAUTH_DATABASE_URL=sqlite+aiosqlite:///./demo.db?check_same_thread=false
```

See `tasos/apiauth/config.py` for more configuration options and their defaults.

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
python -m tasos.apiauth.cli newuser you@website.com --admin
```

Create a main.py file in the root of your project and create your FastAPI app:
```python
from fastapi import FastAPI
from tasos.apiauth.api import add_all_endpoints_to_app

# create your app as you like
app = FastAPI()

# add the endpoints to your app using the default URLs
add_all_endpoints_to_app(app)
```

If you only want to add select endpoints with custom base URLs:
```python
from fastapi import FastAPI

from tasos.apiauth.api import add_base_endpoints_to_app, add_user_endpoints_to_app, add_group_endpoints_to_app, \
    add_permission_endpoints_to_app

# create your app as you like
app = FastAPI()

# add only the endpoints you want at the paths you desire (path is optional and defaults to /api/auth)
add_base_endpoints_to_app(app, path="/api/auth")
add_user_endpoints_to_app(app, path="/api/users")
add_group_endpoints_to_app(app, path="/api/groups")
add_permission_endpoints_to_app(app, path="/api/permissions")

# you could also add all of them at the default paths
# add_all_endpoints_to_app(app)
```

Run the app in development mode:
```bash
uvicorn main:app --reload
```

You should now be able to navigate to http://localhost:8000/docs to see the Swagger UI and use its interactive features
to interact with the API. You can also navigate to http://localhost:8000/redoc to see the ReDoc UI.

### Custom Registration Functions
If you want to customize the registration process, you can create your own registration functions by appending them to
the post registration hooks list. Define your function(s) to accept a database session and user object. For example:
```python
from tasos.apiauth.model import UserOrm
from tasos.apiauth.api.base import post_registration_hooks
from sqlalchemy.ext.asyncio import AsyncSession


async def send_registration_email_hook(db: AsyncSession, user: UserOrm) -> None:
    # for example, save a registration code to the database and send an email to the user with a link to confirm their
    # email address
    pass

post_registration_hooks.append(send_registration_email_hook)
```

### Permissions
To implement permissions, you will first need to create a StrEnum class that defines the permissions you want to use,
for example:
```python
from enum import StrEnum

class MyCustomPermissions(StrEnum):
    read = "read"
    write = "write"
    delete = "delete"
```

**NOTE: We use a string enum instead of strings to avoid typos.**

At this point, you'll need to create an alembic changeset to add the permissions to the database. You can do this by:
```bash
alembic revision --autogenerate -m "Add my custom permissions"
```

Edit the generated migration file and add the following:
```python
from alembic import op
from tasos.apiauth.model import PermissionOrm
from wherever import MyCustomPermissions

def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.bulk_insert(PermissionOrm.__table__, [{"name": perm} for perm in MyCustomPermissions])
    # ### end Alembic commands ###
```

Run the migration:
```bash
alembic upgrade head
```

As you add more permissions, you can repeat this process - you can use the same enumeration class or create a new one.

Now you can use the `UserHasAllPermissions` or `UserHasAnyPermission` dependency to check if a user has the permissions 
you want. For example:

```python
from fastapi import Depends, FastAPI
from tasos.apiauth.helpers import UserHasAllPermissions, UserHasAnyPermission
from tasos.apiauth.api import add_all_endpoints_to_app
from wherever import MyCustomPermissions

# create your app as you like
app = FastAPI()

# add the endpoints to your app using the default URLs
add_all_endpoints_to_app(app)

# you can add as many or as few permissions as you want using the list arguments
perm_checker_all = UserHasAllPermissions(MyCustomPermissions.read, MyCustomPermissions.write)
perm_checker_any = UserHasAnyPermission(MyCustomPermissions.read, MyCustomPermissions.write)


# now inject the dependency into your routes
@app.get("/some/endpoint", dependencies=[Depends(perm_checker_all)])  # user must have both read and write permissions
async def some_endpoint1() -> dict[str, str]:
    return {"works": "wooo!"}


# user must have either read or write permission
@app.get("/some/other/endpoint", dependencies=[Depends(perm_checker_any)])  
async def some_other_endpoint1() -> dict[str, str]:
    return {"works": "wooo!"}
```

If the user doesn't have _ALL_ of the permissions you specified, they will get a 403 Forbidden response.

## Development
To develop this library, clone the repo and install the dependencies with Poetry:
```bash
poetry install
```

### Testing
The tests are separated into unit and integration tests. The unit tests are run against a mocked database and the 
integration tests are run against a real database (SQLite). The integration tests are slower and the unit test mocking
can interfere with the integration tests, so they are separated. The integration tests are marked with the 
`@pytest.mark.integration` decorator and can be run separately from the unit tests.

To run the unit tests:
```bash
poetry run pytest -m "not integration"
```

To run the integration tests:
```bash
poetry run pytest -m "integration"
```
