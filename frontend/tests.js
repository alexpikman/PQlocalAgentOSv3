(() => {
  const btn = document.getElementById("run");
  const status = document.getElementById("status");
  const output = document.getElementById("output");
  const summary = document.getElementById("summary");

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    status.textContent = "Выполняется… (до 5 минут)";
    status.className = "status";
    output.textContent = "";
    summary.innerHTML = "";

    try {
      const res = await fetch("/api/tests/run", { method: "POST" });
      const data = await res.json();

      if (data.ok) {
        status.textContent = "ЗЕЛЁНЫЙ";
        status.className = "status ok";
      } else {
        status.textContent = "КРАСНЫЙ";
        status.className = "status fail";
      }

      summary.innerHTML = `
        <span>Всего: ${data.total ?? "?"}</span>
        <span>Провалов: ${data.failures ?? 0}</span>
        <span>Ошибок: ${data.errors ?? 0}</span>
        <span>Код: ${data.returncode ?? "?"}</span>
      `;
      output.textContent = data.output || "(пусто)";
    } catch (err) {
      status.textContent = "ОШИБКА ЗАПРОСА";
      status.className = "status fail";
      output.textContent = String(err);
    } finally {
      btn.disabled = false;
    }
  });
})();
