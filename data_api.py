"""Snapshot/delta REST, an explicit OData query subset, and historian reads."""

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def timestamp(value):
    if value is None:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("日時にタイムゾーンを付けてください")
    return dt.timestamp()


def predicate(text, fields):
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
            return column + (" IS NULL" if op.lower() == "eq" else " IS NOT NULL")
        if value.startswith("'"):
            parsed = value[1:-1].replace("''", "'")
        elif value.lower() in {"true", "false"}:
            parsed = int(value.lower() == "true")
        else:
            try:
                parsed = float(value) if "." in value else int(value)
            except ValueError:
                raise ValueError("文字列リテラルは単一引用符で囲んでください") from None
        args.append(parsed)
        return column + operator + "?"

    def conjunction():
        nonlocal index
        sql = atom()
        while index < len(tokens) and tokens[index].lower() == "and":
            index += 1
            sql += " AND " + atom()
        return sql

    def expr():
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
    def resource(name):
        opts = c.source_spec().business
        for item in opts.resources:
            if item.name == name:
                return item
        raise HTTPException(404, "コレクションがありません")

    def ready(request):
        authorize(request)
        if not c.ds or c.status == "starting":
            raise HTTPException(
                503, "データを準備しています", headers={"Retry-After": "2"}
            )

    async def fault():
        c.requests += 1
        opts = c.source_spec().business
        if opts.fault == "none" or c.requests % opts.fault_every:
            return None
        if opts.fault == "rate_limit":
            return JSONResponse(
                {"error": "simulated_rate_limit"}, 429, headers={"Retry-After": "2"}
            )
        if opts.fault == "server_error":
            return JSONResponse({"error": "simulated_server_error"}, 503)
        if opts.fault == "unauthorized":
            return JSONResponse({"error": "simulated_expired_credentials"}, 401)
        if opts.fault == "delay":
            await asyncio.sleep(opts.fault_delay_ms / 1000)
        return opts.fault

    def token_data(token):
        try:
            return c.store.untoken(token)
        except TimeoutError as e:
            raise HTTPException(410, str(e)) from None
        except ValueError as e:
            raise HTTPException(400, str(e)) from None

    async def collection(request, name, odata=False):
        ready(request)
        res = resource(name)
        g = res.generator or c.source_spec().generator
        fields = {f.name for f in g.fields} | {"id", "_revision", "_updated_at"}
        injection = await fault()
        if isinstance(injection, Response):
            return injection
        q = request.query_params
        try:
            limit = int(
                q.get("$top" if odata else "limit", c.source_spec().business.page_size)
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
                    or (len(parts) == 2 and parts[1].lower() not in {"asc", "desc"})
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
                    column + " " + (parts[1].upper() if len(parts) == 2 else "ASC")
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
                raise HTTPException(409, "カーソルのデータセット・条件が一致しません")
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
                "SELECT count(*) FROM (" + base + ")", [c.ds, name, snapshot, *args]
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
            values.append({k: value.get(k) for k in selected} if selected else value)
        exp = time.time() + c.source_spec().business.cursor_ttl_seconds
        delta = c.store.token(
            {"ds": c.ds, "res": name, "rev": snapshot, "exp": exp, "type": "delta"}
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
                str(request.base_url).rstrip("/") + "/source/odata/$metadata#" + name
            )
        if injection == "truncate_json":
            return Response(
                json.dumps(result)[: max(1, len(json.dumps(result)) // 2)],
                media_type="application/json",
            )
        return JSONResponse(result, headers={"OData-Version": "4.0"} if odata else {})

    @app.get("/source/rest/{name}")
    async def rest(request: Request, name: str):
        return await collection(request, name)

    @app.get("/source/odata/$metadata")
    def metadata(request: Request):
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

    @app.get("/source/odata/{name}")
    async def odata(request: Request, name: str):
        return await collection(request, name, True)

    @app.get("/source/rest/{name}/delta")
    def delta(request: Request, name: str, token: str, limit: int = 100):
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
            {"id": r["id"], "@removed": {"reason": "deleted"}, "_revision": r["rev"]}
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

    @app.api_route("/source/rest/{name}/{identity}", methods=["GET", "PATCH", "DELETE"])
    async def single(request: Request, name: str, identity: str):
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

    @app.post("/source/rest/{name}")
    async def insert(request: Request, name: str):
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

    @app.get("/source/history/tags")
    def tags(request: Request):
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

    @app.get("/source/history/raw")
    def raw(
        request: Request,
        tag: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 1000,
        cursor: str | None = None,
        quality: str | None = None,
    ):
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

    @app.get("/source/history/aggregate")
    def aggregate(
        request: Request,
        tag: str,
        start: str,
        end: str,
        interval_seconds: int = 60,
        function: str = "mean",
        good_only: bool = True,
        fill: str = "none",
    ):
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
                    [lo, interval_seconds, lo, interval_seconds, c.ds, tag, lo, hi],
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
