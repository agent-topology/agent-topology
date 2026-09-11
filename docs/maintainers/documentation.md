# Maintaining documentation

[Documentation home](../README.md)

The public documentation source lives in `docs/`. Markdown is readable directly in
the repository and can later be rendered into a wiki or static site. This change
does not choose a site generator or provision hosting.

## Information architecture

| Location | Audience and purpose |
| --- | --- |
| `README.md` | Documentation home and primary navigation |
| `getting-started/` | First successful extraction with a runnable minimal example |
| `guides/` | Concepts, consumer workflows, and troubleshooting |
| `reference/` | APIs, CLI behavior, installation, and compatibility |
| `maintainers/` | Development and documentation maintenance |
| `releases/`, `releasing.md` | Published history and maintainer release operations |
| `decisions/` | Accepted architectural decisions and their historical context |
| `reviews/` | Dated review findings and verification boundaries |
| `research/`, `retrospectives/` | Historical evidence, not current user instructions |

Keep current installation and API claims aligned with source manifests and public
exports. Preserve historical release notes and ADR rationale; add a current guide
or an explicit historical note instead of rewriting what was true at the time.

Use English, relative Markdown links, descriptive headings, and fenced code blocks
with language names. Link reusable concepts rather than duplicating their full
definitions. Keep runnable examples free of credentials and model services.

The public documentation guard checks local link targets throughout `docs/` and
the main repository/package entry points. Quickstart examples are executed by
the producer test suites. Run the [development checks](development.md) after edits.

## Preparing a future static site

Use `docs/README.md` as the navigation source and render the user guides/reference
as the primary site. Keep research and internal planning in a clearly identified
maintainer section or out of the public navigation. Preserve existing Markdown
source paths so GitHub and site links can remain stable.

Some authoritative references live outside `docs/`, including the root architecture,
schema, contributing policy, and conformance examples. A future build must either
include those sources with rewritten internal links or map them to the matching
repository revision. Do not blindly copy `docs/` and leave `../` links broken.

For a later S3 + CloudFront deployment, generate an independent output directory
containing HTML and assets. Before publishing, verify that nested pages, directory
index URLs, fragments, CSS/JS assets, and missing-page behavior work under the chosen
URL policy. Choose versioned documentation paths and distinguish current source
from released packages. Upload only rendered output, and use the deployment's cache
invalidation policy for changed pages. Domain, bucket, access controls, generator,
and deployment automation belong to that future hosting task.
