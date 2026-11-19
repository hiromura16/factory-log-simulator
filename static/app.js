"use strict";
const $ = (s) => document.querySelector(s),
  copy = (v) => structuredClone(v);
let info,
  spec,
  profile,
  presets = [],
  profiles = [],
  state,
  uid = 0;
function el(tag, attrs = {}, text = "") {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  n.textContent = text;
  return n;
}
function notice(value, error = false) {
  $("#notice").textContent = value;
  $("#notice").className = error ? "error" : "";
}
async function api(path, body) {
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
  const v = await r.json();
  if (!r.ok)
    throw new Error(
      typeof v.detail === "string" ? v.detail : JSON.stringify(v.detail || v),
    );
  return v;
}
function action(id, fn) {
  $(id).onclick = async (e) => {
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
function tab(id) {
  document
    .querySelectorAll(".tab")
    .forEach((x) => x.classList.toggle("active", x.id === id));
  document
    .querySelectorAll(".nav")
    .forEach((x) => x.classList.toggle("active", x.dataset.tab === id));
}
function ref(s, root) {
  return s.$ref ? root.$defs[s.$ref.split("/").pop()] : s;
}
function empty(s, root) {
  s = ref(s, root);
  if ("default" in s) return copy(s.default);
  if (s.const !== undefined) return s.const;
  if (s.anyOf)
    return s.anyOf.some((x) => x.type === "null")
      ? null
      : empty(s.anyOf[0], root);
  if (s.type === "object")
    return Object.fromEntries(
      Object.entries(s.properties || {}).map(([k, v]) => [k, empty(v, root)]),
    );
  if (s.type === "array") return [];
  if (s.enum) return s.enum[0];
  return s.type === "boolean"
    ? false
    : ["integer", "number"].includes(s.type)
      ? 0
      : "";
}
function object(parent, schema, model, root) {
  for (const [k, s] of Object.entries(schema.properties || {})) {
    if (s.ui_hidden) continue;
    if (!(k in model)) model[k] = empty(s, root);
    parent.append(control(k, s, model[k], (v) => (model[k] = v), root));
  }
}
function control(key, s, value, set, root) {
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
    variants = s.anyOf?.map((x) => ref(x, root)),
    nullableObject = variants?.find((x) => x.type === "object" && x.properties);
  if (nullableObject) {
    const checkbox = el("input", { type: "checkbox", id });
    checkbox.checked = value != null;
    const area = el("div", { class: "grid" });
    box.append(checkbox, area);
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
    function draw() {
      area.replaceChildren();
      value.forEach((row, index) => {
        const d = el("details", { class: "field-card" });
        d.append(
          el(
            "summary",
            {},
            (row.name || row.field || "項目") + " / " + (index + 1),
          ),
        );
        const grid = el("div", { class: "grid" });
        object(grid, item, row, root);
        d.append(grid);
        const buttons = el("div", { class: "actionbar" });
        for (const [text, fn] of [
          [
            "↑",
            () => {
              if (index)
                [value[index - 1], value[index]] = [row, value[index - 1]];
            },
          ],
          ["複製", () => value.splice(index + 1, 0, copy(row))],
          ["削除", () => value.splice(index, 1)],
        ]) {
          const b = el("button", { type: "button" }, text);
          b.onclick = () => {
            fn();
            set(value);
            draw();
          };
          buttons.append(b);
        }
        d.append(buttons);
        area.append(d);
      });
      const add = el("button", { type: "button" }, "＋ 項目を追加");
      add.onclick = () => {
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
    variants?.some((x) => x.format === "password");
  const json =
    shape.type === "array" ||
    shape.type === "object" ||
    (!shape.type && !shape.enum && !s.anyOf) ||
    variants?.some((x) => x.type === "array");
  if (key === "profile_id") {
    input = el("select", { id });
    profiles.forEach((p) =>
      input.append(el("option", { value: p.id }, p.name)),
    );
    input.value = value;
    input.onchange = () => set(input.value);
  } else if (shape.enum) {
    input = el("select", { id });
    shape.enum.forEach((v) =>
      input.append(el("option", { value: v }, String(v))),
    );
    input.value = value;
    input.onchange = () => set(input.value);
  } else if (shape.type === "boolean") {
    input = el("input", { type: "checkbox", id });
    input.checked = !!value;
    input.onchange = () => set(input.checked);
  } else if (json || key === "description") {
    input = el("textarea", {
      id,
      rows: key === "description" ? "8" : "4",
      spellcheck: "false",
    });
    input.value =
      key === "description" ? value : JSON.stringify(value, null, 2);
    input.oninput = () => {
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
    input.oninput = () => {
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
function render() {
  const target = $("#editor");
  target.replaceChildren();
  const area = el("div", { class: "card grid" });
  object(area, info.schemas.spec, spec, info.schemas.spec);
  target.append(area);
}
function renderProfile() {
  const form = $("#profileForm");
  form.replaceChildren();
  object(form, info.schemas.profile, profile, info.schemas.profile);
}
function cleanProfile(p) {
  const v = copy(p);
  delete v.revision;
  delete v.configured_secrets;
  return v;
}
async function refresh() {
  profiles = (await api("/api/profiles")).profiles;
  $("#profileSelect").replaceChildren(
    ...profiles.map((p) => el("option", { value: p.id }, p.name)),
  );
  presets = (await api("/api/presets")).presets;
  $("#presetSelect").replaceChildren(
    ...presets.map((p) =>
      el("option", { value: p.id }, p.spec.name + " · " + p.id),
    ),
  );
  description();
}
function description() {
  const p = presets.find((p) => p.id === $("#presetSelect").value);
  $("#presetDetails").textContent = p?.spec.description || "";
}
function validated(selector) {
  for (const input of $(selector).querySelectorAll("input,select,textarea"))
    if (!input.checkValidity()) {
      input.closest("details")?.setAttribute("open", "");
      input.reportValidity();
      throw new Error("入力を確認してください");
    }
}
function table(target, rows) {
  target.replaceChildren();
  if (!rows?.length) return;
  const names = [...new Set(rows.flatMap((r) => Object.keys(r)))],
    t = el("table"),
    head = el("tr");
  names.forEach((n) => head.append(el("th", {}, n)));
  t.append(head);
  rows.forEach((row) => {
    const tr = el("tr");
    names.forEach((n) =>
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
  });
  target.append(t);
}
function download(value, name) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2) + "\n"], {
      type: "application/json",
    }),
  );
  const a = el("a", { href: url, download: name });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function monitor() {
  state = await api("/api/state");
  $("#status").textContent =
    state.status + " · " + state.produced.toLocaleString() + "件";
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
function show(target) {
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
function hide() {
  tip.hidden = true;
}
document.onmouseover = (e) => {
  const t = e.target.closest("[data-help]");
  if (t) show(t);
  else hide();
};
document.onfocusin = (e) => show(e.target.closest("[data-help]"));
document.onfocusout = hide;
document.onkeydown = (e) => {
  if (e.key === "Escape") hide();
};
window.addEventListener(
  "scroll",
  () => {
    const t =
      document.activeElement?.closest("[data-help]") ||
      [...document.querySelectorAll("[data-help]:hover")].at(-1);
    if (t) show(t);
    else hide();
  },
  true,
);
async function init() {
  info = await api("/api/info");
  $("#title").textContent = info.title;
  document.title = info.title;
  await refresh();
  spec = copy(presets[0]?.spec || info.defaults);
  render();
  profile = cleanProfile(profiles[0]);
  renderProfile();
  document
    .querySelectorAll("[data-tab]")
    .forEach((x) => (x.onclick = () => tab(x.dataset.tab)));
  $("#presetSelect").onchange = description;
  action("#loadPreset", () => {
    spec = copy(presets.find((p) => p.id === $("#presetSelect").value).spec);
    render();
    notice("設定を読み込みました。実行中の状態は開始するまで変わりません。");
  });
  action("#preview", async () => {
    validated("#specForm");
    const v = await api("/api/preview", spec);
    table(
      $("#previewTable"),
      v.records.map((r, i) => ({
        ...r,
        _anomaly: v.anomaly_hits[i].join(","),
      })),
    );
    $("#result").textContent = JSON.stringify(v, null, 2);
    notice("プレビューしました。書き込み・公開・送信はしていません。");
  });
  action("#start", async () => {
    validated("#specForm");
    await api("/api/start", spec);
    await monitor();
    notice("開始しました。");
  });
  action("#stop", async () => {
    await api("/api/stop", {});
    await monitor();
    notice("停止しました。保存済みデータは残ります。");
  });
  action("#toJson", () => {
    validated("#specForm");
    $("#jsonText").value = JSON.stringify(spec, null, 2);
    tab("json");
  });
  async function fromJson() {
    return (await api("/api/preview", JSON.parse($("#jsonText").value)))
      .validated_spec;
  }
  action("#applyJson", async () => {
    spec = await fromJson();
    render();
    tab("generate");
    notice("JSONを検証し画面へ反映しました。");
  });
  action("#savePreset", async () => {
    const id = $("#presetId").value;
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(id))
      throw new Error("プリセットIDを確認してください");
    spec = await fromJson();
    await api("/api/presets/" + id, spec);
    await refresh();
    render();
    notice("プリセットを保存しました。");
  });
  action("#exportJson", async () =>
    download(await fromJson(), $("#presetId").value + ".json"),
  );
  $("#importJson").onchange = async (e) => {
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
  action("#newProfile", () => {
    profile = empty(info.schemas.profile, info.schemas.profile);
    profile.id = "profile-" + Date.now().toString(36);
    profile.name = "新しい公開設定";
    renderProfile();
  });
  action("#editProfile", () => {
    const p = profiles.find((p) => p.id === $("#profileSelect").value);
    profile = cleanProfile(p);
    renderProfile();
    $("#secretState").textContent =
      "設定済み: " + p.configured_secrets.join(", ");
  });
  action("#saveProfile", async () => {
    validated("#profileForm");
    await api("/api/profiles", profile);
    await refresh();
    render();
    notice("保存しました。適用には停止・開始してください。");
  });
  action("#exportProfile", () => {
    const p = cleanProfile(
      profiles.find((p) => p.id === $("#profileSelect").value),
    );
    download(p, p.id + "-profile.json");
  });
  action("#uploadFile", async () => {
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
  });
  $("#jsonText").value = JSON.stringify(spec, null, 2);
  await monitor();
  setInterval(() => monitor().catch(() => {}), 2000);
}
init().catch((e) => notice(e.message, true));
