const form = document.querySelector("#config-form");
const statusEl = document.querySelector("#status");
let activeTemplateField = null;

function formToConfig() {
  const data = new FormData(form);
  return {
    bark: {
      server: data.get("server") || "",
      key: data.get("key") || "",
      level: data.get("level") || "",
      sound: data.get("sound") || "",
      icon: data.get("icon") || ""
    },
    message: {
      title_template: data.get("title_template") || "",
      body_template: data.get("body_template") || "",
      max_body_chars: Number(data.get("max_body_chars") || 160)
    }
  };
}

function applyConfig(config) {
  form.elements.server.value = config.bark.server || "";
  form.elements.key.value = config.bark.key || "";
  form.elements.level.value = config.bark.level || "";
  form.elements.sound.value = config.bark.sound || "";
  form.elements.icon.value = config.bark.icon || "";
  form.elements.title_template.value = config.message.title_template || "";
  form.elements.body_template.value = config.message.body_template || "";
  form.elements.max_body_chars.value = config.message.max_body_chars || 160;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {"Content-Type": "application/json"},
    ...options
  });
  const payload = await response.json();
  if (!response.ok || payload.ok === false) {
    throw new Error((payload.errors || ["请求失败。"]).join(" "));
  }
  return payload;
}

function renderPreview(payload) {
  document.querySelector("#watch-title").textContent = payload.watch.title;
  document.querySelector("#watch-body").textContent = payload.watch.body;
  document.querySelector("#phone-title").textContent = payload.phone.title;
  document.querySelector("#phone-body").textContent = payload.phone.body;
  const icon = document.querySelector("#phone-icon");
  if (payload.phone.icon) {
    icon.src = payload.phone.icon;
    icon.hidden = false;
  } else {
    icon.hidden = true;
  }
}

async function refreshPreview() {
  const payload = await requestJson("/api/preview", {
    method: "POST",
    body: JSON.stringify(formToConfig())
  });
  renderPreview(payload);
}

async function loadInitialState() {
  const configPayload = await requestJson("/api/config");
  applyConfig(configPayload.config);
  renderPreview(await requestJson("/api/preview"));
  const install = await requestJson("/api/install-snippet");
  document.querySelector("#install-intro").textContent = install.intro || install.note || "";
  document.querySelector("#install-step1-title").textContent = install.step1_title || "步骤 1";
  document.querySelector("#install-step1-desc").textContent = install.step1_desc || "";
  document.querySelector("#install-toml").textContent = install.toml;
  document.querySelector("#install-step2-title").textContent = install.step2_title || "步骤 2";
  document.querySelector("#install-step2-desc").textContent = install.step2_desc || "";
  document.querySelector("#test-command").textContent = install.test_command;
}

form.addEventListener("focusin", (event) => {
  if (event.target.name === "title_template" || event.target.name === "body_template") {
    activeTemplateField = event.target;
  }
});

document.querySelectorAll("[data-var]").forEach((button) => {
  button.addEventListener("click", () => {
    const target = activeTemplateField || form.elements.body_template;
    const value = button.dataset.var;
    const start = target.selectionStart || target.value.length;
    const end = target.selectionEnd || target.value.length;
    target.value = target.value.slice(0, start) + value + target.value.slice(end);
    target.focus();
    target.setSelectionRange(start + value.length, start + value.length);
    refreshPreview().catch((error) => statusEl.textContent = error.message);
  });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const saved = await requestJson("/api/config", {
      method: "POST",
      body: JSON.stringify(formToConfig())
    });
    applyConfig(saved.config);
    await refreshPreview();
    statusEl.textContent = saved.saved_path
      ? `配置已保存到 ${saved.saved_path}`
      : "配置已保存。";
  } catch (error) {
    statusEl.textContent = error.message;
  }
});

document.querySelector("#test-send").addEventListener("click", async () => {
  try {
    const payload = await requestJson("/api/test-send", {
      method: "POST",
      body: JSON.stringify(formToConfig())
    });
    statusEl.textContent = payload.message || "测试通知已发送。";
  } catch (error) {
    statusEl.textContent = error.message;
  }
});

form.addEventListener("input", () => {
  window.clearTimeout(window.previewTimer);
  window.previewTimer = window.setTimeout(() => {
    refreshPreview().catch((error) => statusEl.textContent = error.message);
  }, 350);
});

loadInitialState().catch((error) => statusEl.textContent = error.message);
