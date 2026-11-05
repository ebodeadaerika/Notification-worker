// Refreshes the inbox every 10 seconds while the tab is visible.
// Text is inserted with textContent, never innerHTML, so message content can't inject HTML.
(function () {
  var list = document.getElementById("inbox");
  var empty = document.getElementById("empty");
  var updated = document.getElementById("updated");

  function render(items) {
    list.textContent = "";
    items.forEach(function (n) {
      var li = document.createElement("li");
      var title = document.createElement("strong");
      title.textContent = n.title;
      var from = document.createElement("span");
      from.className = "muted";
      from.textContent = " from " + n.from;
      var body = document.createElement("p");
      body.textContent = n.body;
      li.appendChild(title);
      li.appendChild(from);
      li.appendChild(body);
      list.appendChild(li);
    });
    empty.hidden = items.length > 0;
    updated.textContent = "(updated " + new Date().toLocaleTimeString() + ")";
  }

  function refresh() {
    if (document.hidden) return;
    fetch("/api/inbox", { credentials: "same-origin" })
      .then(function (res) {
        if (res.status === 401 || res.redirected) { window.location = "/login"; return null; }
        return res.json();
      })
      .then(function (items) { if (items) render(items); })
      .catch(function () { /* network hiccup: try again next time */ });
  }

  setInterval(refresh, 10000);
})();
