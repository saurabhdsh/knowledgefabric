# Weave Knowledge Fabric — Release 2.0 flyer prompt

Paste the prompt below into a designer, Figma AI, or an image model. It already contains the full Release 2.0 feature set. Keep every claim. Do not add customers, awards, or numbers that are not in this file.

Worked example, safe to print as a caption: a Cost of Care fabric with a care-policy document — 3,224 rows, 11 tables, 15 measured foreign keys, 208 graph nodes, 495 edges, 196 real records on the canvas, 172 links from a named person in a document to the matching row.

---

## Prompt

Design a single premium product flyer for **Weave Knowledge Fabric, Release 2.0**. One page. US Letter, with an A4-safe margin. It must also read on a phone screenshot. This is a keynote object, not a brochure. Dark glass, quiet type, one idea per line.

**Brand.** Name: Weave. Product: Knowledge Fabric. Release mark: 2.0, small, set like a version chip, never as a paragraph. Site line at the foot: cuweave.com. No other logos. No stock photography. No people. No handshakes. No network-node clip art. No purple gradients, no neon grids, no circuit boards.

**Palette, taken from the product.** Background `#070b12`. Glass panels `rgba(255,255,255,0.07)` with a 1px white hairline at 20% and a soft inset highlight. Type `#e8edf4` for titles, `#cbd5e1` for body, `#8b9cb0` for captions. Accents only: cyan `#5ec8f2` and green `#3ecf9b`. One violet `#9b8bd4` allowed on a single chip. Rounded corners 24–28px. Backdrop blur. Shadow is a deep soft drop, never a hard black box.

**Type.** A neo-grotesk in the SF Pro / Neue Haas family. Hero is tight, about −0.03em tracking, two lines maximum. Body is 11–13px equivalent, generous line height. Numbers are tabular. Labels are 10px, uppercase, wide tracking, color `#8b9cb0`.

**Mood.** Certain, calm, exact. The reader should feel that a graph was measured, not drawn. Write the way a well-made instrument is labeled.

### Page structure, top to bottom

**1. Masthead.** Left: a small wordmark “WEAVE”. Right: a glass chip “Knowledge Fabric · 2.0”. No tagline in the masthead.

**2. Hero.** Headline, exactly:

> From source to a graph you can stand behind.

Subhead, exactly:

> Weave reads the fabric, measures what is in it, and draws an edge only when it can name both sides, the evidence, and the confidence.

Under the subhead, six glass steps in one horizontal row. On a narrow crop, they wrap to two rows of three. Each step is a number, a name, and one line:

1. **Profile** — Types, nulls, keys, and foreign keys from value overlap.
2. **Parse** — Headings, tables, real page numbers, OCR for scans.
3. **Model** — An ontology from the full measurement, with evidence on every relationship.
4. **Index** — Rows stay queryable. Text and entity summaries are embedded in this fabric’s own index.
5. **Validate** — The build is published only when search and the counts still hold.
6. **Publish** — Classes and real records, joined, ready to inspect.

**3. Feature field.** A heading: “What Release 2.0 puts in your hands.” Then five glass groups. Every paragraph below is required. Keep the words. Do not merge groups. Do not invent a sixth group. The Context group is required. It is the layer Release 2.0 turns on after the graph is published.

**Create.** One pipeline for a database, a CSV, a PDF, a scan, and a composite. The files you name are the files that enter. A failed extraction or index stays failed. The fabric shows rows imported beside rows in the source. Embeddings are a real model, and the model name is stamped on the fabric.

**Understand.** The ontology is built from the full profile. Every relationship carries a source, a target, an evidence snippet, the columns that bind it, and a measured confidence. The canvas keeps the classes and a sample of the real records. Domain rules live in packs, including healthcare cost of care and IT service management.

**Connect.** A composite is a join. A person named in a document is linked to the matching row. The sources share one ontology. A count is answered from the table store. A question about a passage is answered from the documents. A question that needs both uses rows and passages together. Refresh rebuilds the fabric from the live sources and keeps the same fabric.

**Context.** Release 2.0 enables the context layer. Every answer carries a context envelope: the packet that turn was allowed to use. Each line is one of ontology, table, passage, graph, session, or memory, with its source and its confidence. You can open what the last answers used. A correction waits in a queue, then becomes fabric memory, an ontology alias, or an ontology rule on a draft. The approved ontology stays until that draft is approved. Coverage lists the questions the ontology or the evidence could not carry.

**Trust.** Search is keyword plus vector, reranked into a token budget. Expanding the graph returns values and confidence. Answer confidence comes from those measurements. Each fabric has its own index. Publish writes a version and a lineage. Row sync applies the delta when the primary key is unchanged. PII is classified and stamped. Access is owner, analyst, and viewer, and queries and grants are audited.

**4. Proof strip.** A single quiet band, captioned “A worked fabric.” Five figures in a row, each with a short label:

- 3,224 rows
- 11 tables
- 15 measured foreign keys
- 196 records on the canvas
- 172 document-to-row links

Caption under the figures, in `#8b9cb0`: “Cost of Care tables joined to a care-policy document. Counts, names, and page citations answered from the same fabric.”

**5. Close.** One line, left aligned:

> Open a fabric. See the evidence on the edge.

Right aligned, the only call to action: **cuweave.com**. No QR code unless the page still breathes. No “Request a demo” button. No pricing.

### Craft rules

- One type family. Two accent colors. Plenty of the dark ground showing.
- Features are sentences, not icons-with-verbs. If an icon is used, it is a 14px line icon in `#8b9cb0`, one per group, and it does not illustrate a metaphor.
- The six steps are the visual spine. The five groups are the body, and Context sits with them at the same size as Create, Understand, Connect, and Trust. The five figures are the proof. Nothing else competes with the headline.
- Print it so the glass panels still separate when the blur is flattened to a solid `#10141d`.
- Leave a 20mm margin. Align every panel to one 8px grid.
- The finished flyer should look like it belongs beside the product: dark, glassy, exact, and quiet.

### Words that must not appear

Training, AI-powered, revolutionary, unlock, seamless, next-generation, leverage, synergy, world-class, co-occurrence, roadmap, phase, TODO, commit hashes, test counts, “Release 2.0 stopped…”.
