from sqlalchemy.orm import Session
from app.models.entities import Membership, ProviderConfig, Stage, Workspace

STAGES = [
    ("New Lead", "#94a3b8"),
    ("Contacted", "#3b82f6"),
    ("AI Qualifying", "#8b5cf6"),
    ("Qualified", "#22c55e"),
    ("Proposal", "#eab308"),
    ("Won", "#10b981"),
    ("Lost", "#ef4444"),
]


def create_workspace(db: Session, user_id: str, name: str) -> Workspace:
    workspace = Workspace(name=name)
    db.add(workspace)
    db.flush()
    db.add(Membership(workspace_id=workspace.id, user_id=user_id, role="admin"))
    for i, (label, color) in enumerate(STAGES):
        db.add(Stage(workspace_id=workspace.id, name=label, color=color, position=i))
    for provider in ("gemini", "nvidia"):
        db.add(ProviderConfig(workspace_id=workspace.id, provider=provider))
    db.flush()
    return workspace
