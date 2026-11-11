from types import SimpleNamespace

import pytest

from app.services.state_machine import (
    FlowError,
    fire_client_quote,
    fire_contract,
    fire_milestone,
    fire_project,
    fire_proposal,
    fire_query_letter,
    fire_quote,
    fire_rfp,
)


def _project():
    return SimpleNamespace(phase=1, status="draft", archived=False)


def test_project_full_lifecycle():
    project = _project()

    fire_project(project, "task_map_generated")
    assert project.status == "diagnosing"

    fire_project(project, "requirement_generated")
    assert project.status == "requirement_pending"

    fire_project(project, "proposal_generated")
    assert (project.phase, project.status) == (2, "proposal_pending")

    fire_project(project, "proposal_confirmed")
    assert (project.phase, project.status) == (3, "service_selecting")

    fire_project(project, "client_quote_created")
    assert (project.phase, project.status) == (4, "quote_pending")

    fire_project(project, "client_quote_confirmed")
    assert project.status == "quote_confirmed"

    fire_project(project, "contract_generated")
    assert (project.phase, project.status) == (5, "contracting")

    fire_project(project, "contracts_activated")
    assert (project.phase, project.status) == (6, "executing")

    fire_project(project, "project_archived")
    assert (project.phase, project.status, project.archived) == (7, "closed", True)


def test_invalid_project_transition_is_rejected():
    project = _project()
    with pytest.raises(FlowError):
        fire_project(project, "proposal_confirmed")
    with pytest.raises(FlowError):
        fire_project(project, "project_archived")


def test_proposal_and_contract_transitions():
    proposal = SimpleNamespace(status="generated")
    fire_proposal(proposal, "review")
    fire_proposal(proposal, "send")
    fire_proposal(proposal, "confirm")
    assert proposal.status == "client_confirmed"

    contract = SimpleNamespace(status="draft")
    fire_contract(contract, "review")
    fire_contract(contract, "client_confirm")
    fire_contract(contract, "activate")
    assert contract.status == "active"

    with pytest.raises(FlowError):
        fire_contract(contract, "review")


def test_milestone_transitions():
    milestone = SimpleNamespace(status="pending_submission")
    fire_milestone(milestone, "submit")
    assert milestone.status == "submitted"

    fire_milestone(milestone, "pm_accept")
    fire_milestone(milestone, "expert_submitted")
    fire_milestone(milestone, "finalize", conclusion="passed")
    assert milestone.status == "passed"

    fire_milestone(milestone, "rectify")
    assert milestone.status == "pending_submission"


def test_rfp_quote_and_query_transitions():
    rfp = SimpleNamespace(status="draft")
    fire_rfp(rfp, "approve")
    fire_rfp(rfp, "send")
    fire_rfp(rfp, "reply")
    assert rfp.status == "replied"

    quote = SimpleNamespace(status="draft")
    fire_quote(quote)
    assert quote.status == "received"

    client_quote = SimpleNamespace(status="draft")
    fire_client_quote(client_quote, "send")
    fire_client_quote(client_quote, "confirm")
    assert client_quote.status == "confirmed"

    letter = SimpleNamespace(status="draft")
    fire_query_letter(letter, "send")
    fire_query_letter(letter, "reply")
    fire_query_letter(letter, "close")
    assert letter.status == "closed"
