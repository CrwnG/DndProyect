"""
D&D 5e Advanced Enemy AI System.

Provides tactical decision-making for enemy combatants using
utility-based scoring to evaluate and select optimal actions.

Modules:
- targeting: Target evaluation and prioritization
- behaviors: Role-specific AI behaviors (Brute, Striker, Caster, etc.)
- coordination: Multi-enemy tactical coordination
- tactical_ai: Main AI decision framework
- environmental: Environmental hazard awareness
"""
from .targeting import TargetEvaluator, TargetPriority, TargetScore
from .environmental import (
    EnvironmentalAnalyzer,
    EnvironmentalHazard,
    HazardType,
    PushOpportunity,
    ElementalCombo,
    get_environmental_analyzer,
)
from .behaviors import (
    AIRole,
    AIDecision,
    BaseBehavior,
    MeleeBruteAI,
    RangedStrikerAI,
    SpellcasterAI,
    SupportAI,
    ControllerAI,
    SkirmisherAI,
    MinionAI,
    BossAI,
    get_behavior_for_role,
)
from .coordination import (
    CombatCoordinator,
    CoordinationStrategy,
    CoordinationPlan,
    TargetAssignment,
    coordinate_enemies,
)
from .tactical_ai import TacticalAI, get_ai_for_role, get_ai_for_combatant

__all__ = [
    # Targeting
    'TargetEvaluator',
    'TargetPriority',
    'TargetScore',
    # Environmental
    'EnvironmentalAnalyzer',
    'EnvironmentalHazard',
    'HazardType',
    'PushOpportunity',
    'ElementalCombo',
    'get_environmental_analyzer',
    # Behaviors
    'AIRole',
    'AIDecision',
    'BaseBehavior',
    'MeleeBruteAI',
    'RangedStrikerAI',
    'SpellcasterAI',
    'SupportAI',
    'ControllerAI',
    'SkirmisherAI',
    'MinionAI',
    'BossAI',
    'get_behavior_for_role',
    # Coordination
    'CombatCoordinator',
    'CoordinationStrategy',
    'CoordinationPlan',
    'TargetAssignment',
    'coordinate_enemies',
    # Main AI
    'TacticalAI',
    'get_ai_for_role',
    'get_ai_for_combatant',
]
