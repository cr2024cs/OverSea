INTERNAL_ROLES = {"pm", "lawyer", "admin"}
EDIT_QUOTE_ROLES = {"pm", "admin"}
APPROVER_ROLE = "lawyer"


def is_internal(user):
    return bool(user and user.active and user.role in INTERNAL_ROLES)


def can_access_project(user, project):
    if project is None:
        return False
    if is_internal(user):
        return True
    if not user or not user.active or user.role != "client":
        return False
    return project.client_user_id == user.id


def can_edit_quote(user):
    return bool(user and user.active and user.role in EDIT_QUOTE_ROLES)


def can_approve_query_letter(user):
    return bool(user and user.active and user.role == APPROVER_ROLE)


def ensure_project_scope(token_row, project_id):
    if not token_row.project_id or token_row.project_id != project_id:
        raise PermissionError("token_scope_mismatch")
