"""プレビュー・保存・開始で、同じ設定エラーと位置を返す。"""

import pytest
from fastapi.testclient import TestClient

from studio import create_app


KIND = "logs"


PREVIEW = "/api/preview"
SAVE = "/api/presets/rejected"
START = "/api/start"


def assert_rejected(client, app, payload, expected_path, message, code):
    profile = {"output": "tcp", "host": "logs.example.invalid"}
    response = client.post("/api/profiles", json=profile)
    assert response.status_code == 200, response.text
    before = client.get("/api/state").json()
    desired = app.state.store.meta("desired")
    presets = [item["id"] for item in client.get("/api/presets").json()["presets"]]
    requests = [
        (PREVIEW, payload),
        (SAVE, payload),
        (START, payload),
        ("/api/operations/plan", {"path": START, "payload": payload}),
    ]
    for endpoint, body in requests:
        response = client.post(endpoint, json=body)
        assert response.status_code == 422, (endpoint, response.text)
        error = response.json()["detail"][0]
        assert error["loc"] == ["body", *expected_path]
        assert error["msg"] == message
        assert error["code"] == code
    assert client.get("/api/state").json() == before
    assert app.state.store.meta("desired") == desired
    assert [item["id"] for item in client.get("/api/presets").json()["presets"]] == presets


def test_generator_field_error_uses_relative_location_with_generator_prefix():
    payload = {
        "generator": {
            "fields": [
                {"name": "input_text", "generator": "constant", "value": "sample"},
                {
                    "name": "output_text", "generator": "template",
                    "template": "{input_text:03d}",
                },
            ]
        }
    }
    app = create_app(KIND)
    with TestClient(app) as client:
        assert_rejected(
            client, app, payload, ["generator", "fields", 1, "template"],
            "整数書式 d では整数型の項目を参照してください", "template_integer_format",
        )


@pytest.mark.parametrize(
    "template, expected_message, code",
    [
        ("{field_that_does_not_exist}", "テンプレートで参照する項目が見つかりません", "template_field_not_found"),
        ("{status:03d}", "整数書式 d では整数型の項目を参照してください", "template_integer_format"),
        ("{", "値の型・範囲・書式を確認してください", "invalid_generation_value"),
    ],
)
def test_log_template_error_does_not_modify_preset_or_runtime(template, expected_message, code):
    app = create_app("logs")
    with TestClient(app) as client:
        assert_rejected(
            client, app, {"logs": {"message_template": template}},
            ["logs", "message_template"], expected_message, code,
        )


def test_log_template_can_reference_implicit_event_id_and_sequence():
    app = create_app("logs")
    with TestClient(app) as client:
        response = client.post(
            PREVIEW, json={"logs": {"message_template": "{event_id} {sequence:03d}"}}
        )
        assert response.status_code == 200, response.text
        first = response.json()["records"][0]
        assert first["_formatted_log"].endswith(first["event_id"] + " 000")
