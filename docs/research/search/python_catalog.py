"""Graft navigation adapter for the framework research catalog.

This file is inert development documentation. It is not installed or imported
by agent-topology. The canonical structured evidence is in ``../catalog.yaml``
and the explanatory evidence is in the framework version dossiers.

Graft 0.16 indexes supported code files, not Markdown or YAML. These typed
records expose the catalog's stable vocabulary to graft without duplicating its
URLs, commits, or detailed findings.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchSurface:
    """A searchable pointer from a framework concept to canonical evidence."""

    framework: str
    implementation_language: str
    version: str
    concept: str
    upstream_symbol: str
    evidence_state: str
    catalog_key: str
    research_question: str


def langgraph_1_2_11_compiled_builder() -> ResearchSurface:
    """Point to evidence that CompiledStateGraph retains its StateGraph builder."""
    return ResearchSurface(
        framework="langgraph",
        implementation_language="python",
        version="1.2.11",
        concept="compiled builder",
        upstream_symbol="langgraph.graph.state.CompiledStateGraph.builder",
        evidence_state="verified",
        catalog_key=(
            "frameworks.langgraph.implementations.python.releases.1.2.11."
            "topologySurfaces.compiledBuilder"
        ),
        research_question="Which exact versions passed the compatibility matrix?",
    )


def langgraph_1_2_11_nodes_and_edges() -> ResearchSurface:
    """Point to evidence for StateGraph nodes and ordinary directed edges."""
    return ResearchSurface(
        framework="langgraph",
        implementation_language="python",
        version="1.2.11",
        concept="nodes and ordinary directed edges",
        upstream_symbol="langgraph.graph.state.StateGraph",
        evidence_state="verified",
        catalog_key=(
            "frameworks.langgraph.implementations.python.releases.1.2.11."
            "topologySurfaces.nodesAndOrdinaryEdges"
        ),
        research_question="How do builder declarations compare with drawable output?",
    )


def langgraph_1_2_11_multi_source_edges() -> ResearchSurface:
    """Point to evidence for multi-source joins stored as waiting_edges."""
    return ResearchSurface(
        framework="langgraph",
        implementation_language="python",
        version="1.2.11",
        concept="multi-source join waiting edge",
        upstream_symbol="langgraph.graph.state.StateGraph.waiting_edges",
        evidence_state="verified",
        catalog_key=(
            "frameworks.langgraph.implementations.python.releases.1.2.11."
            "topologySurfaces.multiSourceEdges"
        ),
        research_question="How is a join kept distinct from independent edges?",
    )


def langgraph_1_2_11_conditional_edges() -> ResearchSurface:
    """Point to evidence for conditional branches and unknown destinations."""
    return ResearchSurface(
        framework="langgraph",
        implementation_language="python",
        version="1.2.11",
        concept="conditional branch and unknown routing destinations",
        upstream_symbol="langgraph.graph.state.StateGraph.add_conditional_edges",
        evidence_state="verified",
        catalog_key=(
            "frameworks.langgraph.implementations.python.releases.1.2.11."
            "topologySurfaces.conditionalEdges"
        ),
        research_question="How are undeclared destinations preserved as a gap?",
    )


def langgraph_1_2_11_drawable_graph() -> ResearchSurface:
    """Point to evidence for public drawable graph extraction via get_graph."""
    return ResearchSurface(
        framework="langgraph",
        implementation_language="python",
        version="1.2.11",
        concept="drawable computation graph",
        upstream_symbol="langgraph.pregel.main.Pregel.get_graph",
        evidence_state="verified",
        catalog_key=(
            "frameworks.langgraph.implementations.python.releases.1.2.11."
            "topologySurfaces.drawableGraph"
        ),
        research_question=(
            "Which execution semantics does the drawable graph normalise or lose?"
        ),
    )


def langgraph_1_2_11_subgraphs() -> ResearchSurface:
    """Point to evidence for immediate and recursive subgraph enumeration."""
    return ResearchSurface(
        framework="langgraph",
        implementation_language="python",
        version="1.2.11",
        concept="nested subgraph enumeration",
        upstream_symbol="langgraph.pregel.main.Pregel.get_subgraphs",
        evidence_state="verified",
        catalog_key=(
            "frameworks.langgraph.implementations.python.releases.1.2.11."
            "topologySurfaces.subgraphs"
        ),
        research_question="What remains observable at each requested depth?",
    )


def langgraph_1_2_11_interrupts() -> ResearchSurface:
    """Point to evidence for static interrupt-before and interrupt-after nodes."""
    return ResearchSurface(
        framework="langgraph",
        implementation_language="python",
        version="1.2.11",
        concept="static interrupt before and interrupt after nodes",
        upstream_symbol="langgraph.graph.state.StateGraph.compile",
        evidence_state="verified",
        catalog_key=(
            "frameworks.langgraph.implementations.python.releases.1.2.11."
            "topologySurfaces.interrupts"
        ),
        research_question="Which static interrupt declarations remain observable?",
    )


LANGGRAPH_1_2_11_SURFACES = (
    langgraph_1_2_11_compiled_builder(),
    langgraph_1_2_11_nodes_and_edges(),
    langgraph_1_2_11_multi_source_edges(),
    langgraph_1_2_11_conditional_edges(),
    langgraph_1_2_11_drawable_graph(),
    langgraph_1_2_11_subgraphs(),
    langgraph_1_2_11_interrupts(),
)
