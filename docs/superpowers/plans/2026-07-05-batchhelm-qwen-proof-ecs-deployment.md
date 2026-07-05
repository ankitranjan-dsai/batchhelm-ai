# BatchHelm Qwen Proof And ECS Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a secure, persisted live-Qwen verification receipt and a
reproducible single-replica Alibaba Cloud ECS deployment bundle that can produce
the public URL and evidence required by the hackathon.

**Architecture:** Keep the existing OpenAI-compatible Qwen gateway and upgrade
its default models to current Qwen Cloud recommendations. A token-protected
probe performs one minimal structured request, stores only redacted receipt
metadata in SQLite, and exposes the latest receipt through a read-only endpoint.
Alibaba ECS runs one API container and one web container from a hardened
production Compose file, with `/data` on a host-mounted durable directory and
the API reachable only through the web reverse proxy.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite, httpx, pytest, Docker
Compose, nginx, POSIX shell, Alibaba Cloud ECS, Qwen Cloud

---

## Authoritative Requirements

- Hackathon deadline: July 9, 2026 at 2:00 PM Pacific Time.
- Qwen Cloud base URL:
  `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`.
- Recommended text model: `qwen3.7-plus`.
- Recommended dedicated vision model: `qwen3-vl-plus`.
- The submission needs a working test URL and proof that the backend is running
  on Alibaba Cloud.
- The current SQLite lifecycle permits exactly one API replica.
- Secrets must enter at runtime and must never appear in source, logs, proof
  receipts, or container images.
- Repository authorship and commits remain Ankit Ranjan only.

Primary references:

- `https://qwencloud-hackathon.devpost.com/rules`
- `https://qwencloud-hackathon.devpost.com/resources`
- `https://docs.qwencloud.com/developer-guides/getting-started/first-api-call`
- `https://docs.qwencloud.com/developer-guides/getting-started/text-generation-models`
- `https://docs.qwencloud.com/developer-guides/getting-started/vision-models`
- `https://www.alibabacloud.com/help/en/ecs/user-guide/customize-the-initialization-configuration-for-an-instance`

## Task 1: Align Runtime Defaults With Current Qwen Cloud

**Files:**
- Create: `services/api/tests/test_config.py`
- Modify: `services/api/src/batchhelm_api/config.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`

- [x] **Step 1: Write the failing configuration contract test**

Create `services/api/tests/test_config.py`:

```python
from batchhelm_api.config import Settings


def test_qwen_cloud_defaults_use_current_supported_models() -> None:
    settings = Settings(_env_file=None)

    assert str(settings.qwen_base_url) == (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    )
    assert settings.qwen_text_model == "qwen3.7-plus"
    assert settings.qwen_vision_model == "qwen3-vl-plus"
```

- [x] **Step 2: Run the test and verify the old defaults fail**

Run:

```bash
cd services/api
.venv/bin/pytest -q tests/test_config.py
```

Expected: failure showing `qwen-plus` instead of `qwen3.7-plus`.

- [x] **Step 3: Update the defaults**

Set these defaults in `config.py`, `.env.example`, and `docker-compose.yml`:

```text
QWEN_TEXT_MODEL=qwen3.7-plus
QWEN_VISION_MODEL=qwen3-vl-plus
```

- [x] **Step 4: Verify the configuration contract**

Run:

```bash
cd services/api
.venv/bin/pytest -q tests/test_config.py tests/test_qwen_gateway.py
```

Expected: all selected tests pass.

- [x] **Step 5: Commit and push the Qwen Cloud alignment**

Run:

```bash
git add \
  .env.example \
  docker-compose.yml \
  services/api/src/batchhelm_api/config.py \
  services/api/tests/test_config.py
git commit --author="Ankit Ranjan <ankit0ranjan@gmail.com>" \
  -m "feat(qwen): align runtime defaults with Qwen Cloud"
git push origin main
```

## Task 2: Add A Redacted Live-Qwen Verification Receipt

**Files:**
- Modify: `services/api/src/batchhelm_api/models.py`
- Modify: `services/api/src/batchhelm_api/qwen.py`
- Modify: `services/api/tests/test_qwen_gateway.py`

- [x] **Step 1: Write the failing gateway probe tests**

Add tests that require `QwenGateway.verify_live()` to:

```python
@pytest.mark.asyncio
async def test_live_verification_returns_redacted_provider_receipt() -> None:
    # MockTransport returns an OpenAI-compatible response with id
    # "chatcmpl-batchhelm-proof".
    receipt = await gateway.verify_live()

    assert receipt.provider == "qwen-cloud"
    assert receipt.verified is True
    assert receipt.model == "qwen-plus"
    assert receipt.provider_request_id == "chatcmpl-batchhelm-proof"
    assert receipt.latency_ms >= 0
    assert len(receipt.response_sha256) == 64
    assert "test-key" not in receipt.model_dump_json()


@pytest.mark.asyncio
async def test_live_verification_requires_a_configured_key() -> None:
    with pytest.raises(QwenGatewayError, match="not configured"):
        await QwenGateway(make_settings()).verify_live()
```

- [x] **Step 2: Run the tests and verify the method is missing**

Run:

```bash
cd services/api
.venv/bin/pytest -q \
  tests/test_qwen_gateway.py::test_live_verification_returns_redacted_provider_receipt \
  tests/test_qwen_gateway.py::test_live_verification_requires_a_configured_key
```

Expected: failure because `verify_live` does not exist.

- [x] **Step 3: Add the receipt model**

Add `QwenVerificationReceipt` to `models.py`:

```python
class QwenVerificationReceipt(BaseModel):
    provider: str = "qwen-cloud"
    verified: bool = True
    model: str
    base_url: str
    provider_request_id: str | None = None
    latency_ms: int = Field(ge=0)
    response_sha256: str = Field(min_length=64, max_length=64)
    verified_at: str
```

- [x] **Step 4: Implement the minimal live probe**

Add `verify_live()` to `QwenGateway`. It must:

1. reject an empty API key;
2. POST a low-temperature JSON-object request to `/chat/completions`;
3. require `{"status":"verified","service":"batchhelm"}`;
4. derive a SHA-256 fingerprint from the raw response text;
5. record the provider response `id`, elapsed milliseconds, model, base URL,
   and UTC timestamp;
6. never include request headers, API keys, or response text in the receipt.

- [x] **Step 5: Run all gateway tests**

Run:

```bash
cd services/api
.venv/bin/pytest -q tests/test_qwen_gateway.py
```

Expected: all gateway tests pass.

## Task 3: Persist And Expose Qwen Verification Safely

**Files:**
- Create: `services/api/src/batchhelm_api/qwen_verification_repository.py`
- Create: `services/api/tests/test_qwen_verification_repository.py`
- Modify: `services/api/src/batchhelm_api/config.py`
- Modify: `services/api/src/batchhelm_api/app.py`
- Modify: `services/api/tests/test_api.py`

- [x] **Step 1: Write failing SQLite repository tests**

Define the expected repository behavior:

```python
def test_sqlite_repository_returns_none_before_first_receipt(tmp_path: Path) -> None:
    repository = SQLiteQwenVerificationRepository(tmp_path / "proof.db")
    repository.initialize()
    assert repository.latest() is None


def test_sqlite_repository_persists_latest_receipt(tmp_path: Path) -> None:
    repository = SQLiteQwenVerificationRepository(tmp_path / "proof.db")
    repository.initialize()
    repository.save(build_receipt("request-one", "2026-07-05T10:00:00Z"))
    repository.save(build_receipt("request-two", "2026-07-05T10:01:00Z"))

    latest = repository.latest()
    assert latest is not None
    assert latest.provider_request_id == "request-two"
```

- [x] **Step 2: Run the repository tests and verify the import fails**

Run:

```bash
cd services/api
.venv/bin/pytest -q tests/test_qwen_verification_repository.py
```

Expected: failure because the repository module does not exist.

- [x] **Step 3: Implement the repository**

Create:

```python
class QwenVerificationRepository(Protocol):
    def initialize(self) -> None: ...
    def save(self, receipt: QwenVerificationReceipt) -> None: ...
    def latest(self) -> QwenVerificationReceipt | None: ...


class SQLiteQwenVerificationRepository:
    # SQLite table qwen_verification_receipts stores only the receipt fields.
```

Use WAL mode, a busy timeout, explicit transactions, and newest-first ordering.
Wrap `sqlite3.Error` as `QwenVerificationStoreUnavailable`.

- [x] **Step 4: Verify repository persistence**

Run:

```bash
cd services/api
.venv/bin/pytest -q tests/test_qwen_verification_repository.py
```

Expected: both repository tests pass.

- [x] **Step 5: Write failing API security and proof tests**

Add API tests for:

- `GET /api/qwen/proof` returns `404` before a successful verification;
- `POST /api/qwen/verify` returns `503` when `QWEN_PROOF_TOKEN` is unset;
- a wrong `X-BatchHelm-Proof-Token` returns `403`;
- the correct token calls the injected live gateway, stores the receipt, and
  makes it available through `GET /api/qwen/proof`;
- the public receipt contains no API key or prompt/response body.

- [x] **Step 6: Run the new API tests and verify endpoint failure**

Run:

```bash
cd services/api
.venv/bin/pytest -q tests/test_api.py -k "qwen_proof or qwen_verify"
```

Expected: failure because the endpoints do not exist.

- [x] **Step 7: Add settings and endpoints**

Add:

```text
QWEN_PROOF_TOKEN=
QWEN_PROOF_DATABASE_PATH=./data/qwen-proof.db
```

Implement:

```text
POST /api/qwen/verify
GET  /api/qwen/proof
```

Use `secrets.compare_digest` for the token and increment a
`qwen_verifications` telemetry counter only after a successful live call.

- [x] **Step 8: Run API and repository tests**

Run:

```bash
cd services/api
.venv/bin/pytest -q \
  tests/test_api.py \
  tests/test_qwen_gateway.py \
  tests/test_qwen_verification_repository.py
```

Expected: all selected tests pass.

- [x] **Step 9: Commit and push live-Qwen proof**

Run:

```bash
git add services/api
git commit --author="Ankit Ranjan <ankit0ranjan@gmail.com>" \
  -m "feat(qwen): persist redacted live verification proof"
git push origin main
```

## Task 4: Build The Reproducible ECS Deployment Bundle

**Files:**
- Create: `deploy/alibaba-ecs/compose.yaml`
- Create: `deploy/alibaba-ecs/env.example`
- Create: `deploy/alibaba-ecs/cloud-init.sh`
- Create: `deploy/alibaba-ecs/deploy.sh`
- Create: `deploy/alibaba-ecs/backup.sh`
- Create: `services/api/tests/test_alibaba_ecs_bundle.py`
- Modify: `.gitignore`

- [x] **Step 1: Write the failing deployment contract test**

The test must parse `deploy/alibaba-ecs/compose.yaml` with `yaml.safe_load` and
assert:

- services are exactly `api` and `web`;
- `api` has no host `ports`;
- `web` publishes `80:80`;
- `api` mounts `${BATCHHELM_DATA_DIR}:/data`;
- both services use `restart: unless-stopped`;
- `api` defines a health check;
- `QWEN_API_KEY`, `QWEN_PROOF_TOKEN`, and all five SQLite paths are runtime
  environment values;
- API replication is fixed at one.

- [x] **Step 2: Run the deployment test and verify the bundle is absent**

Run:

```bash
cd services/api
.venv/bin/pytest -q tests/test_alibaba_ecs_bundle.py
```

Expected: failure because `deploy/alibaba-ecs/compose.yaml` does not exist.

- [x] **Step 3: Add the production Compose file**

Create a source-built deployment that:

- builds from the exact checked-out commit;
- keeps port `8000` internal;
- publishes the web reverse proxy on port `80`;
- sets `APP_ENV=production`;
- persists `/data` at `${BATCHHELM_DATA_DIR}`;
- uses the Qwen Cloud base URL and current model defaults;
- carries `QWEN_PROOF_TOKEN` and `QWEN_PROOF_DATABASE_PATH`;
- applies `init: true`, `restart: unless-stopped`, health checks, and
  `no-new-privileges`.

- [x] **Step 4: Add the secret template**

`env.example` must include safe names and non-secret defaults only:

```text
QWEN_API_KEY=
QWEN_PROOF_TOKEN=
PUBLIC_ORIGIN=
BATCHHELM_DATA_DIR=/srv/batchhelm/data
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_TEXT_MODEL=qwen3.7-plus
QWEN_VISION_MODEL=qwen3-vl-plus
```

- [x] **Step 5: Add cloud initialization**

`cloud-init.sh` must be idempotent and:

- require root;
- install Docker Engine, Compose, git, curl, and jq from Ubuntu packages;
- create `/opt/batchhelm` and `/srv/batchhelm/data`;
- enable Docker;
- never accept or write a secret.

- [x] **Step 6: Add the remote deployment command**

`deploy.sh` must:

- require `BATCHHELM_HOST`, `QWEN_API_KEY`, and `QWEN_PROOF_TOKEN`;
- default `BATCHHELM_REVISION` to the local `HEAD`;
- transfer a mode-`600` temporary environment file without echoing values;
- clone or fetch the public repository on ECS;
- check out the exact revision in detached mode;
- run the production Compose file;
- wait for `/health`;
- trigger the protected live-Qwen verification;
- fetch and print the redacted public receipt;
- remove the local temporary file through a trap.

- [x] **Step 7: Add a SQLite-aware backup command**

`backup.sh` must run inside the API container and use SQLite
`Connection.backup()` for:

```text
batchhelm.db
batchhelm-memory.db
orchestration.db
intake.db
qwen-proof.db
```

Then archive the database snapshots and `uploads/` together under
`/srv/batchhelm/backups`.

- [x] **Step 8: Ignore local deployment secrets and proof captures**

Add:

```text
deploy/alibaba-ecs/.env
deploy/alibaba-ecs/proofs/
```

to `.gitignore`.

- [x] **Step 9: Verify deployment contracts and shell syntax**

Run:

```bash
cd services/api
.venv/bin/pytest -q tests/test_alibaba_ecs_bundle.py
cd ../..
bash -n deploy/alibaba-ecs/cloud-init.sh
bash -n deploy/alibaba-ecs/deploy.sh
bash -n deploy/alibaba-ecs/backup.sh
```

Expected: the test and all syntax checks pass.

- [x] **Step 10: Commit and push the ECS bundle**

Run:

```bash
git add .gitignore deploy services/api/tests/test_alibaba_ecs_bundle.py
git commit --author="Ankit Ranjan <ankit0ranjan@gmail.com>" \
  -m "feat(deploy): add reproducible Alibaba ECS release bundle"
git push origin main
```

## Task 5: Document The Evidence Workflow

**Files:**
- Modify: `docs/deployment-alibaba-cloud.md`
- Modify: `docs/alibaba-cloud-proof.md`
- Modify: `docs/qwen-integration.md`
- Modify: `docs/submission-checklist.md`
- Modify: `docs/demo-script.md`
- Modify: `README.md`

- [x] **Step 1: Replace console-only deployment guidance**

Document the exact sequence:

```bash
sudo bash deploy/alibaba-ecs/cloud-init.sh
export BATCHHELM_HOST=ecs-user@the-instance-address
export QWEN_API_KEY
export QWEN_PROOF_TOKEN
bash deploy/alibaba-ecs/deploy.sh
```

Explain the required ECS security group:

- TCP `22` from the operator IP only;
- TCP `80` from `0.0.0.0/0`;
- no public TCP `8000`.

- [x] **Step 2: Document the proof receipt**

Explain:

- `POST /api/qwen/verify` is token-protected and performs a real billable call;
- `GET /api/qwen/proof` is public and redacted;
- the receipt proves endpoint, model, provider response ID, latency, timestamp,
  and response fingerprint without exposing content or credentials.

- [x] **Step 3: Correct the submission status**

Keep deployment, public URL, live Qwen verification, video, and final Devpost
submission unchecked until real external evidence exists. Mark only the
deployment automation and verification mechanism as complete.

- [x] **Step 4: Verify documentation accuracy and attribution**

Run:

```bash
rg -n "qwen-plus|qwen-vl-plus" \
  README.md .env.example docker-compose.yml \
  docs/deployment-alibaba-cloud.md docs/alibaba-cloud-proof.md \
  docs/qwen-integration.md docs/submission-checklist.md \
  deploy services/api/src/batchhelm_api/config.py
./scripts/check-attribution.sh
git diff --check
```

Expected: legacy default model names do not remain in current configuration or
deployment guidance, attribution passes, and the diff has no whitespace errors.

- [x] **Step 5: Commit and push documentation**

Run:

```bash
git add README.md docs
git commit --author="Ankit Ranjan <ankit0ranjan@gmail.com>" \
  -m "docs: operationalize Alibaba deployment evidence"
git push origin main
```

## Task 6: Run Release Gates And Record The Remaining External Inputs

**Files:**
- Modify: `docs/superpowers/plans/2026-07-05-batchhelm-qwen-proof-ecs-deployment.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `services/api/tests/test_alibaba_ecs_bundle.py`

- [x] **Step 1: Run all backend tests**

Run:

```bash
cd services/api
.venv/bin/pytest -q
```

Expected: all backend tests pass.

- [x] **Step 2: Run frontend and repository gates**

Run:

```bash
cd apps/web
npm test
npm run build
cd ../..
./scripts/check-attribution.sh
git diff --check
```

Expected: frontend tests, type checking, build, and attribution pass.

- [x] **Step 3: Verify the repository contains no secret**

Run:

```bash
rg -n -e 'sk-[A-Za-z0-9_-]{20,}' \
  --glob '!docs/superpowers/plans/**' .
for file in .env.example deploy/alibaba-ecs/env.example; do
  awk -F= \
    '/^(QWEN_API_KEY|QWEN_PROOF_TOKEN)=/ { if ($2 != "") exit 1 }' \
    "$file"
done
```

Expected: no matches containing a real value.

- [x] **Step 4: Mark the plan complete and push the verification record**

Run:

```bash
git add docs/superpowers/plans/2026-07-05-batchhelm-qwen-proof-ecs-deployment.md
git commit --author="Ankit Ranjan <ankit0ranjan@gmail.com>" \
  -m "docs: verify Qwen proof and ECS deployment bundle"
git push origin main
```

- [x] **Step 5: Verify the exact remote revision and CI**

Run:

```bash
git status --short --branch
git log -1 --format='%H%n%an <%ae>%n%s'
git ls-remote origin refs/heads/main
gh run list --branch main --limit 3
```

Expected: local and remote `main` match, the author is Ankit Ranjan, and all CI
jobs for the final revision pass.

- [x] **Step 6: Record the unavoidable external deployment inputs**

The code milestone does not claim a live deployment. A real Alibaba Cloud ECS
instance, its address, a Qwen Cloud pay-as-you-go API key, and a random proof
token are still required to produce:

- the public judging URL;
- the persisted live-Qwen verification receipt;
- Alibaba Workbench/ECS screenshots;
- the final demo video and Devpost submission.
