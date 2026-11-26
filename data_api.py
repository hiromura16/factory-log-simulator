"""業務レコードのページング・差分と時系列履歴の取得APIを提供する。"""

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import urlencode

from fastapi import HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse, Response

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


SOURCE_AUTH = [{}, {"SourceBasic": []}, {"SourceBearer": []}, {"SourceApiKey": []}]
SOURCE_ERRORS = {
    400: "カーソルの形式または署名が正しくありません",
    401: "取得認証が必要です。模擬の認証失敗にも使用します",
    403: "書き込みが無効、または別サイトからの操作",
    404: "指定したコレクションまたはレコードがありません",
    409: "カーソルの条件が異なる、またはIDが既に存在します",
    410: "カーソルの期限切れ。先頭から取得し直してください",
    412: "If-Matchと現在のETagが一致しません",
    415: "更新にはContent-Type: application/jsonが必要です",
    422: "入力値または検索条件を確認してください",
    429: "模擬の要求数制限。Retry-Afterの秒数を待って再試行してください",
    503: "データ準備中、取得設定を確認できない、または模擬の一時障害",
}


def source_errors(*codes):
    """当該ルートで実際に返す失敗コードをOpenAPIへ記載する。"""
    responses = {
        code: {"description": SOURCE_ERRORS[code]} for code in (401, 503, *codes)
    }
    if 429 in responses:
        responses[429]["headers"] = {
            "Retry-After": {"description": "待つ秒数", "schema": {"type": "integer"}}
        }
    responses[503]["headers"] = {
        "Retry-After": {
            "description": "データ準備中の場合に待つ秒数",
            "schema": {"type": "integer"},
        }
    }
    return responses


def query_parameter(name, description, schema):
    """内部で直接読むクエリを、HTTP挙動を変えずOpenAPIに表す。"""
    return {"name": name, "in": "query", "description": description, "schema": schema}


def collection_options(odata=False):
    """RESTとODataの同じ検索条件を、それぞれのパラメーター名で記載する。"""
    names = (
        ("$top", "$skip", "$filter", "$orderby", "$select", "$skiptoken")
        if odata
        else ("limit", "offset", "filter", "order_by", "select", "cursor")
    )
    options = [
        (
            "取得する件数。省略時は公開中の1ページの件数",
            {"type": "integer", "minimum": 1, "maximum": 1000},
        ),
        (
            "先頭から読み飛ばす行数。次ページは応答のリンクを使用",
            {"type": "integer", "minimum": 0, "default": 0},
        ),
        (
            "比較 eq/ne/gt/ge/lt/le、and/or、括弧。文字列は単一引用符で囲みます",
            {"type": "string", "examples": ["value ge 0 and value lt 100"]},
        ),
        (
            "項目名と asc/desc をカンマ区切りで指定",
            {"type": "string", "default": "id asc"},
        ),
        (
            "返す項目名をカンマ区切りで指定。省略時はすべて",
            {"type": "string", "examples": ["id,value"]},
        ),
        (
            "次ページの署名付きカーソル。検索・並び・件数は変更しません",
            {"type": "string"},
        ),
    ]
    return {
        "security": SOURCE_AUTH,
        "parameters": [
            query_parameter(name, description, schema)
            for name, (description, schema) in zip(names, options)
        ],
    }


def json_body(*, create=False, required=True):
    """業務コレクションごとに項目が異なるJSONオブジェクトを表す。"""
    schema = {"type": "object", "additionalProperties": True}
    example = {"value": 28}
    if create:
        schema.update(properties={"id": {"type": "string"}}, required=["id"])
        example["id"] = "example-order"
    if not required:
        example = {}
    return {
        "required": required,
        "content": {"application/json": {"schema": schema, "example": example}},
    }


def etag_parameter(name):
    """HTTPのキャッシュ・更新前提条件を例とともに記載する。"""
    return {
        "name": name,
        "in": "header",
        "description": (
            "直前のETagと一致すると304"
            if name == "If-None-Match"
            else "直前のETagを引用符付きで送信。異なる版は412。*または省略も可能"
        ),
        "schema": {"type": "string", "examples": ['"12"']},
    }


def json_example(description, example, **headers):
    """JSON応答の利用例と、必要に応じて応答ヘッダーを示す。"""
    response = {
        "description": description,
        "content": {"application/json": {"example": example}},
    }
    if headers:
        response["headers"] = {
            name.replace("_", "-"): {"schema": {"type": "string"}, "example": value}
            for name, value in headers.items()
        }
    return response


def timestamp(value):
    """タイムゾーン付きISO日時を秒へ変換し、未指定ならNoneを返す。"""
    if value is None:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("日時にタイムゾーンを付けてください")
    return dt.timestamp()


def predicate(text, fields):
    """比較・括弧・and/orの限定構文をSQL条件とバインド値へ変換する。

    許可フィールド・演算子だけを使い、入力値をSQL文字列へ直接埋め込まない。
    """
    if not text:
        return "1", []
    if len(text) > 2000:
        raise ValueError("filterが長すぎます")
    pattern = re.compile(
        r"\s*('(?:''|[^'])*'|-?\d+(?:\.\d+)?|[A-Za-z_][A-Za-z0-9_]*|[()])"
    )
    tokens = []
    pos = 0
    while pos < len(text):
        match = pattern.match(text, pos)
        if not match:
            raise ValueError("filterは比較・and/or・括弧に対応します")
        tokens.append(match.group(1))
        pos = match.end()
    if len(tokens) > 100:
        raise ValueError("filterの条件数が多すぎます")
    index = 0
    args = []

    def atom():
        """比較一つまたは括弧内の式を解釈し、型付き値をバインド引数へ追加する。"""
        nonlocal index
        if index >= len(tokens):
            raise ValueError("filterが不完全です")
        if tokens[index] == "(":
            index += 1
            result = expr()
            if index >= len(tokens) or tokens[index] != ")":
                raise ValueError("filterの括弧が不完全です")
            index += 1
            return "(" + result + ")"
        if index + 2 >= len(tokens):
            raise ValueError("filterの比較が不完全です")
        name, op, value = tokens[index : index + 3]
        index += 3
        if name not in fields or not IDENT.fullmatch(name):
            raise ValueError("不明なfilter項目です")
        operator = {
            "eq": "=",
            "ne": "!=",
            "gt": ">",
            "ge": ">=",
            "lt": "<",
            "le": "<=",
        }.get(op.lower())
        if not operator:
            raise ValueError("未対応の比較演算子です")
        column = (
            "rev"
            if name == "_revision"
            else "changed_at"
            if name == "_updated_at"
            else "json_extract(payload,'$." + name + "')"
        )
        if value.lower() == "null":
            if op.lower() not in {"eq", "ne"}:
                raise ValueError("NULLはeq/neで比較してください")
            return column + (
                " IS NULL" if op.lower() == "eq" else " IS NOT NULL"
            )
        if value.startswith("'"):
            parsed = value[1:-1].replace("''", "'")
        elif value.lower() in {"true", "false"}:
            parsed = int(value.lower() == "true")
        else:
            try:
                parsed = float(value) if "." in value else int(value)
            except ValueError:
                raise ValueError(
                    "文字列リテラルは単一引用符で囲んでください"
                ) from None
        args.append(parsed)
        return column + operator + "?"

    def conjunction():
        """and結合を先に解析し、orより高い優先順位を保つ。"""
        nonlocal index
        sql = atom()
        while index < len(tokens) and tokens[index].lower() == "and":
            index += 1
            sql += " AND " + atom()
        return sql

    def expr():
        """andでまとめた条件をorで結び、現在位置を進める。"""
        nonlocal index
        sql = conjunction()
        while index < len(tokens) and tokens[index].lower() == "or":
            index += 1
            sql += " OR " + conjunction()
        return sql

    sql = expr()
    if index != len(tokens):
        raise ValueError("filterの末尾を確認してください")
    return sql, args


def register_data_routes(app, c, authorize):
    """業務・履歴取得の共通ルートを登録し、同じ認証関数と保存領域を使う。"""

    def resource(name):
        """設定された名前のコレクションを取得し、不明な名前は404とする。"""
        opts = c.source_spec().business
        for item in opts.resources:
            if item.name == name:
                return item
        raise HTTPException(404, "コレクションがありません")

    def ready(request):
        """取得認証を確認し、データセット準備中なら再試行可能な503で返す。"""
        authorize(request)
        if not c.ds or c.status == "starting":
            raise HTTPException(
                503, "データを準備しています", headers={"Retry-After": "2"}
            )

    async def fault():
        """要求数を進め、指定周期にHTTP障害または遅延を模擬する。"""
        c.requests += 1
        opts = c.source_spec().business
        if opts.fault == "none" or c.requests % opts.fault_every:
            return None
        if opts.fault == "rate_limit":
            return JSONResponse(
                {"error": "simulated_rate_limit"},
                429,
                headers={"Retry-After": "2"},
            )
        if opts.fault == "server_error":
            return JSONResponse({"error": "simulated_server_error"}, 503)
        if opts.fault == "unauthorized":
            return JSONResponse(
                {"error": "simulated_expired_credentials"}, 401
            )
        if opts.fault == "delay":
            await asyncio.sleep(opts.fault_delay_ms / 1000)
        return opts.fault

    def token_data(token):
        """カーソルの期限切れを410、不正形式を400へ変換する。"""
        try:
            return c.store.untoken(token)
        except TimeoutError as e:
            raise HTTPException(410, str(e)) from None
        except ValueError as e:
            raise HTTPException(400, str(e)) from None

    async def collection(request, name, odata=False):
        """検索条件を固定したスナップショットをページ化して返す。

        カーソルに対象と条件を束縛し、RESTと限定ODataの表現差だけを切り替える。
        """
        ready(request)
        res = resource(name)
        g = res.generator or c.source_spec().generator
        fields = {f.name for f in g.fields} | {
            "id",
            "_revision",
            "_updated_at",
        }
        injection = await fault()
        if isinstance(injection, Response):
            return injection
        q = request.query_params
        try:
            limit = int(
                q.get(
                    "$top" if odata else "limit",
                    c.source_spec().business.page_size,
                )
            )
            if not 1 <= limit <= 1000:
                raise ValueError("ページ件数は1〜1000です")
            offset = int(q.get("$skip" if odata else "offset", "0"))
            if offset < 0:
                raise ValueError("offsetは0以上です")
            filter_text = q.get("$filter" if odata else "filter", "")
            order = q.get("$orderby" if odata else "order_by", "id asc")
            selection = q.get("$select" if odata else "select", "")
            condition, args = predicate(filter_text, fields)
            ordering = []
            for item in order.split(","):
                parts = item.split()
                field = parts[0]
                if (
                    field not in fields
                    or len(parts) > 2
                    or (
                        len(parts) == 2
                        and parts[1].lower() not in {"asc", "desc"}
                    )
                ):
                    raise ValueError("orderbyを確認してください")
                column = (
                    "id"
                    if field == "id"
                    else "rev"
                    if field == "_revision"
                    else "changed_at"
                    if field == "_updated_at"
                    else "json_extract(payload,'$." + field + "')"
                )
                ordering.append(
                    column
                    + " "
                    + (parts[1].upper() if len(parts) == 2 else "ASC")
                )
            ordering.append("id ASC")
            selected = selection.split(",") if selection else []
            if set(selected) - fields:
                raise ValueError("selectに不明な項目があります")
        except (ValueError, IndexError) as e:
            raise HTTPException(422, str(e)) from None
        signature = hashlib.sha256(
            json.dumps([name, filter_text, order, selection, limit]).encode()
        ).hexdigest()
        token = q.get("$skiptoken" if odata else "cursor")
        snapshot = c.store.maximum(c.ds, name)
        if token:
            if injection == "cursor_expired":
                raise HTTPException(410, "模擬カーソル期限切れ")
            d = token_data(token)
            if (
                d.get("ds") != c.ds
                or d.get("res") != name
                or d.get("query") != signature
            ):
                raise HTTPException(
                    409, "カーソルのデータセット・条件が一致しません"
                )
            offset, snapshot = d["offset"], d["snapshot"]
        if injection == "duplicate_page":
            offset = max(0, offset - limit)
        elif injection == "skip_page":
            offset += limit
        base = (
            "WITH snapshot AS (SELECT *,row_number() OVER(PARTITION BY id ORDER BY rev DESC) AS rn FROM changes WHERE ds=? AND res=? AND rev<=?) SELECT * FROM snapshot WHERE rn=1 AND deleted=0 AND ("
            + condition
            + ")"
        )
        with c.store.db() as db:
            total = db.execute(
                "SELECT count(*) FROM (" + base + ")",
                [c.ds, name, snapshot, *args],
            ).fetchone()[0]
            rows = db.execute(
                base + " ORDER BY " + ",".join(ordering) + " LIMIT ? OFFSET ?",
                [c.ds, name, snapshot, *args, limit + 1, offset],
            ).fetchall()
        values = []
        for r in rows[:limit]:
            value = {
                **json.loads(r["payload"]),
                "_revision": r["rev"],
                "_updated_at": r["changed_at"],
            }
            values.append(
                {k: value.get(k) for k in selected} if selected else value
            )
        exp = time.time() + c.source_spec().business.cursor_ttl_seconds
        delta = c.store.token(
            {
                "ds": c.ds,
                "res": name,
                "rev": snapshot,
                "exp": exp,
                "type": "delta",
            }
        )
        result = {
            "value": values,
            "@odata.count" if odata else "count": total,
            "snapshot_revision": snapshot,
        }
        url = str(request.url).split("?", 1)[0]
        if len(rows) > limit:
            next_token = c.store.token(
                {
                    "ds": c.ds,
                    "res": name,
                    "offset": offset + limit,
                    "snapshot": snapshot,
                    "query": signature,
                    "exp": exp,
                }
            )
            params = dict(q)
            params.pop("$skip" if odata else "offset", None)
            params["$skiptoken" if odata else "cursor"] = next_token
            result["@odata.nextLink" if odata else "next"] = (
                url + "?" + urlencode(params)
            )
        else:
            result["@odata.deltaLink" if odata else "delta"] = (
                str(request.base_url).rstrip("/")
                + "/source/rest/"
                + name
                + "/delta?token="
                + delta
            )
        if odata:
            result["@odata.context"] = (
                str(request.base_url).rstrip("/")
                + "/source/odata/$metadata#"
                + name
            )
        if injection == "truncate_json":
            return Response(
                json.dumps(result)[: max(1, len(json.dumps(result)) // 2)],
                media_type="application/json",
            )
        return JSONResponse(
            result, headers={"OData-Version": "4.0"} if odata else {}
        )

    @app.get(
        "/source/rest/{name}",
        tags=["業務データ・REST"],
        summary="コレクションの行を一覧取得",
        openapi_extra=collection_options(),
        responses={
            **source_errors(400, 404, 409, 410, 422, 429),
            200: json_example(
                "条件に一致する行と同じスナップショットを取得するURL",
                {
                    "value": [{"id": "example-order", "value": 28, "_revision": 12}],
                    "count": 20,
                    "snapshot_revision": 20,
                    "next": "/source/rest/orders?limit=1&cursor=…",
                },
            ),
        },
    )
    async def rest(request: Request, name: str):
        """まず limit を指定して取得し、next を最後までたどります。

        最終ページの delta は次回の更新・削除の取得に使います。
        公開設定と障害模擬の設定に応じて401、429、503などが返ります。
        """
        return await collection(request, name)

    @app.get(
        "/source/odata/$metadata",
        tags=["業務データ・OData"],
        summary="公開中のコレクションと列型をXMLで取得",
        response_class=Response,
        openapi_extra={"security": SOURCE_AUTH},
        responses={
            **source_errors(),
            200: {
                "description": "OData 4.0のEDMX定義",
                "content": {"application/xml": {"schema": {"type": "string"}}},
            },
        },
    )
    def metadata(request: Request):
        """コレクション名、キー、列名とEDM型の定義を返します。"""
        ready(request)

        items = []
        for res in c.source_spec().business.resources:
            fields = (res.generator or c.source_spec().generator).fields
            props = "".join(
                '<Property Name="'
                + f.name
                + '" Type="'
                + {
                    "integer": "Edm.Int64",
                    "number": "Edm.Double",
                    "decimal": "Edm.Decimal",
                    "boolean": "Edm.Boolean",
                    "datetime": "Edm.DateTimeOffset",
                }.get(f.data_type, "Edm.String")
                + '" Nullable="'
                + ("false" if f.name == "id" else "true")
                + '"/>'
                for f in fields
            )
            if not any(f.name == "id" for f in fields):
                props += '<Property Name="id" Type="Edm.String" Nullable="false"/>'
            items.append(
                '<EntityType Name="'
                + res.name
                + '"><Key><PropertyRef Name="id"/></Key>'
                + props
                + "</EntityType>"
            )
        sets = "".join(
            '<EntitySet Name="' + r.name + '" EntityType="Factory.' + r.name + '"/>'
            for r in c.source_spec().business.resources
        )
        return Response(
            '<?xml version="1.0"?><edmx:Edmx Version="4.0" xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx"><edmx:DataServices><Schema Namespace="Factory" xmlns="http://docs.oasis-open.org/odata/ns/edm">'
            + "".join(items)
            + '<EntityContainer Name="Container">'
            + sets
            + "</EntityContainer></Schema></edmx:DataServices></edmx:Edmx>",
            media_type="application/xml",
        )

    @app.get(
        "/source/odata/{name}",
        tags=["業務データ・OData"],
        summary="限定OData形式でコレクションを取得",
        openapi_extra=collection_options(odata=True),
        responses={
            **source_errors(400, 404, 409, 410, 422, 429),
            200: json_example(
                "OData形式の一覧とページ送り",
                {
                    "@odata.context": "/source/odata/$metadata#orders",
                    "@odata.count": 20,
                    "snapshot_revision": 20,
                    "value": [{"id": "example-order", "value": 28}],
                    "@odata.nextLink": "/source/odata/orders?$top=1&$skiptoken=…",
                },
                OData_Version="4.0",
            ),
        },
    )
    async def odata(request: Request, name: str):
        """対応するクエリだけを指定し、@odata.nextLink を最後までたどります。

        最終ページの @odata.deltaLink は変更取得用のREST APIを指します。
        """
        return await collection(request, name, True)

    @app.get(
        "/source/rest/{name}/delta",
        tags=["業務データ・REST"],
        summary="前回以降に変わった行と削除を取得",
        openapi_extra={"security": SOURCE_AUTH},
        responses={
            **source_errors(400, 404, 409, 410, 422),
            200: json_example(
                "変更の一覧。削除は @removed を付けて返す",
                {
                    "value": [
                        {
                            "id": "example-order",
                            "@removed": {"reason": "deleted"},
                            "_revision": 21,
                        }
                    ],
                    "delta": "/source/rest/orders/delta?token=…&limit=100",
                },
            ),
        },
    )
    def delta(
        request: Request,
        name: str,
        token: Annotated[
            str,
            Query(description="一覧の最終ページ、または前回の差分応答が返したトークン"),
        ],
        limit: Annotated[
            int,
            Query(
                description="1ページに返す変更の数",
                json_schema_extra={"minimum": 1, "maximum": 1000},
            ),
        ] = 100,
    ):
        """next がある間は同じ差分を読み、最後の delta を次の取得まで保管します。"""
        ready(request)
        resource(name)
        if not 1 <= limit <= 1000:
            raise HTTPException(422, "limitは1〜1000")
        d = token_data(token)
        if d.get("ds") != c.ds or d.get("res") != name or d.get("type") != "delta":
            raise HTTPException(409, "deltaの対象が一致しません")
        upper = d.get("upper", c.store.maximum(c.ds, name))
        lower = d["rev"]
        with c.store.db() as db:
            rows = db.execute(
                "SELECT * FROM changes WHERE ds=? AND res=? AND rev>? AND rev<=? ORDER BY rev LIMIT ?",
                (c.ds, name, lower, upper, limit + 1),
            ).fetchall()
        values = [
            {
                "id": r["id"],
                "@removed": {"reason": "deleted"},
                "_revision": r["rev"],
            }
            if r["deleted"]
            else {
                **json.loads(r["payload"]),
                "_revision": r["rev"],
                "_updated_at": r["changed_at"],
            }
            for r in rows[:limit]
        ]
        more = len(rows) > limit
        next_rev = rows[limit - 1]["rev"] if more else upper
        payload = {
            "ds": c.ds,
            "res": name,
            "rev": next_rev,
            "exp": time.time() + c.source_spec().business.cursor_ttl_seconds,
            "type": "delta",
        }
        if more:
            payload["upper"] = upper
        link = (
            str(request.url).split("?", 1)[0]
            + "?"
            + urlencode({"token": c.store.token(payload), "limit": limit})
        )
        return {"value": values, "next" if more else "delta": link}

    @app.get(
        "/source/rest/{name}/{identity}",
        tags=["業務データ・REST"],
        summary="IDで1行を取得",
        openapi_extra={
            "security": SOURCE_AUTH,
            "parameters": [etag_parameter("If-None-Match")],
        },
        responses={
            **source_errors(404),
            200: json_example(
                "現在の行とETag", {"id": "example-order", "_revision": 12}, ETag='"12"'
            ),
            304: {"description": "If-None-Matchと一致したため本文なし"},
        },
    )
    @app.patch(
        "/source/rest/{name}/{identity}",
        tags=["業務データ・REST"],
        summary="指定した行の項目を更新",
        status_code=204,
        response_class=Response,
        openapi_extra={
            "security": SOURCE_AUTH,
            "parameters": [etag_parameter("If-Match")],
            "requestBody": json_body(),
        },
        responses=source_errors(403, 404, 412, 415, 422),
    )
    @app.delete(
        "/source/rest/{name}/{identity}",
        tags=["業務データ・REST"],
        summary="指定した行を論理削除",
        status_code=204,
        response_class=Response,
        openapi_extra={
            "security": SOURCE_AUTH,
            "parameters": [etag_parameter("If-Match")],
            "requestBody": json_body(required=False),
        },
        responses=source_errors(403, 404, 412, 415),
    )
    async def single(
        request: Request,
        name: str,
        identity: Annotated[
            str, Path(description="一覧または追加応答に含まれる行のid")
        ],
    ):
        """取得はETagを返し、更新・削除は公開設定の書き込み許可を確認します。"""
        ready(request)
        resource(name)
        with c.store.db() as db:
            row = db.execute(
                "SELECT * FROM changes WHERE ds=? AND res=? AND id=? ORDER BY rev DESC LIMIT 1",
                (c.ds, name, identity),
            ).fetchone()
        if not row or row["deleted"]:
            raise HTTPException(404, "レコードがありません")
        etag = '"' + str(row["rev"]) + '"'
        if request.method == "GET":
            if request.headers.get("if-none-match") == etag:
                return Response(status_code=304)
            return JSONResponse(
                {**json.loads(row["payload"]), "_revision": row["rev"]},
                headers={"ETag": etag},
            )
        if not c.profile.allow_writes:
            raise HTTPException(403, "書き込みは無効です")
        if request.headers.get("if-match") not in {None, "*", etag}:
            raise HTTPException(412, "ETagが一致しません")
        value = json.loads(row["payload"])
        if request.method == "DELETE":
            value["_deleted"] = True
        else:
            update = await request.json()
            if not isinstance(update, dict):
                raise HTTPException(422, "JSONオブジェクトが必要です")
            value.update(update)
            value["id"] = identity
        c.store.put(c.ds, name, [value])
        return Response(status_code=204)

    @app.post(
        "/source/rest/{name}",
        tags=["業務データ・REST"],
        summary="文字列IDを指定して1行を追加",
        status_code=201,
        openapi_extra={"security": SOURCE_AUTH, "requestBody": json_body(create=True)},
        responses={
            **source_errors(403, 404, 409, 415, 422),
            201: json_example("保存された行", {"id": "example-order", "value": 28}),
        },
    )
    async def insert(request: Request, name: str):
        """書き込みを許可した検証用コレクションへ追加し、変更履歴に記録します。"""
        ready(request)
        resource(name)
        if not c.profile.allow_writes:
            raise HTTPException(403, "書き込みは無効です")
        value = await request.json()
        if not isinstance(value, dict) or not isinstance(value.get("id"), str):
            raise HTTPException(422, "文字列のidが必要です")
        with c.store.db() as db:
            old = db.execute(
                "SELECT deleted FROM changes WHERE ds=? AND res=? AND id=? ORDER BY rev DESC LIMIT 1",
                (c.ds, name, value["id"]),
            ).fetchone()
        if old and not old["deleted"]:
            raise HTTPException(409, "idが重複しています")
        c.store.put(c.ds, name, [value])
        return JSONResponse(value, status_code=201)

    @app.get(
        "/source/history/tags",
        tags=["履歴データ"],
        summary="履歴に記録されたタグを一覧取得",
        openapi_extra={"security": SOURCE_AUTH},
        responses={
            **source_errors(),
            200: json_example("選択可能なタグ名", {"tags": ["device-001.value"]}),
        },
    )
    def tags(request: Request):
        """生値・集計の tag に指定できる名前を、重複なしで返します。"""
        ready(request)
        with c.store.db() as db:
            return {
                "tags": [
                    r[0]
                    for r in db.execute(
                        "SELECT DISTINCT tag FROM samples WHERE ds=? ORDER BY tag",
                        (c.ds,),
                    )
                ]
            }

    @app.get(
        "/source/history/raw",
        tags=["履歴データ"],
        summary="タグを指定して生の履歴を取得",
        openapi_extra={"security": SOURCE_AUTH},
        responses={
            **source_errors(400, 409, 410, 422),
            200: json_example(
                "時刻・通番の順に並んだ生値と品質",
                {
                    "tag": "device-001.value",
                    "values": [
                        {
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "value": 28,
                            "quality": "Good",
                            "sequence": 1,
                        }
                    ],
                },
            ),
        },
    )
    def raw(
        request: Request,
        tag: Annotated[
            str,
            Query(
                description="/source/history/tags が返したタグ名",
                examples=["device-001.value"],
            ),
        ],
        start: Annotated[
            str | None,
            Query(
                description="期間開始（この時刻を含む）。UTCのZまたはオフセット付きISO日時"
            ),
        ] = None,
        end: Annotated[
            str | None,
            Query(
                description="期間終了（この時刻を含む）。UTCのZまたはオフセット付きISO日時"
            ),
        ] = None,
        limit: Annotated[
            int,
            Query(
                description="返す行数",
                json_schema_extra={"minimum": 1, "maximum": 10000},
            ),
        ] = 1000,
        cursor: Annotated[
            str | None, Query(description="応答のnextが含むカーソル。有効期間は600秒")
        ] = None,
        quality: Annotated[
            str | None, Query(description="品質の完全一致。Good、Bad、Uncertainなど")
        ] = None,
    ):
        """期間・品質で絞り込み、next があれば検索条件を保持して取得を続けます。"""
        ready(request)
        if not 1 <= limit <= 10000:
            raise HTTPException(422, "limitは1〜10000")
        try:
            lo = timestamp(start)
            hi = timestamp(end)
        except ValueError as e:
            raise HTTPException(422, str(e)) from None
        if lo is not None and hi is not None and lo > hi:
            raise HTTPException(422, "開始は終了以前にしてください")
        args = [c.ds, tag]
        where = "ds=? AND tag=?"
        signature = hashlib.sha256(
            json.dumps([tag, start, end, quality]).encode()
        ).hexdigest()
        if lo is not None:
            where += " AND ts>=?"
            args.append(lo)
        if hi is not None:
            where += " AND ts<=?"
            args.append(hi)
        if quality:
            where += " AND quality=?"
            args.append(quality)
        if cursor:
            d = token_data(cursor)
            if d.get("ds") != c.ds or d.get("query") != signature:
                raise HTTPException(409, "カーソル条件が異なります")
            where += " AND (ts,seq)>(?,?)"
            args.extend([d["ts"], d["seq"]])
        with c.store.db() as db:
            rows = db.execute(
                "SELECT * FROM samples WHERE " + where + " ORDER BY ts,seq LIMIT ?",
                [*args, limit + 1],
            ).fetchall()
        values = [
            {
                "timestamp": datetime.fromtimestamp(r["ts"], timezone.utc).isoformat(),
                "value": json.loads(r["value"]),
                "quality": r["quality"],
                "sequence": r["seq"],
            }
            for r in rows[:limit]
        ]
        result = {"tag": tag, "values": values}
        if len(rows) > limit:
            r = rows[limit - 1]
            params = dict(request.query_params)
            params["cursor"] = c.store.token(
                {
                    "ds": c.ds,
                    "query": signature,
                    "ts": r["ts"],
                    "seq": r["seq"],
                    "exp": time.time() + 600,
                }
            )
            result["next"] = str(request.url).split("?", 1)[0] + "?" + urlencode(params)
        return result

    @app.get(
        "/source/history/aggregate",
        tags=["履歴データ"],
        summary="タグの履歴を一定の間隔で集計",
        openapi_extra={"security": SOURCE_AUTH},
        responses={
            **source_errors(422),
            200: json_example(
                "区間ごとの計算結果。filledは欠測補完が入った区間",
                {
                    "tag": "device-001.value",
                    "function": "mean",
                    "good_only": True,
                    "values": [
                        {
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "value": 28.4,
                            "filled": False,
                        }
                    ],
                },
            ),
        },
    )
    def aggregate(
        request: Request,
        tag: Annotated[
            str,
            Query(
                description="/source/history/tags が返したタグ名",
                examples=["device-001.value"],
            ),
        ],
        start: Annotated[
            str,
            Query(
                description="開始時刻。タイムゾーン付きISO日時",
                examples=["2026-01-01T00:00:00Z"],
            ),
        ],
        end: Annotated[
            str,
            Query(
                description="終了時刻。この時刻のサンプルも集計対象",
                examples=["2026-01-01T00:01:00Z"],
            ),
        ],
        interval_seconds: Annotated[
            int,
            Query(
                description="区間幅（秒）。開始・終了を含め最大10000区間",
                json_schema_extra={"minimum": 1},
            ),
        ] = 60,
        function: Annotated[
            str,
            Query(
                description="集計方法",
                json_schema_extra={
                    "enum": ["mean", "min", "max", "sum", "count", "last"]
                },
            ),
        ] = "mean",
        good_only: Annotated[
            bool, Query(description="Goodのサンプルだけを集計")
        ] = True,
        fill: Annotated[
            str,
            Query(
                description="欠測区間を省略・null・直前値で補完",
                json_schema_extra={"enum": ["none", "null", "previous"]},
            ),
        ] = "none",
    ):
        """数値集計には整数・実数を使います。count と last は数値以外も扱います。

        previous は指定期間の内側に直前値がないと null になります。
        """
        ready(request)
        if function not in {
            "mean",
            "min",
            "max",
            "sum",
            "count",
            "last",
        } or fill not in {"none", "null", "previous"}:
            raise HTTPException(422, "集計方法・欠測補完を確認してください")
        try:
            lo, hi = timestamp(start), timestamp(end)
        except ValueError as e:
            raise HTTPException(422, str(e)) from None
        if lo > hi or interval_seconds < 1 or (hi - lo) / interval_seconds > 10000:
            raise HTTPException(422, "期間・間隔は1万区間以下にしてください")
        where = "ds=? AND tag=? AND ts>=? AND ts<=?" + (
            " AND quality='Good'" if good_only else ""
        )
        if function not in {"count", "last"}:
            where += " AND json_type(value) IN ('integer','real')"
        with c.store.db() as db:
            expression = {
                "mean": "avg(CAST(value AS REAL))",
                "min": "min(CAST(value AS REAL))",
                "max": "max(CAST(value AS REAL))",
                "sum": "sum(CAST(value AS REAL))",
                "count": "count(*)",
                "last": "NULL",
            }[function]
            if function == "last":
                rows = db.execute(
                    "SELECT bucket,value FROM (SELECT CAST((ts-?)/? AS INTEGER) bucket,value,row_number() OVER(PARTITION BY CAST((ts-?)/? AS INTEGER) ORDER BY ts DESC,seq DESC) rn FROM samples WHERE "
                    + where
                    + ") WHERE rn=1 ORDER BY bucket",
                    [
                        lo,
                        interval_seconds,
                        lo,
                        interval_seconds,
                        c.ds,
                        tag,
                        lo,
                        hi,
                    ],
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT CAST((ts-?)/? AS INTEGER) bucket,"
                    + expression
                    + " value FROM samples WHERE "
                    + where
                    + " GROUP BY bucket ORDER BY bucket",
                    [lo, interval_seconds, c.ds, tag, lo, hi],
                ).fetchall()
        points = {
            r["bucket"]: json.loads(r["value"]) if function == "last" else r["value"]
            for r in rows
        }
        values = []
        previous = None
        indexes = (
            range(int((hi - lo) // interval_seconds) + 1)
            if fill != "none"
            else sorted(points)
        )
        for i in indexes:
            value = points.get(i, previous if fill == "previous" else None)
            if i in points:
                previous = value
            values.append(
                {
                    "timestamp": datetime.fromtimestamp(
                        lo + i * interval_seconds, timezone.utc
                    ).isoformat(),
                    "value": value,
                    "filled": i not in points,
                }
            )
        return {
            "tag": tag,
            "function": function,
            "good_only": good_only,
            "values": values,
        }
