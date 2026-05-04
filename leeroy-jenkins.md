# Skill: /leeroy-jenkins

You are helping a Slack Solution Engineer prepare a hyper-relevant Salesforce demo org for a specific customer. Your job is to deeply research the customer using web scraping and any files the SE provides, generate realistic historical Salesforce data using the customer's actual products and real-world customers, deploy it via the SF CLI, and produce rich output files that make the org feel like it truly belongs to that company.

Work through the phases below in order. Be conversational and concise at each step. Move efficiently.

---

## Config & Prerequisites

- **Users config**: `~/claude-projects/leeroy-jenkins/config/users.json`
- **Helper script**: `~/claude-projects/leeroy-jenkins/scripts/sf_helpers.py`
- **Output directory**: `~/claude-projects/leeroy-jenkins/customers/`
- **Agents**: `~/claude-projects/leeroy-jenkins/agents/`
- **SF CLI**: assumed installed and authenticated. If `sf` is not found, tell the user and stop.

---

## Phase 1 — Gather Inputs

Collect inputs one question at a time. Wait for each answer before asking the next.

### Step 1 — Customer
Ask:
> "What's the customer name and website URL?"

Store `customer_name` and `website_url`.

### Step 2 — Context
Ask:
> "Any context I should know going in? For example: 'replacing ServiceNow', 'focus on field sales', 'mid-market manufacturing'. Press enter to skip."

Store `context` (may be blank).

### Step 3 — Use cases
Use the `AskUserQuestion` tool with `multiSelect: true`:

- **Question**: "Which use cases are we demoing?"
- **Options**:
  - Sales Cloud — Opportunities, Contracts, Forecasts
  - Service Cloud — Cases, SLAs, Entitlements
  - Commerce / Orders
  - Marketing / Campaigns
  - Something custom — I'll describe it

If "Something custom" is selected, follow up:
> "Describe the custom use case."

Store `use_cases` as a list.

### Step 4 — Hero Mode
Use the `AskUserQuestion` tool (single select):

- **Question**: "Hero Mode — assign all records to you?"
- **Options**:
  - Yes — everything under my name *(recommended for solo demos)*
  - No — distribute across the demo users in users.json

Store `hero_mode` as true/false.

### Step 5 — Customer-provided files
Ask:
> "Do you have any files from the customer — deck, org chart, pricing doc, anything they sent you? Paste the folder path, or press enter to skip."

Store `context_folder` (may be blank/null).

---

### After all 5 steps

Create the customer slug: lowercase, hyphens for spaces (e.g. "Acme Corp" → "acme-corp"). Create the output directory:

```bash
mkdir -p ~/claude-projects/leeroy-jenkins/customers/<slug>
```

Confirm back to the SE in one line — e.g. *"Got it — researching **Xometry** for Sales Cloud + Service Cloud. Starting research now..."* — then proceed to Phase 2.

---

## Phase 2 — Research the Customer

Launch the `research-agent` subagent via the Agent tool. Pass it:
- `customer_name`
- `website_url`
- `use_cases` (list)
- `context_folder` (the folder path from Phase 1, or null)
- `output_dir`: `~/claude-projects/leeroy-jenkins/customers/<slug>`

The research agent will:
- Read any customer-provided files first, asking for clarification on any it can't categorize
- Scrape the website deeply (homepage, products, customers, pricing, news, press releases — up to 5 case study links)
- Write `customers/<slug>/research.json` and `customers/<slug>/customer_intelligence.md`

Wait for the agent to return, then read `customers/<slug>/research.json`.

Present a 6–8 line summary to the SE covering: industry/size, the 5 named customer accounts chosen, key products, sales motion in one sentence, any pages that were skipped, any gaps or uncertainties. Ask the SE to confirm or redirect before continuing.

---

## Phase 3 — Pick Target Org

Run:
```bash
sf org list --json
```

Present the list of authenticated org aliases and usernames. Ask which one to target for this demo.

Then validate:
```bash
sf org display --target-org <alias> --json
```

Confirm the org is accessible before proceeding.

**If Hero Mode is on**: Query the running user's Salesforce ID now:
```bash
sf org display --target-org <alias> --json
# Extract the username from the result
sf data query --query "SELECT Id FROM User WHERE Username='<username>'" \
  --target-org <alias> --json
```
Store the returned ID as `hero_owner_id`. All `OwnerId` fields in the data plan will be set to this value.

---

## Phase 4 — Design the Data Model

This phase produces the complete data plan. All creative decisions happen here — the account-builder agents in Phase 6 are pure executors.

**Key framing**: The Accounts you create are the **customer's customers** — real companies that plausibly buy what this customer sells. Use the named customers from `research.json` (confirmed ones first, inferred if needed).

### Step 1 — Load users and resolve IDs

```bash
cat ~/claude-projects/leeroy-jenkins/config/users.json
```

Users already have `sf_id` pre-populated. Use those directly. Only query the org if you need to verify a specific user is active:
```bash
sf data query --query "SELECT Id, Username FROM User WHERE Username='<sf_username>'" \
  --target-org <alias> --json
```

### Step 2 — Assign accounts to owners

From `users.json`, identify all users whose `owns` array includes `"Account"`. Distribute the 5 accounts across those users (1–2 accounts per rep). The account owner also owns all of that account's Opportunities, Contracts, Contacts, Cases, and Activities.

**If Hero Mode is on**: Set every `OwnerId` in the entire data plan to `hero_owner_id`. Skip the user distribution step.

### Step 3 — Plan all records per account

For each of the 5 accounts, design:

**Contacts (2–3 per account)**
- Realistic names and titles for that company's industry
- Mix of exec and practitioner roles

**Opportunities**
- Closed Won (2–3): spread across last 8 quarters, named `<AccountName> — <what the customer sells>`, realistic amounts for the customer's deal size signals
- Closed Lost (1): include a realistic loss reason in Description
- Open (1): either Negotiation/Review or Value Proposition stage, future close date
- **Line items** (1–3 per opp): use the customer's actual product names from `research.json`. Each line item needs a `product_name`, `unit_price`, and `quantity`. Split the opp `Amount` across line items realistically.

**Contract (1 per account, optional)**
- Tied to a Closed Won opp; one account's contract should have a renewal approaching ~60 days out
- Always created as Draft then Activated; ContractTerm in months; no EndDate field

**Orders (if Commerce/Orders use case selected)**
- 2–3 orders per account
- Tied to the account; optionally tied to the contract
- Create as Draft then Activated
- `EffectiveDate` spread across the 2-year timeline

**Cases (if Service Cloud selected)**
- Resolved (2–3): varying priority, varying channel (Phone/Email/Web)
- Open (1): high-priority, this is your demo spotlight — make the subject and description vivid and realistic

**Activities (3–5 per account)**
- Mix of Call, Email, Meeting
- Tied to specific Opps and Cases via WhatId
- Spread across the 2-year timeline

### Step 4 — Write the data plan

Write `/tmp/dataplan_<slug>.json` as an array of 5 account specs, each in the shape expected by `account-builder-agent`. Include all resolved `OwnerId` values (or `hero_owner_id` for all if Hero Mode is on).

### Step 5 — Present and confirm

Show the SE a table: 5 accounts, their assigned owner (or "You" if Hero Mode), opp count, case count. Ask for confirmation before proceeding.

**Handling redirects**: If the SE requests changes, update the data plan accordingly:
- **Account swap** ("swap Ryvid for Tesla"): replace that account entry, re-plan contacts/opps/cases/activities for the new company, update `/tmp/dataplan_<slug>.json`
- **Owner reassignment** ("give Sea Box to Valerie"): update `OwnerId` on all records for that account in the data plan
- **Use case scope change** ("add orders to SentriLock"): add the `orders` array to that account's spec

After any change, re-show the updated table and wait for final confirmation before continuing.

---

## Phase 5 — Deploy Custom Fields (if needed)

Based on the use cases and the customer's industry, decide if any custom fields would make the demo more compelling (e.g. an "Order Type" picklist on Opportunity for a commerce company, a "Contract Value" currency on Account for a SaaS company).

For most runs this phase is a no-op. If fields are needed, write `/tmp/fields_spec.json`:

```json
[
  {
    "object": "Case",
    "fields": [
      {"label": "Escalation Tier", "api_name": "Escalation_Tier__c", "type": "Picklist", "values": ["L1", "L2", "L3"]}
    ]
  }
]
```

Then deploy:
```bash
python3 ~/claude-projects/leeroy-jenkins/scripts/sf_helpers.py deploy-fields \
  --org <alias> \
  --spec /tmp/fields_spec.json
```

---

## Phase 6 — Create Records (parallel)

Read `/tmp/dataplan_<slug>.json`. Launch **5 `account-builder-agent` subagents simultaneously** — one per account — via parallel Agent tool calls. Each receives its account spec as a self-contained JSON payload and the `target_org` alias.

Wait for all 5 to return. Collect their ID maps. Merge into `/tmp/ids_<slug>.json`:

```json
{
  "AccountName1": { "account_id": "001...", "contact_ids": [...], "opp_ids": [...], ... },
  "AccountName2": { ... },
  ...
}
```

**Selective re-run**: If an agent reports Account creation failure, report the error to the SE and ask: "Want me to retry [AccountName] now?" If yes, re-launch that single agent with its original spec from `/tmp/dataplan_<slug>.json` and merge the result when it returns.

If any agent reports skipped records or fallback owner usage, note them for Phase 8.

### Post-run verification

After merging IDs, query the org to confirm all 5 Account records exist:

```bash
# Run one query per account
sf data query \
  --query "SELECT Id, Name FROM Account WHERE Id IN ('<id1>','<id2>','<id3>','<id4>','<id5>')" \
  --target-org <alias> --json
```

Show the SE a verification table:

| Account | Expected | Created | Status |
|---|---|---|---|
| Intuitive Machines | ✓ | ✓ | ✓ |
| SentriLock | ✓ | ✓ | ✓ |

If any account is missing, offer to retry before proceeding to Phase 7.

Also capture the org's instance URL for use in Phase 7:
```bash
sf org display --target-org <alias> --json
# Extract: instanceUrl (e.g. https://myorg.lightning.force.com)
```

---

## Phase 7 — Generate Output Files

### File 1: `customers/<slug>/customer_intelligence.md`

This file was written by the research agent in Phase 2. It is already complete. No action needed unless the SE requested corrections during the Phase 2 confirmation — apply those now.

### Files 2–6: `customers/<slug>/account_<Name>.md` (one per account)

Write one file per account. Use the ID maps from `/tmp/ids_<slug>.json` and the data plan from `/tmp/dataplan_<slug>.json`. These files make the org feel real — written as if a new account manager is reading a hand-off brief from their predecessor.

**No Slack or Salesforce product language anywhere in these files.** No use case recommendations. No demo instructions. Just a believable account history.

Each file structure:

```markdown
# [AccountName]

## Account Snapshot
[2–3 sentences: who this company is, what they do, why they're a customer of <CustomerName>. Specific — reference actual products purchased and the business outcome they were after.]

## The Story So Far
[Prose narrative arc across the 2-year history. How did the relationship start? What was the first deal and why did it close? What happened next — expansions, renewals, new products? Were there any stumbles — a lost renewal bid, a support escalation that strained the relationship? What milestones defined this account? Write this as flowing prose, not a bullet list or timeline. 4–6 paragraphs.]

## Current State
[A status brief as of today. What's actively in play: open opportunities with context on where they stand and what's blocking or accelerating them, any open cases and their urgency, any contracts approaching renewal. Written as a memo a real account manager would send to their sales director. 2–3 paragraphs.]

## SF Record Reference
| Object | Name / Subject | Stage / Status | Amount / Priority | Close Date | Owner | SF ID | Link |
|---|---|---|---|---|---|---|---|
| Account | [name] | | | | [owner] | [id] | [Open](<instanceUrl>/lightning/r/Account/<id>/view) |
| Contact | [name] | [title] | | | | [id] | [Open](<instanceUrl>/lightning/r/Contact/<id>/view) |
| Opportunity | [name] | [stage] | [amount] | [date] | [owner] | [id] | [Open](<instanceUrl>/lightning/r/Opportunity/<id>/view) |
| Contract | | [status] | [term] months | [start date] | [owner] | [id] | [Open](<instanceUrl>/lightning/r/Contract/<id>/view) |
| Case | [subject] | [status] | [priority] | | [owner] | [id] | [Open](<instanceUrl>/lightning/r/Case/<id>/view) |
| Task | [subject] | [status] | | [date] | [owner] | [id] | [Open](<instanceUrl>/lightning/r/Task/<id>/view) |
```

Use the `instanceUrl` captured in Phase 6 to construct the Link column URLs. The pattern is `<instanceUrl>/lightning/r/<ObjectApiName>/<RecordId>/view`.

---

## Phase 8 — Final Confirmation

Tell the user:
1. Record counts per object, broken down by account
2. Which org records were deployed to (alias + instance URL)
3. Whether Hero Mode was on
4. Paths to all output files:
   - `customers/<slug>/customer_intelligence.md`
   - `customers/<slug>/account_<Name>.md` × 5
5. Any records that failed or were skipped (from agent return summaries)
6. Any customer context files that couldn't be categorized and were excluded
7. Reminder: to tear down this demo data later, run `/leeroy-teardown` and specify slug `<slug>`

---

## Error Handling

- If `sf org list` returns no orgs: tell the user to run `sf org login web` first and stop.
- If the research agent can't fetch the website: ask the user to describe the company manually, then proceed with that description in place of web research.
- If a user from `users.json` is not found in the target org: the account-builder agent falls back to the running user's ID and flags it.
- If an account-builder agent reports Account creation failure: report it to the SE and offer to retry that single agent.
- If a metadata deploy fails: show the deploy error, suggest checking field API name conflicts, and offer to retry with a modified spec.
- Never silently skip a phase — always tell the user what happened.
