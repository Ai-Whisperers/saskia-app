# **AI Whisperers Data Standard**

## ⚙️ BIG-DATA AND AUTOMATION BASELINE

> *Build once. Scale infinitely.*

* Use **Arrow** + **Parquet** (optionally **Avro**) instead of legacy workers or Python libs — faster, structured, scalable.
* Use **JSON only** for API headers and negotiation — **never** for databases or full payloads.
* **Dockerize each service**, deploy via **Kubernetes**, and use **custom domains**.
* Avoid paid clouds that sell *lock-in instead of tools* — autonomy is the new uptime.

🪄 **Try this:** containerize one small script today; watch how portability rewires your sense of control.

---

## 🧠 RATIONALE — WHY WE BUILD DIFFERENTLY

> *Complexity paid once; simplicity forever.*

**Goal** – shortest path from research → implementation through Arrow-based automation, schema permanence, and clean edges.
**Principle** – front-load complexity once (Arrow / Parquet / Polars) so scaling never breaks.
Every byte stays structure-aware; every service composable; performance is the baseline.

**When others stay “normal,” they lose:**

* **Automation:** ad-hoc JSON → schema drift → chaos in cost, speed, accuracy.
* **Elasticity:** rigid files pin compute → no edge/cloud mobility.
* **AI Alignment:** unstructured data → broken LLM chains → rewrites.
* **Longevity:** text stacks collapse past millions of rows → rebuild loop.
* **Composability:** no Arrow Flight = entropy & exponential tech debt.

> “Normal AI” scales hype, not infrastructure.
> **We scale structure itself** — automation, mobility, durability in one motion.

---

## ⚖️ 2025 AI Startups vs AI Whisperers

| Dimension     | Typical Startup          | **AI Whisperers**                 |
| :------------ | :----------------------- | :-------------------------------- |
| Automation    | No schema → manual fixes | Schema-native → auto-structured   |
| Elasticity    | Data locked in silos     | Workloads flow edge ↔ cloud       |
| AI Alignment  | JSON breaks LLM layers   | Arrow-native → future-proof       |
| Longevity     | REST rebuilds at scale   | Architecture scales by design     |
| Composability | Services drift           | Flight-based → plug-ready harmony |

🧩 **Mini-echo:** our AI *is* the infrastructure — keep repeating this; it locks conceptually.

---

## 📁 REPOSITORY STRUCTURE

```
template-standard/
├── README.md                          # This file - standards overview
├── CLAUDE.md                          # Project context for AI assistants
├── documentation-standard/            # Documentation format standards
│   ├── documentation-format.md        # Human + Toon dual-layer format
│   ├── neuroparsing-protocol.md       # Cognitive neuroscience principles
│   └── proportion-in-docs.md          # Human/Toon ratio guidelines
├── automation-practical-guide/        # Automation and AI integration
│   ├── automation.md                  # .mcp and .claude orchestration
│   ├── integration-system.md          # Testing stratification layers
│   ├── mcp-dual-layering.md           # MCP architecture patterns
│   ├── agnostic-datasets-pipelines.md # Data pipeline standards
│   ├── reality-check.md               # Practical constraints
│   └── abstraction-layers/
│       └── ai-validation-layer/       # AI validation examples
├── deploy&self-hosting-guide/         # Deployment and infrastructure
│   ├── microservices/
│   │   ├── k8s-deployment-template/   # Kubernetes deployment templates
│   │   └── diagram.md                 # Architecture diagrams
│   └── self-hosting/
│       ├── budget/                    # Cost analysis and budgets
│       └── reality-check.md           # Deployment considerations
├── john-ivan-config-templates/        # Development workflow templates
│   └── john-dev-template/             # Coding standards and rules
├── research&exploratory/              # Research and future plans
│   └── long-term-full-automation/     # Automation vision
├── .claude/                           # Claude Code configuration
│   ├── README.md  ├── settings.local.json
│   └── commands/  # validate-docs, check-standards, format-doc
└── .mcp/                              # Model Context Protocol config
    ├── README.md  ├── QUICKSTART.md  ├── SETUP.md  ├── ARCHITECTURE.md
    ├── configs/   # gordon-mcp.yml, docker-compose.mcp-gateway.yml
    └── servers/standards-validator/   # Custom validation server
```

---

## 📘 DOCUMENTATION STANDARD

> *Write so both humans and models can breathe.*

**Human-Language Docs**

* Concise, dense, natural.
* Two levels max (`## Principle → – Rule`).
* One meaning per line.

**LLM-Friendly Docs (Toon Format)**

* Ref: [Toon Repo](https://github.com/toon-format/toon) → ≈ −22 % tokens vs JSON.
* Ideal for fine-tuning, context windows, and reproducibility.

| Dataset     | Toon Tokens | vs JSON | vs YAML | vs XML |
| :---------- | ----------: | ------: | ------: | -----: |
| E-commerce  |      72 743 |   −33 % |   −14 % |  −41 % |
| Event Logs  |     153 223 |   −15 % |    −1 % |  −25 % |
| Deep Config |         631 |   −31 % |    −6 % |  −37 % |

---

## 🧱 FORMATS / LIBRARIES

**Data Formats** – Arrow (processing) · Parquet (storage) → [docs](https://arrow.apache.org/docs/r/articles/read_write.html)
**DataFrames** – Pandas = legacy · Polars = Arrow-native multi-threaded speed
**Parsers & Tools** – Apache POI (Java Office suite) · openpyxl (Excel structure) · pandas.read_excel (fast tabular)

🪞 *Visual cue:* think of Arrow as the bloodstream, Parquet as the bone.

---

## ☁️ DEPLOYMENT / HOSTING

**Dockerization** – portability + Linux harmony
**Kubernetes on-prem** – be your own cloud; evade lock-in

**Quick Path**

1. Hardware → servers / switches / storage / UPS
2. Install → kubeadm | k3s | microk8s | Rancher | Anthos
3. Operate → `kubectl apply` apps + DBs + models
4. Integrate → local LAN or federated cloud

💡 *Action anchor:* run a single-node k3s today; feel instant ownership.

---

## 📦 PACKAGE MANAGEMENT

| Use           | Tool                 |
| :------------ | :------------------- |
| Default       | **pnpm** (monorepos) |
| Flexible      | **yarn**             |
| Legacy stable | **npm** (if needed)  |
| Frontend opt. | **bun** (unstable)   |

---

## 🗄️ DATA STORAGE

* Centralize via shared service endpoints.
* **SQL:** simple CRUD / flat schemas.
* **GraphQL:** nested multi-service queries.

---

## 🔗 MICROSERVICES

**Communication**

* **Arrow Flight REST Bridge:** Arrow streams + JSON metadata.
* **GraphQL + Arrow buffers:** semantic queries → binary returns.

| Plane   | Transport    | Purpose                  |
| :------ | :----------- | :----------------------- |
| Control | REST / HTTPS | Auth · Sessions          |
| Data    | gRPC stream  | High-throughput transfer |

🧩 *Pattern break:* control ≠ data plane → separate them mentally; this improves retention.

---

## 🧰 DEV ENV (LLM-FRIENDLY)

Each repo must include **`.claude`** and **`.mcp`** folders containing project context.

> *These are memory organs, not metadata.*

---

## 🧾 QA LOGGING / TRACEABILITY

| Context               | Traceability Type             |
| :-------------------- | :---------------------------- |
| Requirements / QA     | Requirements Traceability     |
| Version Control       | Audit Trail / Provenance      |
| DevOps / CI-CD        | Artifact Lineage              |
| Data / ML / ETL       | Data Lineage                  |
| Security / Compliance | Accountability / Change Audit |

**Vertical traceability = causal depth:** link *requirement → component → test → metric*.
Maintain dependency-aware test graphs + Depth Index for total coverage.

🧭 *Reflection hook:* trace once, forget never — your system remembers what you design it to.

---