import re

from domain.outcomes import OUTCOME_TO_STATUS, ScoringOutcome
from domain.statuses import STATUS_VIEW, TRANSITIONS, ApplicationStatus
from tests.process_doc import (
    backticked,
    mermaid_block,
    read_process_md,
    section,
    table_rows,
)


def test_transitions_match_state_diagram() -> None:
    diagram = mermaid_block(read_process_md(), "stateDiagram-v2")
    documented = {
        (ApplicationStatus(src), ApplicationStatus(dst))
        for src, dst in re.findall(r"^\s*(\w+)\s*-->\s*(\w+)", diagram, re.M)
    }

    implemented = {
        (src, dst) for src, targets in TRANSITIONS.items() for dst in targets
    }

    assert implemented == documented


def test_final_states_match_state_diagram() -> None:
    diagram = mermaid_block(read_process_md(), "stateDiagram-v2")
    documented = {
        ApplicationStatus(s)
        for s in re.findall(r"^\s*(\w+)\s*-->\s*\[\*\]", diagram, re.M)
    }

    assert {s for s, targets in TRANSITIONS.items() if not targets} == documented


def test_outcome_mapping_matches_decision_table() -> None:
    rows = table_rows(section(read_process_md(), "5."))
    documented = {
        ScoringOutcome(backticked(row[0])[0]): ApplicationStatus(backticked(row[-1])[0])
        for row in rows[1:]
    }

    assert dict(OUTCOME_TO_STATUS) == documented


def test_status_view_matches_client_table() -> None:
    status_section = section(read_process_md(), "4.")
    table = status_section[status_section.index("Что видит клиент") :]
    rows = table_rows(table.split("\n\n", 2)[1])

    documented = {}
    for codes, title, next_action in rows[1:]:
        for code in backticked(codes):
            documented[ApplicationStatus(code)] = (
                title,
                None if next_action == "—" else next_action,
            )

    assert {
        code: (view.title, view.next_action) for code, view in STATUS_VIEW.items()
    } == documented
