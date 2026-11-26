// 管理画面: スキーマから入力を作り、APIへ検証・保存・開始を依頼する。
// 編集状態はブラウザー内、実行状態と永続化はサーバー側が管理する。
"use strict";
const $ =
    (
      s,
    ) => document.querySelector(s),
  copy =
    /* 設定値を深く複製し、編集中の変更が元プリセットへ伝わることを防ぐ。複製不能な値は例外になる。 */ (
      v,
    ) => structuredClone(v);
let info,
  spec,
  profile,
  presets = [],
  profiles = [],
  state,
  uid = 0;
/* タグ・属性・表示文字列から未配置のDOM要素を返す。文字列はHTMLとして解釈せずtextContentに設定する。 */
function el(
  tag,
  attrs = {},
  text = "",
) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  n.textContent = text;
  return n;
}
/* 通知欄の内容とエラー用CSSクラスを更新する。戻り値は使わず、直前の通知を置き換える。 */
function notice(
  value,
  error = false,
) {
  $("#notice").textContent = value;
  $("#notice").className = error ? "error" : "";
}
/* 本文なしはGET、本文ありはJSONのPOSTで同一サービスへ要求し、JSON応答を返す。通信・JSON解析・非成功応答は例外として呼出側へ伝える。 */
async function api(
  path,
  body,
) {
  const r = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  return readApiJson(r);
}
/* 送信しない見本として本文・フレーミング・異常をテキスト表示する。 */
function renderLogPreview(plan) {
  const target = $("#logPreview");
  target.replaceChildren();
  if (!plan) return;
  const labels = { capture: "アプリ内記録", file: "回転ファイル", udp: "Syslog UDP", tcp: "Syslog TCP", tls: "Syslog TLS" };
  target.append(el("p", {},
    plan.format + " / " + (labels[plan.output] || plan.output || "出力先未登録") +
    (plan.tcp_framing ? " / " + plan.tcp_framing : "") +
    "。既定の見本時刻は書式を比べるための固定値です。送信・保存はしていません。"));
  for (const sample of plan.samples) {
    target.append(el("p", { class: "muted" },
      "連番 " + sample.sequence + " / UTF-8 " + sample.message_bytes + " バイト" +
      (sample.wire_bytes === null ? "" : " / TCP境界込み " + sample.wire_bytes + " バイト") +
      (sample.duplicate ? " / 重複あり" : "") + (sample.malformed ? " / 破損ヘッダー" : "")));
    target.append(el("pre", {}, sample.payload));
  }
}

/* 外部送信とファイル保存は確認し、確認した出力先の版だけで実行する。 */
function confirmedStartPath() {
  const destination = profiles.find((item) => item.id === spec.profile_id);
  if (!destination?.revision) throw new Error("登録済み出力先を確認してください。");
  if (destination.output !== "capture" &&
      !window.confirm("「" + destination.name + "」(" + destination.id + "・版 " + destination.revision + ") へログを出力します。続行しますか？")) return null;
  return "/api/start?profile_revision=" + destination.revision;
}

/* 指定ボタンへ非同期処理を登録する。処理中の二重操作を防ぎ、失敗通知とボタン復帰を共通化する。 */
function action(
  id,
  fn,
) {
  $(id).onclick =
    async (
      e,
    ) => {
      e.preventDefault();
      const button = e.currentTarget;
      button.disabled = true;
      try {
        await fn();
      } catch (err) {
        notice(err.message, true);
      } finally {
        button.disabled = false;
      }
    };
}
/* 対象IDのパネルとナビゲーションにactiveを付け、他を非表示扱いにする。編集モデル自体は変更しない。 */
function tab(
  id,
) {
  document
    .querySelectorAll(".tab")
    .forEach(
      /* パネルIDが選択IDと一致するときだけactiveを付与する。 */ (x) =>
        x.classList.toggle("active", x.id === id),
    );
  document
    .querySelectorAll(".nav")
    .forEach(
      /* ナビゲーションのdata-tabが選択IDと一致するときだけactiveを付与する。 */ (x) =>
        x.classList.toggle("active", x.dataset.tab === id),
    );
}
/* ローカルJSON Schemaの$refを$defsから引く。外部URLの取得や参照先の存在検証は行わない。 */
function ref(
  s,
  root,
) {
  return s.$ref ? root.$defs[s.$ref.split("/").pop()] : s;
}
/* スキーマから編集用初期値を再帰生成する。defaultは複製し、nullableはnull、配列は空、オブジェクトは各プロパティを初期化する。 */
function empty(
  s,
  root,
) {
  s = ref(s, root);
  if ("default" in s) return copy(s.default);
  if (s.const !== undefined) return s.const;
  if (s.anyOf)
    return s.anyOf.some(
      /* anyOf内にnull型があるかを判定する。 */ (x) => x.type === "null",
    )
      ? null
      : empty(s.anyOf[0], root);
  if (s.type === "object")
    return Object.fromEntries(
      Object.entries(s.properties || {}).map(
        /* 各プロパティ名と、そのスキーマから再帰生成した初期値の組を返す。 */ ([
          k,
          v,
        ]) => [k, empty(v, root)],
      ),
    );
  if (s.type === "array") return [];
  if (s.enum) return s.enum[0];
  return s.type === "boolean" ? false : ["integer", "number"].includes(s.type) ? 0 : "";
}
/* 表示可能なプロパティごとに入力部品を配置する。欠けた値はモデルへ初期設定し、変更コールバックが同じモデルを更新する。 */
function object(
  parent,
  schema,
  model,
  root,
) {
  for (const [k, s] of Object.entries(schema.properties || {})) {
    if (s.ui_hidden) continue;
    if (!(k in model)) model[k] = empty(s, root);
    parent.append(
      control(
        k,
        s,
        model[k],
        /* 入力部品の新しい値を現在のプロパティへ書き戻す。 */ (v) => (model[k] = v),
        root,
      ),
    );
  }
}
/* スキーマに合うDOM入力を返す。変更時はsetへ値を渡す。入れ子・配列・秘密・JSONを分け、ここでは保存要求を送らない。 */
function control(
  key,
  s,
  value,
  set,
  root,
) {
  const box = el("div", {
      class: "control hint",
      "data-help": s.description || s.title || key,
    }),
    id = "f" + ++uid,
    label = el("label", { for: id }, s.title || key);
  label.append(
    el(
      "span",
      {
        class: "help",
        tabindex: "0",
        "aria-describedby": "tooltip",
        "aria-label": (s.title || key) + "の説明",
      },
      "?",
    ),
  );
  box.append(label);
  const shape = ref(s, root),
    variants = s.anyOf?.map(
      /* anyOfの各候補についてローカル参照を解決する。 */ (x) => ref(x, root),
    ),
    nullableObject = variants?.find(
      /* プロパティを持つオブジェクト型候補を選ぶ。nullableな入れ子の編集判定に使う。 */ (
        x,
      ) => x.type === "object" && x.properties,
    );
  if (nullableObject) {
    const checkbox = el("input", { type: "checkbox", id });
    checkbox.checked = value != null;
    const area = el("div", { class: "grid" });
    box.append(checkbox, area);
    /* 有効チェックに応じて入れ子フォームを再生成する。無効時はnullを通知し、有効時のみ初期値または既存値を編集する。 */
    function draw() {
      area.replaceChildren();
      if (checkbox.checked) {
        value = value || empty(nullableObject, root);
        set(value);
        object(area, nullableObject, value, root);
      } else set(null);
    }
    checkbox.onchange = draw;
    draw();
    box.classList.add("subsection");
    return box;
  }
  if (shape.type === "object" && shape.properties) {
    const d = el("details", { class: "subsection" });
    d.open = key === "generator";
    d.append(el("summary", {}, s.title || key));
    const area = el("div", { class: "grid" });
    object(area, shape, value, root);
    d.append(area);
    return d;
  }
  const item = shape.items ? ref(shape.items, root) : null;
  if (shape.type === "array" && item?.properties) {
    box.classList.add("subsection");
    const area = el("div");
    box.append(area);
    /* 配列全体のカードを再生成する。編集後は添字が変わるため、古いカードのイベント処理を再利用しない。 */
    function draw() {
      area.replaceChildren();
      value.forEach(
        /* 配列の一行を編集カードへ変換し、移動・複製・削除ボタンを配置する。 */ (
          row,
          index,
        ) => {
          const d = el("details", { class: "field-card" });
          d.append(
            el("summary", {}, (row.name || row.field || "項目") + " / " + (index + 1)),
          );
          const grid = el("div", { class: "grid" });
          object(grid, item, row, root);
          d.append(grid);
          const buttons = el("div", { class: "actionbar" });
          for (const [text, fn] of [
            [
              "↑",
              /* 先頭以外の行を直前の行と交換する。配列そのものを変更し、再描画は外側のクリック処理が行う。 */ () => {
                if (index) [value[index - 1], value[index]] = [row, value[index - 1]];
              },
            ],
            [
              "複製",
              /* 現在行の深い複製を直後へ挿入し、入れ子オブジェクトの共有を避ける。 */ () =>
                value.splice(index + 1, 0, copy(row)),
            ],
            [
              "削除",
              /* 現在添字の行を配列から一つ取り除く。 */ () => value.splice(index, 1),
            ],
          ]) {
            const b = el("button", { type: "button" }, text);
            b.onclick =
              /* 選択した配列操作を実行し、変更通知後に全カードを再描画する。 */ () => {
                fn();
                set(value);
                draw();
              };
            buttons.append(b);
          }
          d.append(buttons);
          area.append(d);
        },
      );
      const add = el("button", { type: "button" }, "＋ 項目を追加");
      add.onclick =
        /* 項目スキーマの初期値を末尾へ追加し、変更通知と再描画を行う。 */ () => {
          value.push(empty(item, root));
          set(value);
          draw();
        };
      area.append(add);
    }
    draw();
    return box;
  }
  let input;
  const secret =
    shape.format === "password" ||
    variants?.some(
      /* 候補がpassword形式かを調べ、秘密入力欄の判定に使う。 */ (x) =>
        x.format === "password",
    );
  const json =
    shape.type === "array" ||
    shape.type === "object" ||
    (!shape.type && !shape.enum && !s.anyOf) ||
    variants?.some(
      /* 候補に配列型があるかを調べ、JSONテキスト編集が必要か判定する。 */ (x) =>
        x.type === "array",
    );
  if (key === "profile_id") {
    input = el("select", { id });
    profiles.forEach(
      /* 保存済みプロファイルをID値と表示名の選択肢として追加する。 */ (p) =>
        input.append(el("option", { value: p.id }, p.name)),
    );
    input.value = value;
    input.onchange = /* 選択されたプロファイルIDを編集モデルへ通知する。 */ () =>
      set(input.value);
  } else if (shape.enum) {
    input = el("select", { id });
    shape.enum.forEach(
      /* enumの値を選択肢へ追加する。ラベルは文字列表現、値はDOM属性に渡す。 */ (v) =>
        input.append(el("option", { value: v }, String(v))),
    );
    input.value = value;
    input.onchange = /* 列挙選択の文字列値を編集モデルへ通知する。 */ () =>
      set(input.value);
  } else if (shape.type === "boolean") {
    input = el("input", { type: "checkbox", id });
    input.checked = !!value;
    input.onchange = /* チェック状態を真偽値として編集モデルへ通知する。 */ () =>
      set(input.checked);
  } else if (json || key === "description") {
    input = el("textarea", {
      id,
      rows: key === "description" ? "8" : "4",
      spellcheck: "false",
    });
    input.value = key === "description" ? value : JSON.stringify(value, null, 2);
    input.oninput =
      /* 説明文は文字列のまま、それ以外はJSON解析して通知する。解析失敗はフォームの検証エラーにし、モデルを壊れたJSONで更新しない。 */ () => {
        try {
          set(key === "description" ? input.value : JSON.parse(input.value));
          input.setCustomValidity("");
        } catch {
          input.setCustomValidity("JSONの構文を確認してください");
        }
      };
  } else {
    const numeric = ["integer", "number"].includes(shape.type);
    input = el("input", {
      id,
      type: secret ? "password" : numeric ? "number" : "text",
      autocomplete: secret ? "new-password" : "off",
    });
    input.value = value ?? "";
    if (numeric) input.step = shape.type === "integer" ? "1" : "any";
    if (shape.minimum !== undefined) input.min = shape.minimum;
    if (shape.maximum !== undefined) input.max = shape.maximum;
    if (secret) input.placeholder = "空欄は同じ設定の保存値を維持";
    input.oninput =
      /* 入力を秘密の空欄・nullable・数値の順に変換して通知する。秘密の空欄はnullとして保存済み値の維持を要求する。 */ () => {
        let next = input.value;
        if (secret) next = next || null;
        else if (s.anyOf) {
          if (!next) next = null;
          else
            try {
              next = JSON.parse(next);
            } catch {}
        } else if (numeric) next = Number(next);
        set(next);
      };
  }
  box.append(input);
  return box;
}
/* 生成設定の編集領域を現在specから作り直す。DOMのみ置き換え、サーバーへ保存しない。 */
function render() {
  const root = info.schemas.spec;
  const { profile_id: profileField, ...options } = root.properties;
  const basics = $("#basicEditor");
  const advanced = $("#editor");
  basics.replaceChildren();
  advanced.replaceChildren();
  object(basics, { properties: {
    profile_id: { ...profileField, title: "ログの出力設定" },
  } }, spec, root);
  const { batch_size, ...advancedOptions } = options;
  object(basics, { properties: {
    batch_size: { ...batch_size, title: "1回につくるログの件数" },
  } }, spec, root);
  const logs = ref(advancedOptions.logs, root);
  const labels = {
    format: "ログ書式",
    facility: "発生元の分類（Facility）",
    severity: "重要度（Severity）",
    hostname: "ログ内のホスト名",
    app_name: "ログ内のアプリ名",
    message_template: "ログ本文のひな型",
    rotate_mb: "ファイルを切り替えるサイズ（MiB）",
    backups: "残す過去ファイルの数",
    duplicate_every: "重複を発生させる間隔",
    malformed_every: "壊れたヘッダーを発生させる間隔",
  };
  const logOptions = Object.fromEntries(Object.entries(logs.properties).map(
    ([key, option]) => [key, labels[key] ? { ...option, title: labels[key] } : option],
  ));
  advancedOptions.logs = { ...logs, title: "ログ設定", properties: logOptions };
  object(advanced, { properties: advancedOptions }, spec, root);
  $("#editingPreset").textContent = "編集中の設定: " + (spec.name || "名称未設定");
  $("#previewResults").hidden = true;
}
/* 現在profileから接続設定フォームを作り直す。保存は別の操作で行う。 */
function renderProfile() {
  const form = $("#profileForm");
  form.replaceChildren();
  object(form, info.schemas.profile, profile, info.schemas.profile);
}
/* プロファイルを複製して表示管理用のrevisionとconfigured_secretsを除く。元データは変更しない。 */
function cleanProfile(
  p,
) {
  const v = copy(p);
  delete v.revision;
  delete v.configured_secrets;
  return v;
}
/* プロファイルとプリセットを順に再取得して選択肢を再構成する。通信失敗は呼出側へ伝わり、途中まで更新される場合がある。 */
async function refresh() {
  profiles = (await api("/api/profiles")).profiles;
  $("#profileSelect").replaceChildren(
    ...profiles.map(
      /* プロファイルIDを値、名前をラベルとするoptionを返す。 */ (p) =>
        el("option", { value: p.id }, p.name),
    ),
  );
  presets = (await api("/api/presets")).presets;
  $("#presetSelect").replaceChildren(
    ...presets.map(
      /* プリセットIDを値、設定名とIDをラベルとするoptionを返す。 */ (p) =>
        el("option", { value: p.id }, p.spec.name + " · " + p.id),
    ),
  );
  description();
}
/* 選択プリセットの説明を文字列として表示する。未選択・未検出は空文字列にする。 */
function description() {
  const p = presets.find(
    /* 現在選択中のプリセットIDと一致する要素を探す。 */ (p) =>
      p.id === $("#presetSelect").value,
  );
  const parts = (p?.spec.description || "").trim().split(/\r?\n\s*\r?\n/);
  const scenario = parts.shift()?.replace(/^【想定(?:する状況)?】\s*/, "").trim();
  $("#presetScenario").textContent = scenario || "このひな型には状況の説明がありません。";
  $("#presetDetails").textContent = parts.join("\n\n");
  $("#presetDetailsPanel").hidden = parts.length === 0;
}
/* フォーム内の制約違反を探す。該当箇所のdetailsを開いてブラウザーの検証表示を出し、例外で後続操作を止める。 */
function validated(
  selector,
  showError = true,
) {
  for (const input of $(selector).querySelectorAll("input,select,textarea"))
    if (!input.checkValidity()) {
      if (showError) {
        for (let details = input.closest("details"); details;
          details = details.parentElement.closest("details")) {
          details.open = true;
        }
        input.reportValidity();
      }
      throw new Error("入力を確認してください");
    }
}
/* 行配列から表を作り直す。全行のキーの和集合を列にし、欠落値を明示する。値はHTMLとして解釈しない。 */
function table(
  target,
  rows,
) {
  target.replaceChildren();
  if (!rows?.length) return;
  const names = [
      ...new Set(
        rows.flatMap(
          /* 行のキーを列候補として返す。後段のSetで重複を除く。 */ (r) =>
            Object.keys(r),
        ),
      ),
    ],
    t = el("table"),
    head = el("tr");
  names.forEach(
    /* 列名をテキストの見出しセルとして追加する。 */ (n) =>
      head.append(el("th", {}, n)),
  );
  t.append(head);
  rows.forEach(
    /* 一行の表要素を作り、すべての列についてセルを追加して表へ配置する。 */ (row) => {
      const tr = el("tr");
      names.forEach(
        /* オブジェクト値はJSON文字列、それ以外は文字列へ変換してセルに入れる。欠落値は専用表示にする。 */ (
          n,
        ) =>
          tr.append(
            el(
              "td",
              {},
              typeof row[n] === "object"
                ? JSON.stringify(row[n])
                : String(row[n] ?? "〈欠落〉"),
            ),
          ),
      );
      t.append(tr);
    },
  );
  target.append(t);
}
/* 値を整形JSONのBlobへ変換し、指定名でブラウザーダウンロードを開始する。生成URLは遅延解放してクリック直後の読込を妨げない。 */
function download(
  value,
  name,
) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2) + "\n"], {
      type: "application/json",
    }),
  );
  const a = el("a", { href: url, download: name });
  a.click();
  setTimeout(
    /* 生成したBlob URLを解放する。ダウンロード完了の保証や監視ではない。 */ () =>
      URL.revokeObjectURL(url),
    1000,
  );
}
/* 実行状態を取得し、件数・状態JSON・公開インターフェース・最近のレコードを更新する。取得失敗は呼出側が扱う。 */
async function monitor() {
  state = await api("/api/state");
  const statusLabels = {
    stopped: "停止中",
    starting: "起動中",
    running: "実行中",
    stopping: "停止処理中",
    failed: "エラー",
  };
  $("#status").textContent =
    (statusLabels[state.status] ?? state.status) + " · " +
    state.produced.toLocaleString() + "件";
  $("#stateJson").textContent = JSON.stringify(state, null, 2);
  $("#interfaces").textContent = JSON.stringify(
    state.protocols && Object.keys(state.protocols).length
      ? state.protocols
      : info.source_paths,
    null,
    2,
  );
  table($("#currentTable"), state.recent);
}
const tip = $("#tooltip");
/* 説明対象のdata-helpを表示し、画面外へはみ出しにくい位置へツールチップを配置する。説明のない対象は何もしない。 */
function show(
  target,
) {
  if (!target?.dataset.help) return;
  tip.textContent = target.dataset.help;
  $("#contextHelp").textContent = target.dataset.help;
  tip.hidden = false;
  const r = target.getBoundingClientRect();
  tip.style.left =
    Math.max(12, Math.min(innerWidth - tip.offsetWidth - 12, r.left)) + "px";
  tip.style.top =
    Math.max(
      12,
      r.bottom + tip.offsetHeight < innerHeight
        ? r.bottom + 8
        : r.top - tip.offsetHeight - 8,
    ) + "px";
}
/* ツールチップを非表示にする。説明文の内容は保持する。 */
function hide() {
  tip.hidden = true;
}
document.onmouseover =
  /* マウス位置に最も近い説明対象を探し、ある場合は表示、ない場合は非表示にする。 */ (
    e,
  ) => {
    const t = e.target.closest("[data-help]");
    if (t) show(t);
    else hide();
  };
document.onfocusin =
  /* フォーカスされた入力に最も近い説明対象のツールチップを表示する。 */ (e) =>
    show(e.target.closest("[data-help]"));
document.onfocusout = hide;
document.onkeydown = /* Escapeキーの場合だけツールチップを閉じる。 */ (e) => {
  if (e.key === "Escape") hide();
};
window.addEventListener(
  "scroll",
  /* スクロール後にフォーカス対象または最後のhover対象を探して位置を更新する。該当なしなら非表示にする。 */ () => {
    const t =
      document.activeElement?.closest("[data-help]") ||
      [...document.querySelectorAll("[data-help]:hover")].at(-1);
    if (t) show(t);
    else hide();
  },
  true,
);
/* 初期情報・保存済み設定を読み、フォームと操作イベントを接続する。最後に状態監視を開始する。初期化失敗は末尾のcatchで通知する。 */
async function init() {
  info = await api("/api/info");
  $("#title").textContent = info.title;
  document.title = info.title;
  await refresh();
  spec = copy(presets[0]?.spec || info.defaults);
  render();
  profile = cleanProfile(profiles[0]);
  renderProfile();
  window.FactoryComparison.mount({
    app: "log-simulator",
    listPresets: () => presets,
    currentSpec: () => {
      validated("#specForm", false);
      return copy(spec);
    },
    preview: (candidate) => api("/api/preview", candidate),
    metrics: (spec, data) => ({
      "ログ書式": spec.logs.format,
      "見本の最小サイズ（B）": data.log_preview?.samples.length ? Math.min(...data.log_preview.samples.map((row) => row.message_bytes)) : null,
      "見本の最大サイズ（B）": data.log_preview?.samples.length ? Math.max(...data.log_preview.samples.map((row) => row.message_bytes)) : null,
      "重複する見本の数": data.log_preview?.samples.filter((row) => row.duplicate).length ?? null,
      "書式不正の見本の数": data.log_preview?.samples.filter((row) => row.malformed).length ?? null,
      "切り替えサイズ（MiB）": spec.logs.rotate_mb,
      "保管するローテーション数": spec.logs.backups,
    }),
  });
  document
    .querySelectorAll("[data-tab]")
    .forEach(
      /* 各ナビゲーション要素に対応タブを開くクリック処理を登録する。 */ (x) =>
        (x.onclick = /* 押されたナビゲーションが指すタブへ切り替える。 */ () =>
          tab(x.dataset.tab)),
    );
  $("#specForm").addEventListener("submit", (event) => event.preventDefault());
  $("#specForm").addEventListener("input", () => {
    $("#editingPreset").textContent = "編集中の設定: " + (spec.name || "名称未設定");
    $("#previewResults").hidden = true;
  });
  $("#presetSelect").onchange = description;
  action(
    "#loadPreset",
    /* 選択プリセットを複製して編集欄へ読み込む。開始要求は送らないので、実行中の設定はここでは変えない。 */ () => {
      spec = copy(
        presets.find(
          /* 選択IDに対応する読込元プリセットを探す。 */ (p) =>
            p.id === $("#presetSelect").value,
        ).spec,
      );
      render();
      notice("設定を読み込みました。実行中の状態は開始するまで変わりません。");
    },
  );
  action(
    "#preview",
    /* フォーム検証後にプレビュー要求を送り、レコード・異常注入結果・応答JSONを表示する。実際の開始要求は行わない。 */ async () => {
      validated("#specForm");
      const submitted = JSON.stringify(spec);
      const v = await api("/api/preview", JSON.parse(submitted));
      if (submitted !== JSON.stringify(spec)) return;
      renderLogPreview(v.log_preview);
      table(
        $("#previewTable"),
        v.records.map(
          /* レコードの複製へ対応する異常注入名を表示用の列として追加する。 */ (
            r,
            i,
          ) => ({
            ...r,
            _anomaly: v.anomaly_hits[i].join(","),
          }),
        ),
      );
      $("#result").textContent = JSON.stringify(v, null, 2);
      const results = $("#previewResults");
      results.hidden = false;
      results.focus();
      notice("見本を表示しました。");
    },
  );
  action(
    "#start",
    /* フォーム検証後に開始要求を送信し、状態を再取得して通知する。失敗は共通action処理が表示する。 */ async () => {
      validated("#specForm");
      const path = confirmedStartPath();
      if (!path) return;
      await api(path, spec);
      await monitor();
      notice("開始しました。");
    },
  );
  action(
    "#stop",
    /* 停止要求を送り、最新状態を表示する。保存済みデータを削除する要求ではない。 */ async () => {
      await api("/api/stop", {});
      await monitor();
      notice("停止しました。保存済みデータは残ります。");
    },
  );
  action(
    "#toJson",
    /* フォーム検証後のspecを整形JSON欄へ転記してJSONタブを開く。 */ () => {
      validated("#specForm");
      $("#jsonText").value = JSON.stringify(spec, null, 2);
      $("#presetId").value = "";
      $("#presetDisplayName").value = "";
      $("#presetPurpose").value = "";
      tab("json");
      $("#presetId").focus();
    },
  );
  /* JSON欄を解析してプレビューAPIで検証し、正規化された設定を返す。JSON構文・API検証エラーは呼出側へ伝える。 */
  async function fromJson(draft = readPresetJson($("#jsonText").value), compact = false) {
    const preview = await api("/api/preview", draft);
    return compact ? preview.compact_spec : preview.validated_spec;
  }
  action(
    "#applyJson",
    /* JSONから検証済み設定を取得してフォームへ反映する。実行開始や保存は別操作とする。 */ async () => {
      spec = await fromJson();
      render();
      tab("generate");
      notice("JSONを検証し画面へ反映しました。");
    },
  );
  action(
    "#savePreset",
    /* プリセットIDの文字種と長さを確認し、検証済みJSONを保存する。成功後は一覧とフォームを更新する。 */ async () => {
      const id = $("#presetId").value;
      if (!/^[A-Za-z0-9_-]{1,64}$/.test(id))
        throw new Error("プリセットIDを確認してください");
      const draft = readPresetJson($("#jsonText").value);
      const displayName = $("#presetDisplayName").value.trim();
      const purpose = $("#presetPurpose").value.trim();
      if (displayName) draft.name = displayName;
      if (purpose) draft.description = purpose;
      spec = await fromJson(draft);
      await api("/api/presets/" + id, spec);
      $("#jsonText").value = JSON.stringify(spec, null, 2);
      await refresh();
      $("#presetSelect").value = id;
      description();
      render();
      notice("プリセットを保存しました。");
    },
  );
  action(
    "#exportJson",
    /* JSON欄の検証済み設定を指定IDのファイル名でダウンロードする。 */ async () =>
      download(await fromJson(undefined, $("#compactExport").checked), $("#presetId").value + ".json"),
  );
  $("#importJson").onchange =
    /* 選択ファイルの2MiB制限を確認してJSON欄へ読み込み、サーバー検証後にフォームへ反映する。失敗は通知し、保存はしない。 */ async (
      e,
    ) => {
      try {
        const file = e.target.files[0];
        if (file.size > 2 * 1024 ** 2) throw new Error("JSONは2MiB以下です");
        $("#jsonText").value = await file.text();
        spec = await fromJson();
        render();
        notice("JSONを読み込みました。");
      } catch (err) {
        notice(err.message, true);
      }
    };
  action(
    "#newProfile",
    /* スキーマ初期値から新しい編集用プロファイルを作る。時刻ベースのIDを与えるが、この時点ではサーバーに保存しない。 */ () => {
      profile = empty(info.schemas.profile, info.schemas.profile);
      profile.id = "profile-" + Date.now().toString(36);
      profile.name = "新しい公開設定";
      renderProfile();
    },
  );
  action(
    "#editProfile",
    /* 選択済みプロファイルを複製して編集し、秘密の値ではなく設定済み項目名だけを表示する。 */ () => {
      const p = profiles.find(
        /* 編集対象のプロファイルIDと一致する要素を探す。 */ (p) =>
          p.id === $("#profileSelect").value,
      );
      profile = cleanProfile(p);
      renderProfile();
      $("#secretState").textContent = "設定済み: " + p.configured_secrets.join(", ");
    },
  );
  action(
    "#saveProfile",
    /* 接続設定フォームを検証して保存要求を送り、一覧と生成設定の表示を更新する。実行中への反映には再開始が必要。 */ async () => {
      validated("#profileForm");
      await api("/api/profiles", profile);
      await refresh();
      render();
      notice("保存しました。適用には停止・開始してください。");
    },
  );
  action(
    "#exportProfile",
    /* 選択プロファイルから表示管理情報を除いてJSONをダウンロードする。秘密を取得する追加要求は行わない。 */ () => {
      const p = cleanProfile(
        profiles.find(
          /* 書出し対象のプロファイルIDと一致する要素を探す。 */ (p) =>
            p.id === $("#profileSelect").value,
        ),
      );
      download(p, p.id + "-profile.json");
    },
  );
  action(
    "#uploadFile",
    /* 1MiB以下の接続ファイルをバイト列からBase64へ変換してアップロードする。名前とサイズを確認し、APIエラーは共通処理へ伝える。 */ async () => {
      const f = $("#certFile").files[0];
      if (!f || f.size > 1024 ** 2)
        throw new Error("1MiB以下のファイルを選んでください");
      const bytes = new Uint8Array(await f.arrayBuffer());
      let raw = "";
      for (const b of bytes) raw += String.fromCharCode(b);
      const name = $("#certName").value || f.name;
      const result = await api("/api/connection-files", {
        name,
        content_base64: btoa(raw),
      });
      notice(result.name + " を権限600で配置しました。");
    },
  );
  $("#jsonText").value = JSON.stringify(spec, null, 2);
  await monitor();
  setInterval(
    /* 2秒ごとに状態取得を試みる。監視失敗はここで抑え、次周期に再試行する。重複実行の排他制御は持たない。 */ () =>
      monitor().catch(
        /* 定期監視の失敗だけを無視する。開始・保存などの利用者操作のエラー処理とは別にする。 */ () => {},
      ),
    2000,
  );
}
init().catch(
  /* 初期化の例外をエラー通知欄へ表示する。 */ (e) => notice(e.message, true),
);
