"""Create the (single) app user directly in the database.

There is no self-service registration endpoint - see the comment at the top
of app/api/v1/endpoints/auth.py for why. This is the replacement: run it
once, locally or via CI, against whichever DATABASE_URL is currently
configured (a real Neon connection string in production).

    python -m scripts.create_user --username you --full-name "Your Name" \\
        --email you@example.com

Prompts for a password interactively rather than taking it as an argument,
so it never ends up in shell history.
"""

import argparse
import getpass

from app.database.session import SessionLocal
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate
from app.services.user_service import UserService, UserServiceError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords did not match.")

    db = SessionLocal()
    try:
        service = UserService(UserRepository(db))
        user = service.create_user(
            UserCreate(
                username=args.username,
                full_name=args.full_name,
                email=args.email,
                password=password,
            )
        )
        print(f"Created user {user.username!r} (id={user.id}).")
    except UserServiceError as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        db.close()


if __name__ == "__main__":
    main()
