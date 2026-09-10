# 0006. Repository layout and language boundaries

- Status: Accepted
- Date: 2026-09-10

## Context

A producer reads a compiled graph object through its runtime attributes, so it has to run in the same process as the graph. That makes the producer's language a consequence of the target framework rather than a choice. A Python framework needs a Python producer; a JavaScript one needs a JavaScript producer. The same constraint does not apply anywhere else: the document is JSON, so consumers and fixtures are free of it.

Supporting both Python and TypeScript therefore means three different things with three different costs. Reading the document from either language is already free. Building a consumer in TypeScript is cheap and independent of the producer. Building a second producer is the expensive one, and it is the only one that adds a language to the maintained surface.

Investigation of LangGraph.js confirmed the introspection path exists and maps closely onto the Python one: builder access, branch records, edge and node collections, and static interrupt configuration all have counterparts, including the same wildcard value that needs normalising. So a TypeScript producer is feasible. It is not, however, a test of anything structural. Both runtimes share the same model of a graph, so agreement between them says the extraction is language-independent, not that the core is framework-independent. That is a weaker claim than the one ADR 0005 is waiting for.

One asymmetry did surface. The two runtimes declare a router's possible destinations differently: one through a type annotation, the other through an option passed when the node is added. The concept is the same and the mechanism is not.

## Decision

**One repository, independently versioned packages.** The format, its fixtures, and each producer or consumer are separate packages released on their own cadence. The format version, the hash algorithm version from ADR 0003, and any package version are distinct axes and are never collapsed into a single release number.

**Fixtures carry the discipline that ADR 0005 assigned to repository separation.** A language-neutral package holds the schema and the fixtures, and every producer runner is checked against the same ones. This constrains a producer more tightly than a repository boundary would, because it applies on every commit rather than only when someone crosses a directory.

**Producers are named for the framework they read, not the language they are written in.** The language follows from the framework, so it cannot be the discriminator. A future producer for a different framework that happens to be written in Python would otherwise collide with the existing one.

**Names are explicit where they are read and short where they are typed.** The project name is used unabbreviated for anything published or imported. Each ecosystem supplies its own namespace: a scope on one side, a namespace package on the other, so the two end up structurally parallel even though only one registry has scopes and the other has a single flat name space. Distribution names may be longer than import paths; a distribution name is typed once at install time, while an import path is read every day.

The short form is reserved for the command-line entry point, where brevity is paid for on every invocation. This also makes it the cheapest name to change: an alias can be added or retired without affecting anything published.

**Python first, TypeScript afterwards.** The Python producer is completed and stabilised under ADR 0001 before a second is started. A TypeScript producer is an extension of a working design, not a parallel effort.

**Shared format, idiomatic APIs.** Producers agree on the document they emit and on the fixtures they pass. They do not agree on method signatures. The JavaScript graph representation is moving to an asynchronous accessor, so forcing a common shape would make one side unnatural to no benefit.

**The router-destination asymmetry is resolved in favour of the concept.** The document records the declared destinations of a routing node. How they were declared is framework-specific detail and belongs in the extension area.

## Consequences

- Toolchains and continuous integration must cover two ecosystems once the second producer exists. This is a real cost against keeping the project small, and it is deferred rather than accepted now.
- A consumer written in TypeScript can be built at any time without waiting for a TypeScript producer, and demonstrates the format crossing a language boundary more cheaply than a second producer would.
- Adding a producer means adding a package and a runner, not restructuring anything. A third party can do the same outside this repository.
- The naming split means the command name and the package names can diverge in documentation. The expansion is stated once where a reader first meets the short form, so the two are never presented as unrelated.
- The router-destination handling gives an early, small instance of the exercise ADR 0005 describes: a concept had to be separated from one framework's way of expressing it. It does not satisfy that decision's revisit condition.

## What we are explicitly not doing

- **Releasing the repository as a unit.** A single version number would tie the format to a producer, which is the coupling ADR 0003 already rejected at the level of the hash.
- **Building the TypeScript producer now.** It is out of scope under ADR 0001 and does not advance ADR 0005. The layout leaves room for it; nothing more.
- **Treating a JavaScript producer as the second producer.** Reading the same graph model in another runtime is not the independent implementation that would let us verify the core boundary.
- **Abbreviating anything published or imported.** Short prefixes collide with existing commands and published packages, and the saving is not worth the ambiguity in a project whose premise is being explicit about what is known. The abbreviation exists, but only as the command name.
- **Publishing under a personal or company namespace.** A namespace owned by one party contradicts the position in ADR 0005 and would cost a rename later, when it is most expensive. The project holds its own.

