"""Tests for 2-Ply Adversarial Scenario Tree, Depth/Breadth Limits, and Pruning. Strategy fixtures are SAMPLE_DATA_NOT_REAL_LAW."""

from uuid import uuid4
from backend.src.strategy.schemas import (
    Plausibility,
    ResidualRiskMetadata,
    ScenarioNodeType,
    ScenarioOpposingNode,
    ScenarioResponseNode,
)
from backend.src.strategy.tree import ScenarioTreeExpander


def test_scenario_tree_depth_and_breadth_limits():
    strat_id = uuid4()

    # Create 5 opposing arguments (exceeding B=3)
    opp_nodes = []
    for i in range(5):
        opp_nodes.append(
            ScenarioOpposingNode(
                id=uuid4(),
                parent_id=strat_id,
                depth=1,
                text=f"Adversary defense claim #{i + 1}",
                legal_ground="Allegation of procedural irregularity",
                plausibility=Plausibility.POSSIBLE,
                responses=[
                    ScenarioResponseNode(
                        id=uuid4(),
                        parent_id=strat_id,
                        depth=2,
                        text=f"Our verified statutory rebuttal #{i + 1}",
                        residual_risk=ResidualRiskMetadata(
                            risk_level="low",
                            risk_summary="Manageable cross-examination risk",
                        ),
                    )
                ],
            )
        )

    tree = ScenarioTreeExpander.build_tree(
        strategy_id=strat_id,
        strategy_name="NI Act Section 138 Proceeding",
        opposing_arguments=opp_nodes,
    )

    # 1. Breadth limit: Maximum B=3 opposing arguments allowed
    assert len(tree.opposing_arguments) == 3

    # 2. Depth limit: Root is 0, opposing is 1, response is 2
    for opp in tree.opposing_arguments:
        assert opp.depth == 1
        assert opp.node_type == ScenarioNodeType.OPPOSING_ARGUMENT
        for resp in opp.responses:
            assert resp.depth == 2
            assert resp.node_type == ScenarioNodeType.OUR_RESPONSE
            # 3. Residual risk is metadata on Depth 2 response, NOT a depth 3 node
            assert resp.residual_risk.risk_level == "low"
            assert resp.residual_risk.risk_summary == "Manageable cross-examination risk"


def test_scenario_branch_pruning():
    strat_id = uuid4()
    opp_nodes = [
        ScenarioOpposingNode(
            id=uuid4(),
            parent_id=strat_id,
            depth=1,
            text="Legally sound opposing defense based on limitation expiry",
            legal_ground="Limitation Act Section 3",
            responses=[],
        ),
        ScenarioOpposingNode(
            id=uuid4(),
            parent_id=strat_id,
            depth=1,
            text="Frivolous and baseless delaying motion",
            legal_ground="No ground",
            responses=[],
        ),
        ScenarioOpposingNode(
            id=uuid4(),
            parent_id=strat_id,
            depth=1,
            text="",  # Empty
            legal_ground="",
            responses=[],
        ),
    ]

    tree = ScenarioTreeExpander.build_tree(
        strategy_id=strat_id,
        strategy_name="Test Strategy",
        opposing_arguments=opp_nodes,
    )

    active_branches = ScenarioTreeExpander.get_active_branches(tree)
    assert len(active_branches) == 1
    assert active_branches[0].text == "Legally sound opposing defense based on limitation expiry"

    # Check that invalid branches are marked pruned with reasons
    pruned_nodes = [node for node in tree.opposing_arguments if node.pruned]
    assert len(pruned_nodes) == 2
    assert any("frivolous" in (p.prune_reason or "").lower() for p in pruned_nodes)
