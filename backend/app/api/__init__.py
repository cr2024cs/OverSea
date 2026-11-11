import hashlib

from flask import Blueprint, jsonify, request

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.before_request
def _reject_writes_on_archived_project():
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return None

    from app.extensions import db
    from app.models import (
        AccessToken,
        Candidate,
        ClientQuote,
        Contract,
        Milestone,
        Project,
        Proposal,
        QueryLetter,
        Quote,
        RFP,
    )

    args = request.view_args or {}
    project_id = args.get("project_id")

    if not project_id and args.get("token"):
        token = args["token"]
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        access = AccessToken.query.filter_by(token=digest).first()
        if access is not None:
            project_id = access.project_id
        else:
            rfp = RFP.query.filter_by(token=token).first()
            if rfp is not None:
                project_id = rfp.project_id

    if not project_id:
        mapping = {
            "milestone_id": Milestone,
            "contract_id": Contract,
            "proposal_id": Proposal,
            "rfp_id": RFP,
            "candidate_id": Candidate,
            "client_quote_id": ClientQuote,
            "letter_id": QueryLetter,
        }
        for key, model in mapping.items():
            object_id = args.get(key)
            if not object_id:
                continue
            row = db.session.get(model, object_id)
            if row is not None:
                project_id = row.project_id
                break

    if not project_id and args.get("quote_id"):
        quote = db.session.get(Quote, args["quote_id"])
        if quote is not None:
            rfp = db.session.get(RFP, quote.rfp_id)
            if rfp is not None:
                project_id = rfp.project_id

    if not project_id:
        return None

    project = db.session.get(Project, project_id)
    if project is not None and project.archived:
        return (
            jsonify(
                {
                    "code": "project_archived",
                    "message": "项目已归档，只允许查看",
                }
            ),
            409,
        )
    return None


from app.api import (  # noqa: E402,F401
    admin,
    archives,
    auth,
    chat,
    client_portal,
    config,
    contracts,
    delivery,
    diagnosis,
    documents,
    experts,
    health,
    knowledge,
    lawyer,
    link,
    procurement,
    projects,
    proposals,
    provider,
    queries,
    questionnaire,
    sourcing,
    tokens,
)
