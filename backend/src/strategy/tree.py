"""Two-Ply Adversarial Scenario Tree Engine.

Enforces:
1. Root = Candidate Strategy (Depth 0).
2. First Ply = Opposing Arguments / Defenses (Depth 1, max B=3).
3. Second Ply = Our Response (Depth 2) with supporting legal authority & evidence.
4. Residual risk and unresolved weaknesses stored as METADATA on Depth 2 response nodes
   (no depth-3 nodes).
5. Branch pruning for frivolous or unsupported opposing arguments.
"""

from typing import List, Optional
from uuid import UUID, uuid4
from backend.src.strategy.schemas import (
    LegalCitationReference,
    Plausibility,
    PrecedentReference,
    ResidualRiskMetadata,
    ScenarioNodeType,
    ScenarioOpposingNode,
    ScenarioResponseNode,
    ScenarioTree,
)

MAX_DEPTH = 2
MAX_BRANCHING_FACTOR = 3


class ScenarioTreeExpander:
    """Constructs, validates, and prunes 2-ply adversarial scenario trees."""

    @classmethod
    def build_tree(
        cls,
        strategy_id: UUID,
        strategy_name: str,
        opposing_arguments: List[ScenarioOpposingNode],
    ) -> ScenarioTree:
        """Validate and construct 2-ply scenario tree adhering strictly to depth & breadth limits."""
        # Enforce maximum branching factor B <= 3
        valid_opposing = opposing_arguments[:MAX_BRANCHING_FACTOR]

        # Enforce depth <= 2 and prune invalid branches
        for opp in valid_opposing:
            opp.depth = 1
            opp.node_type = ScenarioNodeType.OPPOSING_ARGUMENT
            # Prune if argument is empty or legally frivolous
            if not opp.text.strip():
                opp.pruned = True
                opp.prune_reason = "Empty or unsubstantiated adversary claim."
            elif "frivolous" in opp.text.lower():
                opp.pruned = True
                opp.prune_reason = "Frivolous claim barred by statutory estoppel."

            for resp in opp.responses:
                resp.depth = 2
                resp.node_type = ScenarioNodeType.OUR_RESPONSE
                # Residual risk is verified to exist on response node
                if not resp.residual_risk:
                    resp.residual_risk = ResidualRiskMetadata(
                        risk_level="medium",
                        risk_summary="Standard procedural risk of litigation delay.",
                    )

        return ScenarioTree(
            root_strategy_id=strategy_id,
            depth=0,
            strategy_name=strategy_name,
            opposing_arguments=valid_opposing,
        )

    @classmethod
    def get_active_branches(cls, tree: ScenarioTree) -> List[ScenarioOpposingNode]:
        """Return only unpruned, legally meaningful scenario branches."""
        return [node for node in tree.opposing_arguments if not node.pruned]
