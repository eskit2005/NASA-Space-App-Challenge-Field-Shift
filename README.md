# NASA-Space-App-Challenge
# Field Shift: Adapting Farms with NASA Data

A decision-support tool that helps farmers explore crop rotation strategies to improve soil health, conserve water, and adapt to changing climate conditions.

**NASA Space Apps Challenge 2026 · Bangladesh · Team [Zerox]**

## The Problem
Farmers face shifting temperatures, unpredictable rainfall, water shortages, extreme weather, and declining soil health. These pressures make it hard to choose crop rotations that protect fields and stay resilient over the long term.

## Our Solution

### Crop Sequence Recommender: Architecture Overview
*A quick guide so everyone knows what each stage does and where we're working.*

---

### Why this architecture?
The problem is big and messy, so we split it into stages. Each stage has one clear job, so we can each own a piece and work in parallel. When the pieces are plugged together, they solve the whole thing. It's also flexible: stages can be skipped or swapped for a given location (e.g. jump from stage 3 straight to 5) without breaking how we work together. The two most critical parts are **sequence filtering** and running the **right optimization function**, so that every sequence gets a correct value.

---

### Stage 1: Data Collection
We gather inputs from farmers and from every available source worldwide: NASA, soil data, IoT sensors, and so on. Farmer input shouldn't be a plain question sheet. It should be a genuine conversation (AI-driven), so we get the maximum amount of input in the most natural way.

---

### Stage 2: Normalization
We clean and standardize all the data so the optimization step and everything downstream receive input in the exact format they expect.

---

### Stage 3: Suitable Crop List
**Problem statement:** For a given location, generate the list of ideal crops.

#### Methodology
* **Test 1:** Use published lists from national or local authorities (government bodies, local research papers). For Bangladesh, that means region-level sources like Chittagong, Sylhet, Barishal, as we did before.
* **Test 2:** If a location has no such list, generate it ourselves. Compare FAO crop requirement data against that location's environment data, and select the crops that match.
* **Test 3:** Use AI to synthesize papers and local data into a crop list where sources are scattered.
* **Fallback:** Test 1 first, then Test 2 (and Test 3 to fill gaps) when no authority list exists.

---

### Stage 4: Sequence Filtering
**Problem statement:** From the crop list, generate crop sequences. Even a short list produces hundreds of thousands of sequences, so we must filter them down rigorously.

#### Methodology
* **Test 1:** Use a rule book. Rigorously check whether suitable rule books exist. Since an algorithm can't run directly on a rule book, add an extraction phase that turns it into algorithmic rules, then use those hard rules to eliminate sequences. Plenty of hard agronomic rules exist that we can use.
* **Test 2:** Use AI as another filtering methodology alongside the rule book.
* **Test 3 (jump):** Skip filtering and use known sequences directly. Papers for places like Barishal and Dhaka list many good (not ideal or best) sequences. We take those and tweak them a little. In the output, we must clearly say these are commonly practiced sequences, not claimed to be the best.

#### Critical points
* Finding out whether a usable rule book really exists.
* Building the extraction phase so rules become algorithmically usable.
* Finding better ways to generate as few sequences as possible from the start, given the crops farmers usually grow in a location.
* **Fallback:** If the rule book doesn't work well, try Test 2 or Test 3. If no research papers or local almanacs exist either, run the optimization on all generated sequences, while continuing to look for a better approach for this stage.

---

### Stage 5: Multi-Criteria Mathematical Optimization & Compromise Programming

The sequence recommendation engine models the final sequence evaluation and portfolio selection as a Multi-Criteria Compromise Programming (CP) problem over a discrete feasible set $\mathcal{S}_{\text{viable}}$, rooted in the foundational work of Romero & Rehman (1985, 2003) and Zeleny (1974), integrated with agricultural cropping sequence constraints from Detlefsen & Jensen (2007) and Hazell & Norton (1986).

#### 1. The Hard Feasibility Filter (Pruning)
Before ranking, every pre-filtered sequence $s_k \in \mathcal{S}$ must satisfy non-negotiable physical and liquidity boundaries to enter the feasible set $\mathcal{S}_{\text{viable}}$:

```math
\mathcal{S}_{\text{viable}} = \{ s_k \in \mathcal{S} \mid C_1(s_k) \le B_{\text{cash}} \land W_t(s_k) \le R_t^{\text{NASA}} + I_t^{\max}, \; \forall t \in \mathcal{T} \}
```

* **Constraint 1 (Working Capital Wall):** $C_1(s_k) \le B_{\text{cash}}$ ensures upfront input costs in Season 1 (seed, fertilizer, fuel, tillage) do not exceed the farmer's liquid cash reserves, preventing debt failure before harvest (Hazell & Norton 1986).
* **Constraint 2 (NASA Seasonal Water Ceiling):** $W_t(s_k) \le R_t^{\text{NASA}} + I_t^{\max}$ ensures crop water evapotranspiration ($ET_c$) in each individual season $t$ does not exceed expected satellite rainfall plus maximum irrigation capacity (Allen et al. 1998; Detlefsen & Jensen 2007).

#### 2. Normalization onto the Dimensionless Unit Hypercube [0, 1]
To prevent scale bias across disparate physical units (BDT, mm, kg N/ha), raw criterion scores $f_{k, j}$ are mapped onto non-dimensional values $\bar{f}_{k, j} \in [0.0, 1.0]$, where $\bar{f}_{k, j} = 1.0$ is the ideal anchor across all viable candidates:

For Benefit Criteria ($j \in \mathcal{J}_{\text{benefit}} = \{\text{profit}, \text{soil}\}$):

```math
\bar{f}_{k, j} = \frac{f_{k, j} - \min_{i \in \mathcal{S}_{\text{viable}}} f_{i, j}}{\max_{i \in \mathcal{S}_{\text{viable}}} f_{i, j} - \min_{i \in \mathcal{S}_{\text{viable}}} f_{i, j}}
```

For Cost Criteria ($j \in \mathcal{J}_{\text{cost}} = \{\text{water}, \text{risk}\}$):

```math
\bar{f}_{k, j} = \frac{\max_{i \in \mathcal{S}_{\text{viable}}} f_{i, j} - f_{k, j}}{\max_{i \in \mathcal{S}_{\text{viable}}} f_{i, j} - \min_{i \in \mathcal{S}_{\text{viable}}} f_{i, j}}
```

#### 3. Compromise Programming Distance Formulation
The ranking engine identifies the optimal sequence by minimizing the weighted $L_p$ distance metric between a candidate sequence and the Ideal Point $\mathbf{f}^\ast = (1, 1, 1, 1)$:

```math
\min_{s_k \in \mathcal{S}_{\text{viable}}} D_p(s_k) = \left[ \sum_{j \in \mathcal{J}} \left( w_j \cdot (1 - \bar{f}_{k, j}) \right)^p \right]^{1/p}
```

**Operational Metric Geometries ($p \in \{1, 2, \infty\}$):**
* **Linear / Compensatory Metric ($p = 1$, Manhattan Distance):** $`D_1(s_k) = \sum_{j \in \mathcal{J}} w_j \cdot (1 - \bar{f}_{k, j})`$. Models complete substitutability between objectives.
* **Geometric Compromise Metric ($p = 2$, Euclidean Distance):** $`D_2(s_k) = \sqrt{\sum_{j \in \mathcal{J}} \left( w_j \cdot (1 - \bar{f}_{k, j}) \right)^2}`$. Penalizes severe deficiencies on any single dimension, yielding the balanced compromise 'knee' of the Pareto frontier.
* **Chebyshev / Minimax Regret Metric ($p = \infty$):** $`D_\infty(s_k) = \max_{j \in \mathcal{J}} \{ w_j \cdot (1 - \bar{f}_{k, j}) \}`$. Minimizes the single worst individual criterion shortfall. Models extreme risk aversion for resource-poor smallholders.

#### 4. Strategic Final Sequence Portfolio Selection
Rather than outputting trivial clones of the same crop sequence, the engine extracts distinct, non-dominated operational archetypes along the Pareto frontier (Branke et al. 2004):
* **Plan 1 (Personalized Compromise Knee):** $`s^\ast_{\text{personalized}} = \arg\min_{s_k \in \mathcal{S}_{\text{viable}}} D_2(s_k)`$ evaluated using elicited weights $\mathbf{w}$.
* **Plan 2 (Minimax Risk-Averse Safeguard):** $`s^\ast_{\text{safe}} = \arg\min_{s_k \in \mathcal{S}_{\text{viable}}} D_\infty(s_k)`$ protecting against worst-case market/climate shocks.
* **Plan 3 (Economic Maximizer):** $`s^\ast_{\text{economic}} = \arg\max_{s_k \in \mathcal{S}_{\text{viable}}} \bar{f}_{k, \text{profit}}`$ (upper cash frontier).
* **Plan 4 (Water Conservation Anchor):** $`s^\ast_{\text{water}} = \arg\max_{s_k \in \mathcal{S}_{\text{viable}}} \bar{f}_{k, \text{water}}`$ (drought/pumping-constrained anchor).
* **Plan 5 (Soil Regeneration Anchor):** $`s^\ast_{\text{soil}} = \arg\max_{s_k \in \mathcal{S}_{\text{viable}}} \bar{f}_{k, \text{soil}}`$ (maximum nitrogen and organic carbon restoration).

*(The top 3–5 representative strategies are passed to Stage 6 for explanation).*

#### 5. Exhaustive Parameter & Variable Reference Table

| Notation | Type | Unit | Description & Role in Formulation |
| :--- | :--- | :--- | :--- |
| $k$ | Index | Dim-less | Sequence identifier ($k \in \{1, \dots, M\}$) for candidate rotation $s_k$. |
| $t$ | Index | Dim-less | Chronological season index ($t \in \mathcal{T} = \{1, \dots, T\}$), e.g., Rabi ($t=1$), Kharif-1 ($t=2$), Kharif-2 ($t=3$). |
| $j$ | Index | Dim-less | Multi-criteria evaluation dimension ($j \in \mathcal{J} = \{\text{profit}, \text{water}, \text{soil}, \text{risk}\}$). |
| $p$ | Parameter | Dim-less | Minkowski metric power parameter ($p \in [1, \infty]$) defining geometric substitution and risk behavior. |
| $\mathcal{S}$ | Set | Sets | Complete pool of candidate crop sequences pre-screened by Stage 4 rule engines. |
| $\mathcal{S}_{\text{viable}}$ | Set | Sets | Subset of candidate sequences satisfying all hard liquidity and water constraints ($\mathcal{S}_{\text{viable}} \subseteq \mathcal{S}$). |
| $s_k$ | Vector | Tuple | Candidate rotation sequence vector $s_k = (c_{k, 1}, c_{k, 2}, \dots, c_{k, T})$. |
| $f_{k, j}$ | Variable | Native | Raw performance value of sequence $s_k$ on criterion $j$ (BDT, mm, kg N/ha, 1–5). |
| $\bar{f}_{k, j}$ | Variable | [0.0, 1.0] | Dimensionless normalized criterion score projected onto unit interval; $1.0$ is ideal. |
| $w_j$ | Parameter | [0.0, 1.0] | Subjective preference weight assigned to criterion $j$ (from Stage 1 conversation), where $\sum_{j \in \mathcal{J}} w_j = 1$. |
| $D_p(s_k)$ | Variable | Non-neg | Weighted distance of sequence $s_k$ from the ideal target coordinate $(1, 1, 1, 1)$. (Lower is better). |
| $B_{\text{cash}}$ | Parameter | BDT / USD | Farmer's available liquid working capital limit for Season 1 input purchases. |
| $C_1(s_k)$ | Variable | BDT / USD | Upfront cash expenditures (seed, fertilizer, fuel, tillage) required in Season 1 ($t=1$). |
| $R_t^{\text{NASA}}$ | Parameter | mm | Expected seasonal rainfall depth derived from NASA POWER / GPM satellite observations. |
| $I_t^{\max}$ | Parameter | mm | Maximum seasonal irrigation capacity (groundwater pumping quota or canal allocation). |
| $W_t(s_k)$ | Variable | mm | Seasonal crop water evapotranspiration demand ($K_c \times ET_0$) for sequence $s_k$. |

#### 6. Detailed Criteria Specification Matrix

| Criterion ($j$) | Objective ($f_{k, j}$) | Unit | Direction | Mathematical Formula | Agronomic & Economic Meaning |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Net Profit** | $f_{k, \text{profit}}$ | BDT/ha | Maximize | $\sum_{t=1}^T (\text{Yield}_{k, t} \times \text{Price}_t - \text{TotalCost}_{k, t})$ | Total multi-season gross margin. Ensures farm household cash-flow viability and debt service capacity. |
| **2. Water Demand** | $f_{k, \text{water}}$ | mm | Minimize | $\sum_{t=1}^T (K_{c, k, t} \times ET_{0, t}^{\text{NASA}})$ | Cumulative crop evapotranspiration ($ET_c$). Lower values preserve groundwater and reduce diesel/electric pumping bills. |
| **3. Soil Nitrogen Delta** | $f_{k, \text{soil}}$ | kg N/ha | Maximize | $\sum_{t=1}^T \Delta N_{k, t}$ | Net rotational nitrogen balance. Positive delta from legume fixation (+20 to +50 kg N/ha) offsets cereal soil depletion. |
| **4. Volatility Risk** | $f_{k, \text{risk}}$ | Index (1–5) | Minimize | $\frac{1}{T} \sum_{t=1}^T \text{RiskFactor}_{k, t}$ | Composite vulnerability score capturing crop perishability, wholesale market price volatility, and drought sensitivity. |

---

### Stage 6: LLM Extraction Layer (Explainability)
Its main job is to act as explainable AI. Industry really respects explainability, and we believe this layer gives us an upper hand in the hackathon: everyone can use AI now, but explainability sets us apart.

The layer takes everything that happened behind the scenes (calculations, filtering, considerations) and explains it in a way farmers easily understand. For example:
* If a sequence comes from an authoritative source, we say it's ideal according to that source.
* If it comes from research papers on what farmers usually do, we say it's commonly practiced, not that it's the best.

#### Where AI fits in
* **Stage 1:** natural conversation with farmers.
* **Stage 3:** synthesizing papers and local data into crop lists.
* **Stage 4:** AI-based filtering as an alternative methodology.
* **Stage 6:** explainability for farmers.

---

### Scaling to an Agentic AI System
* **The problem:** Right now the system is location-specific in places. For Barishal we use an available research paper and go in one direction; another location may need a different approach. There's a base framework (the stages), but not one fixed way of doing each.
* **The idea:** Sub-layers get added or removed per location. For instance, the LLM extraction layer may or may not be needed depending on what's available, and the system can search the internet for missing sources.
* **How we generalize:** Turn it into a flexible agentic system by exposing the important tools to it.
* Keep a human in the loop. A person watches whether the agent is choosing the right path and can redirect it.
* This works as an interface for tweaking the system, removing the need to manually redesign the workflow for every location in the world.
