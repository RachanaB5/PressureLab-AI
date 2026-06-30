<div align="center">

# ⚽ PressureLab AI

### Explain Every Football Decision with Explainable AI

**Football analytics tells you *what* happened. PressureLab AI tells you *why*.**

[![IBM SkillsBuild](https://img.shields.io/badge/IBM%20SkillsBuild-AI%20Builders%20Challenge%202026-blue?style=for-the-badge)](https://github.com/RachanaB5/PressureLab-AI)
[![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)](#)
[![Stars](https://img.shields.io/github/stars/RachanaB5/PressureLab-AI?style=for-the-badge)](https://github.com/RachanaB5/PressureLab-AI)

[Demo Video](#-demo) · [Features](#-key-features) · [Architecture](#-ai-architecture) · [Quick Start](#%EF%B8%8F-running-locally) · [Tech Stack](#%EF%B8%8F-tech-stack)

</div>

---

## 📺 Demo

🎥 **Watch it in action:** [youtu.be/eskxAeMf5bg](https://youtu.be/eskxAeMf5bg)

<div align="center">

https://github.com/user-attachments/assets/d654f6aa-3a0c-4d9b-952c-a05b1ec11bcb

https://github.com/user-attachments/assets/bbf30b77-edf9-4249-a920-19e6b752611b

https://github.com/user-attachments/assets/22391206-f111-4b1b-8b4b-157cbe97f80e

https://github.com/user-attachments/assets/f44a516d-1285-4ea9-a064-acd70e66339b

</div>

🔗 **Repository:** [github.com/RachanaB5/PressureLab-AI](https://github.com/RachanaB5/PressureLab-AI)

---

## 🌍 The Problem

Football analytics platforms today can tell you:

| What they show | What's missing |
|---|---|
| ⚽ Goals | ❌ Why the decision was made |
| 📊 Possession | ❌ What pressure the player faced |
| 📈 xG | ❌ What other options existed |
| 🎯 Passes | ❌ How a different coach would've played it |
| 🗺️ Heatmaps | ❌ The tactical *reasoning* behind the moment |

They rarely answer the one question that actually matters to coaches and analysts:

> ### "Why did this decision happen?"

**PressureLab AI** transforms raw football events into **explainable tactical intelligence** — breaking down player decisions, pressure, passing options, alternatives, and coaching philosophy in plain language.

---

## 💡 Our Solution

PressureLab AI builds a **Digital Match Twin** of real football matches, then layers explainable AI on top of it.

With it, you can:

- 🔍 **Search** any supported match
- 📚 **Browse** the Match Library
- ⏱️ **Jump** directly to key moments
- 🔁 **Replay** tactical situations
- 💬 **Ask** the AI questions about any event
- 🎓 **Compare** how different coaches would respond

Instead of rewatching 90+ minutes of football, you understand the tactical story behind every key moment in seconds.

---

## ✨ Key Features

### ⚽ Digital Match Twin
A live tactical recreation of every key moment — dynamic player positions, passing lanes, pressure zones, dangerous spaces, and full tactical replay.

### 🕵️ Tactical Detective
Explainable AI that answers the hard questions:
- Why did this happen?
- What were the alternatives?
- What was the safest decision?
- What was the riskiest decision?

### 🤖 AI Copilot
Ask natural-language questions, grounded entirely in the selected event:

> *"Why didn't Messi pass?"*
> *"Was Mbappé under pressure?"*
> *"What was the best option here?"*

### 🎓 Coach Perspectives
See how the same moment would be read through different tactical philosophies:

`Pep Guardiola` · `Jürgen Klopp` · `José Mourinho` · `Carlo Ancelotti` · `AI Tactical Coach`

### 📚 Historical Similarity
Surfaces similar tactical situations from past matches and shows how they unfolded — context, not just commentary.

---

## 🧠 AI Architecture

```
                    StatsBomb Event Data
                            │
                            ▼
                    Tactical Snapshot
                            │
                            ▼
                      IBM Docling
             (Football Reports & PDFs)
                            │
                            ▼
                     Context Forge
         (Contextual Memory & Retrieval)
                            │
                            ▼
                       LangFlow
            (AI Workflow Orchestration)
                            │
                            ▼
                      IBM Granite
           (Explainable Tactical Reasoning)
                            │
                            ▼
            Tactical Detective & AI Copilot
```

---

## 🛠️ IBM Technologies Used

| Technology | Role |
|---|---|
| **IBM Granite** | Primary reasoning engine — generates explainable tactical analysis from player position, match state, defensive pressure, passing options, and tactical context |
| **LangFlow** | Orchestrates the AI workflow: `Event → Context Retrieval → Reasoning → Explanation` |
| **Docling** | Processes football reports into structured knowledge — extracts tactical descriptions, match reports, and contextual information |
| **Context Forge** | Provides contextual retrieval and memory, so Granite generates context-aware explanations instead of generic football commentary |
| **IBM Bob Learning Lab** | Concepts incorporated into the explainable football analytics workflow |

Built for the **IBM SkillsBuild AI Builders Challenge 2026**.

---

## 🏗️ Tech Stack

<table>
<tr>
<td valign="top" width="25%">

**Frontend**
- React
- TypeScript
- Tailwind CSS
- Vite

</td>
<td valign="top" width="25%">

**Backend**
- FastAPI
- Python

</td>
<td valign="top" width="25%">

**AI**
- IBM Granite
- LangFlow
- Docling
- Context Forge

</td>
<td valign="top" width="25%">

**ML & Data**
- Scikit-learn
- StatsBomb Open Data

</td>
</tr>
</table>

---

## 📂 Project Structure

```
PressureLab-AI/
├── frontend/      # React + TypeScript + Tailwind UI
├── backend/       # FastAPI service
├── scripts/       # Data & utility scripts
├── docs/          # Documentation
└── README.md
```

---

## ⚙️ Running Locally

### 1. Clone the repo

```bash
git clone https://github.com/RachanaB5/PressureLab-AI.git
cd PressureLab-AI
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## 🔑 Environment Variables

Create a `.env` file in the backend directory:

```env
HF_TOKEN=your_huggingface_token
DATABASE_URL=sqlite:///./pressurelab.db
SECRET_KEY=your_secret
CACHE_VERSION=v9
```

---

## 🎯 Future Improvements

- [ ] Live football match analysis
- [ ] Multi-camera tactical reconstruction
- [ ] Automatic event detection from video
- [ ] Real-time coaching assistant
- [ ] Player tracking from broadcast footage
- [ ] Tactical recommendation engine

---

## 📈 Why PressureLab AI?

Most platforms answer **what happened**.

**PressureLab AI answers *why* it happened.**

That's the difference.

---

## 👩‍💻 Authors

| Name | GitHub |
|---|---|
| **Rachana Bhaskar Gowda** | [@RachanaB5](https://github.com/RachanaB5) |
| **Saatwik Kumar Yadav** | [@skypank-coder](https://github.com/skypank-coder) |

---

<div align="center">

### ⭐ If you enjoyed this project, consider giving the repo a star — it really helps!

</div>
