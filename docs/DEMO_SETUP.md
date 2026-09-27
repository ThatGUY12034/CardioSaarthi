# Running CardioSaarthi on another laptop

Written for the panel demonstration: a laptop that has never run this project, brought to a
working demo in about half an hour, most of which is downloads.

> **A `git clone` on its own is not enough, and this is the one thing to get right.**
> Two things the demo needs are deliberately not in git: the 461 MB of rendered ECG images, and
> the database itself. Both have to be copied across. Clone-only gives you an app that starts,
> shows no ECGs, and has no cases.

---

## 1. What to carry across

Put these on a USB drive or in a shared folder. About **480 MB** in total.

| What | Where it goes | Size | Why |
|---|---|---|---|
| The repository | anywhere, e.g. `C:\CardioSaarthi` | ~10 MB | the code |
| `artifacts\images\` | inside the repository, same path | 461 MB | the rendered ECGs. The database refers to them by this path, so the folder name matters |
| `artifacts\handover\cardiosaarthi-db.sql` | inside the repository, same path | 12 MB | 714 measured cases, the nine parameters for each, and 632 written vignettes |

**`data\` is not needed.** That is 203 MB of raw PhysioNet recordings, used only to re-run the
measurement pipeline or the validation suite. The demo reads already-measured values.

The simplest way to be sure nothing is missed: copy the whole `CardioSaarthi` folder, and skip
only `data`, `.venv`, `node_modules` and `review-api\target`.

---

## 2. What to install

Three things, in any order. All free, all default options.

| | Version | Note |
|---|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | latest | **open it once and wait until it says Running** before the next step |
| [JDK 21 or newer](https://adoptium.net/) | 21+ | Temurin. Tick "Set JAVA_HOME" if the installer offers it |
| [Node.js](https://nodejs.org/) | 20+ | the LTS download |

Then **close and reopen the terminal**, so it picks up the new commands.

---

## 3. Set it up — one command

Open PowerShell in the repository folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File demo\setup.ps1
```

It checks the three installs, writes the configuration, starts the database, loads the 714 cases
and installs the frontend's packages. It says what it is doing at each step and stops with a plain
explanation if something is missing. Running it twice is safe: it never overwrites a database that
already has cases in it.

The first run takes a few minutes, mostly downloading the PostgreSQL image.

---

## 4. Start it — two terminals

Leave both open for the whole demonstration. Their logs are worth having on screen if the panel
asks what is happening.

**Terminal 1 — the backend.** Wait for `Started ReviewApiApplication`. The first run also downloads
Maven and the dependencies, which takes a few minutes; later runs take about twenty seconds.

```powershell
cd review-api; .\mvnw spring-boot:run
```

**Terminal 2 — the interface.**

```powershell
cd frontend; npm run dev
```

Then open **<http://localhost:5173>**.

| Role | Login | Password |
|---|---|---|
| Faculty | `TE/1234` | `1234` |
| Student | `TE/4321` | `1234` |

> Those four-digit passwords exist only because they are easy to type in front of an audience.
> They come from `CARDIO_DEMO_ACCOUNTS`, which is off by default; every account made through the
> API still needs twelve characters. Do not switch this on anywhere other people can reach.

---

## 5. A run of show

An order that demonstrates the architecture rather than just the screens.

1. **Student — practise a case.** Pick a case, work through the nine-step reading. Zoom the ECG.
   Finish and show the result page: each step marked, with the error named where it was wrong.
   The point to make: *nothing on this page was written by a model.* Every mark compares the
   answer against a number computed from the waveform.
2. **Student — a deliberately wrong answer.** Give a PR interval on a case with no P waves.
   It is not marked "wrong" generically; it is `PR_REPORTED_WHEN_ABSENT`, a named clinical mistake.
3. **Faculty — the review queue.** Expand a case, show the nine computed parameters with their
   spread and confidence, and correct one. Show that the engine's original value is still there
   beside the correction. That difference is the pipeline-accuracy evidence, and it is why nothing
   is ever edited in place.
4. **Faculty — the approval gate.** 714 cases measured, 9 approved. An unapproved case returns
   nothing to a student, enforced in the database rather than in the interface. This is the answer
   to "how do you know a student is never shown a wrong value".

**Expect this question:** *714 cases but only 9 usable?* The honest answer is that the gate is
working as designed — a case reaches a student when a named person has approved it, and faculty
review is the project's critical path, not a step that can be skipped. The remaining cases are
measured and queued, waiting on review capacity.

---

## 6. If something goes wrong

| Symptom | Cause and fix |
|---|---|
| `docker compose` fails | Docker Desktop is not running. Open it, wait for **Running**, run the setup again |
| Every ECG is a broken image | `artifacts\images` was not copied, or landed at the wrong path. It must sit at `<repo>\artifacts\images` |
| Login says the credentials are wrong | `CARDIO_DEMO_ACCOUNTS=true` must be in `.env`, and the backend restarted after it was set |
| No cases anywhere | the dump was not restored. Run the setup script again; it reports what it found |
| `Port 8090 is already in use` | something else on that laptop has it. Change `REVIEW_API_PORT` in `.env` **and** the port in `frontend\.env.local` to match |
| `Port 5432 is already in use` | an existing PostgreSQL install. This project already uses 55432 to avoid exactly that, so check `POSTGRES_PORT` in `.env` |
| The backend exits saying the signing key is too short | `CARDIO_JWT_SECRET` needs 32+ characters |
| The interface loads but every request fails | the backend is not up yet. Wait for `Started ReviewApiApplication` |

### Offline as a precaution

Assume the venue has no usable Wi-Fi. Run the whole thing through once on that laptop **while
still on a good connection** — that pulls the PostgreSQL image, the Maven dependencies and the npm
packages onto the disk. After one successful run the demo needs no network at all: nothing calls
out to a model or a dataset at run time.

---

## 7. Refreshing the dump later

If the case bank or the approvals change on the machine that owns the pipeline, take a new dump
and copy it across:

```bash
docker exec cardiosaarthi-postgres pg_dump -U cardiosaarthi -d cardiosaarthi --no-owner --no-privileges > artifacts/handover/cardiosaarthi-db.sql
```

The dump carries Flyway's migration history with it, so the backend sees the schema as already
current and applies nothing on top.
