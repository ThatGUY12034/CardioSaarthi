# Running CardioSaarthi on another laptop

Written for the panel demonstration: a laptop that has never run this project, brought to a
working demo in about half an hour, most of which is downloads.

> **Docker Desktop is the only thing that has to be installed.** The containers carry their own
> JDK and Node, the case bank seeds itself from the repository, and the rendered ECGs download
> once from a release asset. Nothing is copied by USB.

---

## 1. Get it — clone and run

Nothing has to be copied by hand. Everything comes from GitHub: the code and the case bank from the
repository, and the 479 MB of rendered ECGs from a release asset the setup script downloads once.

Install **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** and open it, wait
until it says *Running*. That is the only prerequisite — the containers carry their own JDK and
Node, so neither has to be installed.

```powershell
git clone https://github.com/ThatGUY12034/CardioSaarthi.git
```

```powershell
cd CardioSaarthi; copy demo\env.demo .env
```

```powershell
powershell -ExecutionPolicy Bypass -File demo\setup.ps1
```

The script downloads the ECGs (479 MB, once), checks the download against a committed SHA-256 so a
truncated file is caught rather than extracted, and unpacks them into `artifacts\images`.

## 2. Start it — one command

```powershell
docker compose --profile demo up -d --build
```

The first run builds the two images and takes roughly ten minutes: Maven and npm are downloading
their dependencies inside the build. Later runs start in about twenty seconds.

Watch it come up, and stop watching once the API reports healthy:

```powershell
docker compose --profile demo ps
```

Then open **<http://localhost:5173>**.

| Role | Login | Password |
|---|---|---|
| Faculty | `TE/1234` | `1234` |
| Student | `TE/4321` | `1234` |

> Those four-digit passwords exist only because they are easy to type in front of an audience.
> They come from `CARDIO_DEMO_ACCOUNTS`, which is off by default; every account made through the
> API still needs twelve characters. Do not switch this on anywhere other people can reach.

The case bank loads itself. PostgreSQL runs everything in `demo/seed` the first time it creates its
data directory, so the 714 cases, their nine computed parameters and the 632 written vignettes are
there before the API connects. Flyway finds its own migration history inside that seed and applies
nothing on top.

## 3. Stopping and restarting

```powershell
docker compose --profile demo down
```

That leaves the database intact. To start again, repeat the `up` command — without `--build`, since
the images already exist.

## 4. The development loop, for comparison

`docker compose up -d` on its own starts **only** PostgreSQL, which is what you want while working
on the code: the API then runs from `./mvnw spring-boot:run` and the interface from `npm run dev`,
both with hot reload. That path needs JDK 21 and Node 20 installed. The demo profile exists so a
presentation machine does not.

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
