"""Explicit, repeat-safe seed of fictional CRM records. Never called by application startup."""

import argparse
import getpass
import os
from datetime import timedelta
from decimal import Decimal

from pydantic import TypeAdapter, EmailStr
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import passwords
from app.models.entities import Lead, Stage, User, now
from app.services.workspaces import create_workspace

# Fictional opportunities. Source labels record provenance only; no integrations are connected.
RECORDS = [
    (
        "Olivia Chen",
        "Northstar Studio",
        0,
        12000,
        "website",
        "new",
        "Looking for a clearer way to manage a growing design team’s relationships.",
    ),
    (
        "Marcus Bennett",
        "Brightside Learning",
        0,
        8500,
        "referral",
        "new",
        "Exploring a shared CRM for their student enrollment team.",
    ),
    (
        "Priya Shah",
        "Solara Energy",
        0,
        15000,
        "email",
        "new",
        "Interested in a CRM for their B2B partner network.",
    ),
    (
        "James Wilson",
        "UrbanNest Realty",
        1,
        9200,
        "email",
        "new",
        "Discovery call complete. Interested in a product walkthrough.",
    ),
    (
        "Sofia Martinez",
        "Everwell Health",
        1,
        6800,
        "whatsapp",
        "qualifying",
        "Asked about team collaboration and flexible workflows.",
    ),
    (
        "Daniel Park",
        "Cloudline",
        1,
        18000,
        "linkedin",
        "new",
        "Shared a case study. Following up with their operations team.",
    ),
    (
        "Amara Okafor",
        "Bloom & Co.",
        2,
        14500,
        "website",
        "qualifying",
        "Learning more about their sales process and requirements.",
    ),
    (
        "Ethan Brooks",
        "Atlas Works",
        2,
        11000,
        "referral",
        "qualifying",
        "Reviewing team size, timeline, and the existing workflow.",
    ),
    (
        "Isabel Costa",
        "Finch Financial",
        3,
        25000,
        "email",
        "qualified",
        "Budget confirmed. Evaluating the implementation timeline.",
    ),
    (
        "Noah Taylor",
        "Retail Collective",
        3,
        18000,
        "whatsapp",
        "qualified",
        "Key stakeholders are aligned. Requested a proposal.",
    ),
    (
        "Mei Tan",
        "Waypoint Logistics",
        3,
        32000,
        "website",
        "qualified",
        "Strong fit. Final security review before next steps.",
    ),
    (
        "Arjun Mehta",
        "HealthSync",
        4,
        21000,
        "email",
        "qualified",
        "Proposal shared on Monday. Reviewing feedback next week.",
    ),
    (
        "Emma Laurent",
        "GrowMatter",
        4,
        14500,
        "meta",
        "qualified",
        "Custom proposal in review with the business owner.",
    ),
    (
        "Leo Anderson",
        "EduPrime",
        4,
        27000,
        "whatsapp",
        "qualified",
        "Technical team reviewing the implementation plan.",
    ),
    (
        "Zara Ahmed",
        "Kindred Spaces",
        5,
        24000,
        "referral",
        "closed",
        "A new partnership. Getting their team ready for onboarding.",
    ),
    (
        "Lucas Silva",
        "Fieldwork",
        5,
        18000,
        "website",
        "closed",
        "Signed and ready to build more meaningful relationships.",
    ),
    (
        "Ava Thompson",
        "Oak & Avenue",
        6,
        7000,
        "manual",
        "disqualified",
        "Timing isn’t quite right. Closed for now.",
    ),
]


def seed(email: str, password: str):
    if len(password) < 10 or len(password) > 128:
        raise SystemExit("Demo password must contain 10–128 characters.")
    email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            print("Account already exists. Nothing was changed.")
            return
        user = User(name="Alex Morgan", email=email, password_hash=passwords.hash(password))
        db.add(user)
        db.flush()
        workspace = create_workspace(db, user.id, "Acme Studio · Demo")
        workspace.industry = "Software & technology"
        workspace.description = "A fictional workspace for exploring EasyCRM. All records are demo data."
        stages = db.scalars(
            select(Stage).where(Stage.workspace_id == workspace.id).order_by(Stage.position)
        ).all()
        for i, (name, company, position, value, source, status, summary) in enumerate(RECORDS):
            timestamp = now() - timedelta(hours=i * 5 + 1)
            db.add(
                Lead(
                    workspace_id=workspace.id,
                    stage_id=stages[position].id,
                    name=name,
                    company=company,
                    email=f"contact{i + 1}@example.com",
                    value=Decimal(value),
                    source=source,
                    status=status,
                    summary=summary,
                    title=f"{company} team workspace",
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        db.commit()
        print(
            "Created a fictional demo workspace with 17 leads. Sign in using the email/password you supplied."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="demo@example.com")
    args = parser.parse_args()
    seed(
        args.email,
        os.environ.get("DEMO_PASSWORD") or getpass.getpass("Choose a demo password (10+ characters): "),
    )
