from __future__ import annotations

import sys
from pathlib import Path

from sqlmodel import Session, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import engine  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.models import User  # noqa: E402


PASSWORD = "PdecrPeople123!"

PEOPLE = [
    {
        "email": "pdecr.manager@example.com",
        "full_name": "PD-ECR Test Manager",
        "display_name": "Test Manager",
        "department": "pm",
        "pd_ecr_role": "pd_ecr_manager",
        "is_superuser": True,
    },
    {
        "email": "design.leader@example.com",
        "full_name": "Design Department Leader",
        "display_name": "Design Leader",
        "department": "design",
        "pd_ecr_role": "department_leader",
        "is_superuser": False,
    },
    {
        "email": "design.engineer@example.com",
        "full_name": "Design Engineer",
        "display_name": "Design Engineer",
        "department": "design",
        "pd_ecr_role": "department_member",
        "is_superuser": False,
    },
    {
        "email": "system.leader@example.com",
        "full_name": "System Department Leader",
        "display_name": "System Leader",
        "department": "system",
        "pd_ecr_role": "department_leader",
        "is_superuser": False,
    },
    {
        "email": "system.engineer@example.com",
        "full_name": "System Engineer",
        "display_name": "System Engineer",
        "department": "system",
        "pd_ecr_role": "department_member",
        "is_superuser": False,
    },
    {
        "email": "purchasing.leader@example.com",
        "full_name": "Purchasing Department Leader",
        "display_name": "Purchasing Leader",
        "department": "purchasing",
        "pd_ecr_role": "department_leader",
        "is_superuser": False,
    },
    {
        "email": "purchasing.buyer@example.com",
        "full_name": "Purchasing Buyer",
        "display_name": "Purchasing Buyer",
        "department": "purchasing",
        "pd_ecr_role": "department_member",
        "is_superuser": False,
    },
    {
        "email": "manufacturing.leader@example.com",
        "full_name": "Manufacturing Department Leader",
        "display_name": "Manufacturing Leader",
        "department": "manufacturing",
        "pd_ecr_role": "department_leader",
        "is_superuser": False,
    },
    {
        "email": "manufacturing.engineer@example.com",
        "full_name": "Manufacturing Engineer",
        "display_name": "Manufacturing Engineer",
        "department": "manufacturing",
        "pd_ecr_role": "department_member",
        "is_superuser": False,
    },
    {
        "email": "quality.leader@example.com",
        "full_name": "Quality Department Leader",
        "display_name": "Quality Leader",
        "department": "quality",
        "pd_ecr_role": "department_leader",
        "is_superuser": False,
    },
    {
        "email": "quality.engineer@example.com",
        "full_name": "Quality Engineer",
        "display_name": "Quality Engineer",
        "department": "quality",
        "pd_ecr_role": "department_member",
        "is_superuser": False,
    },
    {
        "email": "catalyst.leader@example.com",
        "full_name": "Catalyst Department Leader",
        "display_name": "Catalyst Leader",
        "department": "catalyst",
        "pd_ecr_role": "department_leader",
        "is_superuser": False,
    },
    {
        "email": "catalyst.engineer@example.com",
        "full_name": "Catalyst Engineer",
        "display_name": "Catalyst Engineer",
        "department": "catalyst",
        "pd_ecr_role": "department_member",
        "is_superuser": False,
    },
    {
        "email": "pdecr.reviewer@example.com",
        "full_name": "PD-ECR Reviewer",
        "display_name": "Reviewer",
        "department": "quality",
        "pd_ecr_role": "reviewer",
        "is_superuser": False,
    },
]


def upsert_person(session: Session, profile: dict[str, object]) -> User:
    user = session.exec(select(User).where(User.email == str(profile["email"]))).first()
    if user is None:
        user = User(
            email=str(profile["email"]),
            hashed_password=get_password_hash(PASSWORD),
        )

    user.full_name = str(profile["full_name"])
    user.display_name = str(profile["display_name"])
    user.department = str(profile["department"])
    user.pd_ecr_role = str(profile["pd_ecr_role"])
    user.is_superuser = bool(profile["is_superuser"])
    user.is_active = True
    user.auth_provider = "local"
    user.hashed_password = get_password_hash(PASSWORD)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def main() -> None:
    with Session(engine) as session:
        users = [upsert_person(session, profile) for profile in PEOPLE]

    print(f"Seeded {len(users)} people")
    print(f"Password for all seeded users: {PASSWORD}")
    print("")
    print("Suggested login accounts:")
    for profile in PEOPLE:
        print(
            "  "
            f"{profile['email']} | {profile['department']} | {profile['pd_ecr_role']}"
        )


if __name__ == "__main__":
    main()