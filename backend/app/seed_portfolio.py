"""Explicit, repeat-safe fictional furnishing business. Never runs at startup."""

import argparse
import getpass
import os

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import passwords
from app.models.entities import KnowledgeText, Lead, Stage, User
from app.schemas.qualification import TemplateInput
from app.services.qualification import examples, save_template
from app.services.workspaces import create_workspace

POLICY = """Willow & Loom is a fictional furnishing studio for EasyCRM demonstrations.

We offer curtains, blinds and sofas in Bengaluru. Consultations are by appointment, Monday to Saturday, 10:00 to 18:00 IST.

Delivery takes 5 days after written order confirmation for the fictional demo catalogue. Custom orders require a written estimate from a salesperson.

The sample furnishing project minimum budget is INR 50,000. Exact prices, stock, warranty terms and discounts require a human quote. These are fictional policies, not real commercial offers.
"""


def seed(email, password):
    email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    if not 10 <= len(password) <= 128:
        raise SystemExit("Choose a demo password of 10–128 characters")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            print("Account already exists. Nothing was changed.")
            return
        user = User(name="Fictional Demo Admin", email=email, password_hash=passwords.hash(password))
        db.add(user)
        db.flush()
        workspace = create_workspace(db, user.id, "Willow & Loom · Fictional Demo")
        workspace.industry = "Furniture & furnishings"
        workspace.description = "Fictional Bengaluru furnishing studio. Service area: Bengaluru. Hours: Mon–Sat 10:00–18:00 IST. Sample data only; no connected external channels."
        db.add(
            KnowledgeText(
                workspace_id=workspace.id,
                title="Fictional catalogue & delivery policy",
                text=POLICY,
                approved=True,
            )
        )
        save_template(db, workspace.id, TemplateInput.model_validate(examples()["furniture"]))
        stage = db.scalar(select(Stage.id).where(Stage.workspace_id == workspace.id, Stage.position == 0))
        for i, (name, interest) in enumerate(
            [
                ("Asha Example", "Curtains for a fictional Bengaluru apartment"),
                ("Rohan Example", "Blinds for a fictional studio"),
                ("Maya Example", "A fictional sofa inquiry; warranty needs human review"),
            ],
            1,
        ):
            db.add(
                Lead(
                    workspace_id=workspace.id,
                    stage_id=stage,
                    name=name,
                    email=f"willow-demo-{i}@example.com",
                    source="manual",
                    summary=interest,
                    title=interest,
                )
            )
        db.commit()
        print(
            f"Created fictional furnishing workspace {workspace.id}: three new manual leads, approved sample policy and active furniture rubric. No model selected, no inference, no external sends."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="furnishing-demo@example.com")
    args = parser.parse_args()
    seed(args.email, os.environ.get("DEMO_PASSWORD") or getpass.getpass("Choose a fictional demo password: "))
