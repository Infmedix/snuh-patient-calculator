"""API 라우트 테스트 — mock FHIR(fixtures) 로 돈다. 실 snuh-fhir 접속 없음."""

import pytest
from fastapi.testclient import TestClient

import main
from src import settings
from src.fhir.client import FhirError, HttpFhirClient, MockFhirClient, search_all


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setattr(settings, "FHIR_MODE", "mock")
    monkeypatch.setattr(settings, "PATH_PREFIX", "")


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


# ===== health =====

def test_liveness(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_readiness_mock(client):
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json()["fhir"] == "mock"


# ===== calculators =====

def test_list_calculators_exposes_specs_variables_flags(client):
    body = client.get("/api/calculators").json()
    ids = [c["id"] for c in body["items"]]
    assert "sofa" in ids and len(ids) == 12
    sofa = next(c for c in body["items"] if c["id"] == "sofa")
    fio2 = next(i for i in sofa["inputs"] if i["key"] == "fio2")
    assert fio2["variable"] == "fio2" and fio2["auto"] is True
    vaso = next(i for i in sofa["inputs"] if i["key"] == "vasopressor")
    assert vaso["type"] == "select" and len(vaso["options"]) == 4
    assert body["variables"]["creatinine"]["label"] == "크레아티닌"
    assert body["flags"]["hypertension"] == "고혈압"


def test_calculate_ok(client):
    r = client.post("/api/calculate/bmi", json={"inputs": {"weight_kg": 70, "height_cm": 175}})
    assert r.status_code == 200
    assert r.json()["value"] == 22.9


def test_calculate_missing_returns_400_with_keys(client):
    r = client.post("/api/calculate/egfr", json={"inputs": {"creatinine": 1.0}})
    assert r.status_code == 400
    assert set(r.json()["detail"]["missing"]) == {"age", "sex"}


def test_calculate_unknown_404(client):
    assert client.post("/api/calculate/nope", json={"inputs": {}}).status_code == 404


# ===== patients =====

def test_snapshot_from_fixture(client):
    r = client.get("/api/patients/10000001/snapshot")
    assert r.status_code == 200
    s = r.json()
    assert s["patient"]["sex"] == "M"
    assert s["values"]["creatinine"]["value"] == 1.8
    assert s["flags"]["atrial_fibrillation"]["present"] is True
    assert s["warnings"] == []


def test_snapshot_unknown_patient_404(client):
    r = client.get("/api/patients/99999999/snapshot")
    assert r.status_code == 404


def test_snapshot_rejects_bad_id(client):
    assert client.get("/api/patients/%20/snapshot").status_code == 400


def test_overview_prefills_and_computes(client):
    r = client.get("/api/patients/10000001/overview")
    assert r.status_code == 200
    body = r.json()
    by_id = {c["id"]: c for c in body["calculators"]}

    # BMI: 62.5 kg / 1.70 m → 21.6
    assert by_id["bmi"]["result"]["value"] == 21.6
    assert by_id["bmi"]["prefill"]["weight_kg"]["source"]["category"] == "clinical"

    # eGFR: Cr 1.8, 68세 남 → 계산됨
    assert by_id["egfr"]["result"] is not None
    assert by_id["egfr"]["prefill"]["age"]["value"] == 68
    assert by_id["egfr"]["prefill"]["sex"]["value"] == "M"
    assert by_id["egfr"]["prefill"]["age"]["source"]["category"] == "patient"

    # CHA2DS2-VASc: 68세 남(1) + HTN(1) + DM(1) + stroke(2) = 5, 심부전 없음(False 로 채움)
    cha = by_id["cha2ds2_vasc"]
    assert cha["prefill"]["hypertension"]["value"] is True
    assert cha["prefill"]["heart_failure"]["value"] is False
    assert cha["result"]["value"] == 5

    # HAS-BLED: SBP 118 → 고혈압 False, Cr 1.8 ≤2.26 이지만 CKD 진단 → 신장 True, 간경변 → 간 True,
    # 뇌졸중 True, 출혈 False, 65세 초과 True → 4 (labile INR·약물·음주는 기본 False)
    hb = by_id["has_bled"]
    assert hb["prefill"]["hypertension"]["value"] is False
    assert hb["prefill"]["renal_abnormal"]["value"] is True
    assert hb["prefill"]["liver_abnormal"]["value"] is True
    assert hb["result"]["value"] == 4

    # Child-Pugh: 복수·뇌병증은 기본 none → 계산됨 (bili 2.6→2, alb 2.9→2, INR 1.9→2, 1, 1 = 8 → B)
    assert by_id["child_pugh"]["result"]["value"] == 8

    # MELD-Na 계산됨, 투석 기본 False
    assert by_id["meld_na"]["result"] is not None

    # CURB-65: 혼미 기본 False, BUN 32(1) RR 22(0) BP 118/72(0) 68세(1) → 2
    assert by_id["curb65"]["result"]["value"] == 2

    # SOFA: fio2 없음 → 계산 불가, missing 에 fio2
    assert by_id["sofa"]["result"] is None
    assert "fio2" in by_id["sofa"]["missing"]
    assert by_id["sofa"]["prefill"]["map"]["source"]["derived"] is True

    # APACHE II: fio2 누락
    assert "fio2" in by_id["apache2"]["missing"]

    # QTc: QT 398, 심전도 HR 96, 남 → Fridericia 계산, 기기 QTc 503 참고
    q = by_id["qtc"]
    assert q["prefill"]["hr"]["value"] == 96
    assert q["prefill"]["reported_qtc_ms"]["value"] == 503
    assert q["result"] is not None

    # NRS-2002: 3개월 체중감소 5.3% → mild 제안, 질병 중증도는 수동 → missing
    n = by_id["nrs2002"]
    assert n["prefill"]["nutrition_status"]["value"] == "mild"
    assert n["prefill"]["weight_loss_3m_pct"]["value"] == pytest.approx(5.3, abs=0.05)
    assert "disease_severity" in n["missing"]


def test_overview_second_fixture_patient_computes_icu_scores(client):
    body = client.get("/api/patients/20000002/overview").json()
    assert body["snapshot"]["patient"]["sex"] == "F" and body["snapshot"]["patient"]["age"] == 77
    by_id = {c["id"]: c for c in body["calculators"]}
    # CURB-65: BUN 24(1) RR 31(1) BP 102/58 → DBP ≤60(1) 77세(1) = 4
    assert by_id["curb65"]["result"]["value"] == 4
    # SOFA: FiO2 0.35 가 간호기록에 있어 계산됨 — PF 62/0.35=177, 호흡보조 없음 → 2, 나머지 0
    assert by_id["sofa"]["result"]["value"] == 2
    assert by_id["sofa"]["prefill"]["fio2"]["source"]["category"] == "clinical"
    # APACHE II 도 계산됨 (FiO2 <0.5 → PaO2 62 → 1점 포함)
    assert by_id["apache2"]["result"] is not None
    assert by_id["apache2"]["result"]["extra"]["aps"]["oxygenation"] == 1
    # CHA2DS2-VASc: 77세 여(2+1) + CHF(1) + HTN(1) = 5
    assert by_id["cha2ds2_vasc"]["result"]["value"] == 5
    # NRS-2002: 3개월 체중감소 51.5→48.0 = 6.8%(mild) 에 BMI 20.0 (<20.5) 이 겹쳐 moderate 제안
    assert by_id["nrs2002"]["prefill"]["nutrition_status"]["value"] == "moderate"
    assert by_id["nrs2002"]["prefill"]["weight_loss_3m_pct"]["value"] == pytest.approx(6.8, abs=0.05)


def test_overview_marks_stale_values(client, monkeypatch):
    monkeypatch.setattr(settings, "STALE_AFTER_DAYS", 0)
    body = client.get("/api/patients/10000001/overview").json()
    bmi = next(c for c in body["calculators"] if c["id"] == "bmi")
    assert bmi["prefill"]["weight_kg"]["source"]["stale"] is True


# ===== prefix / ui =====

def test_prefix_both_deployments(monkeypatch):
    monkeypatch.setattr(settings, "PATH_PREFIX", "/apps/runtime/calculator")
    with TestClient(main.app) as c:
        assert c.get("/apps/runtime/calculator/api/health").status_code == 200   # strip 안 된 배치
        assert c.get("/api/health").status_code == 200                           # strip 된 배치
        r = c.get("/apps/runtime/calculator", follow_redirects=False)
        assert r.status_code == 307 and r.headers["location"] == "/apps/runtime/calculator/"


def test_root_redirects_relative_to_ui(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "./ui/"


def test_ui_without_dist_is_404(tmp_path):
    from fastapi import FastAPI
    from src import ui
    app = FastAPI()
    assert ui.install_ui(app, str(tmp_path / "no-dist")) is False
    c = TestClient(app)
    assert c.get("/ui/").status_code == 404
    assert c.get("/", follow_redirects=False).headers["location"] == "./ui/"


def test_ui_with_dist_serves_index(tmp_path):
    from fastapi import FastAPI
    from src import ui
    d = tmp_path / "dist"
    d.mkdir()
    (d / "index.html").write_text("<!doctype html><title>x</title>")
    app = FastAPI()
    assert ui.install_ui(app, str(d)) is True
    assert "<title>x</title>" in TestClient(app).get("/ui/").text


# ===== fhir client =====

async def test_search_all_pages_until_short_page():
    calls = []

    class Fake:
        async def get(self, path, params=None):
            calls.append(params["_offset"])
            n = 2 if params["_offset"] < 4 else 1
            return {"entry": [{"resource": {}}] * n}

        def describe(self):
            return "fake"

    bundles = await search_all(Fake(), "Observation", {"patient": "x"}, page_size=2, max_pages=10)
    assert calls == [0, 2, 4]
    assert len(bundles) == 3


async def test_search_all_stops_at_max_pages():
    class Fake:
        async def get(self, path, params=None):
            return {"entry": [{"resource": {}}] * 2}

        def describe(self):
            return "fake"

    bundles = await search_all(Fake(), "Observation", {"patient": "x"}, page_size=2, max_pages=3)
    assert len(bundles) == 3


async def test_mock_client_filters_category_and_date():
    m = MockFhirClient(settings.FIXTURES_DIR)
    labs = await m.get("Observation", {"patient": "10000001", "category": "laboratory", "date": "ge2026-10-01", "_count": 100})
    ids = [e["resource"]["id"] for e in labs["entry"]]
    assert "SPCM20260901001" not in ids and "SPCM20261005001" in ids
    ecg = await m.get("Observation", {"patient": "10000001", "category": "exam", "code": "심전도", "_count": 10})
    assert len(ecg["entry"]) == 1
    with pytest.raises(FhirError) as ei:
        await m.get("Patient/nope")
    assert ei.value.status == 404


async def test_http_client_maps_401_without_leaking_token(monkeypatch):
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer snuhfhir_secret"
        return httpx.Response(401, json={"resourceType": "OperationOutcome",
                                         "issue": [{"severity": "error", "code": "login", "diagnostics": "Bearer 토큰이 필요합니다"}]})

    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient

    class Patched(real):
        def __init__(self, *a, **kw):
            kw["transport"] = transport
            super().__init__(*a, **kw)

    monkeypatch.setattr(httpx, "AsyncClient", Patched)
    c = HttpFhirClient("http://fhir.test", "snuhfhir_secret")
    with pytest.raises(FhirError) as ei:
        await c.get("Patient/1")
    assert ei.value.status == 401
    assert "secret" not in ei.value.detail
    assert "토큰" in ei.value.detail


# ===== .env =====

def test_dotenv_fills_only_missing_keys(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text(
        "\n".join(["# comment", "APP_TEST_A=mock", 'APP_TEST_B="quoted"', "export APP_TEST_C=x", "broken line", ""]),
        encoding="utf-8",
    )
    monkeypatch.delenv("APP_TEST_A", raising=False)
    monkeypatch.setenv("APP_TEST_B", "from-shell")
    monkeypatch.delenv("APP_TEST_C", raising=False)
    loaded = settings.load_dotenv(p)
    assert loaded == ["APP_TEST_A", "APP_TEST_C"]
    assert settings._env("APP_TEST_A") == "mock"
    assert settings._env("APP_TEST_B") == "from-shell"     # 셸 값이 우선
    assert settings._env("APP_TEST_C") == "x"
    for k in ("APP_TEST_A", "APP_TEST_C"):
        monkeypatch.delenv(k, raising=False)
