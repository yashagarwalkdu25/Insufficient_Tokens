"""Flask API backend for the Chrome Extension."""
from flask import Flask, request, jsonify
from flask_cors import CORS
from agent import ClaimVerifier
from seed_kb import seed
from vector_store import VectorStore

app = Flask(__name__)
CORS(app)

# Init on startup
seed()
verifier = ClaimVerifier()


@app.route("/api/verify", methods=["POST"])
def verify_claim():
    """Verify a claim. Expects JSON: {"claim": "..."}"""
    data = request.get_json(force=True)
    claim = data.get("claim", "").strip()
    if not claim:
        return jsonify({"error": "No claim provided"}), 400

    try:
        result = verifier.verify(claim)
        evidence_list = []
        for ev in result.evidence:
            evidence_list.append({
                "text": ev.text,
                "source": ev.source,
                "score": round(ev.score, 3),
                "origin": ev.origin,
            })
        return jsonify({
            "claim": result.claim,
            "verdict": result.verdict,
            "confidence": round(result.confidence, 3),
            "reasoning": result.reasoning,
            "evidence": evidence_list,
            "steps": result.steps,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health():
    vs = VectorStore()
    return jsonify({"status": "ok", "kb_size": vs.count()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
