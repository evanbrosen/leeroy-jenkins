# leeroy-jenkins

A Claude Code skill that builds hyper-realistic Salesforce demo orgs for specific customers. Given a company name and website, it researches the customer deeply, generates 5 realistic historical accounts (the customer's actual customers), deploys everything to your SF org via the CLI, and produces rich narrative output files.

## What it does

1. **Researches the customer** — scrapes their website for exact product names, named customers, sales motion, support model, recent news
2. **Designs 5 accounts** — real companies that plausibly buy what your customer sells, with a full 2-year history of opportunities, contracts, cases, and activities
3. **Deploys in parallel** — 5 subagents create all records simultaneously
4. **Generates output files** — a company intelligence brief and per-account narrative hand-off docs with direct links to every SF record

---

## Prerequisites

### 1. Install Homebrew

Homebrew is a package manager for macOS. If you don't have it yet:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the prompts — it will ask for your password and may install Xcode Command Line Tools. Once done, verify:

```bash
brew --version
```

### 2. Install Salesforce CLI

```bash
brew install sf
```

Verify:

```bash
sf --version
```

### 3. Authenticate your Salesforce org

```bash
sf org login web
```

This opens a browser window. Log in to your demo org. Once authenticated, verify it shows up:

```bash
sf org list
```

### 4. Install Claude Code

Follow the setup instructions at [claude.ai/code](https://claude.ai/code) if you haven't already.

---

## Install

Clone this repo and run the install script:

```bash
git clone https://github.com/evanbrosen/leeroy-jenkins.git ~/claude-projects/leeroy-jenkins
cd ~/claude-projects/leeroy-jenkins
bash install.sh
```

This symlinks the skill and agents into `~/.claude/` so edits to the repo take effect immediately without reinstalling.

Then update `config/users.json` with your SF org's usernames and user IDs.

---

## Run

```
/leeroy-jenkins
```

Follow the prompts. You'll need:
- Customer name + website URL
- SF org authenticated via `sf org login web`
- (Optional) A folder of customer-provided files (decks, org charts, etc.)

**Hero Mode**: Say yes when prompted to assign all records to yourself — useful for solo demos.

## Tear down

```
/leeroy-teardown
```

Deletes all records for a given customer slug in reverse dependency order. Optionally removes local output files too.

---

## Output files

All output lands in `customers/<slug>/`:

| File | What it is |
|---|---|
| `research.json` | Structured research data used to build the data plan |
| `customer_intelligence.md` | Full company brief — who they are, what they sell, how they sell, their customers, recent news |
| `account_<Name>.md` × 5 | Per-account narrative hand-off docs with SF Record Reference table and direct record links |

The `customers/` folder is gitignored — customer data never gets committed.

---

## Config

**`config/users.json`** — list of demo org users. Each user needs:
- `name`: display name
- `username`: SF username
- `sf_id`: SF user ID (18-char)
- `owns`: array of objects they own (e.g. `["Account"]`)

---

## Requirements

- macOS with Homebrew
- Salesforce CLI (`sf`) installed via Homebrew
- Claude Code
- Python 3.9+ (for `scripts/sf_helpers.py`)
