import json
import logging
import os
import re

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "ap-southeast-2")
KB_ID = os.environ["KB_ID"]
MODEL_ID = os.environ["MODEL_ID"]
TOP_K = int(os.environ.get("TOP_K", "6"))

agent_rt = boto3.client("bedrock-agent-runtime", region_name=REGION)
model_rt = boto3.client("bedrock-runtime", region_name=REGION)

SYSTEM_PROMPT = """You are a contract-analysis assistant. You answer questions using ONLY the numbered excerpts provided.

Rules:
1. Use only information that appears in the excerpts. Never use outside knowledge about the contract.
2. If the excerpts do not clearly contain the answer, reply exactly: "Not found in the retrieved excerpts." Do not guess. A clause that is not mentioned should be reported as not found, never invented.
3. Cite the excerpt number(s) like [2] after each claim, and the section number if the excerpt shows one.
4. Quote contract language only when exact wording matters, and keep quotes short and verbatim.
5. If different excerpts contain different provisions on the same topic (for example, a main agreement and an exhibit), mention each separately.
6. Be concise. Do not add commentary, speculation, or legal advice.
7. You only answer questions about the contract excerpts provided. If the question is unrelated to contracts or the excerpts (general knowledge, trivia, personal advice), reply exactly: "I can only answer questions about the loaded contracts."
8. State only what the excerpts say. Do not use words like "presumably", "likely" or "may include" to fill gaps. If the excerpts do not say it, say so.
9. If more than one excerpt contains a provision on the same topic (for example the main agreement and an exhibit), mention each and say where it appears."""

DISCLAIMER = "This is legal information based on the retrieved excerpts, not legal advice."


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def _parse_event(event):
    body = event.get("body", event)
    if isinstance(body, str):
        body = json.loads(body)
    return body


def retrieve(question, contract):
    vs_cfg = {"numberOfResults": TOP_K}
    if contract:
        vs_cfg["filter"] = {"equals": {"key": "contract", "value": contract}}
    resp = agent_rt.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": question},
        retrievalConfiguration={"vectorSearchConfiguration": vs_cfg},
    )
    #print (f"response:{resp}")
    return resp.get("retrievalResults", [])


def build_context(results):
    parts, sources = [], []
    for i, r in enumerate(results, start=1):
        text = re.sub(r"\s+", " ", r["content"]["text"]).strip()
        uri = r.get("location", {}).get("s3Location", {}).get("uri", "unknown")
        parts.append(f"[{i}] (source: {uri})\n{text}")
        sources.append({"excerpt": i, "source": uri, "score": r.get("score")})
    return "\n\n".join(parts), sources


def ask_model(question, context):
    user_msg = f"Excerpts:\n{context}\n\nQuestion: {question}"
    resp = model_rt.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_msg}]}],
        inferenceConfig={"maxTokens": 800, "temperature": 0},
    )
    blocks = resp["output"]["message"]["content"]
    # Qwen3 may return a separate reasoning block; keep only the answer text.
    text = "".join(b["text"] for b in blocks if "text" in b)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    return text


def lambda_handler(event, context):
    try:
        body = _parse_event(event)
        question = (body.get("question") or "").strip()
        contract = (body.get("contract") or "").strip()
        #print (f"question:\n{question}\n\n contract:\n{contract}")

        if not question:
            return _response(400, {"error": "Missing 'question'."})
        if len(question) > 1000:
            return _response(400, {"error": "Question too long (max 1000 characters)."})

        results = retrieve(question, contract)
        logger.info("retrieved %d chunks (contract filter: %s)", len(results), contract or "none")

        if not results:
            return _response(200, {
                "answer": "Not found in the retrieved excerpts.",
                "sources": [],
                "disclaimer": DISCLAIMER,
            })

        ctx, sources = build_context(results)
        answer = ask_model(question, ctx)

        return _response(200, {
            "answer": answer,
            "sources": sources,
            "contract_filter": contract or None,
            "disclaimer": DISCLAIMER,
        })

    except ClientError as e:
        logger.exception("AWS error")
        code = e.response.get("Error", {}).get("Code", "Unknown")
        return _response(500, {"error": f"AWS service error: {code}"})
    except Exception:
        logger.exception("Unexpected error")
        return _response(500, {"error": "Internal error."})
