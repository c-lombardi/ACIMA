# Candidate evaluation matrix

Captured: 2026-11-08. Metadata source: GitHub REST API. Selected: 15.

| Repository | Lang | Size KB | Stars | License | Archived | Last push | Decision |
|---|---|---:|---:|---|---|---|---|
| spectreconsole/spectre.console | C# | 16480 | 11690 | MIT | False | 2026-10-26 | **SELECTED** |
| FluentValidation/FluentValidation | C# | 20049 | 9769 | Apache-2.0 | False | 2026-11-03 | **SELECTED** |
| dotnet-architecture/eShopOnWeb | C# | 61146 | 10673 | MIT | True | 2025-01-13 | archived January 2025; excluded as not actively maintained |
| dotnet/BenchmarkDotNet | C# | 73835 | 11527 | MIT | False | 2026-11-06 | 73 MB; valid MIT alternative but Spectre.Console selected for smaller footprint and different domain |
| serilog/serilog | C# | 76363 | 8064 | Apache-2.0 | False | 2026-10-23 | **SELECTED** |
| jellyfin/jellyfin | C# | 79128 | 59121 | GPL-2.0 | False | 2026-11-06 | seed; 79 MB but GPL-2.0 and heavy media dependencies; local-only, superseded by permissive candidates |
| microsoft/semantic-kernel | C# | 107565 | 28747 | MIT | False | 2026-11-07 | seed; 108 MB and external AI services, too costly |
| LuckyPennySoftware/AutoMapper | C# | 127627 | 10180 | NOASSERTION | False | 2026-11-06 | not selected: duplicate/less diverse than chosen alternatives |
| AvaloniaUI/Avalonia | C# | 235964 | 31780 | MIT | False | 2026-11-07 | seed; 236 MB UI framework, too large |
| dotnet/aspnetcore | C# | 413682 | 38503 | MIT | False | 2026-11-08 | seed; 414 MB framework monorepo, too large |
| nopSolutions/nopCommerce | C# | 1730828 | 10180 | NOASSERTION | False | 2026-11-06 | 1.73 GB and custom license; excluded |
| spf13/cobra | Go | 2107 | 44845 | Apache-2.0 | False | 2026-07-11 | **SELECTED** |
| charmbracelet/bubbletea | Go | 5990 | 45644 | MIT | False | 2026-11-01 | **SELECTED** |
| gin-gonic/gin | Go | 10657 | 89602 | MIT | False | 2026-10-10 | **SELECTED** |
| pocketbase/pocketbase | Go | 147003 | 61602 | MIT | True | 2026-10-26 | seed; 147 MB and largely single-package, rejected for size/architecture diversity |
| gohugoio/hugo | Go | 153519 | 90413 | Apache-2.0 | False | 2026-11-07 | seed; 154 MB, too large for the dependency budget |
| prometheus/prometheus | Go | 297022 | 67540 | Apache-2.0 | False | 2026-11-08 | seed; 297 MB, too large for the dependency budget |
| go-gitea/gitea | Go | 373111 | 58956 | MIT | False | 2026-11-08 | seed; 373 MB, too large for the dependency budget |
| jhy/jsoup | Java | 8025 | 11413 | MIT | False | 2026-11-04 | **SELECTED** |
| google/gson | Java | 23579 | 24230 | Apache-2.0 | False | 2026-11-04 | **SELECTED** |
| macrozheng/mall | Java | 58744 | 85017 | Apache-2.0 | False | 2026-09-15 | **SELECTED** |
| spring-projects/spring-boot | Java | 226543 | 81786 | Apache-2.0 | False | 2026-11-06 | seed; 227 MB, too large for Java unsupported-profile evaluation |
| elastic/elasticsearch | Java | 1848722 | 78526 | NOASSERTION | False | 2026-11-08 | seed; 1.85 GB and custom license, too large and unsuitable for redistribution |
| encode/httpx | Python | 8619 | 15747 | BSD-3-Clause | False | 2026-10-02 | **SELECTED** |
| pallets/flask | Python | 12227 | 75068 | BSD-3-Clause | False | 2026-10-30 | **SELECTED** |
| fastapi/fastapi | Python | 58043 | 104565 | MIT | False | 2026-11-07 | **SELECTED** |
| yt-dlp/yt-dlp | Python | 65029 | 206115 | Unlicense | False | 2026-11-04 | seed; 65 MB and monolithic CLI, superseded by three smaller Python candidates |
| django/django | Python | 284185 | 91687 | BSD-3-Clause | False | 2026-11-06 | seed; 284 MB compressed metadata, too large for the 9.7 GB single-sandbox budget after dependencies |
| pandas-dev/pandas | Python | 420830 | 50529 | BSD-3-Clause | False | 2026-11-08 | seed; 421 MB compressed metadata and native build, too costly for this run |
| mealie-recipes/mealie | Python | 456797 | 13843 | AGPL-3.0 | False | 2026-11-08 | 457 MB and AGPL-3.0; local-only but too large for this run |
| honojs/hono | TypeScript | 10290 | 32852 | MIT | False | 2026-11-07 | **SELECTED** |
| drizzle-team/drizzle-orm | TypeScript | 67081 | 36230 | Apache-2.0 | False | 2026-11-08 | **SELECTED** |
| trpc/trpc | TypeScript | 128505 | 40784 | MIT | False | 2026-11-08 | **SELECTED** |
| immich-app/immich | TypeScript | 323679 | 118508 | AGPL-3.0 | False | 2026-11-08 | seed; 324 MB and AGPL, too large for local-only run |
| nestjs/nest | TypeScript | 493011 | 76990 | MIT | False | 2026-11-07 | seed; 493 MB monorepo, too large for the dependency budget |
| Stirling-Tools/Stirling-PDF | TypeScript | 685335 | 96008 | NOASSERTION | False | 2026-11-08 | Java seed listed under TypeScript by GitHub; 685 MB, too large |
| n8n-io/n8n | TypeScript | 796899 | 209807 | NOASSERTION | False | 2026-11-08 | seed; 797 MB and custom license, too large |
| calcom/cal.diy | TypeScript | 1160042 | 49793 | MIT | False | 2026-11-03 | not selected: duplicate/less diverse than chosen alternatives |

## Selection rationale

- Three repositories per implemented language, plus three Java repositories for unsupported-profile evaluation.
- Prefer permissive licenses; AGPL/GPL and custom-license repositories are excluded from this implementation run.
- Avoid repositories over roughly 150 MB compressed metadata when a smaller, actively maintained alternative exists.
- This portfolio is deliberately weighted toward libraries and frameworks; it does not yet prove adoption in large layered applications.
- Java has no ACIMA enforcer in the pinned revision. Java results assess applicability and skill transparency only.
