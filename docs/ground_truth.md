# Ground Truth — Paper Trail vs. the real Enron record

Paper Trail runs on a **faithful reconstruction of the Enron case**, not a blind rediscovery of it. The email corpus is the real, public CMU Enron dataset (435,259 messages). The `finance.*` tables (ownership, the SPE registry, restatement events) are **reconstructed from the public record and labeled as such in DataHub** — seeded to mirror documented history so the hunts have a governed warehouse to investigate. The contribution is the **auditable investigation pattern**, which generalizes to any governed data; we do **not** claim the agent discovered the fraud from scratch.

This page lets a reviewer check that the reconstruction is faithful — the people, entities, and dates the hunts surface are the real ones.

## The people the hunts implicate were the real principals

| Paper Trail finding | Documented Enron reality |
|---|---|
| Hunt 4 flags `finance.executive_summary_report`, owner **andrew.fastow** (CFO), uncertified | **Andrew Fastow**, Enron CFO — architect of the LJM / LJM2 partnerships and the off-balance-sheet SPEs; pleaded guilty to wire and securities fraud, 10-year sentence, forfeited $23.8M. |
| Hunt 4 flags `finance.restatement_events` and `finance.spe_entities`, owner **richard.causey** (Chief Accounting Officer), uncertified | **Richard Causey**, Enron Chief Accounting Officer — charged over the SPE accounting alongside Fastow and Skilling; pleaded guilty to securities fraud. |

## The SPEs the hunts surface were the real vehicles

| Paper Trail finding | Documented Enron reality |
|---|---|
| Hunt 2: 120 pre-disclosure emails reference undisclosed SPEs (Chewco, LJM1/2, Raptor, JEDI) | **Chewco** kept ~$600M of debt off Enron's balance sheet; **LJM1 / LJM2** were Fastow's partnerships; **Raptor I–IV** and **JEDI** were central to the accounting fraud. |
| Hunt 3: 8 off-glossary codenames co-mention with known SPEs (marlin, osprey, talon, yosemite, rawhide, fishtail, condor, porcupine) | Documented Enron / Whitewing-era vehicles include **Talon** (a Raptor entity), **Porcupine** (Raptor-related), **Marlin** and **Osprey** (Whitewing financing), and **Yosemite** (credit-linked notes). |

## The timeline the hunts anchor to is the real one

| Paper Trail finding | Documented Enron reality |
|---|---|
| Hunt 1: comm-volume spike the week of **Oct 8 2001**, 8 days pre-announcement | **Oct 16 2001** — Enron reported a **$618M Q3 loss** and a **$1.2B** reduction in shareholder equity. |
| Restatement window referenced across hunts | **Oct 22 2001** SEC inquiry disclosed; **Nov 8 2001** restatement 8-K. |

## Real vs. reconstructed (no overclaiming)

- **Real:** the 435k-email corpus; the people, SPE names, dates, and disclosure windows above (all public record).
- **Reconstructed (labeled in DataHub):** the `finance.*` tables — ownership assignments, SPE registry, restatement-events — built to reflect the documented case.
- **Not claimed:** blind discovery of the fraud. The value is the **provenance pattern** — every finding is materialized evidence + verbatim SQL + lineage, auditable in DataHub — which works on any real, governed warehouse.

## Sources

- DOJ — Fastow indictment (2002): <https://www.justice.gov/archive/opa/pr/2002/October/02_crm_627.htm>
- SEC — Causey / Skilling litigation release: <https://www.sec.gov/enforcement-litigation/litigation-releases/lr-18582>
- Corpus — CMU Enron Email Dataset (public, May 2015 release).
