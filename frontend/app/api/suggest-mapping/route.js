// This runs on the server (Node), not in the browser. It receives the
// uploaded file from our React form, forwards it to the Python FastAPI
// service, and passes the JSON response straight back to the frontend.

const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || "http://localhost:8000";

export async function POST(request) {
  try {
    const formData = await request.formData();
    const file = formData.get("file");

    if (!file) {
      return Response.json({ error: "No file provided" }, { status: 400 });
    }

    const forwardData = new FormData();
    forwardData.append("file", file, file.name);

    const pythonRes = await fetch(`${PYTHON_SERVICE_URL}/suggest-mapping`, {
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
