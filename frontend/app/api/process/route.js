const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || "http://localhost:8000";

export async function POST(request) {
  try {
    const formData = await request.formData();
    const file = formData.get("file");
    const mapping = formData.get("mapping"); // JSON string, e.g. '{"Order No":"order_id"}'

    if (!file || !mapping) {
      return Response.json({ error: "file and mapping are both required" }, { status: 400 });
    }

    const forwardData = new FormData();
    forwardData.append("file", file, file.name);
    forwardData.append("mapping", mapping);

    // Optional chart-window controls (driven by the results-page filters so the
    // backend stays the source of truth for filtered chart specs).
    ["date_start", "date_end", "group_by", "compare"].forEach((key) => {
      const value = formData.get(key);
      if (value !== null && value !== undefined && value !== "") {
        forwardData.append(key, value);
      }
    });

    const pythonRes = await fetch(`${PYTHON_SERVICE_URL}/process`, {
      method: "POST",
      body: forwardData,
    });

    if (!pythonRes.ok) {
      const errText = await pythonRes.text();
      return Response.json(
        { error: "Python service error", details: errText },
        { status: 502 }
      );
    }

    const data = await pythonRes.json();
    return Response.json(data);
  } catch (err) {
    return Response.json({ error: err.message }, { status: 500 });
  }
}
