# Build Journal

A plain-English record of what I did on this project, why, and what I learned. Technical details and exact evidence live in [EXPERIMENTS.md](EXPERIMENTS.md). New entries go at the end; old entries are not rewritten.

---

# Milestone 1: Local Feasibility

## 1. Started with feasibility instead of implementation

### What I was trying to prove
Whether this project was realistic at all on my own machine and budget, before writing any agent code.

### What I did
I started by treating the project as a feasibility problem instead of immediately building features. I broke the system into its major layers and planned to test each one on its own:
- the official evaluation harness
- the sandbox that runs repository code
- the verification step that grades a patch
- the language model
- the connection between the model and the harness

### Why I did it this way
A coding agent is a stack of parts that all have to work together. If I had started building features and something failed, I wouldn't know which layer was to blame. **Feasibility testing** means proving the risky assumptions first, cheaply, before committing to an architecture. **Layered testing** means checking each layer separately, so that when something breaks, the cause is obvious.

### What happened
This shaped the whole milestone. Each step below proved one layer, and only then moved to the next.

### What failed or surprised me
Nothing yet. This was a planning decision.

### What I learned
Deciding what to prove first is itself an engineering decision.

### What changed because of this
Milestone 1 became "prove the stack works end to end once" rather than "build the agent".

---

## 2. Checked whether my machine could support the project

### What I was trying to prove
Whether my PC could run the harness, a sandbox and some kind of real model.

### What I did
I took stock of the hardware and software: Windows 11 with WSL2 (a Linux environment running inside Windows), Docker Desktop, and an RTX 3070 graphics card with 8 GB of video memory.

### Why I did it this way
The competition's required model is a 31-billion-parameter model. I needed to know early whether it could possibly run locally, because that decides the whole development approach.

### What happened
The machine is fine for the harness and for Docker. It is not big enough for the competition model, which needs roughly twice my GPU memory just for its weights.

### What failed or surprised me
The Windows desktop already uses about 2 GB of the 8 GB of GPU memory, so the real budget is smaller than the spec sheet suggests.

### What I learned
Know the hard limits before designing around them.

### What changed because of this
I accepted early that local development would need a smaller stand-in model, and that the exact competition model would be a separate, occasional profile.

---

## 3. Inspected the official competition harness and starter materials

### What I was trying to prove
What the organizers actually provide, and the minimum I needed to download.

### What I did
I read the competition pages, the organizers' starter notebook and the harness guide. Then I downloaded only a small, verified subset: the task list, one repository snapshot, the sandbox files, the sample submission and the harness packages.

### Why I did it this way
The full dataset is over 22 GB. Downloading everything "just in case" wastes time and disk space, and hides what actually matters. I picked one small, clear task (`requests_6644`, a URL path bug in the `requests` library) to use throughout.

### What happened
I found that the organizers ship a complete evaluation harness called `swegemma`. It runs an agent against a task, collects the agent's changes as a **Git patch** (a text file describing exactly which lines changed), and then grades that patch.

### What failed or surprised me
The harness packages weren't in the competition's data section. I had to trace them through the starter notebook to a separate official dataset. I also found that the submission's budget file isn't read by the local command-line tool at all; the command-line flags control the limits.

### What I learned
Read the official code, not just the documentation. Some of what I found wasn't mentioned anywhere.

### What changed because of this
I decided to treat the official harness as canonical and build on it rather than write my own.

---

## 4. Proved the harness control plane could run without the heavy model stack

### What I was trying to prove
Whether I could run the harness itself without installing gigabytes of GPU and machine-learning software.

### What I did
I installed the harness packages without their declared dependencies, then added only what each real import demanded, one small package at a time, until the harness's command-line tool worked.

### Why I did it this way
A normal install would have pulled in PyTorch and the NVIDIA CUDA libraries, several gigabytes, even though the harness itself doesn't do model inference. I wanted to keep the part that *controls* the evaluation separate from the part that *runs* the model.

### What happened
It worked. The harness's control plane (loading tasks, managing sandboxes, grading) runs with only lightweight packages.

### What failed or surprised me
Some "optional" features are imported unconditionally. For example, the agent framework loads a Google Cloud Storage client even though I never use Google Cloud.

### What I learned
Declared dependencies and actual dependencies are different things. Testing real imports tells you what's truly required.

### What changed because of this
The development machine stays light. The model runs in its own container instead of inside the harness environment.

---

## 5. Tried subprocess sandboxing and learned why environment reproducibility matters

### What I was trying to prove
Whether the harness could set up and test the repository using its simpler "subprocess" mode, which doesn't need Docker.

### What I did
I ran the harness on my task in subprocess mode, skipping the agent entirely.

### Why I did it this way
A **sandbox** is an isolated place where untrusted code (the repository and whatever the agent does to it) can run without touching the rest of the system. Subprocess mode is the lighter option, so I tried it first.

### What happened
It failed before it even unpacked the repository. Ubuntu's version of Python is missing a component the harness needs to create environments. Ubuntu's Python also exits the whole program in that situation instead of raising an error the harness could catch.

### What failed or surprised me
The failure had nothing to do with my task or my code. It came from how the host operating system packages Python. Subprocess mode also uses whatever Python version the host has (3.12), not the 3.13 the official sandbox uses.

### What I learned
**Reproducibility** means the same inputs give the same results on any machine. Anything that depends on the host machine's setup is a reproducibility risk.

### What changed because of this
I dropped subprocess mode rather than modify my system Python, and moved to Docker.

---

## 6. Switched to Docker and built the official sandbox

### What I was trying to prove
Whether the organizers' official sandbox image could be built and run on my machine.

### What I did
I built the Docker image from the organizers' unmodified Dockerfile, then checked it: Python version, test runner, working directory, and whether memory and CPU limits are enforced.

### Why I did it this way
A Docker image packages its own operating system and Python, so it behaves the same everywhere. That directly fixes the reproducibility problem from the previous step, and it matches how the competition itself runs.

### What happened
It built cleanly into a 387 MB image with Python 3.13. The harness's per-container limits (4 GB of memory, 2 CPUs) were enforced.

### What failed or surprised me
Only one small thing: inside a limited container, the system still reports all 16 CPU cores, even though only 2 can actually be used.

### What I learned
Using the official environment is worth more than using a convenient one.

### What changed because of this
Docker became the accepted local sandbox.

---

## 7. Proved clean verification works without an agent

### What I was trying to prove
That the grading step works on its own, before bringing any model into it.

### What I did
I ran the full harness on the task with the agent step switched off. The repository stays unfixed, the official tests are added, and the tests run.

### Why I did it this way
The grading happens in a **clean verification container**: a fresh sandbox where only the patch and the official tests are applied, so the agent can't influence the result. I wanted to see that part working in isolation.

### What happened
The test failed, and the result was `resolved=false`. That was exactly right.

### What failed or surprised me
Nothing failed. The useful surprise was how informative a "failure" can be.

### What I learned
**Why `resolved=false` was useful here:** it proved the task's test really does detect the bug. If the test had passed without a fix, a later "success" would have meant nothing. A baseline failure makes a later pass meaningful.

### What changed because of this
I trusted the grading layer, so any later result would reflect the agent's work and not a harness quirk.

---

## 8. Chose a smaller local Gemma model for development

### What I was trying to prove
Which real model I could use for everyday development at no cost.

### What I did
I compared options and chose Google's official Gemma 4 E4B instruction-tuned model, in a 4-bit compressed format. I serve it with llama.cpp, a lightweight inference server, in a Docker container that uses my GPU.

### Why I did it this way
**Model serving** means running a model behind a web API that other programs can call. llama.cpp can present the same kind of API the harness already expects, so the harness can talk to it without changes. The E4B model was the largest Gemma 4 model I expected to fit in my GPU memory at the harness's full 32,000-token context.

### What happened
This became the "dev profile". The competition's 31B model stays a separate "exact profile", used only when practical.

### What failed or surprised me
Nothing yet at this point.

### What I learned
**Local surrogate vs exact competition model:** a surrogate is a stand-in that behaves similarly enough to develop against, but it isn't the real thing. It's much weaker than the 31B model, so it tests the plumbing, not competitive quality.

### What changed because of this
Development could stay local and free.

---

## 9. Proved the model could make structured tool calls

### What I was trying to prove
Whether the local model could actually run on my GPU at full context and answer in the structured format an agent needs.

### What I did
I downloaded Google's official model file, checked its fingerprint (checksum), started the server and sent it three kinds of requests: a plain message, a tool request, and a request under a different model name.

### Why I did it this way
**Structured tool calling** is how an agent acts. Instead of replying in prose, the model returns a machine-readable instruction such as "call `read_file` with this path and these line numbers". If the model can't do that reliably, nothing else matters.

### What happened
- The model loaded fully onto the GPU at 32K context, using about 3.4 GB of video memory.
- It answered the plain message exactly.
- It returned a correctly formed `read_file` call with the right arguments.
- It also accepted a different model name, which removed a routing worry for later.

### What failed or surprised me
The server image was larger than I expected (about 7 GB), and the model used less GPU memory than I estimated. My estimates were off in both directions.

### What I learned
Measure; don't trust estimates.

### What changed because of this
It was now justified to connect the real model to the real harness.

---

## 10. Connected the real model to the real harness

### What I was trying to prove
Whether the harness could send its requests to my local model without changing the competition submission.

### What I did
I read the harness code to find the exact format of its model configuration file. Then I wrote a small development file, kept outside the repository, that redirects the competition model's name to my local server.

### Why I did it this way
The submission names the 31B competition model. Rather than edit the submission, which must stay competition-valid, I used the harness's own supported mechanism to point that name somewhere else during development. The submission stays untouched.

### What happened
The mapping worked on the first check: all three names the submission uses pointed at my local model.

### What failed or surprised me
I found that the local command-line tool ignores the submission's budget file, so the budgets I set on the command line are the ones that apply.

### What I learned
**Deterministic controls vs model reasoning:** the harness, not the model, decides the limits (how many tool calls, how much time), which files are reachable, how the patch is extracted and whether the tests pass. The model only decides what to investigate and what to change. Keeping that line clear is what makes results trustworthy.

### What changed because of this
The dev profile became a configuration choice, not a code change.

---

## 11. Fixed missing runtime dependencies without changing the architecture

### What I was trying to prove
That the remaining blockers were missing packages, not design problems.

### What I did
When the real model calls started, more small packages turned out to be required by the libraries that send requests. I added them one at a time, each with a size check, within a fixed limit, and stopped whenever that limit would be exceeded so the owner could decide.

### Why I did it this way
Small, visible, reversible steps. Every addition had a clear reason, nothing heavy was allowed in, and I never modified the harness itself.

### What happened
My first full run failed after 8 seconds, before the model was ever called. The agent framework loads an authentication library (`authlib`) only when it builds the full agent pipeline. My pre-check had tested the model directly, not through that pipeline. I added that library plus one of its dependencies, re-checked using the *real* pipeline this time, and then ran again.

### What failed or surprised me
My own pre-check had a blind spot. It passed while the real path still failed.

### What I learned
A test only covers the path it actually exercises. Pre-checks should use the same route as the real run.

### What changed because of this
Later checks go through the real agent pipeline, not a shortcut.

---

## 12. Completed the first end-to-end coding-agent run

### What I was trying to prove
That a real model could drive the whole official loop: investigate, edit, test, submit, and be graded independently.

### What I did
I ran the harness once on `requests_6644` with the local model and the unmodified sample submission, with limits of 30 tool calls and 20 minutes.

### Why I did it this way
One bounded run with no retries gives honest evidence. Repeating until it works would hide how reliable it really is.

### What happened
In about a minute, the model:
1. read four files to find where URLs are handled;
2. edited `src/requests/models.py` so that paths starting with several slashes are reduced to a single slash;
3. ran a nearby test file (20 tests passed);
4. submitted a small patch.

The clean verification container then applied the official test to that patch, and it passed: `resolved=true`.

### What failed or surprised me
Nothing failed. It was faster and more direct than I expected. The model also didn't run the task's own target test; it chose a related one.

### What I learned
**Why `resolved=true` here is strong evidence:** the same test that failed on the unfixed code in step 7 passed on the agent's patch. The grading happened in a separate clean container, and the model had no say in the verdict.

### What changed because of this
Milestone 1's goal was met.

---

## 13. What Milestone 1 proved and what it did not prove

### What I was trying to prove
Whether this project is feasible on my machine at no cost.

### What I did
I reviewed all the evidence together (see [EXPERIMENTS.md](EXPERIMENTS.md)).

### Why I did it this way
To avoid overstating the result.

### What happened
**Proved:** every layer works together locally:
- the official harness
- the Docker sandbox and clean verification
- a real Gemma model on my GPU
- structured tool calling
- a full investigate → edit → test → submit → verify loop

All at $0, with the competition submission unchanged.

**Not proved:** this was **one easy task with one smaller surrogate model**. It says nothing yet about:
- how often the agent succeeds across many tasks
- how the 31B competition model behaves
- whether the graph tools or sub-agents help
- competition score or production readiness

### What failed or surprised me
Most of the real friction was packaging and environment, not model quality.

### What I learned
**Why one success proves feasibility but not performance:** a single pass shows the path exists. Performance is a rate, measured over many tasks and repeated runs. That needs a reproducible evaluation setup, which I don't have yet.

### What changed because of this
The next milestone is about a baseline agent and reproducible evaluation. Its scope will be reviewed and approved before any work starts (see [ROADMAP.md](ROADMAP.md)).

---

## 14. Checking the benchmark before using it, and why the design changed

*This is a progress entry. Milestone 2 is not finished.*

### What I was trying to prove
That the small set of tasks I planned to measure (4 fastapi, 3 rich and 1 requests) could each be trusted as a fair test. A task is only useful if, on the unfixed code, its test really fails because of the bug, and if the test really exercises the code the agent will edit.

### What I did
I picked candidate tasks with a fixed rule (a hash of the task name, so I couldn't cherry-pick). Then I ran each one through the official sandbox with no model at all, just to see whether its tests fail in the right way. I call this the eligibility gate. Details and evidence are in [EXPERIMENTS.md](EXPERIMENTS.md).

### Why I did it this way
Measuring an agent on a task that is broken, or that secretly tests different code from what the agent edits, produces numbers that look meaningful but aren't. Checking first is cheap. Discovering it after 27 model runs would not be.

### What happened
Four things turned up:
1. **One rich task hung.** Its new test never finished and was stopped after 300 seconds. It doesn't fail cleanly, so I ruled it out and fixed a rule for that case.
2. **The harness keeps a hidden cache.** It unpacks the Python packages the tests need into a temporary folder the first time it runs, and never checks that folder again. The folder from Milestone 1 held only four packages, so every later run used that tiny setup no matter which packages I downloaded. Milestone 1's result was measured in that environment. I deleted only that folder, and the harness rebuilt it from the full official set.
3. **FastAPI can't run here.** A package it needs (`typing_inspection`) isn't in the official package collection, so fastapi tasks fail to even load.
4. **Requests tests the wrong code.** With the full package set, a ready-made copy of `requests` is installed, and the tests import that copy instead of the code the agent edits. So an untouched task already "passes", and an agent's changes would never be tested.

### What failed or surprised me
The hidden cache. The failure it caused looked like a missing package, and only reading the harness code showed that my downloads were being ignored. It also means my Milestone 1 pass, though genuine, ran in a smaller environment than I thought.

### What I learned
**Reproducibility:** a result is only comparable if the environment behind it is the same every time. A leftover temporary folder can silently change that environment, so the plan now has to rebuild it at fixed points and write down a fingerprint (a short code that changes if any file changes) to prove nothing drifted.

### What changed because of this
I stopped trying to force the original mix of repositories. Doing that would have meant adding packages from outside the official materials, which would make my benchmark differ from the competition's. Instead the benchmark is now 8 Rich tasks, run 3 times each, on the complete unmodified official package set. The requests positive control is gone, replaced by re-running the gates after the baseline to check that the environment stayed the same. The trade-off is that results describe Rich only. The roadmap records this.

### What came next
Download the rest of the official package set, rebuild the cache, and check Rich candidates one by one until 8 pass the gate or I've looked at 16.
